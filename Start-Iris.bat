@echo off
chcp 65001 >nul
title Iris
cd /d "%~dp0"

set "PY=python"
where python >nul 2>nul || set "PY=py"

echo ============================================================
echo   Iris starting... browser will open automatically
echo   if not, open manually:  http://127.0.0.1:8765/
echo   close this window to quit
echo ============================================================
echo.

if not exist "%~dp0iris" (
    echo [ERROR] iris folder not found next to this bat
    pause
    exit /b 1
)

"%PY%" -m iris gui --port 8765

echo.
echo exited with code %errorlevel%
pause
