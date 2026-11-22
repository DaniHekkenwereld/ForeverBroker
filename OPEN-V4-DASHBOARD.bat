@echo off
cd /d "%~dp0"
if exist "data\v4\dashboard.html" (
  start "" "data\v4\dashboard.html"
) else (
  echo Er is nog geen V4 dashboard. Configureer eerst de VPS en voer PREPARE-V4.bat uit.
  pause
)
