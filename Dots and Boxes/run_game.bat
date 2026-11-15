@echo off
title Dots and Boxes - Human vs AI
echo Starting Dots and Boxes...
cd /d "%~dp0Dots and Boxes"
if exist ".venv\Scripts\python.exe" (
    ".venv\Scripts\python.exe" main.py
) else (
    python main.py
)
if %ERRORLEVEL% NEQ 0 (
    echo.
    echo Game ended or encountered an issue.
    pause
)
