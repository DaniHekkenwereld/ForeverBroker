@echo off
setlocal
cd /d "%~dp0"
set "SCRIPT=%~dp0AHK\ForeverTrader-Voice.ahk"
set "AHK64=%ProgramFiles%\AutoHotkey\v2\AutoHotkey64.exe"
set "AHK32=%ProgramFiles(x86)%\AutoHotkey\v2\AutoHotkey32.exe"
if exist "%AHK64%" (
  start "ForeverTrader Audio" "%AHK64%" "%SCRIPT%"
  exit /b 0
)
if exist "%AHK32%" (
  start "ForeverTrader Audio" "%AHK32%" "%SCRIPT%"
  exit /b 0
)
where AutoHotkey64.exe >nul 2>nul
if not errorlevel 1 (
  start "ForeverTrader Audio" AutoHotkey64.exe "%SCRIPT%"
  exit /b 0
)
echo AutoHotkey v2 is nog niet gevonden.
echo Installeer v2 via https://www.autohotkey.com/ en voer START-AUDIO.bat opnieuw uit.
pause
exit /b 1
