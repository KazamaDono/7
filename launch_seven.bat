@echo off
title Seven AI Assistant - WSL Mode
echo ========================================
echo Launching Seven AI Assistant
echo ========================================
echo.

REM Get current directory
set SCRIPT_DIR=%~dp0
set WSL_PATH=%SCRIPT_DIR:\=/%

REM Launch WSL with venv
echo Starting WSL environment...
wsl bash -c "cd '%WSL_PATH%' && source voice_env/bin/activate && python main.py"

pause