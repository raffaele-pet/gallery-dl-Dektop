@echo off
setlocal
chcp 65001 >nul
title gallery-dl Desktop - Debug
set "PROJECT_DIR=%~dp0"
if not exist "%PROJECT_DIR%.venv\Scripts\python.exe" (
    echo gallery-dl Desktop is not installed. Run INSTALL.bat first.
    pause
    exit /b 1
)
cd /d "%PROJECT_DIR%"
"%PROJECT_DIR%.venv\Scripts\python.exe" "%PROJECT_DIR%app.py"
if errorlevel 1 pause
