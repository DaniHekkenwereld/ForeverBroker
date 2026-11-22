@echo off
cd /d "%~dp0"
powershell.exe -NoProfile -Command "Stop-ScheduledTask -TaskName 'ForeverTrader-Offline' -ErrorAction SilentlyContinue; Unregister-ScheduledTask -TaskName 'ForeverTrader-Offline' -Confirm:$false -ErrorAction SilentlyContinue; Write-Host 'Automatisch starten uitgezet. Eventuele bestaande START.bat handmatig sluiten.'"
pause
