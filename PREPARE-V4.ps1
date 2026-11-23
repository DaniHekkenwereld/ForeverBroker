# ForeverTrader v4: run one sync with credentials persisted by KOPPEL-V4.ps1.
$ErrorActionPreference = 'Stop'
Set-Location -LiteralPath $PSScriptRoot
$storedUrl = [Environment]::GetEnvironmentVariable('FT_V4_URL', 'User')
$storedToken = [Environment]::GetEnvironmentVariable('FT_SYNC_TOKEN', 'User')
if ([string]::IsNullOrWhiteSpace($storedUrl) -or [string]::IsNullOrWhiteSpace($storedToken)) {
    throw 'V4-serververbinding ontbreekt. Voer eerst KOPPEL-V4.bat uit.'
}
$env:FT_V4_URL = $storedUrl
$env:FT_SYNC_TOKEN = $storedToken

if (Get-Command py -ErrorAction SilentlyContinue) {
    & py -3 -u (Join-Path $PSScriptRoot 'v4_bridge.py') --once
} elseif (Get-Command python -ErrorAction SilentlyContinue) {
    & python -u (Join-Path $PSScriptRoot 'v4_bridge.py') --once
} else {
    throw 'Python 3 ontbreekt op Windows'
}
if ($LASTEXITCODE -ne 0) { throw 'V4-synchronisatie mislukt. Bekijk de foutmelding hierboven.' }
