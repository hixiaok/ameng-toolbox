@echo off
chcp 65001 >nul
title Iris
cd /d "%~dp0"

where python >nul 2>nul
if errorlevel 1 (
    echo 没有找到 python，请先安装 Python 3.10+ 并勾选 "Add to PATH"
    pause
    exit /b 1
)

set PORT=8765
echo 正在启动 Iris ...
start "Iris service" /min cmd /c "python -m iris gui --port %PORT% --no-browser"

for /l %%i in (1,1,20) do (
    timeout /t 1 >nul
    powershell -NoProfile -Command "try{ $c=New-Object Net.Sockets.TcpClient; $c.Connect('127.0.0.1',%PORT%); $c.Close(); exit 0 }catch{ exit 1 }" >nul 2>nul && goto ready
)
echo 服务没有起来，请把「Iris service」窗口里的报错发给我。
pause
exit /b 1

:ready
set EDGE1=%ProgramFiles(x86)%\Microsoft\Edge\Application\msedge.exe
set EDGE2=%ProgramFiles%\Microsoft\Edge\Application\msedge.exe
if exist "%EDGE1%" (
    start "" "%EDGE1%" --app=http://127.0.0.1:%PORT%/ --window-size=1200,840
    exit /b 0
)
if exist "%EDGE2%" (
    start "" "%EDGE2%" --app=http://127.0.0.1:%PORT%/ --window-size=1200,840
    exit /b 0
)
start "" http://127.0.0.1:%PORT%/
exit /b 0
