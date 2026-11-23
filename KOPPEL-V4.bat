@echo off
cd /d "%~dp0"
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0KOPPEL-V4.ps1"
if errorlevel 1 echo Koppeling mislukt. Controleer de foutmelding hierboven.
pause
