# Install a per-user Windows Scheduled Task that starts ForeverTrader at Windows logon.
# The desktop market API can be polled while WoW is closed, but Windows must be running.
$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $MyInvocation.MyCommand.Path
$taskName = 'ForeverTrader-Offline'
$worker = Join-Path $root 'OFFLINE-MONITOR.ps1'
if (-not (Test-Path -LiteralPath $worker)) { throw 'OFFLINE-MONITOR.ps1 ontbreekt.' }
if (-not (Test-Path -LiteralPath (Join-Path $root 'trader.py'))) { throw 'trader.py ontbreekt.' }
$user = [Security.Principal.WindowsIdentity]::GetCurrent().Name
$exe = Join-Path $PSHOME 'powershell.exe'
$action = New-ScheduledTaskAction -Execute $exe -Argument ('-NoProfile -NonInteractive -ExecutionPolicy Bypass -WindowStyle Hidden -File "' + $worker + '"') -WorkingDirectory $root
$trigger = New-ScheduledTaskTrigger -AtLogOn -User $user
$principal = New-ScheduledTaskPrincipal -UserId $user -LogonType Interactive -RunLevel Limited
$settings = New-ScheduledTaskSettingsSet -MultipleInstances IgnoreNew -ExecutionTimeLimit ([TimeSpan]::Zero) -StartWhenAvailable -RestartCount 3 -RestartInterval (New-TimeSpan -Minutes 2) -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries
Register-ScheduledTask -TaskName $taskName -Action $action -Trigger $trigger -Principal $principal -Settings $settings -Force | Out-Null
Write-Host 'ForeverTrader: offline monitor geactiveerd bij elke Windows-aanmelding.' -ForegroundColor Green
Write-Host 'Deze taak haalt zelfstandig de openbare AH-data op, ook zonder WoW.' -ForegroundColor Cyan
Write-Host 'Zorg dat START.bat NIET al draait voordat je de taak start.' -ForegroundColor Yellow
Write-Host 'Start nu meteen met: Start-ScheduledTask -TaskName ForeverTrader-Offline'
Write-Host 'Logbestand: data\logs\offline-monitor.log'
