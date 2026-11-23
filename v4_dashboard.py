"""ForeverTrader V4 market desk: safe HTML from actual VPS and saved game data.

No automatic purchases, no fake vendor profits. Every number has a timestamp
and a provenance label. The dashboard never reads game memory or writes WoW.
"""
import datetime as dt
import html
import os
import pathlib
import tempfile


def escape(value):
    return html.escape(str(value if value is not None else '—'),quote=True)


def money(copper):
    if type(copper) is not int:
        return '—'
    negative='-' if copper<0 else ''
    copper=abs(copper)
    gold,rest=divmod(copper,10000)
    silver,cents=divmod(rest,100)
    return f'{negative}{gold:,}g {silver:02d}s {cents:02d}c'


def stamp(ts):
    if type(ts) is not int or ts<=0:
        return 'Onbekend'
    return dt.datetime.fromtimestamp(ts,dt.timezone.utc).astimezone().strftime('%d-%m %H:%M:%S')


def age(ts,now):
    if type(ts) is not int or ts<=0:
        return 'geen meting'
    seconds=max(0,now-ts)
    if seconds<60:return f'{seconds}s geleden'
    if seconds<3600:return f'{seconds//60} min geleden'
    if seconds<86400:return f'{seconds//3600} uur geleden'
    return f'{seconds//86400} dagen geleden'


def cell(content,css=''):
    return '<td'+(' class="'+css+'"' if css else '')+'>'+content+'</td>'


def value(v):
    return '—' if v is None else escape(v)


def selectable(name,current,options):
    return '<select name="'+name+'">'+''.join(
        '<option value="'+escape(k)+'"'+(' selected' if k==current else '')+'>'+
        escape(label)+'</option>' for k,label in options)+'</select>'


def plan_item_ids(plan):
    if not isinstance(plan,str) or not plan.startswith('FT3|'):
        return []
    ids=[]
    for row in plan.split(';')[1:]:
        parts=row.split(':')
        if len(parts)==5 and parts[0].isdigit() and all(x.isdigit() for x in parts[1:]):
            i=int(parts[0])
            if 0<i<10_000_000:ids.append(i)
    return ids[:30]


def opportunity_rows(candidates,now,filters):
    mode=filters.get('mode','all')
    sorting=filters.get('sort','signal')
    term=filters.get('q','').strip().lower()[:70]
    if mode=='interesting':
        candidates=[c for c in candidates if c.get('status')=='INTERESSANT — VERIFIËREN']
    elif mode=='history':
        candidates=[c for c in candidates if (c.get('history_days') or 0)>=3]
    if term:
        candidates=[c for c in candidates if term in str(c.get('name','')).lower()
                    or term in str(c.get('id',''))]
    if sorting=='discount':
        candidates.sort(key=lambda c:(c.get('discount_pct') is None,
                                      -(c.get('discount_pct') or 0),c.get('id',0)))
    elif sorting=='net':
        candidates.sort(key=lambda c:(c.get('theoretical_net_before_deposit') is None,
                                      -(c.get('theoretical_net_before_deposit') or 0),c.get('id',0)))
    elif sorting=='volume':
        candidates.sort(key=lambda c:-(c.get('vol24') or 0))
    elif sorting=='name':
        candidates.sort(key=lambda c:str(c.get('name','')).lower())
    # Default preserves evidence-ranked order sent by the server.
    rows=[]
    for c in candidates[:100]:
        status=c.get('status') or 'ONBEKEND'
        has_theory=(c.get('reference_exit') is not None and status!='VEROUDERD')
        link='https://auctionhouse.tk.gg/m/eu-2-110/'+str(c['id'])
        detail=escape(c.get('reason'))
        if c.get('suffix_warning'):
            detail+=' · <strong>variant/suffix controleren</strong>'
        label=' <small class="sub">#'+escape(c.get('id'))+' · '+escape(c.get('category'))+'</small>'
        name='<a href="'+escape(link)+'" target="_blank" rel="noopener noreferrer">'+escape(c.get('name'))+'</a>'+label
        history=value(c.get('history_days'))+'d / '+value(c.get('history_points'))+' meetpunten'
        sales=value(c.get('vol24'))+' geschat'
        if c.get('sure24') is not None:
            sales+=' · '+value(c.get('sure24'))+' bevestigd'
        notes=escape(c.get('sale_evidence'))
        rows.append('<tr>'+
            cell('<span class="state '+('interesting' if status=='INTERESSANT — VERIFIËREN'
                                        else 'stale' if status=='VEROUDERD' else '')+'">'+escape(status)+'</span>')+
            cell(name,'name')+
            cell(escape(money(c.get('ask'))),'num')+
            cell(escape(money(c.get('hist_median'))),'num')+
            cell((f'{c["discount_pct"]:+.1f}%' if type(c.get('discount_pct')) in (float,int) else '—')+
                 '<small class="sub">'+history+'</small>','num')+
            cell(escape(money(c.get('last_sold_price')))+
                 '<small class="sub">'+escape(age(c.get('last_sold_at'),now))+'</small>','num')+
            cell(sales+'<small class="sub">'+notes+'</small>','num')+
            cell(escape(money(c.get('reference_exit'))) if has_theory else '—','num')+
            cell(escape(money(c.get('max_buy_before_deposit'))) if has_theory else '—','num')+
            cell(escape(money(c.get('theoretical_net_before_deposit'))) if has_theory else '—','num')+
            cell(detail,'reason')+'</tr>')
    return len(candidates),''.join(rows)


def queue_sections(strategies,report,activity,now):
    lookup=report.get('lookup') or {}
    opp={int(x['id']):x for x in report.get('opportunities',[]) if 'id' in x}
    scans={int(x['id']):x for x in activity.get('observations',[]) if 'id' in x}
    blocks=[]
    for s in strategies:
        ids=plan_item_ids(s.get('plan'))
        character=escape(s.get('character'))
        title='<h3>'+character+' <small>'+escape(s.get('realm'))+'</small></h3>'
        summary=('<p>Gold laatst bekend: <b>'+escape(money(s.get('gold')))+'</b>'+
                 ' · Charactergegevens: '+escape(age(s.get('last_seen'),now))+
                 ' · '+str(len(ids))+' items in de zoeklijst</p>')
        items=[]
        for index,i in enumerate(ids,1):
            quote=lookup.get(str(i)) or opp.get(i) or {}
            game=scans.get(i)
            game_price=money(game['ask']) if game else 'Nog niet opgeslagen'
            game_age=age(game['at'],now) if game else ''
            source=money(quote.get('ask'))
            if not report.get('market_fresh'):
                source+=' (oude snapshot)'
            items.append('<tr>'+
                         cell(str(index),'num')+
                         cell(escape(quote.get('name') or f'Item {i}')+
                              ' <small class="sub">#'+str(i)+'</small>','name')+
                         cell(escape(source),'num')+
                         cell(escape(game_price)+
                              ('<small class="sub">'+escape(game_age)+'</small>' if game else ''),'num')+
                         cell(value(quote.get('vol24')),'num')+'</tr>')
        head='<thead><tr><th>#</th><th>Wordt opgezocht</th><th>TK vraagprijs / stuk</th><th>AH-prijs, laatste WoW-save</th><th>Volume 24u (geschat)</th></tr></thead>'
        blocks.append('<div class="character">'+title+summary+
                      ('<div class="tablewrap"><table>'+head+'<tbody>'+''.join(items)+'</tbody></table></div>'
                       if items else '<p>Geen zoekitems vanuit de VPS. Controleer de marktstatus.</p>')+
                      '</div>')
    return ''.join(blocks) or '<p>Er zijn nog geen characters gesynchroniseerd.</p>'


def scan_section(activity,report,now):
    lookups=report.get('lookup') or {}
    names={int(c['id']):c.get('name') for c in report.get('opportunities',[]) if 'id' in c}
    for id,quote in lookups.items():
        if id.isdigit():names[int(id)]=quote.get('name') or names.get(int(id))
    notice='<p class="hint">'+escape(activity.get('notice') or 'Geen gamegegevens')+'</p>'
    last=activity.get('last_search')
    recent=('<p>Laatste opgeslagen opdracht: <b>'+escape(names.get(last['id']) or f'Item {last["id"]}')+
            '</b> · teller '+str(last['count'])+' · '+escape(age(last['at'],now))+'</p>') if last else ''
    rows=[]
    for event in (activity.get('events') or [])[:60]:
        id=event['id']
        result=event['kind']=='Resultaat'
        rows.append('<tr>'+
                    cell(escape(stamp(event['at'])))+
                    cell(escape(event['kind']))+
                    cell(escape(names.get(id) or f'Item {id}')+
                         ' <small class="sub">#'+str(id)+'</small>','name')+
                    cell(escape(money(event['price'])) if result else '—','num')+
                    cell(value(event.get('price_rows')) if result else '—','num')+'</tr>')
    if not rows:
        for data in (activity.get('observations') or [])[:20]:
            id=data['id']
            rows.append('<tr>'+cell(escape(stamp(data['at'])))+
                        cell('AH-prijs opgeslagen')+
                        cell(escape(names.get(id) or f'Item {id}')+' <small class="sub">#'+str(id)+'</small>','name')+
                        cell(escape(money(data['ask'])),'num')+
                        cell(str(data['price_rows']),'num')+'</tr>')
    table=('<div class="tablewrap"><table><thead><tr><th>Tijd</th><th>Gebeurtenis</th>'
           '<th>Item</th><th>Laagste AH-prijs / stuk</th><th>Prijsregels</th></tr></thead>'
           '<tbody>'+''.join(rows)+'</tbody></table></div>' if rows else
           '<p>Er is nog geen zoekgeschiedenis opgeslagen. In WoW: /ft auto status.</p>')
    return notice+recent+table


CSS = """
:root{color-scheme:dark;--bg:#0a1019;--surface:#111c2c;--edge:#263548;--muted:#a3b0c4;--white:#edf3fd;--green:#52c5a8;--amber:#e7b978;--red:#f09288}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--white);font:14px/1.55 system-ui,-apple-system,'Segoe UI',sans-serif}
main{max-width:1560px;margin:0 auto;padding:28px clamp(16px,3vw,42px) 65px}
h1{font-size:29px;letter-spacing:-.7px;margin:2px 0 6px}
h2{font-size:19px;margin:0 0 9px}h3{font-size:16px;margin:0 0 2px}h3 small{font-weight:400;font-size:12px}
p{margin:8px 0;color:var(--muted)}b,strong{color:var(--white)}
a{color:#9ccafb;text-decoration:none}a:hover{text-decoration:underline}
.top{display:flex;justify-content:space-between;align-items:flex-start;gap:20px;flex-wrap:wrap;padding-bottom:24px;border-bottom:1px solid var(--edge)}
.eyebrow{font-size:11px;font-weight:700;letter-spacing:2px;color:var(--green)}
.source{padding:8px 13px;border:1px solid var(--edge);border-radius:8px;color:var(--muted)}
.metrics{display:grid;grid-template-columns:repeat(auto-fit,minmax(195px,1fr));gap:12px;margin-top:22px}
.metric{padding:16px 18px;border:1px solid var(--edge);background:var(--surface);border-radius:11px}
.metric small{display:block;color:var(--muted);font-size:12px}
.metric strong{font-size:21px;display:block;margin:2px 0 1px}
.metric span{color:var(--muted);font-size:12px}
section{margin-top:18px;padding:21px;background:var(--surface);border:1px solid var(--edge);border-radius:12px}
.sectionhead{display:flex;align-items:flex-start;justify-content:space-between;flex-wrap:wrap;gap:10px}
.sectionhead p{margin:0 0 12px}
.warning{margin-top:16px;padding:13px 15px;border:1px solid #76583b;border-radius:8px;background:#231d16;color:#f4d4a6}
.warning.error{border-color:#733e43;background:#29181d;color:#ffb6b5}
.tablewrap{overflow:auto;max-width:100%}
table{width:100%;border-collapse:collapse;min-width:760px}
th{font-weight:600;font-size:11px;letter-spacing:.3px;text-transform:uppercase;color:#aebdd1;background:#172538;white-space:nowrap;text-align:left}
th,td{padding:10px 12px;border-bottom:1px solid #283748;vertical-align:top}
td{color:#d4e0ef}tr:hover td{background:#182537}
td.name{min-width:170px;font-weight:600}td.num{white-space:nowrap;font-variant-numeric:tabular-nums}
td.reason{min-width:260px;white-space:normal;color:#b8c6d8}
.sub{display:block;font-weight:400;color:#8e9bb0;font-size:11px;white-space:normal}
.state{display:inline-block;white-space:nowrap;border-radius:4px;padding:3px 7px;color:#afc5da;background:#1e2e42;font-size:11px}
.state.interesting{color:#93e7ce;background:#15342d}.state.stale{color:#f4b3b3;background:#392127}
.filters{display:flex;gap:8px;flex-wrap:wrap;align-items:center;margin:8px 0 17px}
input,select,button{background:#0a1421;color:var(--white);border:1px solid #40536a;border-radius:7px;font:inherit;padding:9px 10px}
input{min-width:190px;flex:1;max-width:320px}
button{border-color:#57ad97;background:#19483d;cursor:pointer;font-weight:600}
button:hover{background:#216456}
.hint{font-size:12px;color:#b9c6d8}
.character{border-top:1px solid var(--edge);padding-top:13px;margin-top:12px}
.character:first-of-type{border-top:0}
footer{padding-top:20px;color:#8e9bb0;font-size:12px}
@media(max-width:720px){main{padding:16px}h1{font-size:23px}section{padding:15px}}
"""


def render(strategies,refreshed,research=None,activity=None,filters=None):
    research=research or {}
    activity=activity or {}
    filters=filters or {}
    source_at=research.get('snapshot_at')
    fresh=research.get('market_fresh') is True
    opp=list(research.get('opportunities') or [])
    interesting=research.get('interesting_count',0)
    queue_items=sum(len(plan_item_ids(x.get('plan'))) for x in strategies)
    ages=age(source_at,refreshed)
    metrics=[
        ('Marktsnapshot',ages,stamp(source_at)),
        ('Items in marktsnapshot',value(research.get('market_items')), 'EU PvP Alliance'),
        ('Kansen met historie',str(interesting),'Onderzoeken, geen koopopdracht'),
        ('AH-zoeklijst',str(queue_items)+' items',str(len(strategies))+' characters'),
        ('Game-prijzen opgeslagen',str(activity.get('saved_prices',0)),
         age(activity.get('saved_at'),refreshed)),
    ]
    cards=''.join('<div class="metric"><small>'+escape(a)+'</small><strong>'+escape(b)+
                  '</strong><span>'+escape(c)+'</span></div>' for a,b,c in metrics)
    errors=[]
    if research.get('error'):
        errors.append('VPS-onderzoek niet beschikbaar: '+str(research['error']))
    elif not source_at:
        errors.append('Er zijn nog geen echte marktgegevens op de VPS opgeslagen.')
    elif not fresh:
        errors.append('De laatste AH-marktsnapshot is ouder dan 90 minuten. Geen actuele kansen claimen.')
    if research.get('last_error'):
        errors.append('Laatste marktimportfout: '+str(research['last_error'])[:180])
    warnings=''.join('<div class="warning'+(' error' if not fresh else '')+'">'+escape(e)+'</div>' for e in errors)
    term=str(filters.get('q',''))[:70]
    mode=filters.get('mode','all')
    sort=filters.get('sort','signal')
    select_mode=selectable('mode',mode,[('all','Alle signalen'),('interesting','Sterkere signalen'),('history','Minstens 3 dagen historie')])
    select_sort=selectable('sort',sort,[('signal','Bewijs eerst'),('discount','Grootste historische korting'),
                                      ('net','Grootste theoretische marge'),('volume','Meeste geschatte verkopen'),
                                      ('name','Naam A-Z')])
    filters_html=('<form class="filters" method="get" action="/">'
                  '<input name="q" type="search" maxlength="70" placeholder="Zoek itemnaam of ID" value="'+escape(term)+'">'
                  +select_mode+select_sort+'<button type="submit">Toon resultaten</button></form>')
    rows_count,rows=opportunity_rows(opp,refreshed,{'q':term,'mode':mode,'sort':sort})
    opp_html=('<div class="sectionhead"><div><h2>Marktkansen onderzoeken</h2>'
              '<p>VPS: uurlijkse vraagprijzen en historische marktdata. Dit is geen gegarandeerde verkoop of winst.</p></div>'
              '<small>'+str(rows_count)+' resultaten</small></div>'+
              filters_html+
              ('<div class="tablewrap"><table><thead><tr>'
               '<th>Beoordeling</th><th>Item</th><th>TK prijs</th><th>Historische mediaan</th>'
               '<th>Korting / historie</th><th>Gemelde verkoopprijs</th><th>Volume 24u</th>'
               '<th>Referentie-uitstap</th><th>Max koopindicatie*</th><th>Theoretisch verschil*</th><th>Waarom / risico</th>'
               '</tr></thead><tbody>'+rows+'</tbody></table></div>' if rows else
               '<p>Geen kandidaten met deze filters. Geen kansen verzinnen als de data onvoldoende zijn.</p>')+
              '<p class="hint">* Max koopindicatie rekent met 20% marge na 5% AH-cut, '
              'maar VOOR onbekende deposit, niet-verkochte voorraad en prijsbeweging. '
              'De verkoopreferentie is afgeleid uit marktdata, geen gegarandeerde transactie. '
              'Vendorprijzen gebruiken we niet.</p>')
    queue_html=('<div class="sectionhead"><div><h2>Wat zoekt de addon precies?</h2>'
                '<p>De exacte per-character lijst die de VPS in WoW klaarzet, in zoekvolgorde.</p></div></div>'+
                queue_sections(strategies,research,activity,refreshed))
    scans_html=('<div class="sectionhead"><div><h2>AH-zoeklog en gemeten prijzen</h2>'
                '<p>Vanuit jouw WoW SavedVariables, niet uit de publieke marktbron.</p></div></div>'+
                scan_section(activity,research,refreshed))
    details=('<p class="hint">Vernieuwt iedere 30 seconden vanuit de VPS. '
             'De bron zelf publiceert ongeveer één keer per uur. '
             'WoW schrijft zoeklogs alleen bij /reload of uitloggen naar schijf. '
             'Tijdens het spelen zie je realtime voortgang met <b>/ft auto status</b>.</p>')
    return ('<!doctype html><html lang="nl"><head><meta charset="utf-8">'
            '<meta name="viewport" content="width=device-width,initial-scale=1">'
            '<title>ForeverTrader · Market Desk</title><style>'+CSS+'</style></head><body>'
            '<main><div class="top"><div><div class="eyebrow">FOREVERTRADER / V4</div>'
            '<h1>Market Desk</h1><p>EU PvP Alliance · echte bronnen, controleerbare kansen, zicht op AH-zoekactiviteit</p></div>'
            '<div class="source">Bron: <a href="https://auctionhouse.tk.gg/data/" target="_blank" '
            'rel="noopener noreferrer">TK Auction House</a> · '+escape(stamp(source_at))+'</div></div>'
            '<div class="metrics">'+cards+'</div>'+warnings+
            '<section>'+opp_html+'</section>'+
            '<section>'+queue_html+'</section>'+
            '<section>'+scans_html+'</section>'+
            '<section><h2>Zo lees je de gegevens</h2>'+details+
            '<p>TK geeft vraagprijzen, historische vraagprijzen en deels afgeleid verkoopvolume. '
            'Gameprijzen komen uit de addon en kunnen alweer verouderd zijn. '
            'Er is geen automatisch kopen/verkopen en geen bewezen winst tot een echte verkoop is vastgelegd.</p>'
            '<p>Onderzoek verversen: '+escape(stamp(refreshed))+
            ' · Laatste VPS-marktverzoek: '+escape(stamp(research.get('last_attempt')))+'</p></section>'
            '<footer>ForeverTrader V4 · Alle bedragen in gold/silver/copper per item · '
            'Vraagprijs ≠ transactieprijs · Geen vendorflips zonder clientbevestiging.</footer></main></body></html>')


def write(path,strategies,clock):
    """Legacy offline snapshot, used by PREPARE-V4.bat for troubleshooting."""
    p=pathlib.Path(path)
    p.parent.mkdir(parents=True,exist_ok=True)
    data=render(strategies,clock)
    fd,tmp=tempfile.mkstemp(prefix='.v4-dashboard-',dir=str(p.parent))
    try:
        with os.fdopen(fd,'w',encoding='utf-8') as f:
            f.write(data)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp,p);tmp=None
    finally:
        if tmp:
            try:os.unlink(tmp)
            except OSError:pass
    return p
