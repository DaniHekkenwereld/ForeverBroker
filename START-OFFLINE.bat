@echo off
cd /d "%~dp0"
echo ForeverTrader offline monitor - openbare AH-data, geen WoW nodig.
echo Dit venster open laten, of INSTALL-OFFLINE-MONITOR.bat gebruiken voor automatisch starten.
where py >nul 2>nul
if %errorlevel%==0 (py -3 trader.py --no-browser) else (python trader.py --no-browser)
pause
