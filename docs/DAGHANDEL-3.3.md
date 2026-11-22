# ForeverTrader 3.3 — daghandel en urenplanning

## Wat verandert er?

ForeverTrader 3.3 onderzoekt **vaste tijdvensters** voor elk item met voldoende historische uurdata:

- Nacht: 00:00–06:00
- Ochtend: 06:00–12:00
- Middag: 12:00–17:00
- Avond: 17:00–23:00

Tijden zijn lokale **Europe/Amsterdam**-tijden. Het vergelijkt voor elk product **op dezelfde afgelopen dag** wat de mediane vraagprijs in een eerder koopvenster en later verkoopvenster was. Alleen volledig geobserveerde dagen met minimaal 16 unieke uren tellen. Beide vensters moeten minimaal twee prijsmetingen op die dag bevatten. Hij combineert geen goedkope ochtend van maandag met een dure avond van vrijdag.

De selectie probeert **netto** marge na de ingestelde 5% AH-cut te vinden en neemt per product de 25e-percentiel-dagmarge als conservatieve statistiek, niet de hoogste uitschieter. Een dagvenster wordt pas een `daily`-koopkandidaat als:

1. Er minimaal 5 volledige historische dagen met beide vensters zijn.
2. Minimaal 70% van die dagen meer dan 8% theoretische netto prijsstijging na AH-cut had.
3. Ook het lagere kwartiel een theoretische netto marge van minstens 8% haalde.
4. De huidige openbare snapshotprijs onder de berekende maximumkoopprijs valt en het **daadwerkelijke lokale inkoopvenster nog open is**.
5. De verwachte marge met jouw actuele modelprijs na AH-cut en deposit minstens 8% blijft.
6. Genoeg handelsvolume en diepte zichtbaar zijn. Een duur doel zonder afzet is geen betrouwbare trade.

**Dit model vergelijkt aanbodprijzen, geen bewezen eigen verkooptransacties.** Een prijsstijging in data betekent niet dat alle door jou gekochte items verkocht kunnen worden. Houd rekening met AH-concurrentie, listing deposit, mislukte verkopen en circa een uur vertraagde publieke marktdata.

### Nieuwere snapshots

De vorige logs haalden de markt om circa **:18** binnen, terwijl de publicatie veelal rond **:22–:23** kwam. Dat leverde structureel bijna **55 minuten oude** prijzen op. V3.3 verschuift de regelmatige marktupdate daarom naar ongeveer **:27** na ieder heel uur en blijft bij **maximaal één markt-GET per uur**. De eerste opstart zonder eerdere poging kan direct een bestaande momentopname laden. De bron kan alsnog vertraging oplopen; dit is geen in-game realtime prijs.

### Niet blind all-in

De paper-simulatie reserveert **20% cash**. Daghandel mag maximaal **75% totale equity** gebruiken, met **35% per item**, zolang voldoende aanbod en liquiditeit bestaat. Voorbeeld: met fictieve 100g maximaal 35g in één item en in totaal 75g voor strategie `daily`. Dit is dus **niet je volledige echte goldvoorraad**. Hoge inzet op een prijsverschil zonder herhaalbaar bewijs vergroot het verliesrisico.

`direct`, `intraday` en `weekly` blijven beschikbaar. Nieuwe signalen worden op **geschatte absolute netto winst in copper** gesorteerd, niet uitsluitend op ROI. Grote voorstellen worden teruggeschaald naar budget in plaats van helemaal afgewezen.

Nieuwe historische itemimports worden na de vaste watchlist ook op **prijsverschil na AH-cut × realistisch beschikbaar volume** gerangschikt, zodat een item met een grote maar verhandelbare dagspread voorrang krijgt op producten met alleen enorm veel volume. De API blijft beperkt tot de bestaande voorzichtige importcadans.

### Op dashboard

De tabel **Dagplanning** toont per product:
- Historisch goedkoopste koopvenster en latere verkoopvenster.
- Maximaal berekende koopprijs en conservatieve verkoopdoelprijs per stuk.
- Aantal volledige dagen, winrate en conservatieve marge na AH-cut.
- Of er nu een koopvenster is, of het tijdstip al voorbij is, en of er genoeg herhaalbaar bewijs is.
- Indicatieve **nettogoldwinst als alle modelmatig beschikbare units daadwerkelijk zouden verkopen**. Dit is geen gerealiseerde winst en gaat uit van de vertraagde publieke prijs.

Is de historische winrate onvoldoende? Dan staat er **Onvoldoende herhaalbaar** en wordt er geen `daily`-kooporder verzonnen. Kijk ook naar hoeveel items überhaupt geldige uurdata hebben.

### Configuratie (allemaal optioneel)

Bestaande `config.json` blijft bewaard. Zonder nieuwe velden gelden:

```json
"daily_min_days": 5,
"daily_min_win_rate": 0.7,
"daily_min_net_roi_pct": 8,
"daily_capital_pct": 75,
"daily_item_pct": 35
```

Gebruik alleen waarden met `daily_capital_pct + reserve_pct <= 100` en `daily_item_pct <= daily_capital_pct`. Meer risico nemen lost onvoldoende statistiek of slechte liquiditeit niet op.

### Praktische beperking

- De live-testmodus in de WoW-addon **blijft maximaal 5g per sessie en 1g per advies** totdat de echte-goldregistratie en de AH-koppeling op de Forever-client bewezen werken.
- De addon koopt, post of verkoopt **niet** zonder een bewuste gebruikersactie. `/ft live on` is geen onbeheerde bot.
- Na het halen van je inkoopprijs en geplande verkoopmoment moet je nog steeds de actuele veilingprijs, stackgrootte, daadwerkelijke kostprijs en beschikbare mail/voorraad controleren.
- Voor een dag-winstmodel zijn **meer dan 7 dagen** relevante marktdata en vooral echte verkoopresultaten wenselijk. Dagpatronen veranderen, ook door nieuwe raids/events.
- Oude papieren trades zijn nog met oudere verkoopmodellen berekend en blijven ongewijzigd.

## Installeren

Stop `START.bat` met Ctrl+C en voer in de bestaande ForeverTrader-map uit:

```powershell
.\UPDATE.bat
.\TEST.bat
.\START.bat
```

De tabel Dagplanning verschijnt in je bijgewerkte dashboard. Alle bestaande `data/\` en `config.json` blijven staan.

## Ontwikkeltests

- `tests/test_daily.py`: synthetische ochtendgoedkoop/avondduur, geen future leakage, geen order bij vlakke prijzen, budget-afschaling.
- Tests zijn nog niet op jouw Windows-installatie uitgevoerd; controleer de `TEST.bat`-output.
