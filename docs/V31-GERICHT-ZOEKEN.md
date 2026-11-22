# 3.1 — Gerichte zoekopdrachten

- De bestaande FT3 planning is een historisch prijsdoel en limiet, niet een live orderboek. De coach combineert die met complete, exacte item/commodity-resultaten, maximaal 120 seconden oud. De full scan blijft voor marktdekking; zoekresultaten vervangen alleen de cache voor het betreffende item. De full scan kan worden geregistreerd als raw replicate of complete lege browse (samenvatting).
- Gerichte requests in Target.lua/ForeverTrader.lua: SendSearchQuery via gebruikersklik, throttle check, vijf seconden minimumafstand, één uitstaande request; optionele volgende pagina via gebruikersklik. Geen gegarandeerde onbeperkte queries. De code luistert ook naar gewone zoekresultaten en invalidateert de cache bij SendSearchQuery, incomplete resultaten, aankoop, AH sluiten. Geen automatische transacties.
- Prijsberekening: item buyoutAmount is stacktotaal, commodity unitPrice is per stuk. Eigen/accountveilingen worden conservatief uitgesloten. Exacte item keys zonder gearvariant. Bij ontbrekende eigenaarvelden of incomplete resultaten geen advies. Clientvalidatie nodig.
- SQLite: targeted_observations(t,item_id,kind,ask,units,rows,book). Gegroepeerde stacktotalen en aantallen, incl. lege complete resultaten. Geen schatting van afzet uit zoekresultaten. Nieuwe waarnemingen dedupliceren, maximaal 500 observaties / 3 MB in SavedVariables exportbuffer, reeds geïmporteerde observaties blijven in SQLite. De bestanden worden pas op reload/logout bijgewerkt; desktop poll 30 s. Public API interval blijft 1 uur. Paper trading blijft op de externe marktdata; de lokale coach en desktopplanning herrekenen prijs/marge/hoeveelheid met verse targeted data. Niet alle marktitems hebben een historisch doel; watchlist begrenst kandidaatselectie.
- Diagnostiek bevat targeted_observations.csv, volledige database en overige logs. De complete browse-samenvatting wordt als local_exports opgenomen, niet als echte individuele veilingen.

Bronnen (geraadpleegd):
- https://warcraft.wiki.gg/wiki/API_C_AuctionHouse.SendSearchQuery
- https://warcraft.wiki.gg/wiki/API_C_AuctionHouse.GetItemSearchResultInfo
- https://warcraft.wiki.gg/wiki/API_C_AuctionHouse.GetCommoditySearchResultInfo
- https://github.com/xIGBClutchIx/ForeverPlusPlus/blob/main/docs/forever-api.md (community bevindingen over browse/replicate, geen bevestigde live test door ons)
