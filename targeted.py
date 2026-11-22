"""Strict parser for complete exact-item observations; never executes Lua or orders."""
import json, re, math
SCHEMA='''
CREATE TABLE IF NOT EXISTS targeted_observations(t INTEGER,item_id INTEGER,kind TEXT,ask INTEGER,units INTEGER,rows INTEGER,book TEXT,PRIMARY KEY(t,item_id,kind,book));
CREATE INDEX IF NOT EXISTS targeted_latest ON targeted_observations(item_id,t DESC);
'''
def import_log(db,text,clock):
    m=re.search(r'^\s*\["targetLog"\]\s*=\s*"([0-9A-Za-z|:;,]*)"\s*,?\s*$',text,re.M)
    if not m or len(m[1])>4_000_000: return 0
    count=0
    for line in m[1].split(';')[-500:]:
        try:
            ts,f,r,p,item,kind,n,body=line.split('|'); t,i,n=int(ts),int(item),int(n)
            if (f,r,p)!=('Alliance','3','1') or not 0<t<=clock or not 0<i<=10_000_000 or kind not in ('item','commodity') or not 0<=n<=2000:continue
            raw=body.split(',') if body else []
            if len(raw)!=n:continue
            stacks=[tuple(map(int,x.split(':'))) for x in raw]
            stacks=[x+(1,) if len(x)==2 else x for x in stacks]
            if any(len(x)!=3 or not 0<x[0]<=10_000_000 or not 0<x[1]<=9_007_199_254_740_991 or not 0<x[2]<=10000 or (kind=='commodity' and x[1]%x[0]) for x in stacks):continue
            if sum(x[2] for x in stacks)>10000:continue
            ask=min(((cost+qty-1)//qty for qty,cost,_ in stacks),default=None); units=sum(q*n for q,_,n in stacks)
            cur=db.execute('INSERT OR IGNORE INTO targeted_observations VALUES(?,?,?,?,?,?,?)',(t,i,kind,ask,units,sum(x[2] for x in stacks),json.dumps(stacks,separators=(',',':'))));count+=cur.rowcount
        except (ValueError,OverflowError):continue
    return count

def latest(db,i,clock,max_age=120):
    return db.execute('SELECT * FROM targeted_observations WHERE item_id=? AND t<=? AND t>? ORDER BY t DESC,rowid DESC LIMIT 1',(i,clock,clock-max_age)).fetchone()

def affordable(row,limit,max_qty):
    qty=0;cost=0
    for v in sorted(json.loads(row['book']),key=lambda r:r[1]/r[0]):
        q,c=v[:2];n=v[2] if len(v)==3 else 1
        if c>q*limit:continue
        if row['kind']=='commodity':
            take=min(q*n,max_qty-qty);qty+=take;cost+=take*(c//q)
        else:
            take=min(n,(max_qty-qty)//q);qty+=q*take;cost+=c*take
    return qty,cost
