"""ForeverTrader V4 market desk: safe HTML from actual VPS and saved game data.

No automatic purchases, no fake vendor profits. Every number has a timestamp
and a provenance label. The dashboard never reads game memory or writes WoW.
"""
import datetime as dt
import html
import os
import pathlib
import tempfile
import v4_investing_ui
import v4_portfolio_ui
import v4_daily_ui
import v4_quickview
import v4_price_swings


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


def opportunity_rows(candidates,now,filters,budget=None):
    mode=filters.get('mode','all')
    sorting=filters.get('sort','signal')
    term=filters.get('q','').strip().lower()[:70]
    if mode=='interesting':
        candidates=[c for c in candidates if c.get('status')=='INTERESSANT — VERIFIËREN']
    elif mode=='history':
        candidates=[c for c in candidates if (c.get('history_days') or 0)>=3]
    elif mode=='budget':
        candidates=[c for c in candidates if type(budget) is int and
                    type(c.get('ask')) is int and c['ask']<=budget]
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
           '<p>Nog geen opgeslagen gameprijsmetingen. De addon begint automatisch bij AH-openen; de bridge uploadt bij de volgende WoW-save.</p>')
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
/* Immediate visual hierarchy: icons are always accompanied by text. */
.brand-spark{color:var(--green)}
.action-center{margin-top:22px;padding:24px;background:linear-gradient(135deg,#142338,#0d1927 72%);border:1px solid #395169;border-radius:16px}
.focus-heading{display:flex;justify-content:space-between;gap:20px;align-items:start;flex-wrap:wrap}
.focus-heading h2{font-size:25px;letter-spacing:-.4px;margin:4px 0 0}
.focus-heading>div:first-child{max-width:770px}
.focus-headline{font-size:16px;font-weight:700!important;color:#e9f4ff!important;margin:8px 0 3px}
.focus-headline.good{color:#a1efd9!important}
.focus-headline.warn{color:#ffd392!important}
.focus-status{display:flex;gap:8px;justify-content:flex-end;align-items:center;flex-wrap:wrap;max-width:400px;font-size:12px;color:var(--muted)}
.action-pill{font-size:11px;font-weight:700;letter-spacing:.1px;border:1px solid #324a5c;padding:4px 8px;border-radius:50px;background:#1d2b3c;color:#bdd4ea;display:inline-flex;align-items:center;white-space:nowrap}
.action-pill.good{color:#9ae7cd;background:#18372f;border-color:#306753}
.action-pill.warn{color:#f6cc89;background:#3b2f21;border-color:#685132}
.action-pill.neutral{color:#c3d4e9;background:#243347}
.focus-metrics{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:11px;margin:18px 0}
.focus-metric{padding:13px;border:1px solid #31485e;background:#152337;border-radius:10px;display:flex;gap:11px;min-width:0}
.focus-icon{flex:0 0 33px;height:33px;width:33px;display:grid;place-items:center;font-size:19px;border-radius:8px;background:#243448}
.focus-metric>div{min-width:0}
.focus-label{display:block;color:#b8cde2;font-size:11px;line-height:1.3}
.focus-metric strong{display:block;font-size:19px;font-weight:750;white-space:nowrap;font-variant-numeric:tabular-nums}
.focus-metric small{display:block;color:#93a9c0;font-size:10px;line-height:1.5}
.action-grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:13px}
.action-card{display:flex;flex-direction:column;min-width:0;background:#111e30;border:1px solid #354a61;border-radius:12px;padding:16px}
.action-card.good{border-top:3px solid #58bb9c}
.action-card.warn{border-top:3px solid #dfb36d}
.action-card.neutral{border-top:3px solid #8194aa}
.action-card-head{display:flex;justify-content:space-between;align-items:center;gap:8px}
.action-card-head>div{display:flex;align-items:center;gap:9px}
.action-card h3{margin:0;font-size:16px}
.action-icon{width:34px;height:34px;border-radius:9px;display:grid;place-items:center;background:#24374c;font-size:19px}
.action-count{font-size:21px;font-weight:800;font-variant-numeric:tabular-nums}
.action-card-body{margin-top:11px;flex:1;min-width:0}
.swing-highlights{margin-bottom:16px;padding:14px 17px;border-radius:11px;border:1px solid #6c5639;background:#241e1c}
.swing-title{display:flex;gap:12px;align-items:center;justify-content:space-between;flex-wrap:wrap}
.swing-title h3{font-size:15px}
.swing-title small{color:#d8b886}
.swing-highlights>.hint{margin:4px 0 7px}
.swing-highlights>.focus-row{padding:9px 0}
.swing-highlights>a{display:inline-block;margin-top:9px;font-size:12px;font-weight:700}
.focus-row{padding:10px 0;border-top:1px solid #26364a}
.focus-row:first-child{border-top:0}
.focus-item{display:flex;gap:8px;align-items:center;flex-wrap:wrap;font-weight:650}
.focus-item a{font-weight:700}
.focus-row p{margin:5px 0 0;font-size:12px;color:#d5e1ed}
.focus-small{font-size:11px;color:#9eb2c7;display:block;margin-top:3px}
.empty-state{color:#adbfd2;min-height:52px}
.action-foot{padding-top:9px;margin:12px 0 0;font-size:11px;color:#95a9be;border-top:1px solid #25374a}
.focus-bottom{display:flex;align-items:center;justify-content:space-between;gap:12px;flex-wrap:wrap;font-size:12px;color:#b8cce0;margin-top:18px;border-top:1px solid #31455b;padding-top:13px}
.focus-bottom a{font-weight:650}
.details-heading{padding:18px 2px 9px;margin-top:30px}
.details-heading h2{font-size:22px;margin:3px 0 0}
.details-heading p{margin:2px 0 0}
.detail-group{margin:10px 0;background:#111c2c;border:1px solid #2b4055;border-radius:11px;overflow:hidden}
.detail-group summary{list-style:none;display:flex;align-items:center;gap:10px;padding:15px 20px;cursor:pointer;user-select:none;min-height:65px}
.detail-group summary::-webkit-details-marker{display:none}
.detail-group summary:hover,.detail-group[open] summary{background:#1b2c3f}
.detail-group summary:focus-visible{outline:2px solid #91d0fc;outline-offset:-2px}
.detail-heading{font-weight:700;font-size:15px;flex:1}
.detail-preview{font-size:12px;color:#a8bed5}
.detail-chevron{font-size:22px;color:#a9c4df;transition:transform .15s}
.detail-group[open] .detail-chevron{transform:rotate(180deg)}
.detail-content{padding:18px 20px 22px;border-top:1px solid #2b4055}
.detail-content .sectionhead h2{font-size:18px}
.detail-content .metrics{margin-top:0}
@media(max-width:1050px){.focus-metrics{grid-template-columns:repeat(2,minmax(0,1fr))}}
@media(max-width:720px){
 main{padding:14px}h1{font-size:24px}section{padding:15px}
 .action-center{padding:16px}.focus-heading h2{font-size:22px}
 .focus-metrics,.action-grid{grid-template-columns:1fr}
 .focus-metric strong{font-size:18px}
 .detail-group summary{padding:13px;align-items:flex-start;flex-wrap:wrap}
 .detail-preview{width:calc(100% - 32px)}.detail-content{padding:12px}
}
@media(prefers-reduced-motion:reduce){.detail-chevron{transition:none}}
"""


def detail_group(id,title,preview,contents):
    """Keep dense reference tables accessible, but out of the first viewport."""
    return ('<details class="detail-group" id="'+escape(id)+'">'
            '<summary><span class="detail-heading">'+escape(title)+'</span>'
            '<span class="detail-preview">'+escape(preview)+'</span>'
            '<span class="detail-chevron" aria-hidden="true">⌄</span></summary>'
            '<div class="detail-content">'+contents+'</div></details>')


def render(strategies,refreshed,research=None,activity=None,filters=None):
    research=research or {}
    activity=activity or {}
    filters=filters or {}
    source_at=research.get('snapshot_at')
    fresh=research.get('market_fresh') is True
    opp=list(research.get('opportunities') or [])
    interesting=research.get('interesting_count',0)
    queue_items=sum(len(plan_item_ids(x.get('plan'))) for x in strategies)
    budget=research.get('budget_copper')
    if type(budget) is not int:budget=None
    ages=age(source_at,refreshed)
    metrics=[
        ('Marktsnapshot',ages,stamp(source_at)),
        ('Items in marktsnapshot',value(research.get('market_items')), 'EU PvP Alliance'),
        ('Investeringssignalen',str(research.get('shortlist_count',0)),'Korte en lange termijn'),
        ('Stijgende items',str(research.get('rising_count',0)),'Binnen onderzochte artikelen'),
        ('Dalende items',str(research.get('falling_count',0)),'Binnen onderzochte artikelen'),
        ('7d goederenmandje',v4_investing_ui.change(research.get('basket_change_7d_pct')) if fresh else 'Verouderd',
         str(research.get('basket_item_count',0))+' liquide goederen; geen algemene goldinflatie'),
        ('AH-zoeklijst',str(queue_items)+' items',str(len(strategies))+' characters'),
        ('Indicatieve per-item limiet '+str(research.get('budget_character') or ''),money(budget),
         '20% van bekende gold, geen automatisch investeringsbudget'),
        ('Game-prijzen op VPS',str(len(research.get('game_checks') or [])),
         'Uit WoW opgeslagen via de Windows-bridge'),
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
    focus=filters.get('focus','all')
    sort=filters.get('sort','signal')
    select_focus=selectable('focus',focus,[('all','Alle investeringen'),('short','Korte termijn'),
            ('long','Lange termijn'),('rising','Prijs stijgt'),('falling','Prijs daalt'),
            ('dips','Koopdips'),('budget','Binnen limiet')])
    select_mode=selectable('mode',mode,[('all','Alle signalen'),('budget','Binnen mijn zoekbudget'),
                                      ('interesting','Sterkere signalen'),('history','Minstens 3 dagen historie')])
    select_sort=selectable('sort',sort,[('signal','Bewijs eerst'),('discount','Grootste historische korting'),
                                      ('net','Grootste theoretische marge'),('volume','Meeste geschatte verkopen'),
                                      ('name','Naam A-Z'),('momentum24','Sterkste stijging 24u'),
                                      ('momentum7','Sterkste stijging 7d')])
    filters_html=('<form class="filters" method="get" action="/">'
                  '<input name="q" type="search" maxlength="70" placeholder="Zoek itemnaam of ID" value="'+escape(term)+'">'
                  +select_focus+select_mode+select_sort+'<button type="submit">Toon resultaten</button></form>')
    rows_count,rows=opportunity_rows(opp,refreshed,{'q':term,'mode':mode,'sort':sort},budget)
    portfolio_html=v4_portfolio_ui.render(research.get('portfolio'),refreshed,filters)
    daily_html=v4_daily_ui.render(research.get('intraday'))
    invest_html=filters_html+v4_investing_ui.render(research,refreshed,
                      {'q':term,'focus':focus,'sort':sort},budget)
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
             'WoW schrijft zoeklogs bij /reload of uitloggen. De bridge slaat ze dan automatisch op de VPS op. '
             'Tijdens het spelen controleert de addon vanzelf zodra het AH opent.</p>')
    portfolio=research.get('portfolio') or {}
    panels=[
        detail_group('portfolio','📦 Portfolio, characters en transacties',
            str(len(portfolio.get('characters') or []))+' characters · '+
            str(portfolio.get('holding_types') or 0)+' itemsoorten · '+
            str(portfolio.get('trade_count') or 0)+' transacties',portfolio_html),
        detail_group('prijsbewegingen','⚡ Grote prijsbewegingen (24 uur)',
            str((research.get('price_swings') or {}).get('total_swings') or 0)+
            ' prijsafwijkingen · geen bewezen transacties',
            v4_price_swings.render_details(research.get('price_swings'))),
        detail_group('daghandel','🕘 Daghandel',
            str(len((research.get('intraday') or {}).get('patterns') or []))+
            ' onderbouwde patronen',daily_html),
        detail_group('investeringen','📈 Investeringen en trends',
            str(research.get('shortlist_count') or 0)+' signalen · '+
            str(research.get('rising_count') or 0)+' stijgers',invest_html),
        detail_group('markt','🔍 Alle marktkansen',
            str(rows_count)+' items voor verder onderzoek',opp_html),
        detail_group('zoeklijst','📋 AH-zoeklijst per character',
            str(queue_items)+' geplande controles',queue_html),
        detail_group('scans','🧪 AH-controles en diagnose',
            str(len(activity.get('events') or []))+' lokaal bewaarde zoekevents',scans_html),
        detail_group('statistieken','📊 Alle marktstatistieken en uitleg',
            'Bronnen, meettijd en onderliggende dekking',
            '<div class="metrics">'+cards+'</div>'+details+
            '<p>TK geeft vraagprijzen, historische vraagprijzen en deels afgeleid '
            'verkoopvolume. Gameprijzen komen uit de addon en kunnen alweer verouderd zijn. '
            'Er is geen automatisch kopen/verkopen en geen bewezen winst tot een echte verkoop.</p>'
            '<p>Onderzoek ververst: '+escape(stamp(refreshed))+
            ' · Laatste VPS-marktverzoek: '+escape(stamp(research.get('last_attempt')))+'</p>'),
    ]
    return ('<!doctype html><html lang="nl"><head><meta charset="utf-8">'
            '<meta name="viewport" content="width=device-width,initial-scale=1">'
            '<title>ForeverTrader · Market Desk</title><style>'+CSS+'</style></head><body>'
            '<main><div class="top"><div><div class="eyebrow">FOREVERTRADER / 1.0 BETA</div>'
            '<h1>Market Desk <span class="brand-spark" aria-hidden="true">↗</span></h1>'
            '<p>EU PvP Alliance · Slimme kansen, eigen gold en voorraad</p></div>'
            '<div class="source">Bron: <a href="https://auctionhouse.tk.gg/data/" target="_blank" '
            'rel="noopener noreferrer">TK Auction House</a> · '+escape(stamp(source_at))+
            '</div></div>'+
            v4_quickview.render(research,refreshed)+warnings+
            '<div class="details-heading" id="details"><div class="eyebrow">VERDIEPING</div>'
            '<h2>Onderliggende gegevens</h2><p>Alle lange lijsten staan hieronder '
            'uitgeklapt wanneer je ze nodig hebt. Het overzicht hierboven blijft leidend.</p></div>'+
            ''.join(panels)+
            '<footer>ForeverTrader 1.0 Beta · Alle bedragen per item in gold/silver/copper · '
            'Vraagprijs ≠ transactieprijs · Geen automatisch kopen of verkopen.</footer>'
            '</main></body></html>')


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
