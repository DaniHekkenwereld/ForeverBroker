# ForeverBroker

ForeverTrader **v3.3.0** — tradingcoach, conservatievere paper-tradingengine en optionele live-goldtest met handmatige transacties voor WoW Forever EU PvP Alliance.

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

## Nieuw in 3.3: dagelijkse inkoop/verkoop planning

- Een nieuwe **Dagplanning**-tabel onderzoekt eerdere uren per item voor een goedkoop inkoopvenster en later verkoopvenster. Uren zijn lokaal (Europe/Amsterdam).
- Minimaal **5 volledig geobserveerde dagen**, historische winrate **≥70%** en een conservatieve theoretische marge **≥8% netto na AH-cut**. Als dat niet gehaald wordt, verschijnt **Onvoldoende herhaalbaar**; geen verzonnen koopadvies.
- Een daghandelkandidaat moet tijdens het werkelijke koopvenster onder de berekende maximumkoopprijs liggen; een verouderde publieke prijs is geen bewezen live AH-aanbod.
- Bij geschikte daghandelkansen mag het paper-model **75% van de totale equity** inzetten, tot **35% per item**, en houdt minstens **20% cashreserve**. Er wordt op **absolute verwachte netto copperwinst** gerangschikt in plaats van alleen procentueel rendement.
- De bestaande `config.json` blijft staan; extra velden zijn optioneel. De bestaande **live-goldtest blijft maximaal 5g per sessie** en **transacties blijven handmatig**.

Lees de [daghandelhandleiding 3.3](docs/DAGHANDEL-3.3.md) voor de aannames en risico's.

## Nieuw in 3.2: live-goldtest

- De live-testmodus gebruikt alleen verse in-game AH-prijzen (max. 60 seconden oud), met maximaal **1g per advies**, **5g per sessie**, en minstens **15g of 20% walletreserve**.
- De gebruiker bevestigt **iedere koop en verkoop zelf** in WoW. Automatisch onbeheerd kopen of verkopen wordt niet uitgevoerd.
- Bij het uitloggen blijft de laatst bekende echte wallet behouden; afwijkende 0g-exports worden op de desktop gemeld.
- Paper-modelverkopen vereisen nu twee opeenvolgende gunstige snapshots; de uitkomst is nog altijd een simulatie.
- Je bestaande SQLite-database en configuratie blijven behouden bij `.\UPDATE.bat`.

Lees de volledige [handleiding Live Test 3.2](docs/LIVE-TEST-3.2.md).

## Getting started

1. Lees [LEES-MIJ-EERST.md](LEES-MIJ-EERST.md).
2. Voer `SETUP.bat` uit, daarna `DEMO.bat`.
3. Installeer de addon volgens [de installatiehandleiding](docs/ADDON-INSTALLATIE.md).
4. Start de marktengine met `START.bat`.

Echte transacties bevestig je zelf. De live WoW-clientintegratie moet nog worden gevalideerd.

Documentatie: [Techniek](docs/TECHNIEK.md) · [Gericht zoeken (v3.1)](docs/V31-GERICHT-ZOEKEN.md).

Lokale databases, SavedVariables en diagnostiek horen niet in deze publieke repository.
