@echo off
cd /d "%~dp0"
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0DASHBOARD-V4.ps1"
if errorlevel 1 echo Dashboard starten mislukt. Controleer de foutmelding.
pause
