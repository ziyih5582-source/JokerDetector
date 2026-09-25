#!/usr/bin/env bash
# 从项目根目录启动后端（前端页面由后端一并挂载）。
set -euo pipefail

cd "$(dirname "$0")/.."

python_bin=".venv/bin/python"
if [ ! -x "$python_bin" ]; then
  python_bin="python3"
  echo "未找到 .venv，改用系统 python3（依赖需自行安装，见 README.md）" >&2
fi

echo "浏览器打开 http://127.0.0.1:8000/"
exec "$python_bin" -m uvicorn app.main:app --app-dir backend --host 127.0.0.1 --port 8000
