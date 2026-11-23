@echo off
cd /d "%~dp0"
echo V4: laatste sessies uploaden en plannen ophalen voor de volgende WoW-start.
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0PREPARE-V4.ps1"
if errorlevel 1 echo V4-synchronisatie mislukt. Controleer de foutmelding.
pause
