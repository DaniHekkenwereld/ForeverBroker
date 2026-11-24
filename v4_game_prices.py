"""Persist ACTUALLY observed in-client AH prices independently of TK snapshots.

These are read-only observations uploaded from WoW SavedVariables by the
Windows bridge after the game writes the file (logout or /reload).
Never pretend a listing is a fulfilled sale or a live market feed.
"""
import sqlite3

SCHEMA="""
CREATE TABLE IF NOT EXISTS v4_game_quotes (
 account_key TEXT NOT NULL,
 item_id INTEGER NOT NULL,
 observed_at INTEGER NOT NULL,
 kind TEXT NOT NULL,
 ask_copper INTEGER NOT NULL,
 units INTEGER NOT NULL,
 auction_rows INTEGER NOT NULL,
 received_at INTEGER NOT NULL,
 PRIMARY KEY(account_key,item_id,observed_at,kind)
);
CREATE INDEX IF NOT EXISTS v4_game_quotes_latest
 ON v4_game_quotes(item_id,observed_at DESC);
"""


def validate(rows,clock):
    if type(rows) is not list or len(rows)>120:
        raise ValueError('Invalid in-game quote batch')
    checked=[]
    for r in rows:
        if type(r) is not dict:raise ValueError('Invalid in-game quote record')
        if r.get('kind') not in ('item','commodity'):
            raise ValueError('Invalid in-game quote kind')
        fields=('id','at','ask','units','price_rows')
        if any(type(r.get(k)) is not int for k in fields):
            raise ValueError('Noninteger game quote')
        if not (0<r['id']<=10000000 and
                0<r['at']<=clock+300 and
                0<r['ask']<=100000000000 and
                0<=r['units']<=10000000 and
                0<=r['price_rows']<=10000):
            raise ValueError('Invalid in-game AH quote values')
        checked.append(r)
    return checked


def store(db,account_key,rows,received_at):
    if not account_key or len(account_key)>120:
        raise ValueError('Unknown game account')
    added=0
    for r in validate(rows,received_at):
        cur=db.execute("""INSERT OR IGNORE INTO v4_game_quotes
           (account_key,item_id,observed_at,kind,ask_copper,units,
            auction_rows,received_at)
           VALUES (?,?,?,?,?,?,?,?)""",
           (account_key,r['id'],r['at'],r['kind'],r['ask'],
            r['units'],r['price_rows'],received_at))
        added+=cur.rowcount
    return added


def recent(db,asof,limit=60):
    exists=db.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='v4_game_quotes'").fetchone()
    if not exists:return []
    rows=db.execute("""SELECT item_id AS id,observed_at AS at,kind,
                  ask_copper AS ask,units,auction_rows AS price_rows,
                  received_at FROM v4_game_quotes
                  WHERE observed_at <= ? AND observed_at > ?
                  ORDER BY observed_at DESC,item_id LIMIT ?""",
                  (asof,asof-30*86400,min(limit*8,800))).fetchall()
    by_id={}
    for x in rows:
        record=dict(x)
        if record['id'] not in by_id:
            by_id[record['id']]=record
        if len(by_id)>=limit:break
    return list(by_id.values())


def annotate(ideas,quotes,now):
    by_id={q['id']:q for q in quotes}
    for item in ideas:
        verified=by_id.get(item.get('id'))
        cap=item.get('max_price_each')
        if not verified:
            item['game_check']='NOG GEEN OPGESLAGEN AH-CONTROLE'
            item['game_ask']=None
            item['game_checked_at']=None
            continue
        item['game_ask']=verified['ask']
        item['game_checked_at']=verified['at']
        if now-verified['at']>90*60:
            item['game_check']='GAMEPRIJS VEROUDERD'
        elif type(cap) is not int:
            item['game_check']='GEEN KOOPLIMIET'
        elif verified['ask']<=cap:
            item['game_check']='AH-PRIJS BINNEN INSTAPLIMIET (BIJ LAATSTE SAVE)'
        else:
            item['game_check']='AH-PRIJS BOVEN INSTAPLIMIET (BIJ LAATSTE SAVE)'
    return ideas
