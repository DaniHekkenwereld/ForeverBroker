# ForeverBroker

ForeverTrader **v4.0.0** — tradingcoach, conservatievere paper-tradingengine en optionele live-goldtest met handmatige transacties voor WoW Forever EU PvP Alliance.

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

## Nieuw in 3.5: snapshots van al je characters + VPS-synchronisatie

- De WoW-addon registreert automatisch je characternaam, realm, faction, gold, tassen en (indien geopend) eigen AH-veilingen en mailbox. Gegevens van meerdere characters blijven afzonderlijk bewaard in accountbrede SavedVariables.
- De Windows-app leest dit na een SavedVariables-write automatisch in en toont een **Jouw characters**-overzicht met tijdstip per meting.
- Optionele `sync_client.py` uploadt per-character gegevens via HTTPS met een eigen geheime token naar `sync_server.py` op je VPS. Standaard **uitgeschakeld** totdat jij `FT_SYNC_URL` en `FT_SYNC_TOKEN` instelt. Secrets niet in Git zetten.
- **Nog niet live op het moment van inloggen:** WoW schrijft SavedVariables pas bij **/reload of uitloggen**. Om zonder /reload direct bij login naar de VPS te synchroniseren moet de realtime desktop/game-bridge nog worden ontwikkeld en getest.
- De bestaande handelsengine blijft voorlopig een gescheiden paperstrategie. Een echte portfolio-manager die inkoopkosten per char vergelijkt met huidige prijzen ontbreekt nog.

[Handleiding character sync, VPS-installatie en beperkingen](docs/CHARACTER-SYNC-3.5.md).

## Nieuw in 3.4: bekijk alle items, niet alleen materialen

- De nieuwe **brede kansenradar** beoordeelt alle items uit de publieke marktfeed, óók BoE-armor, wapens, recipes, containers, pets en ongebruikelijke items.
- De oude `nc=true`/Trade Goods-beperkingen blijven alleen bestaan waar de **oude paper-handelsstrategie** ze bewust gebruikt; de brede radar en AH-zoekwachtrij hebben die beperking niet.
- Items worden geselecteerd op het theoretische prijsverschil na AH-cut en deposit, geschatte nettowinst in gold, meldingen over eerdere verkopen en budget. Een tweede hogere AH-vraagprijs is nog geen bewezen verkoop.
- De FT3-planning stuurt nieuwe kansrijke itemIDs door als **monitor** (`max=0, qty=0`): automatisch zoeken bij het AH, nooit automatisch kopen op basis van een onbetrouwbare openbare spread.
- De detailhistorie-import richt zich voortaan ook op uitzonderlijke niet-commodities. Bronlimieten blijven gelden.

[Handleiding en concrete voorbeelden uit je diagnosebestand](docs/ALL-ITEMS-3.4.md).

## Nieuw in 3.3.1: automatisch AH zoeken + AHK-audiocues

- Met `/ft auto on` zoekt de addon zelfstandig de items uit je ingeladen FT3-planning zolang je bij het AH staat. Bij een geschikte koop- of verkoopsituatie pauzeert hij zodat de actuele prijs zichtbaar blijft. `/ft auto off` schakelt dit uit.
- Windows **AutoHotkey v2** spreekt **"Loop naar het Auction House"** of **"Loop naar de mailbox"** wanneer de coach daarom vraagt. Installeer AHK v2, start `.\\START-AUDIO.bat` en druk **F6** terwijl WoW actief is. **F7/F8** testen de twee meldingen, **F9** stopt AHK.
- De koppeling leest uitsluitend twee kleine statuskleurvlakken uit het spelvenster. Er wordt niet gescreend op itemprijzen en geen gamegeheugen gelezen.
- **Niet verwarren met een automatische handelaar:** aankopen, verkopen en posten zijn in deze versie nog niet automatisch; daarvoor is eerst een geteste client-specifieke transactie-uitvoerder nodig. De bestaande 5g live-testlimieten gelden nog.

Meer: [AHK-audio en automatisch zoeken](docs/AHK-AUDIO-3.3.1.md).

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
