# Update ForeverBroker from GitHub without touching user data.
# Run this when WoW and START.bat are closed.
$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location -LiteralPath $root

if (-not (Test-Path -LiteralPath (Join-Path $root 'trader.py'))) {
    throw 'Voer de updater uit vanuit de bestaande ForeverBroker/ForeverTrader hoofdmap.'
}
Write-Host 'ForeverBroker: laatste versie ophalen...' -ForegroundColor Cyan

if (Test-Path -LiteralPath (Join-Path $root '.git')) {
    if (-not (Get-Command git -ErrorAction SilentlyContinue)) {
        throw 'Git is niet beschikbaar. Installeer Git of gebruik de ZIP-versie.'
    }
    & git -C $root pull --ff-only origin main
    if ($LASTEXITCODE -ne 0) {
        throw 'Git pull mislukt. Controleer lokale wijzigingen (vooral config.json). Er is niets overschreven.'
    }
} else {
    $work = Join-Path ([IO.Path]::GetTempPath()) ('ForeverBroker-update-' + [guid]::NewGuid().ToString('N'))
    New-Item -ItemType Directory -Path $work -Force | Out-Null
    try {
        $archive = Join-Path $work 'main.zip'
        $unpacked = Join-Path $work 'unzipped'
        Invoke-WebRequest -Uri 'https://codeload.github.com/DaniHekkenwereld/ForeverBroker/zip/refs/heads/main' -OutFile $archive -UseBasicParsing
        Expand-Archive -LiteralPath $archive -DestinationPath $unpacked
        $source = Get-ChildItem -LiteralPath $unpacked -Directory | Select-Object -First 1
        if (-not $source -or -not (Test-Path -LiteralPath (Join-Path $source.FullName 'trader.py')) -or -not (Test-Path -LiteralPath (Join-Path $source.FullName 'addon\ForeverTrader\ForeverTrader.toc'))) {
            throw 'Gedownloade versie is niet compleet. Update afgebroken.'
        }
        $count = 0
        foreach ($file in Get-ChildItem -LiteralPath $source.FullName -File -Recurse) {
            $relative = $file.FullName.Substring($source.FullName.Length).TrimStart([char[]]@('\','/'))
            if ($relative -match '^(data|\.git)[\\/]') { continue }
            if ($relative -eq 'config.json' -and (Test-Path -LiteralPath (Join-Path $root 'config.json'))) { continue }
            $dest = Join-Path $root $relative
            New-Item -ItemType Directory -Path (Split-Path -Parent $dest) -Force | Out-Null
            Copy-Item -LiteralPath $file.FullName -Destination $dest -Force
            $count++
        }
        Write-Host "Broncode bijgewerkt: $count bestanden. config.json en data\ ongewijzigd." -ForegroundColor Green
    } finally {
        Remove-Item -LiteralPath $work -Force -Recurse -ErrorAction SilentlyContinue
    }
}

# Also refresh the installed WoW addon when the existing config knows the client directory.
$configFile = Join-Path $root 'config.json'
if (Test-Path -LiteralPath $configFile) {
    $config = Get-Content -LiteralPath $configFile -Raw | ConvertFrom-Json
    $wow = [string]$config.wow_folder
    if (-not [string]::IsNullOrWhiteSpace($wow)) {
        $wow = $wow.Trim().Trim('"')
        if (Test-Path -LiteralPath (Join-Path $wow '_forever_')) { $wow = Join-Path $wow '_forever_' }
        $addons = Join-Path $wow 'Interface\AddOns'
        $src = Join-Path $root 'addon\ForeverTrader'
        if ((Test-Path -LiteralPath $addons) -and (Test-Path -LiteralPath $src)) {
            $dest = Join-Path $addons 'ForeverTrader'
            New-Item -ItemType Directory -Path $dest -Force | Out-Null
            Copy-Item -Path (Join-Path $src '*') -Destination $dest -Recurse -Force
            Write-Host 'WoW-addon bijgewerkt. Herstart WoW om de wijzigingen te laden.' -ForegroundColor Green
        } else {
            Write-Warning 'WoW-addon niet gevonden: voer INSTALL-ADDON.bat nog een keer uit.'
        }
    } else {
        Write-Warning 'Geen wow_folder ingesteld: voer INSTALL-ADDON.bat eenmalig uit.'
    }
}
Write-Host 'ForeverBroker update gereed.' -ForegroundColor Green
