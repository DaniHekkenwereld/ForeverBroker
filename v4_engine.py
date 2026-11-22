"""ForeverTrader v4: account-aware, read-only strategy decisions.

No model fills, no game automation, no assumption that an AH ask was a sale.
A plan contains search/verification targets, not authorization to buy.
"""
import hashlib
import json
import math
from collections import Counter

import opportunities

SCHEMA = """
CREATE TABLE IF NOT EXISTS v4_strategies (
 character_key TEXT PRIMARY KEY, market_t INTEGER NOT NULL,
 computed_at INTEGER NOT NULL, expires_at INTEGER NOT NULL,
 position_at INTEGER NOT NULL, revision TEXT NOT NULL,
 plan TEXT NOT NULL, actions TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS v4_sessions (
 session_id TEXT PRIMARY KEY, character_key TEXT NOT NULL,
 started_at INTEGER NOT NULL, ended_at INTEGER NOT NULL,
 received_at INTEGER NOT NULL, payload TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS v4_sessions_character
 ON v4_sessions(character_key,ended_at DESC);
"""

MARKET='eu-2-110'
MAX_PLAN_ITEMS=20


def _positive(x):
    return type(x) is int and 0<x<=100000000000


def _stocks(c):
    bags = c.get('bags') if isinstance(c.get('bags'),dict) else {}
    auctions = c.get('auctions') if isinstance(c.get('auctions'),dict) else {}
    return ({int(i):int(q) for i,q in bags.items() if str(i).isdigit() and type(q) is int and q>0},
            {int(i):int(q) for i,q in auctions.items() if str(i).isdigit() and type(q) is int and q>0})


def _sale_reference(x):
    """Asks aren't sales. Return source-reported sale only when present."""
    p=x.get('lastSoldP')
    return p if _positive(p) else None


def _target_and_margin(item,cfg):
    ask=item.get('ask');next_ask=item.get('ask2')
    if not _positive(ask) or not _positive(next_ask) or next_ask<=ask:
        return None
    sale=_sale_reference(item)
    # Do not derive a target solely from someone's ambitious second listing.
    if sale is None:
        return None
    median=item.get('median')
    target=min(int(sale*.95),next_ask-1)
    if _positive(median):
        target=min(target,median)
    if target<=ask:
        return None
    vendor=item.get('vendor')
    deposit=math.ceil(max(0,vendor)*cfg.get('deposit_vendor_pct',15)/100) if type(vendor) is int else 0
    net=target-math.ceil(target*cfg.get('cut_pct',5)/100)-deposit-ask
    roi=net/ask*100
    return (target,net,roi,deposit) if net>0 else None


def build_character(character, market, market_t, clock, cfg):
    """Return a versioned plan and contextual actions for one character.

    Ask/lastSoldP are external price indicators; evidence remains unverified.
    Inventory and wallet may be stale. Never infer trade profit from gold delta.
    """
    key=character['character_key']
    bags,listed=_stocks(character)
    money=character.get('gold')
    fresh_market=0<=clock-market_t<=5400
    wallet_at=character.get('wallet_at')
    fresh_wallet=(type(money) is int and money>=0 and type(wallet_at) is int
                  and 0<=clock-wallet_at<=7*86400)
    reserve_pct=int(cfg.get('reserve_pct',20))
    reserve=math.ceil(money*reserve_pct/100) if fresh_wallet else None
    available=max(0,money-reserve) if fresh_wallet else 0
    max_item=int(money*cfg.get('max_item_pct',10)/100) if fresh_wallet else 0
    # Preserve v3's 5g test budget for *suggested* market exposure until
    # validated live performance permits a new, explicitly approved limit.
    allocated=min(available,50000)
    expires=clock+min(3600, max(300, market_t+5400-clock)) if fresh_market else clock+1800
    rows,cov=opportunities.rank_market(market,cfg,limit=250,budget_gold=max(1,(money or 0)/10000))
    ranked=[]
    actions=[]
    for item_id,qty in sorted(bags.items()):
        if len(actions)>=20:break
        x=market.get(item_id) or {}
        if not _positive(x.get('ask')):
            actions.append(dict(kind='HOLD',id=item_id,name=x.get('name') or str(item_id),
                                qty=qty,reason='Geen betrouwbare actuele prijs'))
            continue
        on_ah=listed.get(item_id,0)
        if on_ah:
            actions.append(dict(kind='CHECK_LISTING',id=item_id,name=x.get('name') or str(item_id),
                                qty=on_ah,reason='Reeds op AH; eerst eigen veiling controleren'))
            continue
        actions.append(dict(kind='REVIEW_SELL' if fresh_market else 'HOLD',id=item_id,
                            name=x.get('name') or str(item_id),qty=qty,
                            market_ask=x['ask'],
                            reason=('Controleer exacte variant, kostprijs en actuele concurrentie'
                                    if fresh_market else 'Marktgegevens te oud om verkoopprijs te adviseren')))
    seen=set(bags)|set(listed)
    # Underprices can always enter the search queue, even without enough
    # sales evidence. But they must remain verify-only.
    for r in rows:
        if len(ranked)>=MAX_PLAN_ITEMS:break
        item_id=r['id']
        if item_id in seen:continue
        x=market.get(item_id) or {}
        target=_target_and_margin(x,cfg)
        sale=_sale_reference(x)
        evidence=(target is not None and x.get('vol24',0)>=3 and
                  sale is not None and sale>=target[0]*.9)
        candidate_cost=r['ask']
        affordable=(fresh_wallet and candidate_cost<=allocated and
                    candidate_cost<=max_item)
        kind=('VERIFY_BUY' if evidence and fresh_market and affordable and
              target[2]>=max(20,cfg.get('min_roi_pct',15)) else 'WATCH')
        if len(actions)<40 and kind=='VERIFY_BUY':
            actions.append(dict(kind=kind,id=item_id,name=r['name'],
                                qty=1,model_buy=candidate_cost,
                                reference_sell=target[0],
                                model_net=target[1],model_roi=round(target[2],1),
                                reason='Controleer live AH, exacte variant en echte verkoopbaarheid'))
        ranked.append(r)
    # Keep scan queue read-only. A publicly observed spread cannot issue a
    # transaction: every row is explicitly max=qty=target=0.
    made=clock
    plan='FT3|'+MARKET+'|'+str(made)+'|'+str(expires)+';'
    plan+=';'.join(f"{r['id']}:0:0:0:0" for r in ranked)
    if not ranked:
        plan=''
    actions.sort(key=lambda a: (
        0 if a['kind']=='REVIEW_SELL' else
        1 if a['kind']=='VERIFY_BUY' else
        2 if a['kind']=='CHECK_LISTING' else 3,
        -a.get('model_net',0), a['id']))
    summary=dict(
        version='4.0.0', character_key=key,realm=character['realm'],
        character=character['character'],created_at=clock,expires_at=expires,
        market_t=market_t,market_fresh=fresh_market,
        wallet_fresh=fresh_wallet,last_seen=character.get('last_seen'),
        gold=money,free_gold_after_reserve=available if fresh_wallet else None,
        reserve=reserve,observed_bag_types=len(bags),observed_auction_types=len(listed),
        coverage=cov,actions=actions[:40],plan=plan,
        warning='Publieke vraagprijzen zijn geen bewezen verkopen; controleer in de game.'
    )
    revision=hashlib.sha256(json.dumps(summary,sort_keys=True,
                          ensure_ascii=False,separators=(',',':')).encode()).hexdigest()[:16]
    summary['revision']=revision
    return summary


def save_strategy(db, strategy):
    db.execute('''INSERT INTO v4_strategies
    (character_key,market_t,computed_at,expires_at,position_at,revision,plan,actions)
    VALUES (?,?,?,?,?,?,?,?) ON CONFLICT(character_key) DO UPDATE SET
    market_t=excluded.market_t,computed_at=excluded.computed_at,
    expires_at=excluded.expires_at,position_at=excluded.position_at,
    revision=excluded.revision,plan=excluded.plan,actions=excluded.actions''',
    (strategy['character_key'],strategy['market_t'],strategy['created_at'],
     strategy['expires_at'],strategy.get('last_seen') or 0,strategy['revision'],
     strategy['plan'],json.dumps(strategy,ensure_ascii=False,separators=(',',':'))))


def strategy_list(db, clock, cfg):
    """The database is authoritative: recalculate after any new session/market."""
    import characters
    latest=db.execute('SELECT t,payload FROM market_snapshots ORDER BY t DESC LIMIT 1').fetchone()
    if latest:
        market={int(k):v for k,v in json.loads(latest['payload']).items()}
        market_t=int(latest['t'])
    else:
        market={}; market_t=0
    out=[]
    for char in characters.read_all(db):
        s=build_character(char,market,market_t,clock,cfg)
        save_strategy(db,s)
        out.append(s)
    return out


def normalize_session(x,received_at):
    """Accept an observation, never claim that inventory changes were trades."""
    if not isinstance(x,dict):
        raise ValueError('Session object required')
    id=x.get('id')
    key=x.get('character_key')
    started=x.get('started_at')
    ended=x.get('ended_at')
    if not isinstance(id,str) or not 1<=len(id)<=160 or not all(c.isalnum() or c in '-_:.' for c in id):
        raise ValueError('Invalid session id')
    if not isinstance(key,str) or not 5<=len(key)<=250 or any(c in key for c in '"\\\r\n'):
        raise ValueError('Invalid character key')
    if any(type(t) is not int for t in (started,ended)) or not 0<started<=ended<=received_at+300:
        raise ValueError('Invalid session times')
    # Inventory state and gold deltas are *observations*. They cannot prove
    # what was bought or sold without an explicit trade record.
    return {'id':id,'character_key':key,'started_at':started,'ended_at':ended,
            'gold_start':x.get('gold_start') if type(x.get('gold_start')) is int else None,
            'gold_end':x.get('gold_end') if type(x.get('gold_end')) is int else None,
            'source':'addon_saved_variables','verified_transactions':False}


def store_sessions(db, sessions, received_at):
    n=0
    for x in sessions:
        session=normalize_session(x,received_at)
        cur=db.execute('''INSERT OR IGNORE INTO v4_sessions
          (session_id,character_key,started_at,ended_at,received_at,payload)
          VALUES (?,?,?,?,?,?)''',
          (session['id'],session['character_key'],session['started_at'],
           session['ended_at'],received_at,
           json.dumps(session,separators=(',',':'))))
        n+=cur.rowcount
    return n
