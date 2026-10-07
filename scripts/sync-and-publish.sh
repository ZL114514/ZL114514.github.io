#!/usr/bin/env bash
# Telegram -> 博客 全链路：拉后台状态 -> 抓取/重排 -> 生成时间线 -> 构建 -> 部署 X99 镜像 -> 推 GitHub
#
#   scripts/sync-and-publish.sh            全量：抓 TG（6 小时一次的计划任务）
#   scripts/sync-and-publish.sh --light    轻量：不抓 TG，用缓存按后台状态重排（10 分钟一次）
#
# 幂等，可反复跑（tg_sync.py 只处理新增/变更/改过状态的帖子；sitegen.py 产物全是派生的）。
set -uo pipefail
cd "$(dirname "$0")/.." || exit 1
PY="./.venv/Scripts/python"
LOG="scripts/.sync.log"
STAMP="scripts/.last_deploy"
LIGHT=0
[ "${1:-}" = "--light" ] && LIGHT=1
MODE=$([ "$LIGHT" = 1 ] && echo 轻量 || echo 全量)

# 两个计划任务（6 小时 / 10 分钟）可能撞车：目录锁串行化，陈旧锁自动接管
LOCK="scripts/.sync.lock"
if ! mkdir "$LOCK" 2>/dev/null; then
  if [ -n "$(find "$LOCK" -maxdepth 0 -mmin +30 2>/dev/null)" ]; then
    rm -rf "$LOCK"; mkdir "$LOCK" 2>/dev/null || exit 0
  else
    echo "=== $(date '+%F %T') 已有同步在跑，跳过 ===" >>"$LOG"; exit 0
  fi
fi
trap 'rmdir "$LOCK" 2>/dev/null || true' EXIT

{
  echo "=== $(date '+%F %T') 同步开始（$MODE）==="

  # 后台（X99 /admin）里的状态：碎碎念 / 博文 / 音游成绩 / 隐藏，外加识别出的成绩与曲绘
  "$PY" scripts/sitegen.py --pull || echo "!! 后台状态没拉回来，沿用本地那份"

  if [ "$LIGHT" = 1 ] && [ -f scripts/tg_posts.json ]; then
    # 轻量：不碰网络，按状态把页面重排一遍（后台改完 10 分钟内落地）
    "$PY" scripts/tg_sync.py --from-cache || { echo "!! 重排失败，中止"; exit 1; }
  else
    # 全量扫描：16 页 ~15 秒，媒体已存在不会重下；增量模式只能看到最近一页，
    # 老帖被编辑/新补媒体就永远发现不了
    "$PY" scripts/tg_sync.py --full || { echo "!! 抓取失败，中止"; exit 1; }
    "$PY" scripts/tg_seed_reactions.py
  fi

  "$PY" scripts/sitegen.py || { echo "!! 生成失败，中止"; exit 1; }

  # 轻量同步遇上"啥也没改"是常态（10 分钟一次）：src/ 没动过就不重建、不重传，
  # 否则 mkdocs --clean 每次都会刷新所有产物的 mtime，增量部署退化成整站上传
  if [ "$LIGHT" = 1 ] && [ -f "$STAMP" ] && [ -f docs/index.html ] \
     && [ -z "$(find src -type f -newer "$STAMP" -print -quit)" ]; then
    echo "源码无变化：跳过构建与部署"
  else
    "$PY" -m mkdocs build --clean || { echo "!! 构建失败，中止"; exit 1; }
    touch docs/.nojekyll
  fi

  # 只传改动过的文件（首次或没有基准时全量），避免每次重传整个媒体目录
  if [ -f "$STAMP" ] && [ -f docs/index.html ]; then
    N=$(find docs -type f -newer "$STAMP" -print | grep -c . || true)
  else
    N="全部"
  fi
  echo "待部署文件：$N"
  if [ "$N" != "0" ]; then
    ok=0
    STAMPABS="$(pwd)/$STAMP"
    for attempt in 1 2 3; do
      if [ -f "$STAMP" ]; then
        # 必须在 docs/ 里做 tar，否则归档里带 docs/ 前缀，会落到镜像的 <根>/docs/ 下
        (cd docs && find . -type f -newer "$STAMPABS" -print0 | tar czf - --null -T -) \
          | ssh -o BatchMode=yes -o ConnectTimeout=20 x99 'tar xzf - -C /srv/zlblog/blog'
      else
        tar czf - -C docs . | ssh -o BatchMode=yes -o ConnectTimeout=20 x99 'tar xzf - -C /srv/zlblog/blog'
      fi
      if [ $? -eq 0 ]; then ok=1; break; fi
      echo "  部署第 $attempt 次失败（SSH 断连？），3 秒后重试"
      sleep 3
    done
    if [ "$ok" = "1" ]; then
      echo "X99 镜像更新完成（$N 个文件）"
      touch "$STAMP"          # 只有成功才推进基准，否则下次会漏掉这批文件
    else
      echo "!! X99 增量部署失败（已重试 3 次；基准未推进，下次会重来）"
    fi
  fi

  if [ -n "$(git status --porcelain)" ]; then
    git add -A
    git commit -q -m "sync($MODE): telegram $(date '+%F %H:%M')" || true
    for attempt in 1 2 3 4 5; do          # GitHub SSH 时不时被掐断，重试到远端确认一致
      git push -q 2>/dev/null || true
      if [ "$(git ls-remote origin -h refs/heads/main | cut -c1-40)" = "$(git rev-parse HEAD)" ]; then
        echo "已推送到 GitHub"
        break
      fi
      echo "  push 第 $attempt 次失败，6 秒后重试"
      sleep 6
    done
  else
    echo "内容无变化，跳过提交"
  fi
  echo "=== $(date '+%F %T') 完成 ==="
} >>"$LOG" 2>&1
