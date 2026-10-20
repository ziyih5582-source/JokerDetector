@echo off
setlocal
chcp 65001 >nul
set "PYTHONUTF8=1"
cd /d "%~dp0"
set "PYEXE=%~dp0.venv\Scripts\python.exe"
if not exist "%PYEXE%" (
  echo [ERROR] 请先使用项目已有虚拟环境安装 backend\requirements.txt。
  pause
  exit /b 1
)
set "JOKER_PROFILE_DIR=%~dp0data\archive-preview"
set "PYTHONPATH=%~dp0backend"
"%PYEXE%" "%~dp0scripts\seed_archive_v7_preview.py" --directory "%JOKER_PROFILE_DIR%"
if errorlevel 1 (
  pause
  exit /b 1
)
echo.
echo 档案预览：http://127.0.0.1:8018/profiles
echo 使用单独的虚构资料库，不修改原有联系人。Ctrl+C 停止。
echo 生成新档案仍需配置项目的 AI 服务；预置示例不代表 AI 识别结果。
"%PYEXE%" -m uvicorn app.main:app --app-dir "%~dp0backend" --host 127.0.0.1 --port 8018
pause
