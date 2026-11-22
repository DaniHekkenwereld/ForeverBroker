# ForeverTrader 3.2 – Live-goldtest en betrouwbaarheid

## Wat werkt wel en niet?

**Wel:** echte openbare Forever EU PvP Alliance-marktgegevens verzamelen, historische patronen en fictieve portefeuille bijhouden, actuele AH-prijzen via in-game zoekactie opvragen, koop- en verkoopadviezen tonen, wallet/tassen/mail/veilingen observeren, en optioneel een live-adviesmodus met budgetlimieten.

**Niet:** een onbeheerde koper/verkoper. Deze addon koopt, plaatst, annuleert of haalt geen items automatisch op. Het Blizzard-AH vereist een fysieke actie voor beschermde aankoop- en plaatsingsstappen. Externe autobot-/autoclicksoftware is risicovol voor je account. Beloof dus niet dat alleen naar AH lopen en mailbox leeghalen genoeg is.

De eerste live-test is **maximaal 5 gold budget per sessie**, **maximaal 1 gold per afzonderlijk advies**, en houdt **minimaal 15 gold of 20% van je wallet** achter (wat meer is). Deze limieten gelden voor **adviezen**, geen garantie voor wat je zelf in Auctionator aanklikt. Alle gold-uitgaven tijdens de live-testsessie tellen conservatief mee. Er is geen automatische daadwerkelijke trade-boekhouding.

## Installeren vanuit je huidige map

1. Sluit WoW en stop `START.bat` met `Ctrl+C`.
2. Maak optioneel eerst een export: `.\EXPORT-DIAGNOSTICS.bat`.
3. Voer `.\UPDATE.bat` uit vanuit je bestaande ForeverTrader-hoofdmap.
4. Start `.\START.bat` en open daarna WoW.
5. Typ in WoW `/ft market` (eenmalig), `/ft start`.
6. Kopieer de FT3-regel uit **In-game handelscoach** op het desktopdashboard; plak via `/ft plan` (Enter).
7. Open het AH en typ **`/ft live on`**. Dit schakelt alleen extra gecontroleerde **koopadviezen** in. Er vindt nog geen transactie plaats.
8. Klik **Zoek volgend**, controleer de **werkelijke actuele prijs per stuk / stack**, onderbiedingen, eigen kostprijs, deposit en voorraad. **Je koopt en plaatst zelf via de WoW/Auctionator-knoppen.**
9. Na een koop controleer je de mailbox; je kunt de coach desgewenst opnieuw laten zoeken. Live-testuitgaven worden conservatief van het sessiebudget afgetrokken zodra het goldsaldo daalt.
10. Stop direct met `/ft live off` of `/ft stop`.

Als de openbare marktdata verlopen zijn, stuurt het dashboard alleen **monitor**-items (geen koopadviezen). Een echte aankoop moet altijd steunen op een recente AH-observatie; de addon weigert live-advies als een gerichte observatie 60 seconden of ouder is.

## Wat is in v3.2 gerepareerd?

- **Logout-wallet:** `PLAYER_LOGOUT` schrijft geen valse 0g meer naar `ForeverTraderDB.wallet`. De desktop markeert afwijkingen tussen de wallet-export en een recente coach-waarneming.
- **Paper-verkoop:** pas na **twee onafhankelijke, opeenvolgende** marktsnapshots met een prijs op/boven het doel én voldoende geschat volume wordt een fictieve verkoop geboekt. Een tussentijdse tegenvallende snapshot reset de bevestiging. Dit is **nog steeds geen bevestigde echte verkoop**, alleen een conservatiever model.
- **Historische winst:** oude paper-transacties blijven staan in je database. Winst uit oudere versies gebruikt nog het vroegere, optimistischere verkoopmodel.
- **Live-budget:** echte wallet vereist; beperkte blootstelling, verse orderboekprijs, geen koopadvies op `monitor`-regels of wanneer het AH gesloten is.

## Grenzen van de test

- Je krijgt in de desktopsoftware nog altijd **geen directe live datastroom** uit WoW; SavedVariables worden pas bij /reload of uitloggen door de client weggeschreven.
- De openbare marktsnapshots kunnen 50–60 minuten achterlopen, en zijn **geen** live verhandelbare aanbiedingen.
- In-game live-toetsing is nog niet op jouw Forever-client bewezen; het blijft nodig om de scan, zoekresultaten en geldbedragen te verifiëren.
- Echt winst/verlies van WoW-transacties kan de engine **niet** automatisch nauwkeurig reconstrueren uit het model alleen. Noteer echte aankopen/verkopen afzonderlijk.
- Als je bij het AH bent en `/ft live on` geen advies toont, is dat op zichzelf geen fout. Het systeem laat alleen een advies toe wanneer aan alle voorwaarden is voldaan.
- Voor sluitende echte handel zijn nog vereist: gevalideerde AH-controls op Forever, kostprijsregistratie per gekocht lot, listing-/sale matching met de post- en mail-events en tests op echte transacties. Start daarom met bedragen die je kunt missen.

## Controleren

Vanuit de root: `.\TEST.bat` (Python). Lua-tests zijn beschikbaar in `tests/coach_test.lua` en `tests/client_mock.lua`, maar moeten op een Lua-runtime of in WoW worden uitgevoerd. Het v3.2 Python-testpakket is uitgevoerd op Linux met lokale mocks en gemigreerde kopie van je diagnostiekdatabase; **de echte Windows/WoW-client is nog niet gevalideerd**.
