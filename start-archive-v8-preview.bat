@echo off
setlocal
chcp 65001 >nul
set "PYTHONUTF8=1"
cd /d "%~dp0"
set "PYEXE=%~dp0.venv\Scripts\python.exe"
if not exist "%PYEXE%" (
  echo [ERROR] 请先按 README 配置项目虚拟环境。
  pause
  exit /b 1
)
set "JOKER_PROFILE_DIR=%~dp0data\archive-v8-preview"
echo 档案 v8 预览：http://127.0.0.1:8020/profiles
echo 使用独立预览资料目录；不覆盖 data/private。Ctrl+C 停止。
"%PYEXE%" -m uvicorn app.main:app --app-dir "%~dp0backend" --host 127.0.0.1 --port 8020
pause
