@echo off
rem ============================================================
rem  Joker Detector Pro - 局域网共享模式（手动触发）
rem  端口固定：8000；本机仍可用 http://127.0.0.1:8000/
rem ============================================================
setlocal
chcp 65001 >nul
set "PYTHONUTF8=1"

cd /d "%~dp0"

set "PYEXE="
if exist ".venv\Scripts\python.exe" set "PYEXE=.venv\Scripts\python.exe"
if not defined PYEXE (
  where python >nul 2>&1
  if %errorlevel%==0 set "PYEXE=python"
)

if not defined PYEXE (
  echo [ERROR] Python not found. Install Python 3.10+ and retry.
  pause
  exit /b 1
)

echo Using interpreter: %PYEXE%
echo.

"%PYEXE%" "%~dp0scripts\start_lan.py" %*

pause
