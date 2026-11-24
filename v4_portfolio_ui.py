"""Read-only multi-character portfolio and investment tasks dashboard."""
import datetime as dt
import html


def e(value):
    return html.escape(str(value if value is not None else '—'),quote=True)


def g(value):
    if type(value) is not int:return '—'
    sign='-' if value<0 else ''
    gg,rest=divmod(abs(value),10000)
    silver,copper=divmod(rest,100)
    return f'{sign}{gg:,}g {silver:02d}s {copper:02d}c'


def at(value):
    if type(value) is not int or value<=0:return 'Nog niet gemeten'
    return dt.datetime.fromtimestamp(value,dt.timezone.utc).astimezone().strftime('%d-%m %H:%M')


def cell(value,cls=''):
    return '<td'+(' class="'+cls+'"' if cls else '')+'>'+value+'</td>'


def table(headers,rows,empty):
    if not rows:return '<p>'+e(empty)+'</p>'
    return ('<div class="tablewrap"><table><thead><tr>'+
            ''.join('<th>'+e(x)+'</th>' for x in headers)+
            '</tr></thead><tbody>'+''.join(rows)+'</tbody></table></div>')


def render(report,now,filters=None):
    p=report or {}
    filters=filters or {}
    gold=p.get('gold_total_last_known')
    count=p.get('wallet_count',0)
    cash=('<div class="metrics">'
          '<div class="metric"><small>Gold · alle bekende characters</small><strong>'+
          e(g(gold))+'</strong><span>'+str(count)+' goldmetingen, bijbehorende leeftijden hieronder</span></div>'
          '<div class="metric"><small>Gold gemeten afgelopen 7 dagen</small><strong>'+
          e(g(p.get('gold_recent_7d')))+'</strong><span>Niet zomaar overdraagbaar tussen characters</span></div>'
          '<div class="metric"><small>Voorraadindicatie op AH-vraagprijs</small><strong>'+
          e(g(p.get('portfolio_ask_mark')))+'</strong><span>Geen gegarandeerde opbrengst, nooit echte P&amp;L</span></div>'
          '<div class="metric"><small>Resultaat van geregistreerde AH-transacties</small><strong>'+
          e(g(p.get('realized_profit')))+'</strong><span>Alleen verkochte lots met bekende aankoopkosten</span></div>'
          '<div class="metric"><small>Verschillende item-ID’s</small><strong>'+
          str(p.get('holding_types',0))+'</strong><span>'+
          str(p.get('unpriced_holding_types',0))+' niet betrouwbaar te prijzen</span></div>'
          '</div>')
    notices=[]
    if p.get('wallet_missing'):
        notices.append(str(p['wallet_missing'])+' character(s) zonder goldmeting.')
    if not p.get('market_fresh'):
        notices.append('AH-marktdata verouderd; voorraadprijzen en koopadviezen zijn niet actueel.')
    notices.append('Kostprijzen komen uit automatisch gemeten aankopen en eventuele oudere notities. '
                   'Niet-meetbare transacties en transfers krijgen geen verzonnen kostprijs.')
    if p.get('unresolved_ah_count'):
        notices.append(str(p['unresolved_ah_count'])+
                       ' AH-gebeurtenissen missen item, aantal of werkelijk bedrag. '
                       'Deze zijn zichtbaar bij Onvolledige transacties en tellen niet als winst.')
    if p.get('unmatched_sales'):
        notices.append(str(p['unmatched_sales'])+
                       ' verkoop(en) konden niet volledig aan geregistreerde aankopen worden gekoppeld.')
    notice=''.join('<p class="warning">'+e(x)+'</p>' for x in notices)
    chars=[]
    for c in p.get('characters') or []:
        a=c.get('allocation') or {}
        sync=('Recent' if c.get('wallet_fresh') else 'Oud/onbekend')
        bank=('Niet gescand (optioneel)' if not c.get('bank_checked') else at(c.get('bank_at')))
        chars.append('<tr>'+cell(e(c.get('character')),'name')+
             cell(e(g(c.get('gold'))),'num')+
             cell(e(sync)+'<small class="sub">'+e(at(c.get('wallet_at')))+'</small>')+
             cell(str(c.get('bag_types',0))+' itemtypes<small class="sub">'+e(at(c.get('bags_at')))+'</small>')+
             cell((str(c.get('bank_types',0))+' itemtypes' if c.get('bank_checked') else '—')+
                  '<small class="sub">'+e(bank)+'</small>')+
             cell(str(c.get('auction_types',0))+' itemtypes<small class="sub">'+e(at(c.get('auctions_at')))+'</small>')+
             cell(str(c.get('equipment_types',0))+' itemtypes<small class="sub">'+e(at(c.get('equipment_at')))+'</small>')+
             cell(e(g(a.get('investable')))+'<small class="sub">Indicatie, niet automatisch te besteden</small>','num')+'</tr>')
    char_table=table(['Character','Gold','Goldmeting','Tassen','Bank','Eigen AH','Uitgerust','Onderzoeksruimte'],
                     chars,'Nog geen characters. Log in met de addon en sluit de client daarna af.')
    buys=[]
    for idea in (p.get('buy_review') or [])[:70]:
        buys.append('<tr>'+cell(e('KORT' if idea['horizon']=='short' else 'LANG'))+
                    cell(e(idea['character']))+
                    cell(e(idea['name'])+'<small class="sub">#'+str(idea['id'])+'</small>','name')+
                    cell(e(g(idea['price_current'])),'num')+
                    cell(e(g(idea['max_price_each'])),'num')+
                    cell((e(g(idea.get('game_ask'))) if idea.get('game_ask') is not None
                           else 'Nog niet gemeten')+
                         '<small class="sub">'+e(idea.get('game_check',''))+
                         ((' · '+e(at(idea['game_checked_at']))) if idea.get('game_checked_at') else '')+
                         '</small>')+
                    cell(e(idea.get('qty')),'num')+
                    cell(e(g(idea.get('estimated_cost'))),'num')+
                    cell(e(g(idea.get('exit_scenario'))),'num')+
                    cell(e(idea.get('reason')),'reason')+'</tr>')
    buy_table=table(['Termijn','Character','Item','TK vraagprijs','Max instap*',
                     'Gameprijs op VPS (laatste save)','Max indicatief aantal','Kosten tegen TK',
                     'Hypothetisch verkoopscenario','Waarom'],
                    buys,'Geen onderbouwde koopkansen binnen de bekende goldlimieten. '
                    'Dat is beter dan goud verspillen aan ongefundeerde signalen.')
    checks=[]
    for quote in (p.get('game_checks') or [])[:35]:
        label=quote.get('name') or 'Item '+str(quote.get('id'))
        checks.append('<tr>'+cell(e(label)+'<small class="sub">#'+
                      str(quote['id'])+'</small>','name')+
                      cell(e(g(quote['ask'])),'num')+
                      cell(e(at(quote['at'])))+
                      cell(e(quote['kind']))+
                      cell(e(quote['price_rows']),'num')+'</tr>')
    check_table=table(['Item','Echt gemeten game-vraagprijs','Meting in WoW',
                       'Type','AH-prijsregels'],checks,
                      'Nog geen AH-prijzen op de VPS. De addon controleert automatisch '
                      'bij het openen van het AH; na een WoW-save verstuurt de bridge de resultaten.')
    term=str(filters.get('p','')).strip().lower()[:65]
    items=[x for x in (p.get('holdings') or []) if not term or term in
           str(x.get('name','')).lower() or term in str(x.get('id'))]
    holdings=[]
    for i in items:
        holders=', '.join(x.get('character','?') for x in (i.get('holders') or []))
        stock=('Tas '+str(i['bags'])+' · Bank '+str(i['bank'])+
               ' · AH '+str(i['auctions'])+' · Gear '+str(i['equipment']))
        bound=('Gebonden: '+str(i['bound_bags']+i['bound_bank'])
               if i.get('bound_known') else 'Binding nog niet geverifieerd')
        color=('interesting' if i.get('advice')=='VERKOOP CONTROLEREN' else
               'stale' if 'RISICO' in i.get('advice','') else '')
        holdings.append('<tr>'+
            cell(e(i.get('name'))+'<small class="sub">#'+str(i['id'])+' · '+e(holders)+'</small>','name')+
            cell(str(i['total'])+'<small class="sub">'+e(stock)+'</small>','num')+
            cell(e(i.get('potentially_sellable'))+'<small class="sub">'+e(bound)+'</small>','num')+
            cell(e(g(i.get('ask'))),'num')+
            cell(e(g(i.get('quoted_mark'))),'num')+
            cell((e(g(i.get('recorded_purchase_cost'))) if
                  i.get('recorded_purchase_cost') is not None else '—')+
                 '<small class="sub">'+str(i.get('recorded_purchase_units') or 0)+
                 ' stuks met gemeten kostprijs</small>','num')+
            cell(e(g(i.get('week_median'))),'num')+
            cell(e(i.get('volume_24h')),'num')+
            cell('<span class="state '+color+'">'+e(i.get('advice'))+'</span>')+'</tr>')
    search='<form action="/" method="get" class="filters"><input name="p" type="search" maxlength="65" placeholder="Zoek jouw item of item-ID" value="'+e(filters.get('p',''))+'"><button type="submit">Zoek in portfolio</button></form>'
    holdings_table=search+table(['Item / characters','Totaal en locatie','Mogelijk verkoopbaar',
                                 'AH-vraagprijs','Totale AH-indicatie','Geregistreerde kostprijs','Historische mediaan',
                                 'Geschat volume 24u','Beoordeling'],
                                holdings,'Geen items gevonden.')
    themes=[]
    for idea in p.get('themes') or []:
        themes.append('<tr>'+cell(e(idea['name'])+' <small class="sub">#'+str(idea['id'])+'</small>','name')+
                     cell(e(idea['theme']))+
                     cell(e(g(idea.get('ask'))),'num')+
                     cell(e(idea.get('volume_24h')),'num')+
                     cell(e(g(idea.get('last7_median')))+
                          '<small class="sub">'+e(idea.get('history_days_7d'))+' meetdagen</small>','num')+
                     cell((str(idea['discount_vs_7d_pct'])+'%' if type(idea.get('discount_vs_7d_pct')) in (float,int)
                           else '—'),'num')+
                     cell('<span class="state">'+e(idea.get('portfolio_action'))+'</span>')+
                     cell(str(idea.get('owned',0)),'num')+
                     cell(e(idea.get('event_date'))+'<small class="sub">'+
                          e(idea.get('days_to_event'))+' dagen tot datum</small>')+
                     cell(e(idea.get('thesis'))+'<small class="sub">'+e(idea.get('status'))+
                          ' · <a href="'+e(idea.get('event_source'))+
                          '" target="_blank" rel="noopener noreferrer">Officiële raidkalender</a></small>','reason')+'</tr>')
    journal=[]
    for trade in p.get('trades') or []:
        status=('BUY' if trade['side']=='BUY' else 'SELL')
        pnl=(e(g(trade.get('realized_net_after_reported_cost'))) if status=='SELL' else '—')
        if status=='SELL' and trade.get('unmatched_quantity',0):
            pnl='Onbekende kostprijs'
        journal.append('<tr>'+cell(e(at(trade['happened_at'])))+
                       cell(e(trade.get('character')))+
                       cell(e(status))+
                       cell(e('Automatisch AH' if trade.get('source') in ('AH_BUY','AH_MAIL')
                              else 'Oude registratie'))+
                       cell('Item '+str(trade['item_id']),'name')+
                       cell(str(trade['quantity']),'num')+
                       cell(e(g(trade['total_copper'])),'num')+
                       cell(pnl,'num')+'</tr>')
    trade_table=table(['Tijd','Character','Actie','Bron','Item-ID','Aantal',
                       'Werkelijk bedrag','Gerealiseerd resultaat (bekende lots)'],
                      journal,'Nog geen afgeronde AH-transacties met compleet bewijs opgeslagen.')
    issues=[]
    for x in p.get('unresolved_ah_events') or []:
        item=x.get('item_name') or ('Item '+str(x.get('item_id'))
                                 if x.get('item_id') else 'Item nog niet bekend')
        issues.append('<tr>'+cell(e(at(x.get('at'))))+
                      cell(e(x.get('character')))+cell(e(x.get('side')))+
                      cell(e(item),'name')+
                      cell(e(x.get('quantity')),'num')+
                      cell(e(g(x.get('total_copper'))),'num')+
                      cell(e(x.get('reason')),'reason')+'</tr>')
    issue_table=table(['Waargenomen','Character','Type','Item','Aantal','Bedrag',
                       'Wat ontbreekt?'],issues,
                      'Geen onvolledige AH-transacties geregistreerd.')
    theme_table=table(['Item','Mogelijke katalysator','TK-vraagprijs','Volume','7d mediaan','Prijs vs week','Wat doen?','Eigen stuks','Raidmijlpaal','Reden + onzekerheid'],
                      themes,'Geen thematische watchlist.')
    return ('<div class="sectionhead"><div><h2>Jouw totale portfolio</h2>'
            '<p>Gold + ALLE bekende items, afzonderlijk per tas, bank, eigen AH en equipment.</p></div>'
            '<small>'+e(str(p.get('holding_types',0)))+' soorten items</small></div>'+
            cash+notice+'<h3>Characters en laatste metingen</h3>'+char_table+
            '<h3>Vandaag: mogelijke aankopen binnen jouw goldruimte</h3>'+buy_table+
            '<p class="hint">* Max instap en verkoopscenario volgen historische publieke vraagprijzen. '
            'Gebonden, uitgerust, ontbrekende en te oude gegevens tellen niet als vrij verhandelbare voorraad. '
            'Geen enkele aankoop wordt automatisch uitgevoerd. '
            'Budget per character, buffer en risico verschillen met beschikbare gold.</p>'+
            '<h3>In-game AH-prijzen op VPS opgeslagen</h3>'+check_table+
            '<p class="hint">Dit zijn daadwerkelijk in WoW gemeten vraagprijzen, '
            'NIET realtime. De meting staat pas op de VPS nadat WoW SavedVariables '
            'heeft opgeslagen bij logout of /reload. De VPS blijft intussen '
            'publieke marktprijzen verzamelen.</p>'+
            '<h3>Wat doe ik met wat ik al bezit?</h3>'+holdings_table+
            '<p class="hint">'+e(p.get('estimated_value_warning'))+'</p>'+
            '<h3>Automatisch geregistreerde aankopen en verkopen</h3>'+trade_table+
            '<p class="hint">De addon registreert aankopen bij een succesvolle AH-aankoop met '
            'bijbehorende gold-uitgave. Verkopen telt hij pas bij een afgeronde '
            'seller-factuur in je WoW-mailbox. Open je mailbox normaal om de '
            'facturen te laten uitlezen; je hoeft niets per item in te voeren. '
            'De bridge synchroniseert bij de volgende WoW-save.</p>'+
            '<h3>Onvolledige transacties (niet meegerekend als winst)</h3>'+issue_table+
            '<h3>Speculatieve tier- en raidthema’s</h3>'+theme_table+
            '<p class="hint">Zonder bevestigde tierdatum of bewezen oorzakelijk verband zijn dit '
            'onderzoeksthema’s, GEEN koopadviezen. </p>')
