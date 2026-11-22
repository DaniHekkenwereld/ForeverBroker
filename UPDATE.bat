@echo off
cd /d "%~dp0"
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0update.ps1"
if errorlevel 1 (
    echo.
    echo Update mislukt. Lees de foutmelding hierboven.
    pause
    exit /b 1
)
