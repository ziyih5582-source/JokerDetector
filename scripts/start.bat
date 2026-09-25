@echo off
rem 从项目根目录启动后端（前端页面由后端一并挂载）。
cd /d "%~dp0.."
if not exist ".venv\Scripts\python.exe" (
  echo 请先按 README.md 的步骤创建 .venv 并安装依赖。
  pause
  exit /b 1
)
echo 浏览器打开 http://127.0.0.1:8000/
".venv\Scripts\python.exe" -m uvicorn app.main:app --app-dir backend --host 127.0.0.1 --port 8000
pause
