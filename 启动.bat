@echo off
chcp 65001 >nul
title Iris
cd /d "%~dp0"

where python >nul 2>nul
if errorlevel 1 (
    echo 没有找到 python，请先安�?Python 3.10+ 并勾�?"Add to PATH"
    pause
    exit /b 1
)

echo 正在启动 Iris 界面...
echo.
python -m iris gui

echo.
echo 界面已退出�?pause
