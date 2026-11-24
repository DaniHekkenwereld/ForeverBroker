# Update the existing V4 VPS over the already pinned SSH host.
$ErrorActionPreference='Stop'
Set-Location -LiteralPath $PSScriptRoot
$hostIp='136.144.216.107'
$knownHosts=Join-Path $env:LOCALAPPDATA 'ForeverTrader\known_hosts'
if (-not (Test-Path -LiteralPath $knownHosts)) {
    throw 'De VPS SSH-sleutel ontbreekt. Voer KOPPEL-V4.bat eerst uit.'
}
if (-not (Get-Command ssh.exe -ErrorAction SilentlyContinue)) {
    throw 'Windows OpenSSH ontbreekt.'
}
Write-Host 'ForeverTrader V4 VPS bijwerken. SSH kan om het VPS- en sudo-wachtwoord vragen.' -ForegroundColor Cyan
$remoteCommand='set -e; cd ~/ForeverBroker; git pull --ff-only; python3 -m compileall -q v4_server.py v4_investing.py v4_investing_ui.py v4_research.py v4_dashboard.py v4_engine.py v4_dashboard_live.py v4_portfolio.py v4_portfolio_ui.py v4_trades.py v4_daily_radar.py v4_daily_ui.py characters.py v4_bridge.py; python3 -m unittest discover -s tests -q; sudo systemctl restart forevertrader-v4; sudo systemctl is-active --quiet forevertrader-v4; echo FOREVERTRADER_V4_DEPLOY_OK'
& ssh.exe -tt -o 'PubkeyAuthentication=no' -o "UserKnownHostsFile=$knownHosts" "hekkenwereld@$hostIp" $remoteCommand
if ($LASTEXITCODE -ne 0) {
    throw 'VPS-update mislukt. Bij falende tests is de VPS-service NIET opnieuw gestart.'
}
$token=[Environment]::GetEnvironmentVariable('FT_SYNC_TOKEN','User')
if ([string]::IsNullOrWhiteSpace($token)) {
    throw 'VPS is bijgewerkt, maar de Windows-token ontbreekt. Gebruik KOPPEL-V4.bat.'
}
Write-Host 'Nieuwe investerings-API controleren via HTTPS...' -ForegroundColor Cyan
# systemctl "active" does not mean the Python socket and reverse proxy are
# ready after a restart. Retry only transient gateway/startup failures.
$research = $null
for ($attempt = 1; $attempt -le 5; $attempt++) {
    try {
        $research = Invoke-RestMethod -Uri "https://$hostIp/api/v4/research" -Headers @{Authorization="Bearer $token"} -TimeoutSec 20
        break
    } catch {
        $status = $null
        if ($_.Exception.Response) {
            $status = [int]$_.Exception.Response.StatusCode
        }
        if (($status -and $status -notin @(502, 503, 504)) -or $attempt -eq 5) {
            Write-Warning 'VPS herstart, maar HTTPS-API is niet gezond. Controleer VPS-service en logs; geen herinstallatie nodig.'
            throw
        }
        Write-Host "API nog niet klaar (HTTP $status); opnieuw controleren ($attempt/5)..." -ForegroundColor Yellow
        Start-Sleep -Seconds 4
    }
}
if ($research.version -ne '4.0.0' -or $research.market -ne 'eu-2-110') {
    throw 'De VPS gaf niet de verwachte marktanalyse.'
}
if ($null -eq $research.investments -or $null -eq $research.portfolio -or $null -eq $research.intraday) {
    throw 'VPS retourneert niet alle V1-beta modules (investeringen, portfolio, daghandel).'
}
Write-Host "VPS werkt. Items onderzocht: $($research.analyzed_count). Investeringssignalen: $($research.shortlist_count)." -ForegroundColor Green
if ($research.market_fresh -ne $true) {
    Write-Warning 'De huidige AH-marktsnapshot is verouderd. De radar toont geen actuele koopsignalen.'
}
Write-Host 'Start nu DASHBOARD-V4.bat.' -ForegroundColor Green
