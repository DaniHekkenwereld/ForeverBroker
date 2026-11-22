# ForeverTrader 3.5 — Character-synchronisatie en VPS-ontvanger

## Wat er al is ingebouwd

**WoW-addon:** registreert automatisch bij iedere character-login en bij veranderingen in je geld of tassen:
- Characternaam, realm en faction, laatst gezien;
- gold en het tijdstip van de laatste geldmeting;
- inventaris in gewone tassen, met itemID en hoeveelheid;
- eigen AH-aanbiedingen **alleen nadat je het AH hebt geopend**;
- mailboxstatus **alleen nadat je de mailbox hebt geopend**.

Deze informatie staat per character in `ForeverTraderDB.characters`. Bij iedere update wordt ook een begrensde `charactersWire`-export opgebouwd voor de Windows-app. Eerder bezochte characters worden niet weggegooid. Bankvoorraad en historische inkoopprijzen zijn nog niet beschikbaar. Een oude waarneming krijgt in het dashboard een eigen tijdstip.

**Windows-desktop:** importeert de laatst weggeschreven accountbrede SavedVariables automatisch in `character_snapshots` in SQLite. Hij gebruikt ze **niet als bewezen actuele gegevens** zolang het spel de bestanden niet heeft bijgewerkt. De paperportfolio is strikt gescheiden van de echte characterbezittingen.

**VPS:** `sync_server.py` ontvangt snapshots in `POST /api/v1/characters` met een lange Bearer-sleutel; geld en inventaris worden per character gescheiden opgeslagen. Oudere metingen overschrijven geen recentere waarden. Hij luistert standaard **alleen op 127.0.0.1:8765** en moet achter een HTTPS reverse proxy staan.

**Uploader:** `sync_client.py` verstuurt de laatste opgeslagen snapshots zodra het Windows-desktopprogramma draait en de configuratie aanwezig is. Veranderingen worden direct na het wegschrijven van SavedVariables door de eerstvolgende desktop-ronde verwerkt. Bij netwerkfouten wordt later opnieuw geprobeerd. Wanneer de inhoud niet verandert, wordt maximaal ieder uur opnieuw bevestigd.

## Belangrijke beperking: nog niet live direct bij inloggen

WoW-addons kunnen niet zelf een externe HTTPS-API aanroepen en WoW schrijft SavedVariables pas bij **/reload of uitloggen**. Daarom is het volgende onderscheid belangrijk:

- **Bij inloggen:** de addon leest direct je huidige character en schrijft de nieuwe gegevens naar zijn interne SavedVariables.
- **Tijdens spelen:** veranderingen worden in de game bijgewerkt.
- **Bij /reload of uitloggen:** WoW schrijft die gegevens naar schijf, waarna de Windows-app ze zonder handmatige export oppakt en naar de VPS kan sturen.
- **Zonder /reload of uitloggen:** directe serveroverdracht is **nog niet gerealiseerd**. Hiervoor is een extra realtime Windows/game-bridge nodig. De bestaande AHK-audiobrug verstuurt geen inventorydata.

De synchronisatie is dus niet al exact op het loginmoment live op de server; dat mag niet worden voorgesteld als afgerond.

## VPS instellen

Op een Linux-VPS met Python 3.10+:

1. Plaats de projectbestanden onder een privéserviceaccount.
2. Genereer een willekeurige geheime sleutel van minstens 32 tekens. Zet die **niet** in GitHub of een publiek configuratiebestand.
3. Start met omgevingsvariabelen `FT_SYNC_TOKEN`, `FT_SYNC_HOST=127.0.0.1`, `FT_SYNC_PORT=8765` en optioneel `FT_SYNC_DB=/var/lib/forevertrader/characters.sqlite`:
   `python3 sync_server.py`
4. Laat Caddy of nginx op een eigen HTTPS-hostnaam `/api/v1/characters` proxy'en naar `127.0.0.1:8765`. Zet de Python HTTP-server nooit zelf publiek open.
5. Gebruik een systemd-service voor automatische herstart.

Op Windows, in de gebruikersomgeving waarin ForeverTrader draait:

- `FT_SYNC_URL=https://jouw-eigen-domein.example/api/v1/characters`
- `FT_SYNC_TOKEN=<dezelfde geheime sleutel>`

Herstart daarna de offline monitor of `START.bat`. De URL moet HTTPS zijn; HTTP wordt bewust geweigerd. Als de variabelen ontbreken, blijft de upload uitgeschakeld.

## Installatie op de pc

Sluit WoW en de ForeverTrader-desktop, voer `UPDATE.bat` en `TEST.bat` uit, en start ForeverTrader. Wanneer `wow_folder` en bij meer dan één account `account_folder` correct ingesteld zijn, verschijnen characters vanzelf na het volgende wegschrijven van SavedVariables. De actieve pc kan via `INSTALL-OFFLINE-MONITOR.bat` zelfstandig de uploader uitvoeren zolang Windows draait. Zonder VPS kun je alle per-character data eerst lokaal testen.

## Wat nog moet voor de volledige 24/7 handelsassistent

1. Een daadwerkelijk bereikbare VPS configureren en de beveiligde synchronisatie end-to-end testen.
2. Een betrouwbare **realtime** transportbrug tussen open WoW en de Windows-app bouwen, zodat een login zonder /reload meteen op de VPS zichtbaar wordt.
3. Echte transacties en inkoopprijzen per character vastleggen; zonder kostprijs kunnen we geen bewezen winst per verkoop uitrekenen.
4. In de serverstrategie voorraad, actuele geldreserve, houdperiode en eigenaarschap per character meenemen. De bestaande paper-engine doet dit nog **niet**; hij is geen echte automatische portfolio-manager.

Geen wachtwoorden, accountsessies of gevoelige WoW-logins worden naar de VPS gestuurd. Wel de door jou gekozen character-, gold- en inventorygegevens via een beveiligde verbinding.
