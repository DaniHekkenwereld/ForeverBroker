# One-shot first-run bootstrap for ForeverTrader 1.0 Beta on Windows.
# Requires existing KOPPEL-V4 and installed WoW addon path.
$ErrorActionPreference='Stop'
Set-Location -LiteralPath $PSScriptRoot
Write-Host '=== ForeverTrader 1.0 Beta: Portfolio & Trading Desk ===' -ForegroundColor Cyan
$processes=Get-Process -Name 'Wow','WowClassic','WowClassic_t','Wow-64','WowClassic64' -ErrorAction SilentlyContinue
if ($processes) {
    throw 'Sluit WoW volledig af voordat je de beta installeert; anders kunnen SavedVariables niet veilig worden bijgewerkt.'
}
$cfg=Get-Content (Join-Path $PSScriptRoot 'config.json') -Raw | ConvertFrom-Json
if ([string]::IsNullOrWhiteSpace([string]$cfg.wow_folder)) {
    throw 'WoW-map ontbreekt. Draai INSTALL-ADDON.bat eerst.'
}
foreach ($step in @(
    @{Name='1/4 Windows-addon en dashboard bijwerken';Script='update.ps1'},
    @{Name='2/4 VPS upgraden en servertests draaien';Script='DEPLOY-V4.ps1'},
    @{Name='3/4 Automatische Windows-bridge installeren/starten';Script='INSTALL-V4-BRIDGE.ps1'},
    @{Name='4/4 Portfolio en nieuwste advies synchroniseren';Script='PREPARE-V4.ps1'}
)) {
    Write-Host ''
    Write-Host $step.Name -ForegroundColor Cyan
    $path=Join-Path $PSScriptRoot $step.Script
    & powershell.exe -NoProfile -ExecutionPolicy Bypass -File $path
    if ($LASTEXITCODE -ne 0) {
        throw "Mislukt: $($step.Script). De volgende stap is niet uitgevoerd."
    }
}
Write-Host ''
Write-Host 'Code en VPS gesynchroniseerd. Dashboard wordt nu geopend.' -ForegroundColor Green
Write-Host 'WoW: alleen het Auction House openen; prijzen worden automatisch gecontroleerd.' -ForegroundColor Yellow
Write-Host 'Een bankscan is optioneel (alleen nodig als er bankvoorraad is).' -ForegroundColor Yellow
Write-Host 'Bij uitloggen of /reload schrijft WoW de data; de Windows-bridge verstuurt deze automatisch naar de VPS.' -ForegroundColor Yellow
& powershell.exe -NoProfile -ExecutionPolicy Bypass -File (Join-Path $PSScriptRoot 'DASHBOARD-V4.ps1')
if ($LASTEXITCODE -ne 0) { throw 'Het dashboard kon niet worden gestart.' }
