#!/usr/bin/env bash
# Telegram -> 博客 全链路：抓取 -> 构建 -> 部署 X99 镜像 -> 推 GitHub -> 播种 reaction
# 幂等，可反复跑（tg_sync.py 只处理新增/变更的帖子）。
set -uo pipefail
cd "$(dirname "$0")/.." || exit 1
PY="./.venv/Scripts/python"
LOG="scripts/.sync.log"
STAMP="scripts/.last_deploy"

{
  echo "=== $(date '+%F %T') 同步开始 ==="
  "$PY" scripts/tg_sync.py || { echo "!! 抓取失败，中止"; exit 1; }
  "$PY" scripts/tg_seed_reactions.py
  "$PY" -m mkdocs build --clean || { echo "!! 构建失败，中止"; exit 1; }

  # 只传改动过的文件（首次或没有基准时全量），避免每次重传整个媒体目录
  if [ -f "$STAMP" ]; then
    N=$(find docs -type f -newer "$STAMP" -print | grep -c . || true)
  else
    N="全部"
  fi
  echo "待部署文件：$N"
  if [ "$N" != "0" ]; then
    ok=0
    for attempt in 1 2 3; do
      if [ -f "$STAMP" ]; then
        find docs -type f -newer "$STAMP" -print0 | tar czf - --null -T - \
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
    git commit -q -m "sync: telegram $(date '+%F %H:%M')"
    git push -q && echo "已推送到 GitHub" || echo "!! git push 失败"
  else
    echo "内容无变化，跳过提交"
  fi
  echo "=== $(date '+%F %T') 完成 ==="
} >>"$LOG" 2>&1
