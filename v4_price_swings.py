"""Whole-market 24-hour ask-price swing radar.

Uses the 24 hourly ASK slots already present in the public market overview.
No extra provider requests, no five-day recurring-pattern requirement, and
NO claim that observed asks were successful trades. A dip is a review lead.
"""
import html
import math
import statistics

MIN_OBSERVATIONS=8
MIN_ABSOLUTE_SWING=10000  # 1g difference per item
MIN_RELATIVE_SWING_PCT=20
MAX_RESULTS=100


def positive(x):
    return type(x) is int and 0<x<=100_000_000_000


def analyze(market,snapshot_at,clock,limit=MAX_RESULTS):
    """Flag both currently cheap outliers and earlier dips that recovered."""
    fresh=(type(snapshot_at) is int and 0<=clock-snapshot_at<=5400)
    candidates=[]
    count=0
    for raw_id,row in market.items():
        if type(raw_id) is not int or not 0<raw_id<=10000000 or not isinstance(row,dict):
            continue
        ask=row.get('ask')
        history=row.get('history')
        if not positive(ask) or not isinstance(history,list) or not 8<=len(history)<=48:
            continue
        prices=[p for p in history if positive(p)]
        if len(prices)<MIN_OBSERVATIONS:continue
        low=min(prices)
        high=max(prices)
        spread=high-low
        swing_pct=round((high/low-1)*100,1)
        if spread<MIN_ABSOLUTE_SWING or swing_pct<MIN_RELATIVE_SWING_PCT:
            continue
        # A single very cheap listing may temporarily change the floor; only
        # describe the *observed* ask range and never assume exit liquidity.
        baseline=int(statistics.median(prices))
        if ask<=baseline*0.85 and baseline-ask>=MIN_ABSOLUTE_SWING:
            state='DIP — IN GAME CONTROLEREN'
            priority=0
        elif ask>=low*1.2 and ask-low>=MIN_ABSOLUTE_SWING:
            state='DIP VOORBIJ — PRIJS HERSTELD'
            priority=1
        else:
            state='STERKE SCHOMMELING'
            priority=2
        # Measured high is another ASK, not a sale. This is NOT a profit.
        theoretical_net=high-math.ceil(high*.05)-low
        candidates.append({
            'id':raw_id,'name':str(row.get('name') or f'Item {raw_id}'),
            'current_ask':ask,'low_24h':low,'high_24h':high,
            'median_24h':baseline,'spread_copper':spread,
            'swing_pct':swing_pct,'status':state,'priority':priority,
            'volume_24h':row.get('vol24') if type(row.get('vol24')) is int else None,
            'sample_count':len(prices),'snapshot_at':snapshot_at,
            'source':'Publieke uurlijkse AH-vraagprijzen, geen verkoopbewijzen',
            'illustrative_net_after_cut':max(0,theoretical_net),
        })
        count+=1
    # Favor active dips, then material gold swings. Excessively thin markets
    # remain visible but are explicitly NOT buy recommendations.
    candidates.sort(key=lambda r:(r['priority'],
                      -min(r['spread_copper'],1_000_000),
                      -min(r['swing_pct'],100),r['id']))
    cap=max(0,min(int(limit),MAX_RESULTS)) if type(limit) is int else MAX_RESULTS
    return {'swings':candidates[:cap],'total_swings':count,
            'active_dips':sum(r['priority']==0 for r in candidates),
            'recovered_dips':sum(r['priority']==1 for r in candidates),
            'market_fresh':fresh,'snapshot_at':snapshot_at,
            'method':'Minimaal 8 gemeten uurlijkse vraagprijzen, 20% en 1g '
                     'verschil binnen 24 uur. Signaleert dips, niet bewezen '
                     'verkopen of voorspelbare ochtend/avondhandel.'}


def display_gold(copper):
    if not positive(copper) and copper!=0:return '—'
    g,rem=divmod(copper,10000)
    s,c=divmod(rem,100)
    return f'{g:,}g {s:02d}s {c:02d}c'


def render_details(report):
    """Optional, collapsed dashboard table of observed swings."""
    swings=(report or {}).get('swings') or []
    if not swings:
        return '<p>Geen grote schommelingen gevonden in de huidige 24-uurs meetreeks.</p>'
    rows=[]
    for row in swings:
        id=row['id']
        name=html.escape(str(row['name']),quote=True)
        label=html.escape(str(row['status']),quote=True)
        link='<a href="https://auctionhouse.tk.gg/m/eu-2-110/'+str(id)+
             '" target="_blank" rel="noopener noreferrer">'+name+'</a>'
        rows.append('<tr><td class="name">'+link+
                    '<small class="sub">#'+str(id)+'</small></td>'+
                    '<td><span class="state">'+label+'</span></td>'+
                    '<td class="num">'+display_gold(row['current_ask'])+'</td>'+
                    '<td class="num">'+display_gold(row['low_24h'])+'</td>'+
                    '<td class="num">'+display_gold(row['high_24h'])+'</td>'+
                    '<td class="num">'+display_gold(row['spread_copper'])+'</td>'+
                    '<td class="num">'+str(row['swing_pct'])+'%</td>'+
                    '<td class="num">'+str(row['sample_count'])+' metingen</td></tr>')
    return ('<p class="hint">Alleen uurlijkse AH-vraagprijzen; koopmoment en '
            'verkoop zijn niet bewezen. Groot prijsverschil betekent niet '
            'dat er een koper was. Controleer de listing altijd in WoW.</p>'+
            '<div class="tablewrap"><table><thead><tr>'+
            '<th>Item</th><th>Signalering</th><th>Nu (publiek)</th>'+
            '<th>Laagste 24u</th><th>Hoogste 24u</th><th>Verschil</th>'+
            '<th>Schommeling</th><th>Dekking</th></tr></thead><tbody>'+
            ''.join(rows)+'</tbody></table></div>')
