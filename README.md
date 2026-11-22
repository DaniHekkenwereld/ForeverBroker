# ForeverBroker

ForeverTrader v3.1 — tradingcoach en paper-tradingengine voor WoW Forever EU PvP Alliance.

## Bijwerken (Windows)

Voor een bestaande ZIP-installatie zonder Git voer je **eenmalig** in de hoofdmap uit:

```powershell
Invoke-WebRequest https://raw.githubusercontent.com/DaniHekkenwereld/ForeverBroker/main/update.ps1 -OutFile .\update.ps1
powershell -NoProfile -ExecutionPolicy Bypass -File .\update.ps1
```

Daarna gebruik je bij iedere nieuwe versie alleen:

```powershell
.\UPDATE.bat
```

Sluit eerst WoW en `START.bat`. De updater bewaart `config.json` en `data/` en vernieuwt, wanneer `wow_folder` is ingesteld, ook de WoW-addon. In een Git-clone gebruikt de updater `git pull --ff-only` (lokale wijzigingen kunnen dat blokkeren).

## Getting started

1. Lees [LEES-MIJ-EERST.md](LEES-MIJ-EERST.md).
2. Voer `SETUP.bat` uit, daarna `DEMO.bat`.
3. Installeer de addon volgens [de installatiehandleiding](docs/ADDON-INSTALLATIE.md).
4. Start de marktengine met `START.bat`.

Echte transacties bevestig je zelf. De live WoW-clientintegratie moet nog worden gevalideerd.

Documentatie: [Techniek](docs/TECHNIEK.md) · [Gericht zoeken (v3.1)](docs/V31-GERICHT-ZOEKEN.md).

Lokale databases, SavedVariables en diagnostiek horen niet in deze publieke repository.
