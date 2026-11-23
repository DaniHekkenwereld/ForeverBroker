"""Explain empirical intraday buys/sells without false exact-hour prediction."""
import html


def e(x):return html.escape(str(x if x is not None else '—'),quote=True)


def gold(v):
    if type(v) is not int:return '—'
    g,r=divmod(v,10000)
    s,c=divmod(r,100)
    return f'{g:,}g {s:02d}s {c:02d}c'


def render(report):
    d=report or {}
    rows=[]
    for p in d.get('patterns') or []:
        buy=f'{p["buy_window"]} {p["buy_start"]:02d}:00–{p["buy_end"]:02d}:00'
        sell=f'{p["sell_window"]} {p["sell_start"]:02d}:00–{p["sell_end"]:02d}:00'
        rows.append('<tr>'+
                    '<td><span class="state '+('interesting' if p['phase']=='BUY_WINDOW' else '')+
                    '">'+e(p['status'])+'</span></td>'+
                    '<td class="name">'+e(p['name'])+'<small class="sub">#'+str(p['id'])+'</small></td>'+
                    '<td>'+e(buy)+'</td><td>'+e(sell)+'</td>'+
                    '<td class="num">'+e(gold(p.get('ask')))+'</td>'+
                    '<td class="num">'+e(gold(p['max_buy_before_deposit']))+'</td>'+
                    '<td class="num">'+e(gold(p['target_ask_scenario']))+'</td>'+
                    '<td class="num">'+str(p['paired_days'])+' dagen<small class="sub">'+
                    str(p['win_rate'])+'% gemeten winstgevende dagen</small></td>'+
                    '<td class="num">'+str(p['conservative_net_roi_pct'])+'%<small class="sub">excl. deposit</small></td></tr>')
    if rows:
        table='<div class="tablewrap"><table><thead><tr>'+
              ''.join('<th>'+x+'</th>' for x in ('Actie vandaag','Item','Instapvenster',
                      'Uitstapvenster','TK vraagprijs','Max instap*',
                      'Verkoopscenario*','Onderzochte dagen','25e percentiel ROI*'))+
              '</tr></thead><tbody>'+''.join(rows)+'</tbody></table></div>'
    else:
        table=('<p>Er is nog geen herhaald dagpatroon dat aan de minimumvoorwaarden voldoet. '
               'We geven dus geen verzonnen advies zoals “8:00 kopen, 18:00 verkopen”.</p>')
    return ('<div class="sectionhead"><div><h2>Daghandel: ochtend kopen, avond verkopen?</h2>'
            '<p>Analyseert herhaalde lokale prijsvensters met voldoende complete handelsdagen.</p></div>'+
            '<small>'+str(len(d.get('patterns') or []))+' patronen · '+e(d.get('timezone'))+
            '</small></div>'+
            '<p class="hint">Onderzochte items: '+e(d.get('tested_items'))+
            ' · onvoldoende historie: '+e(d.get('missing_history_count'))+
            ' · minimaal '+e(d.get('min_completed_days'))+
            ' volledig gemeten dagen met 16 uurlijkse metingen. '
            'Tijdvakken zijn breed, niet exact 08:00 of 18:00.</p>'+
            table+
            '<p class="hint">* Berekeningen gebruiken publieke vraagprijzen en 5% AH-cut. '
            'Niet bevestigd dat de prijs daadwerkelijk verhandelbaar was, '
            'en niet inclusief listing-deposits, niet-verkochte veilingen '
            'of hoeveelheid. Koop/verkoop blijft je eigen handeling.</p>')
