@echo off
cd /d "%~dp0"
where py >nul 2>nul
if %errorlevel%==0 (py -3 trader.py --history-only) else (python trader.py --history-only)
pause
