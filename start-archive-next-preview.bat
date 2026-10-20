@echo off
setlocal
chcp 65001 >nul
set "PYTHONUTF8=1"
cd /d "%~dp0"
if not exist "%~dp0.venv\Scripts\python.exe" (
  echo [ERROR] 请先按 README 配置项目虚拟环境。
  pause
  exit /b 1
)
set "JOKER_PROFILE_DIR=%~dp0data\archive-next-preview"
echo 档案 v8.4 预览：http://127.0.0.1:8021/profiles
echo 独立预览资料保存在 data\archive-next-preview，请保管其中的档案库和密钥。
echo 这是本地开发预览，Ctrl+C 停止。
"%~dp0.venv\Scripts\python.exe" -m uvicorn app.main:app --app-dir "%~dp0backend" --host 127.0.0.1 --port 8021
pause
