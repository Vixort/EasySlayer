@echo off
title EasySlayer Auto Fishing Bot
echo ========================================================
echo         EasySlayer Auto Fishing Bot - Launcher
echo ========================================================
echo.
py main.py
if %ERRORLEVEL% NEQ 0 (
    python main.py
)
pause
