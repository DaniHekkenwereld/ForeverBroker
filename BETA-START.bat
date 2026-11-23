@echo off
setlocal
cd /d "%~dp0"
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0BETA-START.ps1"
if errorlevel 1 (
 echo.
 echo INSTALLATIE OF DASHBOARD MISLUKT. Bekijk de melding hierboven.
 pause
 exit /b 1
)
