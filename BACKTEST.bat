@echo off
cd /d "%~dp0"
where py >nul 2>nul
if %errorlevel%==0 (py -3 trader.py --backtest) else (python trader.py --backtest)
pause
