# ForeverTrader 3.3.1 — automatische zoekronde en gesproken routeaanwijzingen

## Wat doet deze versie?

1. **Automatisch AH-zoeken:** wanneer je bij het Auction House staat, zoekt de addon met `/ft auto on` vanzelf de volgende items uit je geladen FT3-planning. Geen herhaalde klik op **Zoek volgend** meer.
2. **AHK-spraak:** een apart AutoHotkey v2-programma zegt **'Loop naar het Auction House'** of **'Loop naar de mailbox'** wanneer de coach die stap nodig vindt. Het spreekt alleen bij statusveranderingen; tussendoor blijft het stil.
3. **Grenzen:** de automatische zoekronde respecteert de bestaande 5-secondentussenruimte, de server-throttle, de geldigheid van de FT3-planning en wacht op resultaten. Bij een actuele koop- of verkoopkans pauzeert de zoekronde, zodat de aanbieding niet door een volgende zoekopdracht verdwijnt.

**Belangrijk: alleen de zoekopdrachten en gesproken routeaanwijzingen zijn geautomatiseerd. De huidige AHK-versie koopt en plaatst nog niets.** De addon en AHK hebben nog geen gevalideerde veilige transactie-uitvoerder. Geef ze geen vrije toegang tot je 20g totdat echte clientacties, bedragen, bevestigingen en verkoopsignalen zijn getest. Voor de volledige "alleen naar AH en mail lopen"-workflow ontbreekt die stap nog.

## Installatie op Windows

Zorg dat [AutoHotkey v2](https://www.autohotkey.com/) is geïnstalleerd; v1 is niet geschikt.

1. Sluit WoW en stop `START.bat`.
2. Voer `.\UPDATE.bat` uit. De updater kopieert ook de nieuwe addon- en AHK-bestanden; bestaande `config.json` en `data/\` blijven staan.
3. Start `.\TEST.bat` en `.\START.bat`.
4. Voer `.\START-AUDIO.bat` uit. Dit start `AHK/ForeverTrader-Voice.ahk`.
5. Start WoW, ga naar je mage, open het AH, typ `/ft market`, `/ft start` en laad de actuele planning via `/ft plan`.
6. Typ `/ft auto on`. De zoekwachtrij begint daarna vanzelf; `/ft auto off` zet dit weer uit.
7. **Druk F6 terwijl het WoW-venster actief is** om de AHK-spraak aan dat venster te koppelen.

## AHK toetsen

| Toets | Functie |
|------|---------|
| **F6** | Koppel het huidige WoW-venster; start spraakmonitor |
| **F7** | Test: "Loop naar het Auction House" |
| **F8** | Test: "Loop naar de mailbox" |
| **F9** | Sluit AHK-spraakmonitor / noodstop voor AHK |

De addon toont rechtsboven in het ForeverTrader-venster **twee kleine gekleurde vakjes** als signaal voor de AHK-spraakmonitor. Die veranderen van kleur bij AH, mailbox of geen routeaanwijzing. Houd de addon zichtbaar en het WoW-venster op de voorgrond; in exclusief fullscreen kan PixelSearch onbetrouwbaar zijn. Gebruik bij voorkeur fullscreen windowed.

Spraak gebruikt Windows SAPI. Een Nederlandstalige stem wordt gebruikt wanneer Windows die beschikbaar heeft; anders kan de uitspraak een andere taalaccent hebben. Als SAPI ontbreekt, geeft AHK verschillende pieptonen.

## Gedrag van het zoeken

- De wachtrij start pas als WoW de juiste Alliance-markt bevestigt en een niet-verlopen FT3-planning geladen is.
- Een item met een bruikbaar aanbod blijft in beeld; de automatische ronde pauzeert om geen volgende resultaten over het scherm heen te laden.
- Bij geen bruikbare aanbiedingen gaat de ronde pas na de wachttijden door.
- Voor nieuwe actuele strategieadviezen moet je regelmatig een nieuwe FT3-planning uit het dashboard laden; oude plannen verlopen bewust.
- De gebruiker moet nog **zelf** een aankoop en plaatsing bevestigen; deze versie beweert geen echte goldwinst te boeken.

## Bekende beperkingen

- De AHK-spraak-/pixelkoppeling is ontworpen voor AutoHotkey v2 op Windows. De exacte werking op jouw WoW-client en Windows-resolutie moet nog worden getest; de twee audiosneltoetsen F7/F8 zijn een eerste test.
- Wanneer je het ForeverTrader-venster verbergt of een ander programma voor WoW zet, kan AHK geen zichtbaar statusvakje detecteren.
- De mailbox wordt niet automatisch geleegd. De audiomelding is een routeadvies; je moet zelf naar de mailbox lopen, de inhoud ophalen en weer naar de AH gaan.
- AHK-aankopen/verkopen vallen onder onbeheerde gameplay-automatisering en kunnen tot accountmaatregelen leiden. De gebruiker neemt dat risico zelf. Er wordt hier geen suggestie gedaan dat een AHK-bot is toegestaan.
