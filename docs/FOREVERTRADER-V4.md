# ForeverTrader v4.0 — centrale handelsengine

## Doel

ForeverTrader v4 scheidt het 24/7 onderzoek (VPS) van het spelen in WoW (addon). De server verzamelt de publieke EU PvP Alliance-markt met het bestaande uurlijkse rate-limitbeleid. De server bewaard de nieuwste market snapshot, prijshistorie en de laatste bekende voorraad/gold **per character**. De server berekent telkens nieuwe **koopcontroles, verkoopcontroles, vasthouden en monitoring** op basis van het actuele aanbod en maximaal 14 dagen historische vraagprijzen. Alle items uit de publieke feed komen in aanmerking, inclusief recipes, BoEs en rare items.

De Windows-bridge is de enige component die met de VPS communiceert en SavedVariables kan openen. WoW-addons kunnen zelf geen netwerkverzoeken versturen. Dit systeem gebruikt géén game-memory reading, game input automation of verborgen dataverkeer.

## Automatische marktidentiteit op WoW Forever

De addon is voor **EU PvP Alliance** gebouwd en gebruikt voor character- en sessie-identiteit altijd de vaste publieke marktcode `eu-2-110`, bijvoorbeeld `eu-2-110#Voornaam Achternaam`. Dat is een **markt-ID, geen in-game realmnaam**. WoW Forever heeft voornaam én achternaam; `UnitName('player')` en `UnitFullName('player')` geven de achternaam als tweede waarde terug, niet de realm. `GetUnitName('player', true)` kan de volledige naam teruggeven. De addon gebruikt daarom **de volledige voor- en achternaam** om spelers met dezelfde voornaam niet samen te voegen.

Sinds de Forever-clientwijzigingen in november 2026 kunnen `GetRealmName()` en vergelijkbare functies leeg of onbetrouwbaar zijn. De addon hangt daarom niet meer af van realmnaam-CVars, `/ft realm ...`, of handmatige `/ft market`-bevestiging. De addon leest zelf de characternaam, faction en regio. Alleen EU Alliance krijgt de live-AH-coach; het marktprofiel zelf is bewust vooraf geconfigureerd voor de specifieke Forever-installatie, niet via een onbetrouwbare realm API gedetecteerd.

Oude characterobservaties met foutieve realm-labels worden voor hetzelfde Alliance-character zonder gegevensverlies naar de marktcode gemigreerd. Het sessiejournaal gebruikt dezelfde marktcode. De export heeft precies 14 velden per character; legacy-exports met foutieve structuur worden nooit stil als kooptransacties behandeld.

**Een nieuwe pc:** de addon en Windows-bridge moeten eenmalig worden geïnstalleerd en gekoppeld, maar in WoW zijn geen realm- of marktcommando's nodig. De bridge gebruikt uitsluitend de WoW-accountmapnaam als basis voor de gehashte accountidentiteit; een andere schijfletter of installatielocatie verandert je character-key dus niet.

## De complete datastroom

1. **Server 24/7**: `v4_server.py` leest met `legacy.parse_market` de publieke AH-data, volgens de bestaande API-pogingfrequentie (maximaal één per uur; :27 cadence bij opvolgende aanvragen). Opslag in de bestaande `data/paper/trader.sqlite` met `market_snapshots`, `price_history` en `import_log`; een kleine selectie krijgt extra detailhistorie. **Start NIET tegelijkertijd de oude desktop `START.bat` met dezelfde DB** als de server. De oude paper-engine heeft geen rol in live v4-advisering.
2. **Characterposities**: de addon onthoudt accountbreed gold, tassen, eigen veilingen (wanneer AH geopend) en mailbox (wanneer mailbox geopend). Een tijdstempel per onderdeel maakt onderscheid tussen vers en oud. Oudere metingen overschrijven geen nieuwere.
3. **Inloggen**: WoW leest zijn eigen SavedVariables. De addon selecteert uit `v4PlanBlob` de FT3-controlelijst voor precies het ingelogde `realm#character`. `/ft v4` toont tot acht serveraanbevelingen. `/ft auto on` kan AH-zoekopdrachten uitvoeren **bij een geopend AH**. De bijbehorende prijscontroles zijn geen koopautorisaties.
4. **Tijdens spelen**: de addon gebruikt de actuele WoW-wallet, bag-inhoud, mail en AH-observaties; hij gebruikt de serverlijst als onderzoeksprioriteit. Deze WoW-data zijn actueler dan de laatste publieke snapshot. Geen automatische aankopen of postings.
5. **Uitloggen / /reload**: WoW schrijft SavedVariables met de nieuwe accountbrede characterstand en een sessieoverzicht met login/logout-tijd, begin- en eindgold, begin- en eindtasinhoud. Een verschil in geld of tassen is een **observatie, nooit bewijs van een koop/verkoop of gerealiseerde winst**.
6. **Windows-bridge**: `v4_bridge.py` herkent de vernieuwde SavedVariables binnen maximaal 15 seconden plus netwerkvertraging, uploadt de sessies via HTTPS met Bearer-token (`POST /api/v4/sync`), haalt verse adviezen op (`GET /api/v4/strategies`) en zet de nieuwe `v4PlanBlob` en `v4ActionsBlob` klaar voor de volgende WoW-start.
7. **Veilig schrijven**: zolang een WoW-proces draait, **leest** de bridge de SavedVariables wel en mag hij uploaden, maar **schrijft hij deze niet**. Een wijziging terwijl de client draait wordt anders vaak bij de volgende logout overschreven. Zodra WoW helemaal afgesloten is, zet de bridge de nieuwe strategie erin en bewaart de eerste originele versie als `ForeverTrader.lua.v4-backup`.

### Eén beperking die je moet weten

De server kan na uitloggen verder rekenen. De **nieuwe planlijst komt echter pas effectief in de addon terecht als WoW de bijgewerkte SavedVariables opnieuw laadt**, doorgaans bij de volgende start van de game. Wanneer je in het characterselectiescherm wisselt zonder WoW af te sluiten, is geen tussentijdse strategiesynchronisatie mogelijk. Hiervoor zou een aparte live-koppeling nodig zijn. De addon kan tijdens één lange sessie wel actuele AH-prijzen blijven opvragen, maar ontvangt niet automatisch nieuwe serverplannen als hij al draait.

## Strategie: wat wordt wél en niet geadviseerd?

De v4-ranking loopt over **alle itemcategorieën**. Voor een echte `VERIFY_BUY`-controle verlangt v4:
- De publieke marktsnapshot is maximaal 90 minuten oud en het characterwallet maximaal 7 dagen.
- Er is een prijsverschil met de tweede vraagprijs, gemeld verkoopvolume en een laatst gemelde verkoopprijs die het modeldoel ondersteunt.
- Het item heeft minstens 12 publieke historische prijswaarnemingen over minstens 3 dagen en de huidige prijs ligt minstens 15% onder de historische mediane *vraagprijs*.
- De theoretische netto marge na 5% AH-cut en geschatte deposit bedraagt minstens 20%.
- De aankoop past binnen de reserve van 20%, maximaal 10% van de eigen wallet per item, en de bestaande 5g proefblootstelling voor de geselecteerde kansen.
- Je bezit of list ditzelfde itemID nog niet. Random suffixes/varianten vergen expliciete controle.

`VERIFY_BUY` betekent: **controleer dat item handmatig aan het AH**, niet: het item wordt gekocht. De daadwerkelijk geïnjecteerde FT3-lijst heeft uitsluitend regels `itemID:0:0:0:0` (monitor). Andere signalen zijn `REVIEW_SELL`, `CHECK_LISTING`, `HOLD` en `WATCH`. `/ft v4` toont deze adviezen in WoW. Zonder gedocumenteerde inkoopprijs wordt een item nooit als bewezen winstgevende verkoop aangemerkt.

De server deelt geen fake GPH, paper-trades of fictieve verkopen uit als werkelijkheid.

## VPS installeren (eenmalig)

**Vereist:** Linux VPS met Python 3.10+, HTTPS-domein, DNS-record, Caddy of nginx, Python-projectcode. De VPS hoeft WoW niet te draaien.

- Kopieer de repository naar `/opt/ForeverBroker` en maak gebruiker `forevertrader`, inclusief schrijfrechten op `/opt/ForeverBroker/data`.
- **Belangrijk voor je bestaande markthistorie:** zet, met de oude desktopengine uit, een consistente backup van je huidige `data/paper/trader.sqlite` op dezelfde locatie op de VPS voordat je v4 start. Gebruik bij voorkeur de `trader.sqlite` uit een diagnostische ZIP of een SQLite-backup, niet een live WAL-database die nog wordt bijgewerkt. Zonder deze stap begint de server met nieuwe prijshistorie en zijn historische signals voorlopig beperkt.
- Maak met een veilige random generator een unieke sleutel van minimaal 32 tekens. **Zet hem nooit in de repository**.
- Maak `/etc/forevertrader/v4.env` (rechten 0600), bijvoorbeeld:

```ini
FT_SYNC_HOST=127.0.0.1
FT_SYNC_PORT=8765
FT_SYNC_DB=/opt/ForeverBroker/data/paper/trader.sqlite
FT_SYNC_TOKEN=VERVANG_DOOR_EEN_ECHT_RANDOM_GEHEIM_MINIMAAL_32
```

- Kopieer `deploy/forevertrader-v4.service` naar `/etc/systemd/system/`. Gebruik `systemctl daemon-reload`, `systemctl enable --now forevertrader-v4`.
- Richt Caddy of nginx in met geldige TLS; voorbeeld: `deploy/Caddyfile.example`. De Python-service luistert alleen op localhost; zet poort 8765 **niet publiek** open.
- Test `https://jouw-domein/health`; verwacht `{"ok":true,"version":"4.0.0"}`.

De server haalt zelfstandig marktdata op, ongeacht de loginstatus van je characters.

## Windows koppelen

1. Zorg dat je eerdere `config.json` een juiste `wow_folder` heeft (en `account_folder` als meerdere accountfolders bestaan). Eerst `UPDATE.bat` en `TEST.bat`, terwijl WoW gesloten is.
2. Stel de gebruikersomgevingsvariabelen in voor de Windows-gebruiker waaronder de bridge draait:

```powershell
[Environment]::SetEnvironmentVariable('FT_V4_URL', 'https://jouw-echte-domein', 'User')
[Environment]::SetEnvironmentVariable('FT_SYNC_TOKEN', 'DEZELFDE_LANGE_PRIVÉSLEUTEL_ALS_DE_SERVER', 'User')
```

3. Open een **nieuw** Windows-terminalvenster en gebruik `PREPARE-V4.bat`. Je ziet hoeveel characters en sessies naar de server zijn verzonden en hoeveel strategieën lokaal klaarstaan.
4. Met `START-V4-BRIDGE.bat` blijft de bridge draaien. Gebruik voor automatisch opstarten bij Windows-aanmelding `INSTALL-V4-BRIDGE.bat` (Taakplanner). Log: `data/logs/v4-bridge.log`.
5. **Sluit WoW volledig** voordat je voor het eerst een nieuwe serverstrategie ophaalt, en start WoW daarna weer. Gebruik in-game `/ft v4`, `/ft start` en eventueel `/ft auto on` aan het AH.

Zonder de omgevingsvariabelen is upload uitgeschakeld; zonder beschikbare VPS is v4 nog niet end-to-end actief. De Win-bridge mag blijven draaien zonder WoW maar de pc moet aanstaan voor de tussentijdse gegevensoverdracht.

## Bestanden

- `v4_server.py`: server, marktwerker, API.
- `v4_engine.py`: strategie per character, historie, risicolimieten, sessieadministratie.
- `v4_bridge.py`: upload, strategie ophalen, veilige SavedVariables-injectie vóór WoW-start.
- `addon/ForeverTrader/V4.lua`: per-character plannen en sessiejournaal.
- `tests/test_v4.py`, `tests/v4_mock.lua`, `tests/client_mock.lua`: regressietests.
- `PREPARE-V4.bat`, `START-V4-BRIDGE.bat`, `INSTALL-V4-BRIDGE.bat`: Windows hulpmiddelen.

## Wat v4 bewust nog niet doet

- Geen zelfstandige AH-aankopen of nieuwe veilingen plaatsen.
- Geen in-game realtime VPS-sync als WoW al draait. De serverstrategie wordt bij de volgende **game-start** ingeladen.
- Geen opslag van bewezen inkoopkosten/verkopen per individueel item. Omdat WoW-inventory en gold door quests, trades, repairs enzovoorts kunnen veranderen, is een goldverschil geen betrouwbare gerealiseerde handelswinst. Een toekomstig transactiejournaal moet daadwerkelijke deals afzonderlijk verifiëren.
- Geen automatische berekening van betrouwbare GPH uit nieuwe kansen; daarvoor ontbreken echte verkoopresultaten.

V4 is een nieuwe architectuur op bestaande data. **De VPS, TLS, authenticatie, Windows-paths en werking in de echte WoW-client moeten nog end-to-end worden getest**, ook nadat de geautomatiseerde code-tests groen zijn.
