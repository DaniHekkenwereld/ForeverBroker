$ErrorActionPreference='Stop'
Set-Location $PSScriptRoot
# Task Scheduler may start with a stale process environment after initial pairing.
# Read the persisted per-user settings directly before launching Python.
$storedUrl = [Environment]::GetEnvironmentVariable('FT_V4_URL', 'User')
$storedToken = [Environment]::GetEnvironmentVariable('FT_SYNC_TOKEN', 'User')
if (-not [string]::IsNullOrWhiteSpace($storedUrl)) { $env:FT_V4_URL = $storedUrl }
if (-not [string]::IsNullOrWhiteSpace($storedToken)) { $env:FT_SYNC_TOKEN = $storedToken }
$logPath=Join-Path $PSScriptRoot 'data\logs'
New-Item -ItemType Directory -Force -Path $logPath | Out-Null
$log=Join-Path $logPath 'v4-bridge.log'
"[$(Get-Date -Format 's')] V4 bridge start" | Out-File $log -Append -Encoding utf8
try {
    if (Get-Command py -ErrorAction SilentlyContinue) {
        & py -3 -u (Join-Path $PSScriptRoot 'v4_bridge.py') *>> $log
    } elseif (Get-Command python -ErrorAction SilentlyContinue) {
        & python -u (Join-Path $PSScriptRoot 'v4_bridge.py') *>> $log
    } else {
        throw 'Python 3 ontbreekt'
    }
    if ($LASTEXITCODE -ne 0) { throw "V4 bridge afgebroken met code $LASTEXITCODE" }
} catch {
    "[$(Get-Date -Format 's')] ERROR: $($_.Exception.Message)" | Out-File $log -Append -Encoding utf8
    throw
}
