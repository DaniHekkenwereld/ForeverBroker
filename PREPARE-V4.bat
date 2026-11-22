@echo off
cd /d "%~dp0"
echo V4: laatste sessies uploaden en plannen ophalen voor de volgende WoW-start.
where py >nul 2>nul
if %errorlevel%==0 (py -3 -u v4_bridge.py --once) else (python -u v4_bridge.py --once)
pause
