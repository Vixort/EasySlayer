@echo off
title EasySlayer - Build Executable
echo ====================================================
echo  Building EasySlayer Standalone Executable (.exe)
echo ====================================================
echo.

py -m pip install pyinstaller
py -m PyInstaller --clean --noconsole --onefile --add-data "white_slider_template.png;." --hidden-import "pynput.keyboard._win32" --hidden-import "pynput.mouse._win32" --name "EasySlayer" main.py

if %ERRORLEVEL% EQU 0 (
    echo.
    echo ====================================================
    echo  Build Successful!
    echo  Output file: dist\EasySlayer.exe
    echo ====================================================
) else (
    echo.
    echo [ERROR] Build failed. Please check the logs above.
)
pause
