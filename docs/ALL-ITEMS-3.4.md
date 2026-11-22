# ForeverTrader v3.4.0 — ALLE itemcategorieën

## Waarom dit nodig was

De vorige versies konden ongeveer 7.000 items **inlezen**, maar de feitelijke handelsselectie sloeg alles met `nc=true` over en keek bij strategische aanbevelingen vrijwel alleen naar `Trade Goods` en `Consumable`. Voor de historische detailimport selecteerde de engine aanvankelijk vooral de 21 materiaal-watchlistitems. Daardoor werden BoE-armor, zeldzame wapens, patterns en andere categorieën niet serieus onderzocht.

In de diagnostische database van 22 november 2026:
- 7.155 verschillende items over vijf openbare snapshots;
- 7.058 items in de nieuwste snapshot;
- 6.994 daarvan met een positieve vraagprijs;
- 5.625 met `nc=true` in de nieuwste snapshot, vaak niet-commodities;
- slechts 15 items met geïmporteerde uitgebreide uurhistorie.

Dat waren de **limieten van onze eigen code, niet het AH**.

## Nieuw: brede kansenradar

De nieuwe module `opportunities.py` loopt **alle itemrecords** uit elke publieke marktsnapshot langs, zonder categoriefilter. Dit omvat Armor, Weapon, Recipe, Miscellaneous, Container, Consumable, Trade Goods en overige klassen.

Een eerste kandidaat ontstaat als:
- er een werkelijke laagste én tweede *gepubliceerde vraagprijs* is;
- een conservatief modeldoel onder de tweede vraagprijs wordt berekend, eventueel begrensd door de gepubliceerde mediaan;
- na de ingestelde 5% AH-cut en geschatte deposit **minstens 20% theoretische nettomarge** overblijft.

De radar toont naam, categorie, prijs, volgende vraagprijs, berekend doel, theoretisch goldverschil per stuk, 24h-volume, recentst gemelde verkoopprijs, betaalbaarheid met het ingestelde budget, en of de waarde door echte verkopen wordt ondersteund. De standaard radarbankroll staat op **20g** (je mage); wijzig optioneel `radar_budget_gold` in je bewaarde `config.json`.

De radar berekent iedere 30 seconden opnieuw op de **nieuwste opgeslagen marktsnapshot**. Hij doet geen extra onbeperkte API-aanvragen.

### Wat kwam er daadwerkelijk uit de al opgeslagen database?

Er waren 435 items met een *indicatief* prijsverschil van minstens 20% na ingestelde fees. Bijvoorbeeld:
- Pattern: Deviate Scale Gloves: laagste vraagprijs 20s, tweede 2g04s.
- Pattern: Wicked Leather Headband: 1g50s90c tegenover 3g48s90c.
- Wind Dancer Boots: ongeveer 9g tegenover 22g70s.
- Distilled Firewater: 1g tegenover 1g97s.

**Dit bewijst niet dat een item tegen die hogere prijs verkocht zal worden.** De tweede prijs is een *vraagprijs* en volume is niet altijd een bewezen verkoop. Veel zeldzame armor en weapons delen een itemID ondanks verschillende random enchants of suffixes: de exacte variant moet in WoW worden gecontroleerd. Voor die items toont de radar een expliciete waarschuwing.

## Wat doet de automatische AH-zoekwachtrij?

De desktopversie vult de FT3-monitorregels nu met:
1. De sterkste breed gevonden kansen (ongeveer driekwart van de slots).
2. Een aantal oude liquide watchlist-items voor vergelijking.

Monitorregels blijven `max=0; qty=0; target=0`. De Lua-addon zoekt deze automatisch met `/ft auto on`, maar **promoveert een statistisch prijsgat niet zelf tot een koopadvies**. De uitkomst is een actuele controle van het AH-aanbod, géén automatische aankoop.

De historische detailimport (nog steeds maximaal drie items per ronde om de bron te ontzien) geeft voorrang aan de breed ontdekte uitzonderingen. Pas met voldoende vervolgdata kunnen we verantwoord een aparte BoE/snipingstrategie evalueren.

**Wat nog niet af is:** automatisch kopen, automatisch posten en echte verkoopresultaten. Er is nog geen bewezen netto gold-per-dag uit deze bredere scanner.

## Installatie

Sluit WoW en `START.bat`, daarna:

```powershell
.\UPDATE.bat
.\TEST.bat
.\START.bat
```

Het dashboard bevat nu **Alle items: brede kansenradar**. Laad opnieuw de actuele FT3-regel in de addon via `/ft plan`; de eerder ingeladen regel kent die nieuwe items niet. Typ `/ft auto on` in WoW als je de automatische zoekronde wilt gebruiken.

De bestaande data en configuratie blijven staan. Een oude historische detailimport blijft bewaard.

## Betekenis van de getallen

Een theoretische spread van 10g is **niet hetzelfde als 10g winst**. De modelberekening veronderstelt dat de huidige laagste aanbieding voor de zichtbare prijs gekocht kan worden en vervolgens later voor een modeldoel verkocht kan worden. Betrouwbaarheid hangt af van echte listingprijzen, identieke itemvarianten, aantoonbaar verkoopvolume, afzettempo, fees en mislukte auctions.
