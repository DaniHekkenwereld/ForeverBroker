@echo off
setlocal
cd /d "%~dp0"
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0DEPLOY-V4.ps1"
if errorlevel 1 (
  echo.
  echo VPS-update mislukt. Bekijk de foutmelding hierboven.
  pause
  exit /b 1
)
echo.
echo VPS bijgewerkt. Start DASHBOARD-V4.bat.
pause
