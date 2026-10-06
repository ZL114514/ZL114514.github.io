#!/usr/bin/env bash
# 构建站点并推送到 main，GitHub Pages 从 docs/ 发布
set -euo pipefail
cd "$(dirname "$0")"

PY=".venv/Scripts/python"
[ -x "$PY" ] || PY=".venv/bin/python"

"$PY" -m mkdocs build --clean
touch docs/.nojekyll

git add -A
git commit -m "publish: $(date '+%Y-%m-%d %H:%M')" || echo "nothing to commit"
git push
echo "已推送，稍等 1 分钟左右生效。"
