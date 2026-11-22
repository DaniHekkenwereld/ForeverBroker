@echo off
cd /d "%~dp0"
set /p "CSV=Plak het volledige pad naar je population CSV: "
where py >nul 2>nul
if %errorlevel%==0 (py -3 trader.py --population "%CSV%") else (python trader.py --population "%CSV%")
pause
