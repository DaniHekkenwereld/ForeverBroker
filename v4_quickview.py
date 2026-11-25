"""Fast visual action overview for the ForeverTrader market desk.

Actions remain conservative and read-only. Public asking prices, hypothetical
exit scenarios and stale SavedVariables must never become 'buy now' signals.
All detail views stay available below the overview.
"""
import html


def e(value):
    return html.escape(str(value if value is not None else '—'),quote=True)


def gold(amount):
    if type(amount) is not int:return '—'
    sign='-' if amount<0 else ''
    g,rest=divmod(abs(amount),10000)
    s,c=divmod(rest,100)
    return f'{sign}{g:,}g {s:02d}s {c:02d}c'


def nice_age(ts,now):
    if type(ts) is not int or not 0<ts<=now+300:return 'geen geldige tijd'
    age=max(0,now-ts)
    if age<60:return f'{age}s geleden'
    if age<3600:return f'{age//60} min geleden'
    if age<86400:return f'{age//3600} uur geleden'
    return f'{age//86400} dagen geleden'


def valid_item(item):
    return type(item) is int and 0<item<=10000000


def item_link(row):
    item=row.get('id')
    name=e(row.get('name') or ('Item '+str(item) if valid_item(item) else 'Onbekend item'))
    if not valid_item(item):return '<strong>'+name+'</strong>'
    return ('<a href="https://auctionhouse.tk.gg/m/eu-2-110/'+str(item)+
            '" target="_blank" rel="noopener noreferrer">'+name+'</a>')


def evaluate(research,now):
    """Dedupe item decisions and never promote contradictory/old prices."""
    p=research.get('portfolio') or {}
    fresh=research.get('market_fresh') is True
    quotes={r['id']:r for r in research.get('game_checks') or []
            if type(r) is dict and valid_item(r.get('id'))}
    stronger={r['id']:r for r in research.get('opportunities') or []
              if type(r) is dict and valid_item(r.get('id'))}
    seen=set()
    verified=[]
    watch=[]
    for r in p.get('buy_review') or []:
        if type(r) is not dict:continue
        item=r.get('id')
        if not valid_item(item) or item in seen:continue
        seen.add(item)
        cap=r.get('max_price_each')
        quote=quotes.get(item)
        other=stronger.get(item)
        price=quote.get('ask') if quote else None
        when=quote.get('at') if quote else None
        if not fresh:
            reason='Marktbron niet actueel'
        elif type(cap) is not int or cap<=0:
            reason='Geen betrouwbare instaplimiet'
        elif quote is None or type(price) is not int or price<=0:
            reason='Nog geen echte AH-prijs op VPS'
        elif type(when) is not int or not 0<=now-when<=15*60:
            reason='Gameprijs is niet recent genoeg'
        elif price>cap:
            reason='Gemeten AH-prijs is hoger dan de instaplimiet'
        elif not other or other.get('status')!='INTERESSANT — VERIFIËREN':
            reason='Investeringsradar en marktkansen bevestigen elkaar niet'
        elif (other.get('suffix_warning') or
              type(other.get('max_buy_before_deposit')) is not int or
              price>other['max_buy_before_deposit']):
            reason='Variant of tweede instaplimiet nog niet bevestigd'
        else:
            reason=None
        line={'id':item,'name':r.get('name'),'character':r.get('character'),
              'horizon':r.get('horizon'),'qty':r.get('qty'),
              'max_price_each':cap,'game_price':price,'game_at':when,
              'reason':reason}
        (verified if reason is None else watch).append(line)
    selling=[]
    holding=[]
    for r in p.get('holdings') or []:
        if type(r) is not dict or not valid_item(r.get('id')):continue
        advice=r.get('advice') or ''
        if (fresh and advice=='VERKOOP CONTROLEREN' and
                type(r.get('potentially_sellable')) is int and
                r['potentially_sellable']>0):
            selling.append(r)
        elif advice.startswith('AANHOUDEN'):
            holding.append(r)
    selling.sort(key=lambda r:(-(r.get('quoted_mark') or 0),r['id']))
    holding.sort(key=lambda r:(-(r.get('quoted_mark') or 0),r['id']))
    return {'buy':verified,'watch':watch,'sell':selling,'hold':holding,
            'patterns':len((research.get('intraday') or {}).get('patterns') or []),
            'issues':p.get('unresolved_ah_count') or 0,
            'quotes':len(quotes),'market_fresh':fresh}


def pill(kind,text):
    return '<span class="action-pill '+kind+'">'+e(text)+'</span>'


def item_row(label,details,kind='neutral'):
    return ('<div class="focus-row '+kind+'">'
            '<div class="focus-item">'+label+'</div>'
            '<p>'+details+'</p></div>')


def render(research,now):
    research=research or {}
    summary=evaluate(research,now)
    portfolio=research.get('portfolio') or {}
    gold_total=portfolio.get('gold_total_last_known')
    characters=portfolio.get('characters') or []
    pnl=portfolio.get('realized_profit')
    market= ('Actueel' if summary['market_fresh'] else
             'Verouderd / onbekend')
    market_kind='good' if summary['market_fresh'] else 'warn'
    snapshot=nice_age(research.get('snapshot_at'),now)
    lead=('Alleen een prijs binnen de limiet is niet genoeg: er moet ook een '
          'recente gameprijs én een tweede marktcontrole zijn. Jij bevestigt '
          'de koop of verkoop altijd zelf.')
    if not summary['market_fresh']:
        headline='Afwachten: marktgegevens zijn niet actueel.'
        headline_kind='warn'
    elif summary['buy']:
        headline=str(len(summary['buy']))+' instapprijs/-prijzen gecontroleerd. Hercontroleer in het AH.'
        headline_kind='good'
    elif summary['watch']:
        headline='Nog niet kopen: eerst de openstaande controles afronden.'
        headline_kind='warn'
    else:
        headline='Geen onderbouwd koopsignaal op dit moment.'
        headline_kind='neutral'

    swing_report=research.get('price_swings') or {}
    swing_items=swing_report.get('swings') or []
    swing_fresh=swing_report.get('market_fresh') is True

    stats=[
        ('💰','Gold · alle characters',
         gold(gold_total),str(len(characters))+' characters · laatst bekend'),
        ('📦','Voorraad',''+str(portfolio.get('holding_types',0))+' itemsoorten',
         str(portfolio.get('unpriced_holding_types',0))+' zonder bruikbare AH-waarde'),
        ('🧾','Bevestigde winst',gold(pnl),'— betekent: onvoldoende kostprijsbewijs'),
        ('📡','Gameprijschecks op VPS',str(summary['quotes'])+' items',
         'Na WoW-save naar VPS verstuurd'),
    ]
    metrics=''.join(
        '<div class="focus-metric"><span class="focus-icon" aria-hidden="true">'+symbol+
        '</span><div><span class="focus-label">'+e(label)+'</span>'+
        '<strong>'+e(num)+'</strong><small>'+e(foot)+'</small></div></div>'
        for symbol,label,num,foot in stats)
    status=(
        '<div class="focus-status">'
        +pill(market_kind,'● Markt '+market)+
        '<span>Bron: '+e(snapshot)+'</span>'
        +('<span>'+pill('warn','⚠ '+str(summary['issues'])+' onvolledige AH-registraties')+'</span>'
          if summary['issues'] else '')+
        ('<span>'+pill('neutral','Nog geen gameprijschecks op VPS')+'</span>'
         if not summary['quotes'] else '')
        +'</div>'
    )

    def buy_line(r):
        return item_row(item_link(r)+pill('good','Instap gemeten'),
            '<strong>AH: '+e(gold(r['game_price']))+'</strong> · Max '+e(gold(r['max_price_each']))+
            '<span class="focus-small">Gemeten '+e(nice_age(r['game_at'],now))+
            ' · '+e(r.get('character'))+
            ' · altijd opnieuw controleren vóór kopen</span>', 'good')

    def watch_line(r):
        return item_row(item_link(r)+pill('warn','Niet kopen'),
            '<strong>Max: '+e(gold(r['max_price_each']))+'</strong>'+
            ' · Gameprijs: '+e(gold(r['game_price']))+
            '<span class="focus-small">'+e(r['reason'])+'</span>','warn')

    def sell_line(r):
        return item_row(item_link(r)+pill('warn','Verkoop controleren'),
            '<strong>'+e(r['potentially_sellable'])+' verkoopbare stuks</strong> · TK-vraagprijs '+
            e(gold(r.get('ask')))+
            '<span class="focus-small">Prijs t.o.v. week: '+
            (e(str(round(r['versus_week_pct'],1))+'%')
             if type(r.get('versus_week_pct')) in (int,float) else '—')+
            ' · verkoop niet bevestigd</span>','warn')

    def hold_line(r):
        return item_row(item_link(r)+pill('neutral','Volgen'),
            '<strong>'+e(r.get('total'))+' stuks</strong> · TK-vraagprijs '+
            e(gold(r.get('ask')))+
            '<span class="focus-small">Geen vastgesteld verkoopsignaal</span>')

    buy_content=(''.join(buy_line(r) for r in summary['buy'][:2]) if summary['buy'] else
                 '<p class="empty-state">Geen koop met voldoende bewijs. '
                 'Er worden dus geen aankopen aangeraden op basis van een losse AH-vraagprijs.</p>')
    sell_content=(''.join(sell_line(r) for r in summary['sell'][:2]) if summary['sell'] else
                  '<p class="empty-state">Je voorraad heeft nu geen voldoende onderbouwd '
                  'signaal om een verkoop te controleren.</p>')
    watch_content=(''.join(watch_line(r) for r in summary['watch'][:2]) if summary['watch'] else
                   '<p class="empty-state">Geen openstaande koopkandidaten.</p>')
    hold_content=(''.join(hold_line(r) for r in summary['hold'][:2]) if summary['hold'] else
                  '<p class="empty-state">Nog geen items met een duidelijk '
                  'aanhoudadvies.</p>')
    swing_rows=[]
    for swing in swing_items[:4]:
        if type(swing) is not dict or not valid_item(swing.get('id')):continue
        live_dip=swing_fresh and swing.get('priority')==0
        kind='warn' if live_dip else 'neutral'
        state=('DIP — IN GAME CONTROLEREN' if live_dip else
               'DIP GEZIEN / HERSTELD' if swing.get('priority')==1 else
               'SCHOMMELING / BRON VEROUDERD')
        swing_rows.append(
            item_row(item_link(swing)+pill(kind,state),
                '<strong>Laagste 24u: '+e(gold(swing.get('low_24h')))+
                '</strong> · Hoogste 24u: '+e(gold(swing.get('high_24h')))+
                ' · Nu: '+e(gold(swing.get('current_ask')))+
                '<span class="focus-small">Verschil '+e(gold(swing.get('spread_copper')))+
                ' ('+e(swing.get('swing_pct'))+'%) · publieke vraagprijzen, geen verkoopbewijs</span>',
                kind))
    swing_html=(
        '<div class="swing-highlights">'
        '<div class="swing-title"><h3>⚡ Grote prijsbewegingen (24 uur)</h3>'+
        '<small>'+e(swing_report.get('active_dips') or 0)+' actuele dips · '+
        e(swing_report.get('recovered_dips') or 0)+' herstelmomenten</small></div>'+
        '<p class="hint">Ook bij zeldzame items zonder genoeg verkoopdata. '
        'Dit zijn controlesignalen, geen automatische koopadviezen.</p>'+
        (''.join(swing_rows) if swing_rows else
         '<p class="empty-state">Nog geen grote prijsbewegingen met voldoende uurlijkse metingen.</p>')+
        '<a href="#prijsbewegingen">Alle prijsbewegingen bekijken</a></div>'
    )

    blocks=[
        ('🛒','Instap gecontroleerd',len(summary['buy']),'good',buy_content,
         'Geen automatische koop: check de actuele listing.'),
        ('📤','Verkoop controleren',len(summary['sell']),'warn',sell_content,
         'Alleen items uit je eigen voorraad.'),
        ('👀','Eerst controleren',len(summary['watch']),'warn',watch_content,
         'De addon doet de AH-prijscontrole vanzelf.'),
        ('📦','Vasthouden / volgen',len(summary['hold']),'neutral',hold_content,
         'Geen aanname dat de AH-prijs een verkoop is.'),
    ]
    cards=''.join(
        '<article class="action-card '+style+'">'
        '<div class="action-card-head"><div><span class="action-icon" aria-hidden="true">'+icon+
        '</span><h3>'+e(title)+'</h3></div>'+
        '<span class="action-count">'+str(count)+'</span></div>'+
        '<div class="action-card-body">'+content+'</div>'+
        '<p class="action-foot">'+e(foot)+'</p></article>'
        for icon,title,count,style,content,foot in blocks)

    extra=('<div class="focus-bottom">'
           '<div>🕒 <strong>Daghandel:</strong> '+str(summary['patterns'])+
           ' onderbouwde patronen'+
           (' · Geen bewezen koop-/verkoopvenster.' if summary['patterns']==0
            else ' · Bekijk de daghandel-details.')+'</div>'
           '<a href="#details">Alle details bekijken ↓</a></div>')
    return ('<section class="action-center" id="overzicht" aria-labelledby="action-title">'
            '<div class="focus-heading"><div><div class="eyebrow">JOUW ACTIECENTRUM</div>'
            '<h2 id="action-title">Wat moet ik nu doen?</h2>'
            '<p class="focus-headline '+headline_kind+'">'+e(headline)+'</p>'
            '<p>'+e(lead)+'</p></div>'+status+'</div>'+
            '<div class="focus-metrics">'+metrics+'</div>'+
            swing_html+'<div class="action-grid">'+cards+'</div>'+extra+'</section>')
