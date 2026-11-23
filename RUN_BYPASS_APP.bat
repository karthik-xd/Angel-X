@echo off
title Campus Shield GUI
cd /d "%~dp0"

:: Check for administrative rights and elevate if not
net session >nul 2>&1
if %errorLevel% neq 0 (
    powershell -Command "Start-Process py -ArgumentList '\"%~dp0gui_app.py\"' -Verb RunAs"
    exit /b
)

py gui_app.py
