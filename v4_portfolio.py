"""Account-wide Forever portfolio: gold, bags, bank, bound gear and AH listings.

All balances come from game SavedVariables and retain independent timestamps.
Public AH asking prices are only indicative marks, NEVER realized sale proceeds.
No inferred cost basis or automatic trade decisions.
"""
import math
import statistics

import characters
import v4_investing

MARKET='eu-2-110'

THEMES={
    12363:('Nieuwe craftingvraag / tiers',
           'Arcane Crystal kan via transmute Arcanite opleveren voor crafting; '
           'geen directe enchanting-grondstof. Tierdatum en vraag zijn niet bevestigd.'),
    12360:('Nieuwe craftingvraag / tiers',
           'Arcanite Bar voor recepten en equipment; vraag na een tierwissel is een hypothese.'),
    14344:('Nieuwe uitrusting / enchanting',
           'Large Brilliant Shard voor high-level enchants; eventuele piek bij nieuwe gear is speculatief.'),
    16203:('Nieuwe uitrusting / enchanting',
           'Greater Eternal Essence wordt gebruikt bij high-level enchants; '
           'vraag kan rond nieuwe uitrusting veranderen.'),
    7068:('Raidvoorbereiding / consumables',
          'Elemental Fire kan crafting-/consumablevraag krijgen; intraday-patroon eerst meten.'),
    13468:('Raidvoorbereiding / consumables',
           'Black Lotus voor flasks; aanbod en volume wegen zwaar mee.'),
}


def counts(value):
    if not isinstance(value,dict):return {}
    return {int(i):q for i,q in value.items()
            if str(i).isdigit() and type(q) is int and q>0}


def fresh(at,clock,seconds):
    return type(at) is int and 0<=clock-at<=seconds


def fraction(copper):
    return round(copper/10000,2) if type(copper) is int else None


def allocation(money,reserve_pct=20):
    if type(money) is not int or money<0:return None
    reserve=math.ceil(money*reserve_pct/100)
    free=max(0,money-reserve)
    # Never propose investing all portable gold; the user confirms each buy.
    investable=int(free*.60)
    short_share=.75 if money<100*10000 else .60 if money<500*10000 else .45
    short=int(investable*short_share)
    long=investable-short
    return {'gold':money,'reserve':reserve,'free':free,
            'investable':investable,'short_budget':short,'long_budget':long,
            'short_max_item':min(int(free*.12),short),
            'long_max_item':min(int(free*.08),long),
            'policy':'20% goldreserve, maximaal 60% van vrije gold te investeren; '
                     'gevarieerde kleine posities. Geen automatische orders.'}


def build(db,market,market_t,clock,cfg,investments=None):
    investments=investments or []
    by_invest={i['id']:i for i in investments}
    source_fresh=fresh(market_t,clock,90*60)
    chars=characters.read_all(db)
    char_rows=[]
    holdings={}
    gold_total=0
    gold_recent=0
    known_wallets=0
    unknown_wallets=0
    missing_banks=0
    for ch in chars:
        game=ch['character']
        bags=counts(ch.get('bags'))
        bank=counts(ch.get('bank'))
        auctions=counts(ch.get('auctions'))
        equipment=counts(ch.get('equipment'))
        bound_bag=counts(ch.get('bag_bound'))
        bound_bank=counts(ch.get('bank_bound'))
        if ch.get('bank_at') is None:missing_banks+=1
        wallet=ch.get('gold')
        if type(wallet) is int:
            gold_total+=wallet
            known_wallets+=1
            if fresh(ch.get('wallet_at'),clock,7*86400):
                gold_recent+=wallet
        else:unknown_wallets+=1
        info={
            'character':game,'realm':ch['realm'],'faction':ch['faction'],
            'last_seen':ch['last_seen'],'gold':wallet,'wallet_at':ch.get('wallet_at'),
            'wallet_fresh':fresh(ch.get('wallet_at'),clock,7*86400),
            'bags_at':ch.get('bags_at'),'bank_at':ch.get('bank_at'),
            'auctions_at':ch.get('auctions_at'),'equipment_at':ch.get('equipment_at'),
            'bag_types':len(bags),'bank_types':len(bank),
            'auction_types':len(auctions),'equipment_types':len(equipment),
            'bank_checked':ch.get('bank_at') is not None,
            'allocation':allocation(wallet,cfg.get('reserve_pct',20))
                        if fresh(ch.get('wallet_at'),clock,7*86400) else None,
        }
        char_rows.append(info)
        ids=set(bags)|set(bank)|set(auctions)|set(equipment)
        for item in ids:
            obj=holdings.setdefault(item,{'id':item,'bags':0,'bank':0,
                                  'auctions':0,'equipment':0,'bound_bags':0,
                                  'bound_bank':0,'holders':[],'bound_known':True})
            obj['bags']+=bags.get(item,0)
            obj['bank']+=bank.get(item,0)
            obj['auctions']+=auctions.get(item,0)
            obj['equipment']+=equipment.get(item,0)
            obj['bound_bags']+=bound_bag.get(item,0)
            obj['bound_bank']+=bound_bank.get(item,0)
            if bags.get(item) and ch.get('bag_bound_at') is None:
                obj['bound_known']=False
            if bank.get(item) and ch.get('bank_bound') is None:
                obj['bound_known']=False
            obj['holders'].append({
                'character':game,'bags':bags.get(item,0),'bank':bank.get(item,0),
                'auctions':auctions.get(item,0),'equipment':equipment.get(item,0),
                'bank_at':ch.get('bank_at'),'bags_at':ch.get('bags_at'),
            })
    # Historical comparisons for held items, including those not currently
    # among the 160 liquid investment candidates.
    held_ids=list(holdings)
    history=v4_investing.history_for_ids(db,held_ids[:650],market_t) if market_t>0 else {}
    rows=[]
    quoted_total=0
    unpriced=0
    for item,row in holdings.items():
        x=market.get(item) or {}
        ask=x.get('ask') if v4_investing.positive(x.get('ask')) else None
        suffix=(x.get('cls') in ('Armor','Weapon'))
        raw=row['bags']+row['bank']+row['auctions']+row['equipment']
        loose=row['bags']+row['bank']+row['auctions']
        available=(max(0,loose-row['bound_bags']-row['bound_bank'])
                   if row['bound_known'] else None)
        # Even a source quote isn't realizable money; never count gear as
        # sellable. Variant/suffix price is also unsafe at itemID level.
        priced=bool(source_fresh and ask is not None and available is not None
                    and not suffix)
        quote_mark=ask*available if priced else None
        if quote_mark is not None:quoted_total+=quote_mark
        elif loose>0:unpriced+=1
        points=history.get(item,[])
        week,n,d=v4_investing.section(points,market_t,0,168) if market_t>0 else (None,0,0)
        change=v4_investing.pct(ask,week)
        vol=x.get('vol24') if type(x.get('vol24')) is int else None
        if not source_fresh:advice='MARKTDATA OUD'
        elif available is None:advice='HANDELBAARHEID CONTROLEREN'
        elif available==0:advice='NIET VERHANDELBAAR / UITGERUST'
        elif ask is None:advice='GEEN BRONPRIJS'
        elif suffix:advice='VARIANT CONTROLEREN'
        elif n>=8 and d>=3 and change is not None and change>=25:
            advice='VERKOOP CONTROLEREN'
        elif n>=8 and d>=3 and change is not None and change<=-20:
            advice='DALING — RISICO CONTROLEREN'
        elif item in by_invest and by_invest[item].get('trend') in ('STIJGT','STIJGT SNEL'):
            advice='AANHOUDEN / MOMENTUM CONTROLEREN'
        else:advice='AANHOUDEN / PRIJS CONTROLEREN'
        rows.append({**row,'id':item,
                     'name':x.get('name') or f'Item {item}',
                     'category':x.get('cls') or 'Onbekend',
                     'total':raw,'potentially_sellable':available,
                     'ask':ask,'quoted_mark':quote_mark,'ask_age':market_t,
                     'week_median':week,'versus_week_pct':change,
                     'history_points':n,'history_days':d,
                     'volume_24h':vol,'advice':advice,
                     'suffix_risk':suffix})
    rows.sort(key=lambda x:(-(x['quoted_mark'] or 0),-x['total'],x['id']))
    observed_held=set(holdings)
    buy=[]
    for inv in investments:
        if not source_fresh:break
        if not str(inv.get('signal','')).startswith(('KORT','LANG')):continue
        if inv['id'] in observed_held:continue
        limit=inv.get('max_buy_before_deposit')
        if type(limit) is not int or limit<inv['ask']:continue
        horizon='short' if inv['signal'].startswith('KORT') else 'long'
        for ch in char_rows:
            a=ch.get('allocation')
            if not a or ch['faction']!='Alliance':continue
            cap=a['short_max_item'] if horizon=='short' else a['long_max_item']
            if not cap or inv['ask']>cap:continue
            # One suggested unit for a rare item; no blind bulk orders.
            qty=max(1,min(10,cap//inv['ask'],
                      max(1,(inv.get('volume_24h') or 0)//10)))
            buy.append({'character':ch['character'],'id':inv['id'],
                        'name':inv['name'],'horizon':horizon,'qty':qty,
                        'price_current':inv['ask'],'max_price_each':min(limit,cap),
                        'estimated_cost':qty*inv['ask'],
                        'exit_scenario':inv.get('exit_scenario'),
                        'trend_24h_pct':inv.get('change_24h_pct'),
                        'trend_7d_pct':inv.get('change_7d_pct'),
                        'confidence_note':'Scenario exclusief deposit, geen gegarandeerde verkoop',
                        'reason':inv['warning']})
            if len(buy)>=35:break
        if len(buy)>=35:break
    ideas=[]
    for item,(theme,thesis) in THEMES.items():
        q=market.get(item) or {}
        inv=by_invest.get(item) or {}
        ideas.append({'id':item,'name':q.get('name') or f'Item {item}',
                      'theme':theme,'thesis':thesis,
                      'ask':q.get('ask') if v4_investing.positive(q.get('ask')) else None,
                      'volume_24h':q.get('vol24') if type(q.get('vol24')) is int else None,
                      'trend_7d_pct':inv.get('change_7d_pct'),
                      'owned':holdings.get(item,{}).get('total',0),
                      'event_date':None,
                      'status':'ONDERZOEKEN, GEEN BEVESTIGDE TIERKATALYSATOR'})
    return {
        'characters':char_rows,'gold_total_last_known':gold_total,
        'gold_recent_7d':gold_recent,'wallet_count':known_wallets,
        'wallet_missing':unknown_wallets,'bank_not_seen':missing_banks,
        'market_fresh':source_fresh,'holdings':rows,
        'holding_types':len(rows),'portfolio_ask_mark':quoted_total,
        'unpriced_holding_types':unpriced,
        'estimated_value_warning':(
            'Slechts een indicatieve optelsom van verse, laagste AH-vraagprijzen '
            'voor potentieel verkoopbare items. Geen gerealiseerde waarde, '
            'geen kostprijs of bewezen winst.'),
        'buy_review':buy,'themes':ideas,
        'realized_profit':None,'cost_basis_known':False,
        'note':'Gebonden/uitgeruste items niet als verkoopbaar gewaardeerd. '
               'De bank wordt alleen opnieuw gemeten bij openen. '
               'Per-character gold kan niet vanzelf worden samengevoegd.',
    }
