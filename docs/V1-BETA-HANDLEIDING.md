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
4. Log uit of voer /reload uit; de client schrijft SavedVariables en de Windows-bridge verstuurt de informatie naar de VPS.
5. Open het dashboard. Je ziet per character gold, voorraad per locatie, ouderdom van metingen, mogelijke marktwaarde en wat te controleren.

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

## Echte kostprijs optioneel vastleggen

Na daadwerkelijke inkoop van twee Arcane Crystals voor totaal 15g25s:

    /ft trade buy 12363 2 15.25g

Na daadwerkelijke verkoop van twee stuks en NET ontvangen 18g:

    /ft trade sell 12363 2 18g

Log uit om ze te synchroniseren. FIFO koppelt alleen uitdrukkelijk ingevoerde aankopen en verkopen. Ontbrekende inkoopbasis wordt niet ingevuld met fictieve winst. Dit zijn handmatige verklaringen, geen automatisch uit AH-aankopen afgeleide transacties.

## Wat deze beta NIET belooft

- Geen automatisch kopen, verkopen of onbeheerde bots.
- Geen realtime webupdates van bank/tassen terwijl WoW geen SavedVariables schrijft.
- Geen gegarandeerde winst, taxatie of verkoopprijs: TK-waarden zijn ASK-prijzen, volume bevat schattingen.
- Geen bruikbaar intraday-/langetermijnadvies als bronhistorie nog ontbreekt. De VPS draait doorlopend maar TK publiceert ongeveer elk uur.
- Regressietests met mocks en API-tests zijn geen bewijs dat alle Forever-bank- of AH-events met jouw echte client werken. Test eerst met kleine bedragen.

GitHub: https://github.com/DaniHekkenwereld/ForeverBroker
CI: https://github.com/DaniHekkenwereld/ForeverBroker/actions
