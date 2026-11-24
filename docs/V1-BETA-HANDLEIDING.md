# ForeverTrader 1.0 Beta — handleiding

**WoW Forever EU PvP Alliance.** Multi-character portfolio en AH-investeringsradar. Niet automatisch kopen of verkopen.

## Morgenochtend installeren

Sluit WoW volledig. Open PowerShell in je bestaande ForeverTrader-map.

1. Voer UPDATE.bat uit. Dit haalt BETA-START.bat op en werkt de WoW-addon bij.
2. Voer BETA-START.bat uit. Dit werkt de VPS bij, draait regressietests, synchroniseert en opent het dashboard. SSH/sudo kan om je wachtwoord vragen.
3. Als een stap faalt: controleer de foutmelding. Handel niet op basis van oude adviezen. De VPS controleert of investeringen, portfolio en daghandelfuncties bereikbaar zijn.

Daarna kun je DASHBOARD-V4.bat gebruiken om alleen het dashboard te openen. De Windows-bridge werkt zelfstandig zolang deze correct geïnstalleerd is.

## Accountbrede portfolio opbouwen

1. Log met de vernieuwde addon in op elk character.
2. Open op elk character de bank minstens één keer. Anders kunnen bankitems niet betrouwbaar worden gelezen.
3. Tassen inclusief gebonden items, uitgeruste gear en gold worden geregistreerd. Bij een open AH worden eigen veilingen geregistreerd.
4. Typ /ft portfolio in WoW om direct de gemeten gold, tassen, gear en de bankstatus van dit character te controleren.
5. Log uit of voer /reload uit; de client schrijft SavedVariables en de Windows-bridge verstuurt de informatie naar de VPS.
6. Open het dashboard. Je ziet per character gold, voorraad per locatie, ouderdom van metingen, mogelijke marktwaarde en wat te controleren.

Bankgegevens worden niet gewist omdat de bank bij een latere login gesloten is. Oude/ontbrekende stockmetingen worden zichtbaar gemaakt. De addon kan tijdens inloggen niet rechtstreeks over HTTPS synchroniseren. De synchronisatie vindt na een WoW-save plaats.

## Wat toont het dashboard?

- Portfolio: alle bekende character-gold, bank, tassen, gear en eigen AH-aantallen.
- Kooponderzoek: alleen kandidaten passend bij gold, reserve en risicoprofiel. Grotere portefeuilles krijgen ook meer langetermijnruimte.
- Wat verkopen of vasthouden: historische prijsbeweging van items die je zelf bezit.
- Daghandel: bewezen herhalende koop-/verkoopuren, gebaseerd op 5 complete dagen met minstens 16 uurlijkse vraagprijzen per dag, niet gokken.
- Investeringen: stijging/daling in 24 uur en 7 dagen, historisch goedkope instap, mogelijke koersomslag, risico en speculatieve weekscenario's.
- Tier-/raidthema's: Arcane Crystal/Arcanite, enchanting-materialen, Elemental Fire, Black Lotus. Een raid-openingsdatum is geen gegarandeerde prijsstijging.
- Wat controleert de addon: exacte itemlijst en opgeslagen werkelijk gemeten AH-vraagprijzen. In WoW zijn de actuele opdrachten zichtbaar met /ft auto status.

## In-game

Open het AH en typ /ft auto on. Typ /ft auto status voor het aantal zoekopdrachten en resultaten. Typ /ft v4 voor de laatste per-character investeringsonderzoeken met instap- en scenarioverkoopprijs. Gameprijzen komen op het dashboard pas beschikbaar na een nieuw SavedVariables-save-event; de webpagina leest geen live WoW-geheugen.

## Aankopen, verkopen en winst: automatisch

Geen per-item commando's en geen invoerschermen. De WoW-addon kijkt passief naar de Auction House-API, bevestigde aankopen en werkelijk afgeschreven gold. Bij commodity-aankopen gebruikt hij het item en aantal uit de aankoop-events of de bevestigde aankoopintentie. Bij gewone veilingen koppelt hij de veiling-ID aan de exact waargenomen stack.

Een verkoop telt **pas** wanneer de mailbox een afgeronde seller-factuur teruggeeft. Alleen een geplaatste of verdwenen veiling is geen gerealiseerde verkoop. De addon gebruikt de daadwerkelijke uitbetaling min teruggestorte deposit, niet een verwachte vraagprijs. De normale mailbox moet eenmaal worden geopend om zulke facturen in de client te laden. Dat is geen handmatige administratie.

Na een WoW-save (/reload of uitloggen) verstuurt de bestaande Windows-bridge de automatisch geregistreerde transacties naar de VPS. Elke transactie krijgt een unieke sleutel en kan niet opnieuw worden meegeteld bij een volgende sync. Het dashboard toont transacties, FIFO-kostprijzen en gerealiseerd resultaat wanneer zowel inkoop- als verkoopbedrag vaststaan.

Bij een ontbrekende hoeveelheid, een niet gemeten gold-uitgave, een onherkenbare mail of een onbekende itemvariant blijft de gebeurtenis zichtbaar als **onvolledige AH-waarneming**. Die telt niet mee als winst. Daarmee ontstaat geen verzonnen P&L. Oudere handmatige registraties blijven uitsluitend voor historische compatibiliteit bestaan, maar zijn niet meer nodig en de nieuwe addon heeft geen transactiecommando.

Technische grens: de gewone WoW-addon heeft geen directe HTTPS-toegang, en gegevens uit verkochte veilingen op een uitgelogd character zijn pas zichtbaar als WoW die via mailbox/API beschikbaar stelt. Daarom is exacte reconstructie van *ieder* verleden of offline item zonder voldoende gamegegevens niet te garanderen.

## Wat deze beta NIET belooft

- Geen automatisch kopen, verkopen of onbeheerde bots.
- Geen realtime webupdates van bank/tassen terwijl WoW geen SavedVariables schrijft.
- Geen gegarandeerde winst, taxatie of verkoopprijs: TK-waarden zijn ASK-prijzen, volume bevat schattingen.
- Geen bruikbaar intraday-/langetermijnadvies als bronhistorie nog ontbreekt. De VPS draait doorlopend maar TK publiceert ongeveer elk uur.
- Regressietests met mocks en API-tests zijn geen bewijs dat alle Forever-bank- of AH-events met jouw echte client werken. Test eerst met kleine bedragen.

GitHub: https://github.com/DaniHekkenwereld/ForeverBroker
CI: https://github.com/DaniHekkenwereld/ForeverBroker/actions
