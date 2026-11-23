"""HTML for investment trends. Pure renderer; never assume a quoted ask was a sale."""
import html


def e(value):
    return html.escape(str(value if value is not None else '—'),quote=True)


def gold(value):
    if type(value) is not int:return '—'
    sign='-' if value<0 else ''
    g,s=divmod(abs(value),10000)
    sil,c=divmod(s,100)
    return f'{sign}{g:,}g {sil:02d}s {c:02d}c'


def change(value):
    if type(value) not in (float,int):return '—'
    return ('+' if value>0 else '')+f'{value:.1f}%'


def render(report, now, filters=None, budget=None):
    filters=filters or {}
    entries=list(report.get('investments') or [])
    focus=filters.get('focus','all')
    term=filters.get('q','').strip().lower()[:70]
    sort=filters.get('sort','signal')
    if term:
        entries=[x for x in entries if term in str(x.get('name','')).lower()
                 or term in str(x.get('id'))]
    if focus=='short':
        entries=[x for x in entries if str(x.get('signal','')).startswith('KORT')]
    elif focus=='long':
        entries=[x for x in entries if str(x.get('signal','')).startswith('LANG')]
    elif focus=='rising':
        entries=[x for x in entries if x.get('trend') in ('STIJGT','STIJGT SNEL')]
    elif focus=='falling':
        entries=[x for x in entries if x.get('trend') in ('DAALT','DAALT SNEL')]
    elif focus=='dips':
        entries=[x for x in entries if type(x.get('discount_vs_7d_pct')) in (float,int)
                 and x['discount_vs_7d_pct']<=-15]
    elif focus=='budget':
        entries=[x for x in entries if type(budget) is int
                 and type(x.get('ask')) is int and x['ask']<=budget]
    if sort=='discount':
        entries.sort(key=lambda x:(x.get('discount_vs_7d_pct') is None,
                                   x.get('discount_vs_7d_pct') or 0))
    elif sort=='net':
        entries.sort(key=lambda x:-(x.get('scenario_margin_before_deposit') or 0))
    elif sort=='volume':
        entries.sort(key=lambda x:-(x.get('volume_24h') or 0))
    elif sort=='name':
        entries.sort(key=lambda x:str(x.get('name','')).lower())
    elif sort=='momentum24':
        entries.sort(key=lambda x:(x.get('change_24h_pct') is None,
                                   -(x.get('change_24h_pct') or 0)))
    elif sort=='momentum7':
        entries.sort(key=lambda x:(x.get('change_7d_pct') is None,
                                   -(x.get('change_7d_pct') or 0)))
    rows=[]
    for x in entries[:100]:
        signal=str(x.get('signal') or 'ONBEKEND')
        css='interesting' if signal.startswith(('KORT','LANG')) else (
            'stale' if signal in ('VEROUDERD','DALING — AFWACHTEN') else '')
        link='https://auctionhouse.tk.gg/m/eu-2-110/'+str(x['id'])
        title='<a href="'+e(link)+'" target="_blank" rel="noopener noreferrer">'+e(x.get('name'))+'</a>'
        title+='<small class="sub">#'+e(x.get('id'))+' · '+e(x.get('category'))+'</small>'
        history='<small class="sub">'+e(x.get('history_days_7d'))+' dagen / '+e(x.get('history_points_7d'))+' metingen</small>'
        volume=e(x.get('volume_24h'))+' geschat'
        if x.get('confirmed_24h') is not None:
            volume+=' · '+e(x.get('confirmed_24h'))+' bronbevestigd'
        warning=e(x.get('warning'))
        if x.get('variant_risk'):
            warning+=' · <strong>exacte variant checken</strong>'
        columns=[
            '<span class="state '+css+'">'+e(signal)+'</span><small class="sub">'+e(x.get('horizon') or 'Geen koopadvies')+'</small>',
            title, e(gold(x.get('ask'))),e(change(x.get('change_24h_pct'))),
            e(change(x.get('change_7d_pct'))),
            e(gold(x.get('price_7d')))+history,
            e(change(x.get('discount_vs_7d_pct'))),
            volume+'<small class="sub">'+e(x.get('sale_evidence'))+'</small>',
            e(gold(x.get('exit_scenario'))),
            e(gold(x.get('max_buy_before_deposit'))),
            e(gold(x.get('scenario_margin_before_deposit')))+
             '<small class="sub">'+e(change(x.get('scenario_roi_before_deposit')))+'</small>',
            warning,
        ]
        rows.append('<tr>'+''.join('<td class="'+('reason' if k==11 else 'name' if k==1 else 'num')+
                    '">'+v+'</td>' for k,v in enumerate(columns))+'</tr>')
    headings=['Signaal / termijn','Item','AH vraagprijs','Trend 24u','Trend 7d',
              'Mediaan 7d','Afwijking','Volume 24u','Verkoopscenario*',
              'Max inkoop*','Scenario verschil*','Waarom / risico']
    table=('<div class="tablewrap"><table><thead><tr>'+
           ''.join('<th>'+e(x)+'</th>' for x in headings)+
           '</tr></thead><tbody>'+''.join(rows)+'</tbody></table></div>' if rows else
           '<p>Geen onderbouwde kandidaten met deze filters. We verzinnen geen koersdoelen.</p>')
    return ('<div class="sectionhead"><div><h2>Investeren: korte en lange termijn</h2>'+
            '<p>Prijsstijging, daling, historisch instapmoment en verkoopbaarheid.</p></div>'+
            '<small>'+str(len(entries))+' resultaten · '+
            e(report.get('analyzed_count',0))+' onderzocht</small></div>'+
            table+
            '<p class="hint">24u en 7d vergelijken mediane publieke VRAAGPRIJZEN. '
            'Dit zijn geen daadwerkelijk behaalde verkoopprijzen. '
            '* Verkoopscenario = 95% van de 7d mediaan; geen voorspelling. '
            'Max inkoop vergt 20% theoretische marge na AH-cut, '
            'EXCLUSIEF deposit, niet-verkochte voorraad en prijsrisico. '
            'Geen externe vendorwaardes gebruikt.</p>')
