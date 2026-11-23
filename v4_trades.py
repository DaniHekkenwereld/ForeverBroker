"""Idempotent, self-declared WoW trades for portfolio cost basis.

These are MANUAL confirmations, not detection of actual Blizzard fills.
Inventory/gold observations remain authoritative and are never inferred from
reported trades. All values copper and all trade IDs account scoped.
"""
import json
import sqlite3

SCHEMA="""
CREATE TABLE IF NOT EXISTS v4_manual_trades (
 trade_id TEXT PRIMARY KEY,
 character_key TEXT NOT NULL,
 happened_at INTEGER NOT NULL,
 received_at INTEGER NOT NULL,
 side TEXT NOT NULL,
 item_id INTEGER NOT NULL,
 quantity INTEGER NOT NULL,
 total_copper INTEGER NOT NULL,
 source TEXT NOT NULL DEFAULT 'addon_manual'
);
CREATE INDEX IF NOT EXISTS v4_trades_actor_item
 ON v4_manual_trades(character_key,item_id,happened_at,trade_id);
"""

def validate(entry,clock):
    if type(entry) is not dict:raise ValueError('Trade entry must be a map')
    key=entry.get('character_key')
    trade_id=entry.get('id')
    if not isinstance(key,str) or not 5<=len(key)<=250 or any(
            c in key for c in '"\\\r\n'):
        raise ValueError('Invalid trade character')
    if not isinstance(trade_id,str) or not 1<=len(trade_id)<=180 or not all(
            ch.isalnum() or ch in ':._-' for ch in trade_id):
        raise ValueError('Invalid trade id')
    if entry.get('side') not in ('BUY','SELL'):
        raise ValueError('Invalid trade side')
    t=entry.get('at')
    item=entry.get('item_id')
    qty=entry.get('quantity')
    copper=entry.get('total_copper')
    if any(type(x) is not int for x in (t,item,qty,copper)):
        raise ValueError('All trade amounts must be integers')
    if not 0<t<=clock+300 or not 0<item<=10000000:
        raise ValueError('Invalid trade time/item')
    if not 0<qty<=100000 or not 0<copper<=9007199254740991:
        raise ValueError('Invalid trade amount')
    return entry


def store(db,entries,received,valid_keys):
    if type(entries) is not list or len(entries)>500:
        raise ValueError('Too many manual trades')
    added=0
    for record in entries:
        r=validate(record,received)
        if r['character_key'] not in valid_keys:
            raise ValueError('Trade refers to unknown account character')
        existing=db.execute("""SELECT character_key,happened_at,side,item_id,
                                quantity,total_copper FROM v4_manual_trades
                                WHERE trade_id=?""",(r['id'],)).fetchone()
        if existing:
            current=(r['character_key'],r['at'],r['side'],r['item_id'],
                     r['quantity'],r['total_copper'])
            if tuple(existing)!=current:
                raise ValueError('Trade ID re-used with different details')
            continue
        try:
            cur=db.execute("""INSERT OR IGNORE INTO v4_manual_trades
              (trade_id,character_key,happened_at,received_at,side,item_id,quantity,
               total_copper,source)
              VALUES (?,?,?,?,?,?,?,?,'addon_manual')""",
              (r['id'],r['character_key'],r['at'],received,r['side'],
               r['item_id'],r['quantity'],r['total_copper']))
        except sqlite3.Error:
            raise
        added+=cur.rowcount
    return added


def summarize(db,items=None,limit=60):
    # FIFO cost matching uses ONLY expressly registered buys; unknown opening
    # inventory and unregistered transfers are never assigned an invented basis.
    query="""SELECT trade_id,character_key,happened_at,side,item_id,quantity,
                    total_copper FROM v4_manual_trades
              ORDER BY happened_at,trade_id"""
    exists=db.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='v4_manual_trades'").fetchone()
    records=[dict(r) for r in db.execute(query)] if exists else []
    lots={}
    for r in records:
        key=(r['character_key'],r['item_id'])
        if r['side']=='BUY':
            lots.setdefault(key,[]).append({'quantity':r['quantity'],
                'amount':r['total_copper'],'total_qty':r['quantity'],
                'remaining_qty':r['quantity']})
            continue
        # Sell proceeds are net only IF the user entered net received copper.
        qty_left=r['quantity']
        matched_cost=0
        matched_qty=0
        for lot in lots.get(key,[]):
            if qty_left<=0:break
            take=min(qty_left,lot['remaining_qty'])
            if take<=0:continue
            unit=lot['amount']/lot['total_qty']
            matched_cost+=round(unit*take)
            lot['remaining_qty']-=take
            qty_left-=take
            matched_qty+=take
        r['matched_quantity']=matched_qty
        r['unmatched_quantity']=qty_left
        if qty_left==0:
            r['matched_cost']=matched_cost
            r['realized_net_after_reported_cost']=r['total_copper']-matched_cost
        else:
            # Do not infer net gain on the unmatched portion.
            r['matched_cost']=None
            r['realized_net_after_reported_cost']=None
    cost={}
    for (_,item),batches in lots.items():
        remaining=sum(x['remaining_qty'] for x in batches)
        remaining_cost=sum(round(x['amount']*x['remaining_qty']/x['total_qty'])
                           for x in batches if x['remaining_qty']>0)
        if remaining:
            entry=cost.setdefault(item,{'known_units':0,'known_cost':0})
            entry['known_units']+=remaining
            entry['known_cost']+=remaining_cost
    realized=sum(r['realized_net_after_reported_cost'] for r in records
                 if r['side']=='SELL' and r.get('realized_net_after_reported_cost') is not None)
    unmatched_sales=sum(1 for r in records if r['side']=='SELL' and
                        r.get('unmatched_quantity',0)>0)
    return {
        'positions':cost,'recent_trades':list(reversed(records[-limit:])),
        'reported_realized_net':realized if records else None,
        'reported_realized_known':any(r['side']=='SELL' and
               r.get('realized_net_after_reported_cost') is not None for r in records),
        'unmatched_sales':unmatched_sales,'trade_count':len(records),
        'basis_source':'Uitsluitend handmatig in WoW geregistreerde BUY/SELL-bedragen; '
                       'alle niet-geregistreerde voorraad heeft onbekende kostprijs. '
                       'Gebruik bij SELL werkelijk NET ontvangen gold (na AH-kosten).'
    }
