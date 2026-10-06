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
    if [ -f "$STAMP" ]; then
      find docs -type f -newer "$STAMP" -print0 | tar czf - --null -T - \
        | ssh -o BatchMode=yes -o ConnectTimeout=20 x99 'tar xzf - -C /srv/zlblog/blog' \
        && echo "X99 镜像增量更新完成" || echo "!! X99 增量部署失败"
    else
      tar czf - -C docs . | ssh -o BatchMode=yes -o ConnectTimeout=20 x99 'tar xzf - -C /srv/zlblog/blog' \
        && echo "X99 镜像全量更新完成" || echo "!! X99 全量部署失败"
    fi
    touch "$STAMP"
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
