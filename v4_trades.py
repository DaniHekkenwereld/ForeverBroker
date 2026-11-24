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
CREATE TABLE IF NOT EXISTS v4_trade_issues (
 issue_id TEXT PRIMARY KEY,
 character_key TEXT NOT NULL,
 at INTEGER NOT NULL,
 side TEXT NOT NULL,
 item_id INTEGER NOT NULL,
 quantity INTEGER NOT NULL,
 total_copper INTEGER NOT NULL,
 reason TEXT NOT NULL,
 item_name TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS v4_issue_character ON v4_trade_issues(character_key,at);
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
    if entry.get('source','addon_manual') not in ('addon_manual','AH_BUY','AH_MAIL'):
        raise ValueError('Unknown receipt source')
    return entry


ISSUE_REASONS={
    'PURCHASE_WITHOUT_ITEM_ID','QUANTITY_UNKNOWN','COST_UNCONFIRMED',
    'INCOMPLETE_EXECUTION','MAIL_ITEM_UNRESOLVED',
    'MAIL_QUANTITY_UNRESOLVED','MAIL_NET_UNCONFIRMED',
}


def validate_issue(row,clock):
    if type(row) is not dict:raise ValueError('Issue must be a map')
    if type(row.get('id')) is not str or not 1<=len(row['id'])<=180:
        raise ValueError('Invalid issue id')
    if type(row.get('character_key')) is not str or not 5<=len(row['character_key'])<=250:
        raise ValueError('Invalid issue character')
    if row.get('side') not in ('BUY','SELL'):
        raise ValueError('Invalid issue side')
    if row.get('reason') not in ISSUE_REASONS:
        raise ValueError('Unknown issue reason')
    for key in ('at','item_id','quantity','total_copper'):
        if type(row.get(key)) is not int:raise ValueError('Invalid issue integer')
    if not 0<row['at']<=clock+300 or not 0<=row['item_id']<=10000000:
        raise ValueError('Invalid issue item/time')
    if not 0<=row['quantity']<=100000 or not 0<=row['total_copper']<=9007199254740991:
        raise ValueError('Invalid issue quantity/value')
    if type(row.get('item_name')) is not str or len(row['item_name'])>240:
        raise ValueError('Invalid issue item name')
    return row


def sync_issues(db,entries,known_chars):
    if type(entries) is not list or len(entries)>100:
        raise ValueError('Too many unresolved AH events')
    for r in entries:
        if r['character_key'] not in known_chars:
            raise ValueError('AH evidence belongs to other account')
    for key in known_chars:
        db.execute('DELETE FROM v4_trade_issues WHERE character_key=?',(key,))
    for r in entries:
        db.execute('''INSERT INTO v4_trade_issues
         (issue_id,character_key,at,side,item_id,quantity,total_copper,reason,item_name)
         VALUES(?,?,?,?,?,?,?,?,?)''',
         (r['id'],r['character_key'],r['at'],r['side'],r['item_id'],
          r['quantity'],r['total_copper'],r['reason'],r['item_name']))
    return len(entries)


def recent_issues(db,limit=70):
    table=db.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='v4_trade_issues'").fetchone()
    if not table:return []
    return [dict(row) for row in db.execute(
        'SELECT * FROM v4_trade_issues ORDER BY at DESC, issue_id LIMIT ?',(limit,))]


def store(db,entries,received,valid_keys):
    if type(entries) is not list or len(entries)>500:
        raise ValueError('Too many manual trades')
    added=0
    for record in entries:
        r=validate(record,received)
        if r['character_key'] not in valid_keys:
            raise ValueError('Trade refers to unknown account character')
        existing=db.execute("""SELECT character_key,happened_at,side,item_id,
                                quantity,total_copper,source FROM v4_manual_trades
                                WHERE trade_id=?""",(r['id'],)).fetchone()
        if existing:
            current=(r['character_key'],r['at'],r['side'],r['item_id'],
                     r['quantity'],r['total_copper'],r.get('source','addon_manual'))
            if tuple(existing)!=current:
                raise ValueError('Trade ID re-used with different details')
            continue
        try:
            cur=db.execute("""INSERT OR IGNORE INTO v4_manual_trades
              (trade_id,character_key,happened_at,received_at,side,item_id,quantity,
               total_copper,source)
              VALUES (?,?,?,?,?,?,?,?,?)""",
              (r['id'],r['character_key'],r['at'],received,r['side'],
               r['item_id'],r['quantity'],r['total_copper'],
               r.get('source','addon_manual')))
        except sqlite3.Error:
            raise
        added+=cur.rowcount
    return added


def summarize(db,items=None,limit=60):
    # FIFO cost matching uses ONLY expressly registered buys; unknown opening
    # inventory and unregistered transfers are never assigned an invented basis.
    query="""SELECT trade_id,character_key,happened_at,side,item_id,quantity,
                    total_copper,source FROM v4_manual_trades
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
        'basis_source':'Gamebevestigde AH aankopen met gemeten gold-uitgave en '
                       'afgeronde seller-mailfacturen, plus bestaande legacy notities. '
                       'Onbekende prijs of hoeveelheid wordt niet als winst geboekt.'
    }
