@echo off
cd /d "%~dp0"
if exist "data\paper\dashboard.html" (
    start "" "data\paper\dashboard.html"
) else (
    echo Nog geen dashboard. Start eerst START.bat of de offline monitor.
    pause
)
