# Foreground worker for Windows Task Scheduler. Runs while Windows session is active.
# WoW and its addon are NOT required; only the public market API is queried.
$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location -LiteralPath $root
$logs = Join-Path $root 'data\logs'
New-Item -Path $logs -ItemType Directory -Force | Out-Null
$log = Join-Path $logs 'offline-monitor.log'
function Log-Line($message) {
    "[$(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')] $message" | Out-File -FilePath $log -Encoding utf8 -Append
}
Log-Line 'Monitor gestart (geen WoW-client nodig).'
try {
    if (Get-Command py -ErrorAction SilentlyContinue) {
        # -u ensures monitor logs reach the file without buffering.
        & py -3 -u (Join-Path $root 'trader.py') --no-browser *>> $log
    } elseif (Get-Command python -ErrorAction SilentlyContinue) {
        & python -u (Join-Path $root 'trader.py') --no-browser *>> $log
    } else {
        throw 'Python 3 ontbreekt. Installeer Python en herstart de taak.'
    }
    $code = $LASTEXITCODE
    if ($code -ne 0) { throw "ForeverTrader gestopt met exitcode $code. Mogelijk al actief via START.bat." }
    Log-Line 'Monitor netjes afgesloten.'
} catch {
    Log-Line "FOUT: $($_.Exception.Message)"
    throw
}
