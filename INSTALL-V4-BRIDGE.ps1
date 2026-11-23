# Automatically run bridge on Windows login. Does not start WoW.
$ErrorActionPreference='Stop'
$root=Split-Path -Parent $MyInvocation.MyCommand.Path
$script=Join-Path $root 'RUN-V4-BRIDGE.ps1'
if (-not (Test-Path $script)) {throw 'RUN-V4-BRIDGE.ps1 ontbreekt'}
$user=[Security.Principal.WindowsIdentity]::GetCurrent().Name
$exe=Join-Path $PSHOME 'powershell.exe'
$action=New-ScheduledTaskAction -Execute $exe -Argument ('-NoProfile -NonInteractive -ExecutionPolicy Bypass -WindowStyle Hidden -File "'+$script+'"') -WorkingDirectory $root
$trigger=New-ScheduledTaskTrigger -AtLogOn -User $user
$principal=New-ScheduledTaskPrincipal -UserId $user -LogonType Interactive -RunLevel Limited
$settings=New-ScheduledTaskSettingsSet -MultipleInstances IgnoreNew -ExecutionTimeLimit ([TimeSpan]::Zero) -StartWhenAvailable -RestartCount 3 -RestartInterval (New-TimeSpan -Minutes 2) -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries
Register-ScheduledTask -TaskName 'ForeverTrader-V4-Bridge' -Action $action -Trigger $trigger -Principal $principal -Settings $settings -Force | Out-Null
# Start immediately as well: a scheduled logon trigger does not fire retroactively.
Start-ScheduledTask -TaskName 'ForeverTrader-V4-Bridge'
Write-Host 'V4 bridge gestart en ingesteld voor automatisch starten bij Windows-aanmelding.' -ForegroundColor Green
Write-Host 'Als FT_V4_URL en FT_SYNC_TOKEN nog niet zijn ingesteld kan de bridge niet syncen.' -ForegroundColor Yellow
Write-Host 'Handmatig starten: Start-ScheduledTask -TaskName ForeverTrader-V4-Bridge'
Write-Host 'Log: data\logs\v4-bridge.log'
