# ForeverTrader 3.2 – Getting started

## 3.2: live-goldtest (let op: geen onbewaakte bot)
De standaardmodus blijft paper trading. Je kunt binnen WoW optioneel `/ft live on` gebruiken **bij het geopende AH** na `/ft market`, `/ft start` en het laden van een FT3-planning. De coach laat dan uitsluitend koopadviezen door die gebaseerd zijn op AH-zoekresultaten jonger dan 60 seconden, met maximaal 1g per advies, 5g per sessie en minimaal 15g of 20% walletreserve. **Je moet de daadwerkelijke aankopen en verkoopplaatsingen zelf bevestigen.** De addon automatiseert dat niet. Schakel uit met `/ft live off`. Alle details: [docs/LIVE-TEST-3.2.md](docs/LIVE-TEST-3.2.md).

De paper-verkoopcontrole is aangescherpt: twee opeenvolgende marktobservaties zijn nodig, maar ook dit blijft een modelschatting. De onjuiste 0g-wallet-export bij logout wordt voorkomen en bestaande verdachte exports krijgen een waarschuwing. Bestaande paper-resultaten uit eerdere versies blijven ongewijzigd in de database.


EU PvP Alliance. Windows. Eerst paper trading; echte transacties blijven handmatig. De desktopengine houdt historie, dag-/weekpatronen, onderzoek en een fictieve portefeuille bij; de in-game coach zegt wat je zelf moet doen. Geen automatische besturing, klikken, kopen, verkopen of mailbox ophalen.

## Installatie (eenmalig)
1. Pak het ZIP-bestand uit in een **nieuwe** map, bijvoorbeeld `C:\Games\ForeverTrader-v3.1`. Bewaar v3.0 als backup. Wil je de paperdata behouden: sluit beide versies met Ctrl+C, maak een diagnostiekbackup, kopieer `data\paper\trader.sqlite` naar dezelfde submap in v3.1. Kopieer je aangepaste config.json indien gewenst (zelfde instellingen), en voer INSTALL-ADDON.bat opnieuw uit. De nieuwe tabel wordt automatisch aangemaakt. Gebruik maar één writer. Voeg geen demo-data toe aan de paperdatabase.
2. Installeer Python 3.12 indien nodig; dubbelklik `SETUP.bat` (tijdzonegegevens). Test eerst `DEMO.bat`; dit opent het dashboard met fictieve marktdata. Sluit het venster met Ctrl+C.
3. Installeer Auctionator voor Forever via CurseForge. Optioneel Postage voor handmatige bulk-mail. Kies één full-scan-addon; de 15 min cooldown wordt gedeeld. Eventuele AHledger/TSM-addons zijn niet verplicht.
4. Sluit WoW; dubbelklik `INSTALL-ADDON.bat`. Plak je WoW- of `_forever_`-map. Start WoW opnieuw en controleer of ForeverTrader aanstaat.
5. Start `START.bat`. Laat dit openstaan voor openbare marktgegevens en paper trading. Het ZIP bevat **geen** reeds geïmporteerde echte markthistorie. Gegevens en volledige scans van TK zijn ongeveer per uur, lokale AH-scans per kwartier. De eerste historische import wordt gefaseerd gevuld.

## Eén handelssessie
1. Log in op EU PvP Alliance. Typ `/ft market` om de PvP-realm zelf te bevestigen (de addon kan factie/regio controleren, niet het PvP-ruleset). Typ `/ft start`.
2. Open eerst de mailbox. Haal AH-items en beschikbaar gold zelf op, controleer ook verlopen veilingen, overige berichten en COD. De coach toont wat hij werkelijk heeft gezien; pending is geen beschikbaar gold.
3. Ga naar het Auction House. Doe een Full Scan in Auctionator. Als de server zegt dat de cooldown loopt, wacht. De coach telt vanaf laatste ontvangen scan; geen gegarandeerde servercooldown.
4. In het desktopdashboard staat **In-game handelscoach**. Kopieer de FT3-regel (selecteer + Ctrl+C). Klik in de coach op Planning plakken (of `/ft plan`), Ctrl+V, Enter. De regel is een korte lijst met item-ID, maximale inkoopprijs, hoeveelheid, verkoopdoel en verwachte hold. De addon gebruikt die als historische planning en vergelijkt die met de actuele gerichte zoekresultaten. Advies verloopt maximaal 90 min na de externe marktsnapshot. Ververs bij nieuwe data; geen internet in Lua, geen automatische desktop→WoW-verbinding.
5. Klik **Zoek volgend**: de coach kiest een item uit de planning dat opnieuw gecontroleerd moet worden. Je kunt ook zelf zoeken in Auctionator of `/ft search 2589` gebruiken voor een item uit de planning. Bij een gedeeltelijk resultaat klik je nogmaals op Zoek volgend wanneer de server gereed is. Alleen volledige zoekresultaten van maximaal twee minuten oud leiden tot koop- of verkoopadvies. Controleer actuele prijs per stuk, stack en kosten; bevestig zelf. De coach herkent gedocumenteerde aankoop-events indien de client die afgeeft; anders klik op **Naar mailbox**. Na aankoop wordt de lokale prijs-cache verwijderd. Controleer de mailbox en zoek opnieuw voordat je verder handelt. Haal items zelf op.
6. Ga terug naar het AH. Verkoopadvies verschijnt voor passende items in je tas met directe verkoopdoelen; controleer eigen kostprijs, deposit en actuele verkoopprijs. Voor langere intraday- en weekly-holds toont de inkoopregel de verwachte houdtijd. De desktopengine simuleert die, maar de addon houdt nog geen echte per-lot kostprijs/hold-administratie bij. Bewaar zulke posities zelf en controleer het nieuwe marktadvies voor verkoop.
7. De coach meldt nieuw mail-signaal, aankoop, geobserveerde betaalbare mail, vervallen verwacht betaalmoment of een periodieke controle (30 min). Loop zelf naar de mailbox en klik zelf om op te halen. Bij nieuwe mail kan de inhoud nog onbekend zijn. Bij een gedeeltelijke inbox blijft de coach waarschuwen. `/ft stop` stopt de handelssuggesties; `/ft status` opent het venster opnieuw. Geen geluid tijdens normale gameplay als handelmodus uit staat.

## Diagnose
- `/reload` of uitloggen laat WoW SavedVariables naar schijf schrijven. Dit synchroniseert de uitleesgegevens voor de desktop, die het bestand elke 30 seconden controleert; **niet** nodig voor elke lokale coach-update. Gerichte resultaten worden apart opgeslagen in `targeted_observations`. De openbare paper trading blijft op publieke marktdata draaien, niet op beperkte zoekresultaten (die bewijzen geen verkoopvolume). Een nog geldige planning blijft na reload bewaard; gebruik `/ft start` om de coach opnieuw te activeren en `/ft market` als de realmbevestiging ontbreekt. Een enkele character per sessie gebruiken; geen echte geconsolideerde meerdere-character-boekhouding.
- Sluit `START.bat` met Ctrl+C en dubbelklik `EXPORT-DIAGNOSTICS.bat`. Upload `data/paper/ForeverTrader-Diagnostics.zip` naar de chat. Dit bevat de database, beslissingen, cashflow, fouten, forecasts en lokale read-only exports. Config bevat geen WoW-pad of accountfolder. Controleer desondanks vóór delen.
- Echte aankoop/verkoopopbrengsten worden nog niet volledig als gekoppelde transacties geboekt. Werkelijke gold, tas, actieve veilingen en mail zijn observaties; de paperportefeuille is een aparte simulatie.
- Python + Lua logica en gemockte client zijn getest. Live API-responses, WoW-client, events, prijssemantiek en Windows-installatie nog testen op jouw pc. Koop niets uitsluitend op basis van testadvies.

## Nieuw in 3.1
- Gerichte zoekopdrachten gebruiken de normale moderne AH-API; één zoekactie per klik, minimaal vijf seconden tussen door de coach gestarte requests, alleen als de gedeelde throttle gereed is. Geen automatische querylus of aankoop. De server kan extra beperkingen opleggen.
- Volledige replicate-scans en herkende complete lege browse-scans worden onderscheiden. Browse-samenvattingen zijn geen individuele stacks en mogen geen koopadvies veroorzaken.
- Zelf zoeken werkt ook: de coach luistert naar item- en commodity-resultaatevents. Geen volledige resultaten, onbekend eigendom, oude prijzen of geen aanbod = geen koopadvies. De desktop bewaart maximaal 500 nog beschikbare zoekobservaties uit de addonexport per import; reeds geïmporteerde observaties blijven behouden.
- De twee minuten zijn een lokale geldigheidstermijn, niet een garantie voor de prijs of serverlimiet. Voor directe flips blijft de verkoopdoelprijs een schatting.
- Testen: 30 Python-tests, Lua-coach, gesimuleerde client en gerichte zoeklogica. Echte Forever-client en Windows-installatie nog valideren.

## Hotfix 3.1.1 – planning en gerichte prijscontroles
- Verhelpt het afkeuren van FT3-regels na plakken met verdubbelde `|`-tekens of extra witruimte in de WoW-invoer.
- Stuurt naast echte koopkansen ook monitor-items door uit de bestaande watchlist wanneer de markt nog geen harde koopsignalen oplevert. Monitor-items zijn **nooit koopadvies**: ze kunnen uitsluitend gericht worden gezocht en leveren observaties voor de database.
- Herhaalt niet steeds hetzelfde monitor-item zolang andere nog niet zijn gecontroleerd.
- Een volledige Auctionator-scan moet apart in WoW worden uitgevoerd; `Full scan: nog niet ontvangen` betekent dat de addon nog geen scanresultaat heeft gezien.
- De desktop leest SavedVariables pas na `/reload` of uitloggen. Bij meer dan een gevonden WoW-accountmap moet `account_folder` in `config.json` worden ingesteld.
