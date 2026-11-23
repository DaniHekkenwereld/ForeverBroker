"""Read-only per-character snapshots exported by the WoW addon.

The WoW client flushes SavedVariables only on reload/logout; this importer
cannot provide true live login synchronization. Never execute Lua source.
"""
import hashlib
import re
import sqlite3

SCHEMA = """
CREATE TABLE IF NOT EXISTS character_snapshots(
    character_key TEXT PRIMARY KEY,
    realm TEXT NOT NULL,
    character TEXT NOT NULL,
    faction TEXT NOT NULL,
    last_seen INTEGER NOT NULL,
    gold INTEGER,
    wallet_at INTEGER,
    bags TEXT,
    bags_at INTEGER,
    auctions TEXT,
    auctions_at INTEGER,
    mail_at INTEGER,
    mail_pending INTEGER,
    mail_ready INTEGER,
    mail_attachments INTEGER
);
CREATE TABLE IF NOT EXISTS character_portfolio (
    character_key TEXT PRIMARY KEY,
    bank TEXT,bank_at INTEGER,bank_bound TEXT,
    bag_bound TEXT,bag_bound_at INTEGER,
    equipment TEXT,equipment_at INTEGER
);
"""
STOCK_WIRE = re.compile(r'^\s*\["stockWire"\]\s*=\s*"([^"\\]{1,65000})"\s*,?\s*$',re.M)
WIRE = re.compile(r'^\s*\["charactersWire"\]\s*=\s*"([^"\\]{1,65000})"\s*,?\s*$', re.M)

def parse_counts(raw):
    if not raw:
        return {}
    if len(raw) > 15000:
        raise ValueError('oversized item list')
    found={}
    for row in raw.split(','):
        parts=row.split(':')
        if len(parts)!=2:
            raise ValueError('bad item entry')
        item,qty=(int(x) for x in parts)
        if not 0<item<=10_000_000 or not 0<qty<=10_000_000:
            raise ValueError('bad item amount')
        if item in found:
            raise ValueError('duplicate item')
        found[item]=qty
    return found

def _optional_int(x):
    return int(x) if x != '' else None

def parse_saved_variables(text, now, account):
    match=WIRE.search(text)
    if not match:
        return []
    wire=match.group(1)
    if wire == 'FTCHAR1':
        return []
    rows=wire.split(';')
    if rows.pop(0) != 'FTCHAR1' or len(rows)>40:
        raise ValueError('invalid character export header')
    result=[]
    account_hash=hashlib.sha256(account.encode('utf-8')).hexdigest()[:24]
    for row in rows:
        f=row.split('|')
        if len(f)!=14:
            raise ValueError('invalid character export row')
        last,realm,name,faction,gold,wallet_at,bags_at,bags,auctions_at,auctions,mail_at,pending,ready,attachments=f
        if not (1<=len(realm)<=100 and 1<=len(name)<=100 and 1<=len(faction)<=32):
            raise ValueError('bad character identity')
        if any(ord(c)<32 or c in '";\\|' for c in realm+name+faction):
            raise ValueError('invalid character characters')
        last=int(last)
        if not 0<last<=now+300:
            raise ValueError('invalid character timestamp')
        gold=_optional_int(gold);wallet_at=_optional_int(wallet_at)
        bags_at=_optional_int(bags_at);auctions_at=_optional_int(auctions_at)
        mail_at=_optional_int(mail_at)
        if gold is not None and not 0<=gold<=9_007_199_254_740_991:
            raise ValueError('invalid wallet')
        for at in (wallet_at,bags_at,auctions_at,mail_at):
            if at is not None and not 0<at<=now+300:
                raise ValueError('invalid observation time')
        result.append(dict(
            character_key=f'{account_hash}:{realm}:{name}', realm=realm,
            character=name, faction=faction, last_seen=last,
            gold=gold, wallet_at=wallet_at, bags=parse_counts(bags) if bags_at else None,
            bags_at=bags_at, auctions=parse_counts(auctions) if auctions_at else None,
            auctions_at=auctions_at, mail_at=mail_at,
            mail_pending=_optional_int(pending), mail_ready=_optional_int(ready),
            mail_attachments=_optional_int(attachments)
        ))
    return result

def parse_stock_wire(text,now,account):
    """Bounded non-executable location export for bank/bags/equipped items."""
    match=STOCK_WIRE.search(text)
    if not match or match.group(1)=='FTSTOCK1':return {}
    lines=match.group(1).split(';')
    if lines.pop(0)!='FTSTOCK1' or len(lines)>40:
        raise ValueError('Invalid stock export')
    identity=hashlib.sha256(account.encode('utf-8')).hexdigest()[:24]
    result={}
    for line in lines:
        f=line.split('|')
        if len(f)!=10:raise ValueError('Invalid stock export row')
        last,realm,name,bank_at,bank,bank_bound,bag_bound_at,bag_bound,equip_at,equip=f
        if not (1<=len(realm)<=100 and 1<=len(name)<=100):
            raise ValueError('Invalid stock identity')
        if any(ord(c)<32 or c in '";\\|' for c in realm+name):
            raise ValueError('Invalid stock identity characters')
        last=int(last)
        if not 0<last<=now+300:raise ValueError('Invalid stock last seen')
        values={}
        for ts_key,data_key,raw_ts,raw_data in (
            ('bank_at','bank',bank_at,bank),
            ('bank_at','bank_bound',bank_at,bank_bound),
            ('bag_bound_at','bag_bound',bag_bound_at,bag_bound),
            ('equipment_at','equipment',equip_at,equip)):
            at=int(raw_ts) if raw_ts else None
            if at is None:
                if raw_data:raise ValueError('Stock with missing timestamp')
                continue
            if not 0<at<=now+300 or at>last+300:
                raise ValueError('Invalid stock measurement time')
            values[ts_key]=at
            values[data_key]=parse_counts(raw_data)
        key=f'{identity}:{realm}:{name}'
        if key in result:raise ValueError('Duplicate stock character')
        result[key]=values
    return result


def store(db,rows):
    """Newer observed fields win independently; never erase offline characters."""
    import json
    imported=0
    for r in rows:
        cur=db.execute('SELECT * FROM character_snapshots WHERE character_key=?',(r['character_key'],)).fetchone()
        old=dict(cur) if cur else {}
        merged=dict(old) if old else {
            'character_key':r['character_key'],'realm':r['realm'],
            'character':r['character'],'faction':r['faction'],
            'last_seen':0,'gold':None,'wallet_at':None,'bags':None,
            'bags_at':None,'auctions':None,'auctions_at':None,
            'mail_at':None,'mail_pending':None,'mail_ready':None,'mail_attachments':None}
        if r['last_seen'] >= merged['last_seen']:
            merged['last_seen']=r['last_seen'];merged['faction']=r['faction']
        for at,keys in [('wallet_at',['gold']),('bags_at',['bags']),
                        ('auctions_at',['auctions']),
                        ('mail_at',['mail_pending','mail_ready','mail_attachments'])]:
            fresh=r.get(at)
            if fresh is not None and fresh >= (merged[at] or 0):
                merged[at]=fresh
                for k in keys:
                    val=r.get(k)
                    merged[k]=json.dumps(val,sort_keys=True,separators=(',',':')) if k in ('bags','auctions') else val
        if merged != old:
            db.execute('''INSERT OR REPLACE INTO character_snapshots
                (character_key,realm,character,faction,last_seen,gold,wallet_at,
                 bags,bags_at,auctions,auctions_at,mail_at,mail_pending,mail_ready,mail_attachments)
                VALUES (:character_key,:realm,:character,:faction,:last_seen,:gold,:wallet_at,
                        :bags,:bags_at,:auctions,:auctions_at,:mail_at,:mail_pending,:mail_ready,:mail_attachments)''',merged)
            imported+=1
        # Location observations are independently timestamped. Missing bank
        # scans NEVER erase an older bank snapshot.
        old_stock=db.execute('SELECT * FROM character_portfolio WHERE character_key=?',
                             (r['character_key'],)).fetchone()
        portfolio=dict(old_stock) if old_stock else {
            'character_key':r['character_key'],
            'bank':None,'bank_at':None,'bank_bound':None,
            'bag_bound':None,'bag_bound_at':None,
            'equipment':None,'equipment_at':None,
        }
        previous=dict(portfolio)
        for time_key,fields in (
            ('bank_at',('bank','bank_bound')),
            ('bag_bound_at',('bag_bound',)),
            ('equipment_at',('equipment',))):
            at=r.get(time_key)
            if at is not None and at>=(portfolio[time_key] or 0):
                portfolio[time_key]=at
                for field in fields:
                    data=r.get(field)
                    if data is not None:
                        portfolio[field]=json.dumps(data,sort_keys=True,
                                                     separators=(',',':'))
        if portfolio!=previous:
            db.execute("""INSERT OR REPLACE INTO character_portfolio
                (character_key,bank,bank_at,bank_bound,bag_bound,bag_bound_at,
                 equipment,equipment_at)
                VALUES (:character_key,:bank,:bank_at,:bank_bound,:bag_bound,
                        :bag_bound_at,:equipment,:equipment_at)""",portfolio)
            if merged==old:imported+=1
    return imported

def read_all(db):
    import json
    db.executescript(PORTFOLIO_SCHEMA)
    extra={r['character_key']:dict(r) for r in db.execute(
        'SELECT * FROM character_portfolio')}
    rows=[]
    for r in db.execute('SELECT * FROM character_snapshots ORDER BY last_seen DESC,character_key'):
        x=dict(r)
        for k in ('bags','auctions'):
            x[k]=json.loads(x[k]) if x[k] else None
        location=extra.get(x['character_key']) or {}
        for key in ('bank','bank_bound','bag_bound','equipment'):
            x[key]=json.loads(location[key]) if location.get(key) else None
        for key in ('bank_at','bag_bound_at','equipment_at'):
            x[key]=location.get(key)
        rows.append(x)
    return rows
