$ErrorActionPreference = 'Stop'
Set-Location $PSScriptRoot
$inputPath = (Read-Host 'Plak je World of Warcraft-map (of _forever_-map)').Trim().Trim('"')
$folder = Get-Item -LiteralPath $inputPath
if (Test-Path -LiteralPath (Join-Path $folder.FullName '_forever_')) { $folder = Get-Item -LiteralPath (Join-Path $folder.FullName '_forever_') }
if ($folder.Name -ne '_forever_' -or -not (Test-Path -LiteralPath (Join-Path $folder.FullName 'Interface'))) { throw 'Selecteer de bestaande _forever_-map van WoW.' }
$addons = Join-Path $folder.FullName 'Interface\AddOns'
New-Item -ItemType Directory -Path $addons -Force | Out-Null
Copy-Item -LiteralPath (Join-Path $PSScriptRoot 'addon\ForeverTrader') -Destination $addons -Recurse -Force
$config = Get-Content -LiteralPath (Join-Path $PSScriptRoot 'config.json') -Raw | ConvertFrom-Json
$config.wow_folder = $folder.FullName
$json = $config | ConvertTo-Json -Depth 8
[IO.File]::WriteAllText((Join-Path $PSScriptRoot 'config.json'), $json, [Text.UTF8Encoding]::new($false))
Write-Host 'Addon geplaatst en config ingesteld. Herstart WoW, controleer de add-onlijst en gebruik /ft status.'
