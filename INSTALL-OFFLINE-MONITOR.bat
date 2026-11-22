@echo off
cd /d "%~dp0"
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0INSTALL-OFFLINE-MONITOR.ps1"
if errorlevel 1 (
    echo.
    echo Installatie mislukt. Controleer de bovenstaande foutmelding.
)
pause
