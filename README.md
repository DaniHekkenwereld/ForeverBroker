# ForeverBroker

## ForeverTrader 1.0 Beta — Portfolio & Trading Desk

**Bestaande Windows-installatie morgen gebruiken:** sluit WoW, voer eerst `UPDATE.bat` uit en daarna `BETA-START.bat`. Dit werkt de Windows-addon en VPS bij, voert regressietests uit, synchroniseert en opent het dashboard. SSH/sudo kan om wachtwoorden vragen.

- **Jouw portfolio:** gold, tassen inclusief gebonden items, bank en banktassen, uitgeruste items en eigen AH-veilingen, met per-character tijdstempels. Open de bank op elk character minstens één keer en log uit zodat WoW zijn SavedVariables wegschrijft.
- **Investeringsradar:** korte en lange prijsontwikkelingen, historische instapmomenten, risico, liquiditeit en risicogewogen goldbudgetten per character.
- **Daghandel:** ochtend kopen/avond verkopen alleen bij voldoende op meerdere complete dagen aangetroffen prijspatronen; niet op basis van een losse voorspelling.
- **Raid-/tieronderzoek:** thema's voor Arcanite, enchanting-materialen en consumables, met speculatieve prijsimpact duidelijk apart van officiële data.
- **Echte transacties bijhouden:** optioneel na een echte inkoop `/ft trade buy 12363 2 15.25g` of na werkelijke netto verkoop `/ft trade sell 12363 2 18g`; FIFO-kostprijzen voor alleen bekende handmatige transacties.
- **AH-verificatie:** `/ft auto on` zoekt de VPS-kandidaten; `/ft auto status` toont exacte game-zoekactiviteit. Aankopen en verkopen zelf uitvoeren.

**Beperking:** TK publiceert doorgaans een marktsnapshot per uur. SavedVariables worden pas bij logout of /reload naar Windows geschreven, zodat tijdens het spelen geen live bank- of portfolio-synchronisatie mogelijk is. Vraagprijs en scenario zijn niet hetzelfde als gegarandeerde verkoopwinst. De beta is automatisch getest met Python-/Lua-regressies; een echte WoW Forever-clientsessie blijft noodzakelijk voor definitieve validatie.

[Lees de 1.0 Beta-handleiding](docs/V1-BETA-HANDLEIDING.md).


ForeverTrader **v4.0.0** — centrale 24/7 AH-server, per-character handelsstrategie en WoW-addon voor WoW Forever EU PvP Alliance. De oudere paper-tradingengine blijft apart beschikbaar.

## Ubuntu 26 VPS: installatie met één script

Op een **frisse Ubuntu VPS** met Python 3.11+ en sudo, log in als de gewone SSH-gebruiker:

```bash
git clone https://github.com/DaniHekkenwereld/ForeverBroker.git ~/ForeverBroker
cd ~/ForeverBroker
bash deploy/INSTALL-V4-SERVER.sh
```

Het script compileert de Python-code, draait de regressietests en **stopt bij fouten**. Bij succes maakt het een unieke geheime token aan in `/etc/forevertrader/v4.env`, installeert de `forevertrader-v4`-systemd-service onder de ingelogde gebruiker en controleert lokaal `http://127.0.0.1:8765/health`.

**Beveiliging:** dit maakt nog geen openbare verbinding. De API blijft op `127.0.0.1:8765`; voor de Windows-bridge moet er daarna eerst een werkende HTTPS-verbinding komen. De token nooit in GitHub of chat plakken.

## ForeverTrader V4: server onderzoekt, addon zoekt aan het AH

De v4-server verzamelt onafhankelijk van WoW elk uur de openbare marktprijzen en bouwt historie op. Hij bewaart de laatst gesynchroniseerde gold, tassen, bekende veilingen en afgesloten sessies **per character**, en berekent telkens nieuwe onderzoeks- en handelsadviezen op basis van historische prijsdata en beschikbare gold. De Windows-bridge verstuurt sessiegegevens na uitloggen en zet een korte `FT3`-controleplanning en adviezen per character klaar voordat WoW opnieuw start.

**V4 starten:** na de eenmalige VPS-/Windows-koppeling installeert `INSTALL-V4-BRIDGE.bat` de automatische Windows-bridge. Sluit WoW na de eerste koppeling volledig af zodat de bridge de serverzoeklijst kan klaarzetten. Daarna volstaat in-game: AH openen en `/ft auto on` (alleen zoeken); `/ft auto status` vertelt waarom zoeken eventueel pauzeert. Geen handmatige FT3-planning meer plakken. De read-only zoeklijst blijft maximaal 24 uur bruikbaar, ook tijdens lange WoW-sessies. Voor een **live desktopoverzicht** start je `DASHBOARD-V4.bat`: dit haalt elke 30 seconden rechtstreeks de nieuwste strategieën op van de VPS, zonder WoW te wijzigen.

**Belangrijk:** draai op de VPS `v4_server.py` en NIET daarnaast `START.bat` voor dezelfde database. De addon kan geen internetverbinding openen; de bridge kan een serverplan pas veilig in SavedVariables zetten **nadat WoW volledig is afgesloten**. In één al lopende gamesessie komt geen nieuwe serverplanning binnen. Geen automatische koop- of verkoopacties. Geen geverifieerde GPH zolang we geen echte transactiekosten en verkoopresultaten hebben.

### Market Desk: zichtbare kansen en AH-zoeklog

Start op je Windows-pc **`DASHBOARD-V4.bat`**. Dit start lokaal een browserdashboard dat iedere 30 seconden de VPS bevraagt via het beveiligde `/api/v4/research` endpoint; de onderliggende bron publiceert doorgaans maar één marktsnapshot per uur.

Je ziet er de echte TK-vraagprijzen, 14-daagse vraagprijshistorie indien geïmporteerd, **als verkoop gemelde** bedragen en geschatte/waar beschikbaar bevestigde volumes. Het dashboard toont een conservatieve **referentie-uitstapprijs, maximale theoretische koopprijs en potentieel verschil vóór deposit** uitsluitend waar daarvoor gegevens zijn. Zo'n marge is nooit gegarandeerde winst; een externe vraagprijs is geen verkoop. Vendor flips worden **niet** berekend: de Forever-vendorprijs is nog niet in de game gevalideerd.

Verder bevat het de **exacte 20 (of minder) zoekitems per character**, op volgorde, plus de echte zoekopdrachten en laagste in-game AH-prijzen uit de opgeslagen addon-export. De nieuwe addon zegt bij elke zoekopdracht en ieder volledig ontvangen resultaat ook in WoW wat hij doet. Typ `/ft auto status` voor de huidige sessie.

**Beperking:** WoW schrijft SavedVariables alleen bij uitloggen of `/reload`. Het dashboard kan die in-game prijzen dus pas daarna uitlezen en toont nadrukkelijk hoe oud ze zijn. Het leest geen geheugen en koopt of verkoopt niets automatisch.

[Volledige V4-handleiding, serverinstallatie, Windows-configuratie en beperkingen](docs/FOREVERTRADER-V4.md).

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
