"""WoW Forever investment radar: trend direction, buy-dips and capital turnover.

Strictly observational: market ASK quotes, never guaranteed bids/sales.
No external vendor prices, automatic orders, or predictive precision claims.
Runs only on stored VPS market history; no external HTTP requests.
"""
import math
import statistics

import opportunities

HISTORY_DAYS=14
MAX_ANALYZED=650
LIMIT=160


def positive(value):
    return type(value) is int and 0<value<=100_000_000_000


def median(values):
    return int(statistics.median(values)) if values else None


def pct(new,old):
    return round((new/old-1)*100,1) if positive(new) and positive(old) else None


def history_for_ids(db,ids,at):
    """Fetch only bounded selected item histories, preserving quote timestamps."""
    result={}
    ids=sorted(set(i for i in ids if type(i) is int and i>0))[:MAX_ANALYZED]
    for start in range(0,len(ids),200):
        batch=ids[start:start+200]
        sql=('SELECT item_id,t,ask FROM price_history WHERE source=? '
             'AND t>=? AND t<=? AND ask>0 AND item_id IN ('+
             ','.join('?' for _ in batch)+') ORDER BY item_id,t')
        for item_id,t,ask in db.execute(sql,('tk',at-14*86400,at,*batch)):
            result.setdefault(item_id,[]).append((t,ask))
    return result


def section(points,at,from_hours,to_hours):
    lo=at-to_hours*3600
    hi=at-from_hours*3600
    items=[price for t,price in points if lo<t<=hi]
    days={t//86400 for t,price in points if lo<t<=hi}
    return median(items),len(items),len(days)


def choose_candidates(market,cfg):
    """Prioritise liquidity, whole-market spreads and commodity benchmark data."""
    valid={i:x for i,x in market.items()
           if isinstance(x,dict) and positive(x.get('ask'))}
    # Top liquids can be good long-term investments even without a spread
    # at this instant. Do not only analyze today's large undercuts.
    liquids=sorted(valid,key=lambda i:(-(
        valid[i].get('vol24') if type(valid[i].get('vol24')) is int else 0),i))
    safe={i:{**x,'vendor':0} for i,x in valid.items()}
    spreads,_=opportunities.rank_market(safe,cfg,limit=350,budget_gold=1_000_000)
    # Reserve coverage for real player-traded commodities, the inflation basket.
    commodity=[i for i in liquids if valid[i].get('cls') in
               ('Trade Goods','Consumable','Consumables') and not valid[i].get('nc')]
    ids=list(dict.fromkeys([r['id'] for r in spreads[:250]]+
                           liquids[:300]+commodity[:100]))[:MAX_ANALYZED]
    return ids,valid


def analyze(db,market,at,cfg,clock=None):
    """Return investable research, raw trends, and a transparent basket index.

    A recommendation is an investigation candidate, not proof that buyers
    exist at the scenario resale price. Deposit, slippage and unsold lots
    are intentionally excluded and must be displayed to the user.
    """
    ids,valid=choose_candidates(market,cfg)
    history=history_for_ids(db,ids,at)
    fresh=(clock is None or 0<=clock-at<=5400)
    cut=cfg.get('cut_pct',5)/100
    entries=[]
    commodity_moves=[]
    for item_id in ids:
        x=valid[item_id]
        points=history.get(item_id,[])
        last24,n24,d24=section(points,at,0,24)
        prev24,nprev,dprev=section(points,at,24,48)
        last7,n7,d7=section(points,at,0,168)
        prev7,nprev7,dprev7=section(points,at,168,336)
        last6,n6,_=section(points,at,0,6)
        prev6,np6,_=section(points,at,6,12)
        if n24<3 or nprev<3:short_move=None
        else:short_move=pct(last24,prev24)
        if n7<8 or nprev7<8 or d7<3 or dprev7<3:long_move=None
        else:long_move=pct(last7,prev7)
        six_move=pct(last6,prev6) if n6>=2 and np6>=2 else None
        ask=x['ask']
        discount=pct(ask,last7)
        volume=x.get('vol24') if type(x.get('vol24')) is int and x['vol24']>=0 else None
        sure=x.get('sure24') if type(x.get('sure24')) is int and x['sure24']>=0 else None
        cls=x.get('cls') or 'Unknown'
        suffix=cls in ('Armor','Weapon') or bool(x.get('nc'))
        # Trade-goods basket is a price index from matched items with two
        # complete seven-day windows: not the entire WoW gold inflation rate.
        if (cls in ('Trade Goods','Consumable','Consumables') and not suffix
                and volume is not None and volume>=10 and long_move is not None):
            commodity_moves.append(long_move)
        trend=('STIJGT SNEL' if short_move is not None and short_move>=10 else
               'DAALT SNEL' if short_move is not None and short_move<=-10 else
               'STIJGT' if short_move is not None and short_move>=3 else
               'DAALT' if short_move is not None and short_move<=-3 else
               'STABIEL' if short_move is not None else 'ONBEKEND')
        history_ok=n7>=8 and d7>=3 and last7 is not None
        liquid=volume is not None and volume>=10
        # Allow the "falling knife" classification before a buy signal.
        if not fresh:
            signal='VEROUDERD';horizon=None
            why='Marktsnapshot ouder dan 90 minuten'
        elif not history_ok:
            signal='MEER HISTORIE';horizon=None
            why='Voor dit item ontbreken 3 verschillende dagen met minstens 8 marktmetingen'
        elif not liquid:
            signal='DUNNE MARKT';horizon=None
            why='Minder dan 10 geschatte verkopen per dag; uitstappen kan lang duren'
        elif short_move is not None and short_move<=-10:
            signal='DALING — AFWACHTEN';horizon=None
            why='De mediane vraagprijs daalt snel; een lage prijs kan verder zakken'
        elif discount is not None and discount<=-15 and short_move is not None and short_move>=3:
            signal='KORT — HERSTEL';horizon='1–3 dagen'
            why='Vraagprijs minstens 15% onder weekmediaan; 24u-trend draait omhoog'
        elif discount is not None and discount<=-15 and short_move is not None and short_move>=-3:
            signal='KORT — KOOPDIP';horizon='1–5 dagen'
            why='Minstens 15% onder weekmediaan zonder sterke nieuwe daling'
        elif (long_move is not None and long_move>=10 and
              (short_move is None or short_move>=-3) and
              discount is not None and discount<=3):
            signal='LANG — OPWAARTS';horizon='1–3 weken'
            why='7-daagse vraagprijsmediaan stijgt tegenover vorige week; instap niet veel hoger dan weekmediaan'
        elif short_move is not None and short_move>=10:
            signal='STIJGT SNEL — NIET NAJAGEN';horizon=None
            why='Prijs versnelt; geen onderbouwd goedkoop instapmoment'
        elif short_move is not None and short_move<=-3:
            signal='DAALT — VOLGEN';horizon=None
            why='Vraagprijs daalt; wacht op stabilisatie of herstel'
        else:
            signal='VOLGEN';horizon=None
            why='Geen sterk instapmoment uit beschikbare prijs- en volumedata'
        # A hypothetical conservative rebound scenario; NOT a sales forecast.
        exit_scenario=int(last7*.95) if history_ok else None
        if exit_scenario is not None and exit_scenario<=ask:
            exit_scenario=None
        # Maximum asking-price entry for >=20% nominal ROI after AH cut;
        # does not include vendor-dependent deposits / other losses.
        proceeds=(exit_scenario-math.ceil(exit_scenario*cut)
                  if exit_scenario is not None else None)
        max_buy=(int(proceeds/1.2) if proceeds is not None else None)
        margin=(proceeds-ask if proceeds is not None and proceeds>ask else None)
        roi=(round(margin/ask*100,1) if margin is not None else None)
        if signal.startswith(('KORT','LANG')):
            if suffix:
                signal='VARIANT CONTROLEREN'
                why='Non-commodity/suffix varianten kunnen onder één item-ID samenkomen; geen betrouwbare vergelijkbare prijs'
                horizon=None
            elif max_buy is None or ask>max_buy:
                signal='MARGE TE KLEIN'
                why='Huidige vraagprijs ligt boven de maximale instapprijs voor 20% scenario-ROI na AH-cut'
                horizon=None
        rank={'KORT — HERSTEL':0,'KORT — KOOPDIP':1,'LANG — OPWAARTS':2,
              'STIJGT SNEL — NIET NAJAGEN':3,'DALING — AFWACHTEN':4,
              'DAALT — VOLGEN':5,'VOLGEN':6,'MARGE TE KLEIN':7,
              'VARIANT CONTROLEREN':8,'DUNNE MARKT':9,'MEER HISTORIE':10,'VEROUDERD':11}
        entry={
            'id':item_id,'name':str(x.get('name') or f'Item {item_id}'),
            'category':str(cls),'ask':ask,'volume_24h':volume,
            'confirmed_24h':sure,'listed':x.get('listed') if type(x.get('listed')) is int else None,
            'price_24h':last24,'price_prev_24h':prev24,
            'price_7d':last7,'price_prev_7d':prev7,
            'change_24h_pct':short_move,'change_7d_pct':long_move,
            'change_6h_pct':six_move,'discount_vs_7d_pct':discount,
            'history_points_7d':n7,'history_days_7d':d7,
            'history_points_prev7d':nprev7,
            'trend':trend,'signal':signal,'horizon':horizon,
            'exit_scenario':exit_scenario,
            'max_buy_before_deposit':max_buy,
            'scenario_margin_before_deposit':margin,
            'scenario_roi_before_deposit':roi,'warning':why,
            'variant_risk':suffix,
            'sale_evidence':('Deels bronbevestigd' if sure and sure>0 and not suffix
                             else 'Alleen geschat/onbekend'),
            'source_timestamp':at,
            'priority':rank.get(signal,12)
        }
        entries.append(entry)
    entries.sort(key=lambda v:(v['priority'],
             -(v.get('scenario_margin_before_deposit') or 0),
             -(v.get('volume_24h') or 0),v['id']))
    basket=round(statistics.median(commodity_moves),1) if len(commodity_moves)>=10 else None
    return {
        'investments':entries[:LIMIT],
        'analyzed_count':len(ids),
        'history_covered':sum(x['history_points_7d']>=8 for x in entries),
        'rising_count':sum(x['trend'] in ('STIJGT SNEL','STIJGT') for x in entries),
        'falling_count':sum(x['trend'] in ('DAALT SNEL','DAALT') for x in entries),
        'shortlist_count':sum(x['priority']<=2 for x in entries),
        'basket_change_7d_pct':basket,
        'basket_item_count':len(commodity_moves),
        'basket_description':('Mediaan van gelijk gewogen, liquide consumables/trade goods '
                              'met twee weken historische publieke vraagprijzen. '
                              'Geen directe meting van goudinflatie.'),
        'quote_only':True,
    }
