# ForeverBroker 3.1.1 – hotfix voor 0 items / verkeerd formaat

De screenshot van 22 november toonde werkende marktdata met 7.013 items maar 0 planregels. De code liet uitsluitend paper-order kandidaten uit een beperkte watchlist door en bood daardoor geen gerichte zoekwachtrij aan.

* De desktopplanning verstuurt echte handelsregels en vult aan met `monitor`-regels (`itemid:0:0:0:0`). Die regels zijn uitsluitend voor gericht zoeken; de addon kan op basis daarvan **niet kopen en niet verkopen**.
* De in-game parser verdraagt verdubbelde pipes (`||`) en witruimte na plakken vanuit de browser.
* De gerichte zoekwachtrij doorloopt monitor-items, in plaats van altijd opnieuw het eerste item te kiezen.
* Live prijscontroles blijven twee minuten geldig; aankopen moeten handmatig worden bevestigd.
* De full scan is een aparte stap; SavedVariables schrijven bij reload/logout.

## Updaten vanuit bestaande ZIP-installatie

1. Sluit ForeverTrader (Ctrl+C) en sluit WoW volledig af. Houd de bestaande map aan zodat de paper-`trader.sqlite` behouden blijft.
2. Haal `coach.py`, `addon/ForeverTrader/Logic.lua`, `Target.lua`, `ForeverTrader.lua`, `ForeverTrader.toc` op van de nieuwste `main` in https://github.com/DaniHekkenwereld/ForeverBroker.
3. Voer `INSTALL-ADDON.bat` opnieuw uit en wijs naar je `_forever_`-map.
4. Start `START.bat`, start WoW, `/ft start`, en klik na de automatische dashboardverversing `/ft plan` om de nieuwe FT3-lijst te laden.
5. Open het AH en klik `Zoek volgend`; voor full scan gebruik je Auctionator. Open na `/reload` het dashboard voor eigen AH-data.

Let op: de lijst met monitor-items is voor onderzoek. De app voert geen echte transacties uit.
