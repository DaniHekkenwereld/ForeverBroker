"""Discover repeated Amsterdam-local intraday buy/sell windows without overfit.

Uses the existing daily.analyse paired complete-day model. It requires at
least five independent complete days, 16 hourly observations/day, paired
buy/sell hours and positive net edge before listing deposits.
"""
import datetime as dt
from zoneinfo import ZoneInfo

import daily


def build(db,market,asof,clock,cfg,investments=None,held_ids=None):
    investments=investments or []
    held_ids=held_ids or []
    zone=ZoneInfo(cfg.get('timezone','Europe/Amsterdam'))
    local=dt.datetime.fromtimestamp(clock,dt.timezone.utc).astimezone(zone)
    candidates=[]
    # Liquid consumables first, then any owned/monitored item with enough data.
    liquids=sorted((i for i,x in market.items() if isinstance(x,dict)
                    and x.get('cls') in ('Trade Goods','Consumable','Consumables')
                    and type(x.get('vol24')) is int and x['vol24']>=10
                    and type(x.get('ask')) is int and x['ask']>0),
                   key=lambda i:(-market[i]['vol24'],i))
    candidates=list(dict.fromkeys(
        [int(i) for i in held_ids if int(i) in market]+
        [int(i) for i in cfg.get('watchlist',[]) if int(i) in market]+
        [i['id'] for i in investments[:70] if i['id'] in market]+
        liquids[:100]))[:160]
    matched=[]
    incomplete=0
    for i in candidates:
        plan=daily.analyse(db,i,asof,cfg)
        if plan is None:
            incomplete+=1
            continue
        if not plan.get('eligible'):
            continue
        item=market.get(i,{})
        ask=item.get('ask')
        # No volume or unverified variants as actionable ideas.
        vol=item.get('vol24')
        if type(vol) is not int or vol<10:continue
        if item.get('cls') in ('Weapon','Armor'):continue
        phase=('BUY_WINDOW' if plan['buy_start']<=local.hour<plan['buy_end'] else
               'SELL_WINDOW' if plan['sell_start']<=local.hour<plan['sell_end'] else
               'WAIT')
        # The source is hourly; a current buy is still only a review.
        cheap=(type(ask) is int and ask>0 and ask<=plan['ceiling'])
        status=('NU KOOPPRIJS CONTROLEREN' if phase=='BUY_WINDOW' and cheap
                and 0<=clock-asof<=5400 else
                'VERKOOPVENSTER — EIGEN VOORRAAD CONTROLEREN' if phase=='SELL_WINDOW' else
                'WACHT OP INSTAPVENSTER' if phase=='WAIT' else
                'PRIJS TE HOOG / BRON TE OUD')
        matched.append({
            'id':i,'name':item.get('name') or f'Item {i}',
            'ask':ask if type(ask) is int and ask>0 else None,
            'buy_window':plan['buy'],'buy_start':plan['buy_start'],
            'buy_end':plan['buy_end'],'sell_window':plan['sell'],
            'sell_start':plan['sell_start'],'sell_end':plan['sell_end'],
            'paired_days':plan['samples'],'win_rate':round(plan['win_rate']*100,1),
            'conservative_net_roi_pct':round(plan['conservative_net_roi'],1),
            'median_net_roi_pct':round(plan['median_net_roi'],1),
            'max_buy_before_deposit':plan['ceiling'],
            'target_ask_scenario':plan['target'],
            'volume_24h':vol,'phase':phase,'status':status,
            'timezone':str(zone),'snapshot_at':asof,
            'risk':'Uurlijkse vraagprijs, geen bewezen transactie. '
                   'Deposit/failed listings niet verwerkt; controleer AH.',
        })
    matched.sort(key=lambda r:(
        0 if r['status']=='NU KOOPPRIJS CONTROLEREN' else
        1 if r['status'].startswith('VERKOOPVENSTER') else
        2 if r['status']=='WACHT OP INSTAPVENSTER' else 3,
        -r['conservative_net_roi_pct'],-r['paired_days'],r['id']))
    return {
        'timezone':str(zone),'current_local_hour':local.hour,
        'patterns':matched[:45],'tested_items':len(candidates),
        'missing_history_count':incomplete,
        'min_completed_days':cfg.get('daily_min_days',5),
        'method':'Herhaalde ochtend/middag/avondvensters in voltooide lokale '
                 'dagen, minstens 16 uurlijkse vraagprijzen per dag. '
                 'Geen garantie dat je kunt kopen/verkopen tegen deze prijzen.'
    }
