"""Evidence-labelled EU PvP Alliance opportunity research from the server's stored data.

All monetary amounts are copper per individual item. No vendor flips, automatic
trading, simulated profits or claims that publicly observed asks are sales.
The public provider's non-commodity sale estimates are not confirmed fills.
"""
import json
import math

import opportunities
import trader
import v4_engine

MARKET = 'eu-2-110'
RESEARCH_LIMIT = 120
MARKET_FRESH_SECONDS = 90 * 60


def pos(v):
    return type(v) is int and 0 < v <= 100_000_000_000


def optional_count(v):
    return v if type(v) is int and v >= 0 else None


def build(db, clock, cfg):
    """Build a bounded, read-only market overview. Never contact the provider."""
    row = db.execute(
        'SELECT t,received,payload FROM market_snapshots ORDER BY t DESC LIMIT 1'
    ).fetchone()
    result = {
        'version':'4.0.0', 'market': MARKET, 'generated_at':clock,
        'source':'auctionhouse.tk.gg', 'snapshot_at':None, 'received_at':None,
        'market_fresh':False, 'market_age_seconds':None,
        'market_items':0, 'priced_items':0, 'candidate_count':0,
        'opportunities':[], 'lookup':{},
        'last_attempt':trader.getmeta(db,'market_attempt',0) or None,
        'last_error':trader.getmeta(db,'market_last_error','') or None,
    }
    if not row:
        return result
    age=clock-int(row['t'])
    market={int(i):v for i,v in json.loads(row['payload']).items()}
    result.update(snapshot_at=int(row['t']), received_at=int(row['received']),
                  market_fresh=0<=age<=MARKET_FRESH_SECONDS,
                  market_age_seconds=age,
                  market_items=len(market))
    # A large budget here avoids hiding interesting listings from the report:
    # the dashboard is research, not account-specific authorisation to buy.
    # Never trust provider vendor values for deposit or vendor-flip math.
    # The screener only uses theoretical seller spreads before deposits.
    no_vendor={i:{**x,'vendor':0} for i,x in market.items() if isinstance(x,dict)}
    ranked,coverage=opportunities.rank_market(
        no_vendor,cfg,limit=300,budget_gold=1_000_000)
    result['priced_items']=coverage['priced']
    result['candidate_count']=coverage['spread_positive']
    # Historical data are populated by the existing VPS market importer only.
    picks=ranked[:RESEARCH_LIMIT]
    historical=v4_engine.summarize_history(
        db,[r['id'] for r in picks],int(row['t']))
    entries=[]
    for r in picks:
        item=market.get(r['id'],{})
        ask=r['ask']
        h=historical.get(r['id'],{})
        hist=h.get('median')
        points=h.get('points',0)
        days=h.get('days',0)
        discount=round((hist-ask)*100/hist,1) if pos(hist) else None
        volume=optional_count(item.get('vol24'))
        sure=optional_count(item.get('sure24'))
        flow_hours=optional_count(item.get('flowHours'))
        last_sale=item.get('lastSoldP')
        raw_sold_at=item.get('lastSoldT')
        sold_at=raw_sold_at//1000 if type(raw_sold_at) is int and raw_sold_at>0 else None
        has_recent_sale=(pos(last_sale) and sold_at is not None and
                         0<=int(row['t'])-sold_at<=7*86400)
        history_ok=points>=12 and days>=3
        # Second ASK is a listing, not a guaranteed exit. Only source-reported
        # sale plus historical asks may form a conservative reference price.
        reference=None
        if has_recent_sale and history_ok and pos(hist) and pos(r['next_ask']):
            reference=min(int(last_sale*.95),hist,r['next_ask']-1)
            if reference<=ask:reference=None
        price_after_cut=(reference-math.ceil(reference*cfg.get('cut_pct',5)/100)
                         if reference else None)
        potential=(price_after_cut-ask if price_after_cut is not None else None)
        if potential is not None and potential<=0:
            potential=None
        theoretical_roi=(round(potential/ask*100,1) if potential is not None else None)
        max_buy=(int(price_after_cut/1.2) if price_after_cut else None)
        # No unverified vendor values are used, even as assumed deposit.
        if not result['market_fresh']:
            status='VEROUDERD'
            reason='Uurlijkse marktsnapshot is ouder dan 90 minuten'
        elif not history_ok:
            status='MEER HISTORIE NODIG'
            reason=f'{points} prijsmetingen op {days} dagen; vereist minstens 12 metingen op 3 dagen'
        elif not has_recent_sale:
            status='VERKOOP ONZEKER'
            reason='Geen recente, als verkoop aangemerkte transactie binnen 7 dagen'
        elif volume is None or volume<3:
            status='VERKOOP ONZEKER'
            reason='Te weinig geschat verkoopvolume in de laatste 24 uur'
        elif discount is None or discount<15:
            status='MONITOREN'
            reason='Huidige vraagprijs ligt niet 15% onder de historische mediaan'
        elif theoretical_roi is None or theoretical_roi<20:
            status='MONITOREN'
            reason='Onvoldoende theoretische marge vóór onbekende stortingskosten'
        else:
            status='INTERESSANT — VERIFIËREN'
            reason=('Historisch goedkoper dan gebruikelijk; controleer actuele '
                    'AH-prijs, variant en werkelijke verkoopbaarheid')
        # Non-commodities cannot have confirmed sales in the provider feed.
        sale_evidence=('Alleen geschatte verkoop' if item.get('nc')
                       else ('Deels bevestigde verkopen' if sure and sure>0
                             else 'Verkoop geschat of onbekend'))
        entries.append({
            'id':r['id'],'name':r['name'],'category':r['category'],
            'ask':ask,'ask2':r['next_ask'],'hist_median':hist,
            'history_points':points,'history_days':days,
            'discount_pct':discount,'listed':optional_count(item.get('listed')),
            'depth5':optional_count(item.get('depth5')),
            'vol24':volume,'sure24':sure,'flow_hours':flow_hours,
            'last_sold_price':last_sale if pos(last_sale) else None,
            'last_sold_at':sold_at,'sale_evidence':sale_evidence,
            'suffix_warning':bool(item.get('nc') or r.get('suffix_risk')),
            'reference_exit':reference,'max_buy_before_deposit':max_buy,
            'theoretical_net_before_deposit':potential,
            'theoretical_roi_before_deposit':theoretical_roi,
            'status':status,'reason':reason,'snapshot_at':int(row['t']),
        })
    # Signal strength first, then potential net copper; no ROI from the next
    # seller's aspirational listing alone is considered a recommendation.
    ranks={'INTERESSANT — VERIFIËREN':0,'MONITOREN':1,'VERKOOP ONZEKER':2,
           'MEER HISTORIE NODIG':3,'VEROUDERD':4}
    entries.sort(key=lambda x:(ranks.get(x['status'],9),
                               -(x['theoretical_net_before_deposit'] or 0),
                               -(x['discount_pct'] or 0),x['id']))
    result['opportunities']=entries
    result['interesting_count']=sum(
        x['status']=='INTERESSANT — VERIFIËREN' for x in entries)
    # Resolve names/prices for the exact per-character scanner queue, including
    # fallback liquid items which may not appear among spread candidates.
    queue_ids=set()
    for s in db.execute('SELECT plan FROM v4_strategies'):
        plan=s[0] or ''
        for part in plan.split(';')[1:]:
            fields=part.split(':')
            if len(fields)==5 and fields[0].isdigit() and int(fields[0])>0:
                queue_ids.add(int(fields[0]))
    for i in sorted(queue_ids):
        info=market.get(i) or {}
        result['lookup'][str(i)]={
            'name':info.get('name') or f'Item {i}',
            'ask':info.get('ask') if pos(info.get('ask')) else None,
            'vol24':optional_count(info.get('vol24')),
            'snapshot_at':int(row['t']),
        }
    return result
