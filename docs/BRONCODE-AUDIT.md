# Broncode- en SavedVariables-audit (v1-referentie; zie TECHNIEK.md voor v2)
Peildatum: 21 november 2026. Scope: openbaar toegankelijke broncode, projectdocumentatie, API-contracten; geen daadwerkelijk geïnstalleerde Forever-client of user-SavedVariables ontvangen. Geen derdepartijcode gekopieerd of meegeleverd. De tool is eigen Python/Lua-code.

| Bron | Bevinding | Keuze v1 |
|---|---|---|
| [Forever API-export](https://github.com/Atraeau/WoW-Addons/blob/main/docs/api/Auction-Mail-Trade/C_AuctionHouse.md), [Warcraft Wiki](https://warcraft.wiki.gg/wiki/API_C_AuctionHouse.GetReplicateItemInfo) | GetReplicateItemInfo: positie 3 aantal, 10 buyout, 17 itemID, index 0 tot n-1. REPLICATE_ITEM_LIST_UPDATE na ReplicateItems. | Lees alleen bestaande scan; persist raw values. | 
| [Arbitrage](https://github.com/derek-etherton/Arbitrage) | Documenteert de Auctionator FullScan payload en stack-buyout (totaal, te delen door aantal); interne hook is niet stabiel. | Geen hook op intern Auctionator-object; luister naar native event. Eenheid nog controleren in client. |
| [Auctionator public API voorbeeld](https://github.com/JedborgWoW/Auctionator-3.3.5a/blob/main/Source/Variables/Main.lua) (fork, geen bevestigde Forever-versie) | `AUCTIONATOR_PRICE_DATABASE` kan versies, realm-tabellen en CBOR bevatten. De fork biedt geen garantie over de actuele Forever-release. | Niet blind decoderen. Werkelijk gebruikte Auctionator.lua vereist voor een exacte aparte adapter. |
| [Simsar Forever](https://github.com/berkecuhadar/simsar-forever) | README bevestigt Auctionator full scan + exportaddon, professions, bags/bank, gold ledger; sommige source-tree links niet toegankelijk. | Referentiearchitectuur, geen fork of afhankelijkheid. |
| [AHledger addon/sync](https://github.com/DeepCapt/ahledger-sync), [addon-documentatie](https://ahledger.com/addon) | `AHledger.lua` bevat scans; schrijven op reload/logout. Source-available, niet automatisch permissief. | Gebruik gedocumenteerde HTTP-API; geen hergebruik van code en geen SV-parser zonder voorbeeld. |
| [Postage TOC](https://github.com/DrKlampz/Postage/blob/main/Postage.toc), [Inbox.lua](https://github.com/DrKlampz/Postage/blob/main/Inbox.lua) | Interface 16001, SavedVariables `PostageDB`; `GetInboxInvoiceInfo` voor `seller_temp_invoice`, netto uit bid + deposit - cut. Dit is runtime-berekening, dus niet aannemen dat pending als veld in SV staat. | Eigen read-only mailbox-snapshot. Geen kopiëren van Postage-code. |
| [Gold Forever](https://github.com/gold-forever/addon) | README bevestigt `GoldForever.lua`, events, bags/professions, scan; all rights reserved. | Alleen referentie, niet opgenomen. |
| [TK-data](https://auctionhouse.tk.gg/data/) | `eu-2-110` = EU PvP Alliance volgens community-mapping, overzicht compact `f/o`, integer copper, ms-timestamp. Volume deels inferred, snapshots ongeveer elk uur. Max één overview-request/uur. | Primaire provider; veldnamen i.p.v. harde array-indexen; market-guard; SQLite snapshot archief. |
| [AHledger API](https://ahledger.com/developers) | AHL1 plain-text tabel, `forever/pvp/alliance/eu` header, Unix seconden, geschat dagvolume x10. Crafting API met net margin. | Aanvullend prijs- en craftingadvies, alleen in geheugen. Credit in dashboard. Geen archivering van AHledger-prijstabel. |
| [auctionhouse.fyi](https://auctionhouse.fyi/docs/api) | Spelersscans, orderbooks, API. | Mogelijke volgende provider; niet geïntegreerd in v1. |

## Eigen exportcontract FT1
`_forever_/WTF/Account/<account>/SavedVariables/ForeverTrader.lua` → `ForeverTraderDB`. Vier stringvelden:
- `schema`: `FT1`
- `wallet`: `time|copper|faction|region`
- `mail`: `time|pendingCopper|readyCopper` (alleen zichtbare mail, geen garantie op volledig geladen inbox)
- `scan`: `time|faction|region|rowCount;itemID:quantity:rawBuyout;...`

Parser accepteert alleen het eigen schema en de verwachte velden, voert geen Lua uit en wijzigt geen SavedVariables. Scanhoeveelheden en raw buyouts worden niet gebruikt voor paper orders in v1. Geen eigenaar/bieder/character naam, geen gamegeheugen, netwerk vanuit addon of externe input. Er is één meest recente export per geselecteerde accountfolder; mailbox en wallet kunnen bij characterwissel verschillende momentopnamen zijn. Controleer timestamps en open mailbox opnieuw.

## Validatie en open punten
- Publieke API-documentatie geraadpleegd; directe HTTP-responses niet toegankelijk in deze omgeving. V1 gebruikt de gedocumenteerde schema's en weigert onbekende markt/snapshot. HTTP op Windows nog daadwerkelijk testen.
- Python-tests draaien offline met fixtures. Lua en installatiescript moeten nog in de Forever-client / Windows worden gevalideerd.
- Optionele Journalator/Syndicator/TSM/Auction Assistant SavedVariables zijn niet geaudit op actuele schema's; user-bestanden ontbreken. Geen claim dat v1 deze uitleest.
- Crafting-radar vereist recente AHledger-data en recepten die je daadwerkelijk kent. Niet automatisch verhandeld; geen deposit en executiekosten voor crafting verwerkt anders dan provider-margin.
- Werkelijke AH-commissie, depositregels, stacksemantiek, verkoopafhandeling en ingestelde realm in de client verifiëren voordat conclusies uit de modelresultaten worden getrokken.
