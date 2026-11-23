# ForeverTrader V4: investeringsradar

**Doel:** gold investeren in items met een kans op waardestijging, op korte (1–5 dagen) en langere termijn (1–3 weken). Geen willekeurige vendor flips of alleen AH-spreads.

## Installeren op Windows

1. Sluit WoW volledig en voer UPDATE.bat uit in de ForeverTrader-map.
2. Voer DEPLOY-V4.bat uit. Dit haalt nieuwe code naar de VPS, test die, herstart de service en verifieert via HTTPS dat de investerings-API werkt. SSH kan om het VPS- en sudo-wachtwoord vragen.
3. Voer DASHBOARD-V4.bat uit. Het lokale Market Desk-dashboard toont trendkansen, prijsdalingen, stijgingen en de exacte AH-zoeklijst.
4. Om de nieuwe zoeklijst direct te laden kun je met gesloten WoW PREPARE-V4.bat uitvoeren. De Windows-bridge werkt normaal automatisch bij.
5. Start WoW, open het Auction House en voer /ft auto on in. Met /ft auto status zie je hoeveel opdrachten en resultaten er zijn. De laatste opgeslagen AH-prijzen verschijnen in het dashboard na /reload of uitloggen.

## Betekenis van de signalen

- KORT — HERSTEL: minstens 15% goedkoper dan de weekmediaan, terwijl de mediane prijs de afgelopen 24 uur weer stijgt.
- KORT — KOOPDIP: goedkope instap ten opzichte van de weekmediaan, zonder een sterke nieuwe daling.
- LANG — OPWAARTS: een sterkere week-op-week stijgende prijstrend, zonder extreem hoog instapniveau.
- DALING — AFWACHTEN: recente snelle daling. Niet elk goedkoop item is een koopkans.
- STIJGT SNEL — NIET NAJAGEN: koersstijging zonder aantoonbaar goedkope instap.
- ONVOLDOENDE HISTORIE, DUNNE MARKT of MARGE TE KLEIN: geen geloofwaardig koopvoorstel.

## Data en risico

Alle prijzen zijn per item. De marktbasis is een uurlijkse TK Auction House-snapshot voor WoW Forever EU PvP Alliance. Dit zijn vraagprijzen, GEEN gegarandeerde verkoopprijzen. Het volume bevat schattingen.

Het korte verkoopscenario gebruikt 95% van de recente 7-daagse mediane vraagprijs. Het lange scenario veronderstelt expliciet dat de afgelopen weektrend nog een week doorzet (maximale extrapolatie +50%). Dit is een *speculatieve berekening*, geen toekomstvoorspelling.

De inkoopgrens vergt minstens 20% theoretische marge na AH-cut, maar is exclusief stortingskosten, onverkochte veilingen, koersrisico en liquiditeitsrisico. Externe vendorprijzen worden niet gebruikt.

De goederenmand-indicator laat alleen de mediane 7-daagse prijsontwikkeling van minstens 10 liquide vergelijkbare items zien, niet een betrouwbare inflatiemeting voor alle WoW-gold.

Langdurige trends vereisen dat de VPS minstens twee weken bruikbare historie voor die items heeft. Als die data ontbreken, toont het systeem dat in plaats van winst te verzinnen. De addon zoekt dan maximaal vijf onderzoekskandidaten om zijn lokale prijzen te controleren.

De handelsfunctie blijft read-only: geen automatische aankopen of verkopen. Controleer elk signaal en de exacte itemvariant in de game.
