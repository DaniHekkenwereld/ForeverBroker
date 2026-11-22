@echo off
cd /d "%~dp0"
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0INSTALL-V4-BRIDGE.ps1"
if errorlevel 1 echo Installatie mislukt. Controleer de foutmelding.
pause
