@echo off
powershell.exe -NoProfile -Command "Stop-ScheduledTask -TaskName 'ForeverTrader-V4-Bridge' -ErrorAction SilentlyContinue; Unregister-ScheduledTask -TaskName 'ForeverTrader-V4-Bridge' -Confirm:$false -ErrorAction SilentlyContinue; Write-Host 'Automatische V4 bridge uitgeschakeld.'"
pause
