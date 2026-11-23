# ForeverTrader v4: eenmalig de Windows-bridge aan een nieuwe Ubuntu VPS koppelen.
# De sleutel wordt via SSH gelezen, niet in de terminal of in deze repository getoond.
$ErrorActionPreference = 'Stop'
Set-Location -LiteralPath $PSScriptRoot

$hostIp = '136.144.216.107'
$expectedFingerprint = 'SHA256:HNubz3zfdyrAHrbNx6/q/4QFHdlYTmALCifZxPW/Gdg.'
$api = 'https://' + $hostIp
$cfgPath = Join-Path $PSScriptRoot 'config.json'
if (-not (Test-Path -LiteralPath $cfgPath)) { throw 'config.json ontbreekt. Voer dit vanuit je bestaande ForeverTrader-map uit.' }
$cfg = Get-Content -LiteralPath $cfgPath -Raw | ConvertFrom-Json
if ([string]::IsNullOrWhiteSpace([string]$cfg.wow_folder)) {
    throw 'WoW-pad ontbreekt in config.json. Voer eerst INSTALL-ADDON.bat uit in DEZE map.'
}

Write-Host '=== ForeverTrader v4 koppelen ===' -ForegroundColor Cyan
Write-Host 'Controleer HTTPS-certificaat en lokale API...'
$health = Invoke-RestMethod -Uri ($api + '/health') -TimeoutSec 15
if ($health.ok -ne $true -or $health.version -ne '4.0.0') {
    throw 'Server-API gaf geen geldige ForeverTrader v4 gezondheidsreactie.'
}
Write-Host 'HTTPS werkt met gevalideerd TLS-certificaat.' -ForegroundColor Green

# C:\Users\...\.ssh\known_hosts heeft op deze pc rechtenproblemen.
# Bewaar de vertrouwenssleutel daarom apart in het gebruikersprofiel.
$sshDir = Join-Path $env:LOCALAPPDATA 'ForeverTrader'
New-Item -ItemType Directory -Path $sshDir -Force | Out-Null
$knownHosts = Join-Path $sshDir 'known_hosts'
Write-Host ''
Write-Host 'Er volgt een SSH-verbinding. Controleer bij de eerste bevestiging de servervingerafdruk:' -ForegroundColor Yellow
Write-Host $expectedFingerprint -ForegroundColor Yellow
Write-Host 'Antwoord alleen yes als de getoonde vingerafdruk exact overeenkomt.'
Write-Host 'Vul daarna het NIEUWE VPS-wachtwoord in (invoer wordt niet getoond).'
# -- is not supported by every Windows ssh build. Use exactly one SSH command.
$remoteCommand = 'sed -n "s/^FT_SYNC_TOKEN=//p" /etc/forevertrader/v4.env'
$sshOutput = & ssh.exe -o 'PubkeyAuthentication=no' -o "UserKnownHostsFile=$knownHosts" "hekkenwereld@$hostIp" $remoteCommand
if ($LASTEXITCODE -ne 0) { throw 'Kon token niet veilig via SSH ophalen. Controleer je wachtwoord of SSH-verbinding.' }
$token = (($sshOutput | Out-String).Trim())
if ($token -notmatch '^[A-Za-z0-9_-]{40,}$') {
    throw 'De opgehaalde server-token ontbreekt of heeft een onverwacht formaat.'
}

# Voor dit venster direct actief; voor de geplande taak ook bij volgende Windows-login.
$env:FT_V4_URL = $api
$env:FT_SYNC_TOKEN = $token
[Environment]::SetEnvironmentVariable('FT_V4_URL', $api, 'User')
[Environment]::SetEnvironmentVariable('FT_SYNC_TOKEN', $token, 'User')
Write-Host 'Serveradres en toegangssleutel voor jouw Windows-gebruiker ingesteld.' -ForegroundColor Green
Remove-Variable token,sshOutput -ErrorAction SilentlyContinue

Write-Host ''
Write-Host 'Eenmalige v4-synchronisatie uitvoeren...'
if (Get-Command py -ErrorAction SilentlyContinue) {
    & py -3 -u (Join-Path $PSScriptRoot 'v4_bridge.py') --once
} elseif (Get-Command python -ErrorAction SilentlyContinue) {
    & python -u (Join-Path $PSScriptRoot 'v4_bridge.py') --once
} else {
    throw 'Python 3 ontbreekt op Windows. Installeer Python 3 en voer KOPPEL-V4.bat opnieuw uit.'
}
if ($LASTEXITCODE -ne 0) { throw 'V4-synchronisatie mislukt. Controleer de foutmelding hierboven.' }
Write-Host ''
Write-Host 'Koppeling ingesteld. Automatisch laten draaien: INSTALL-V4-BRIDGE.bat' -ForegroundColor Green
Write-Host 'Belangrijk: WoW volledig sluiten voordat serverplannen naar SavedVariables worden geschreven.'
