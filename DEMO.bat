@echo off
cd /d "%~dp0"
where py >nul 2>nul
if %errorlevel%==0 (py -3 trader.py --demo) else (python trader.py --demo)
pause
