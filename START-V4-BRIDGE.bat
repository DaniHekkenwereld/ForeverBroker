@echo off
cd /d "%~dp0"
echo ForeverTrader v4 - sessies synchroniseren en serverstrategie klaarzetten.
echo Alleen SavedVariables lezen bij WoW aan; schrijven alleen als WoW volledig is afgesloten.
where py >nul 2>nul
if %errorlevel%==0 (py -3 -u v4_bridge.py) else (python -u v4_bridge.py)
pause
