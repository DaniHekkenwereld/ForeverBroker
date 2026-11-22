"""ForeverTrader 2.0 - local research and paper trading, no game input."""
import argparse, csv, datetime as dt, io, json, math, pathlib, sqlite3, statistics as st, time, uuid, zipfile, os, webbrowser, tempfile
from collections import defaultdict
from zoneinfo import ZoneInfo
import legacy as old
import coach
import targeted
import daily
ROOT=pathlib.Path(__file__).resolve().parent
VERSION='3.3.0'; MARKET=old.MARKET; BASE='https://auctionhouse.tk.gg/api'
UTC=dt.timezone.utc
D=lambda x: json.dumps(x,ensure_ascii=False,sort_keys=True,separators=(',',':'))
SCHEMA='''
CREATE TABLE IF NOT EXISTS meta(key TEXT PRIMARY KEY,value TEXT);
CREATE TABLE IF NOT EXISTS strategy_versions(id TEXT PRIMARY KEY,version TEXT,config TEXT);
CREATE TABLE IF NOT EXISTS items(id INTEGER PRIMARY KEY,name TEXT,category TEXT,item_level INTEGER,required_level INTEGER,vendor INTEGER,group_name TEXT);
CREATE TABLE IF NOT EXISTS market_snapshots(t INTEGER PRIMARY KEY,received INTEGER,source TEXT,payload TEXT);
CREATE TABLE IF NOT EXISTS price_history(item_id INTEGER,t INTEGER,source TEXT,ask INTEGER,ask2 INTEGER,listed INTEGER,depth INTEGER,sold INTEGER,sure INTEGER,median INTEGER,value INTEGER,added INTEGER,cancelled INTEGER,expired INTEGER,PRIMARY KEY(item_id,t,source));
CREATE INDEX IF NOT EXISTS price_time ON price_history(t,item_id);
CREATE TABLE IF NOT EXISTS daily_candles(item_id INTEGER,t INTEGER,source TEXT,payload TEXT,PRIMARY KEY(item_id,t,source));
CREATE TABLE IF NOT EXISTS order_book(item_id INTEGER,t INTEGER,price INTEGER,units INTEGER,auctions INTEGER,PRIMARY KEY(item_id,t,price));
CREATE TABLE IF NOT EXISTS sales_history(item_id INTEGER,t INTEGER,price INTEGER,units INTEGER,sure INTEGER,PRIMARY KEY(item_id,t,price));
CREATE TABLE IF NOT EXISTS population_history(t INTEGER,level_min INTEGER,level_max INTEGER,characters INTEGER,source TEXT,PRIMARY KEY(t,level_min,level_max));
CREATE TABLE IF NOT EXISTS game_events(t INTEGER,name TEXT,kind TEXT,source TEXT,PRIMARY KEY(t,name));
CREATE TABLE IF NOT EXISTS crafting_recipes(id INTEGER PRIMARY KEY,payload TEXT,received INTEGER);
CREATE TABLE IF NOT EXISTS patterns(item_id INTEGER,asof INTEGER,kind TEXT,bucket INTEGER,n INTEGER,ratio REAL,PRIMARY KEY(item_id,asof,kind,bucket));
CREATE TABLE IF NOT EXISTS trade_decisions(id INTEGER PRIMARY KEY,t INTEGER,snapshot INTEGER,item_id INTEGER,strategy TEXT,action TEXT,reason TEXT,ask INTEGER,target INTEGER,quantity INTEGER,roi REAL,confidence REAL,version TEXT,details TEXT);
CREATE TABLE IF NOT EXISTS predictions(id INTEGER PRIMARY KEY,decision_id INTEGER,t INTEGER,horizon INTEGER,target INTEGER,expected_profit INTEGER,confidence REAL,outcome TEXT,actual_profit INTEGER,resolved INTEGER);
CREATE TABLE IF NOT EXISTS inventory(id TEXT PRIMARY KEY,item_id INTEGER,name TEXT,strategy TEXT,qty INTEGER,cost INTEGER,deposit INTEGER,target INTEGER,proceeds INTEGER,bought INTEGER,list_at INTEGER,expires INTEGER,status TEXT,decision_id INTEGER);
CREATE TABLE IF NOT EXISTS incoming(id TEXT PRIMARY KEY,item_id INTEGER,amount INTEGER,eta INTEGER,strategy TEXT);
CREATE TABLE IF NOT EXISTS paper_sale_checks(lot_id TEXT PRIMARY KEY,first_t INTEGER NOT NULL,last_t INTEGER NOT NULL,consecutive INTEGER NOT NULL);
CREATE TABLE IF NOT EXISTS transactions(id INTEGER PRIMARY KEY,t INTEGER,lot_id TEXT,item_id INTEGER,strategy TEXT,action TEXT,cash_delta INTEGER,profit INTEGER,qty INTEGER,details TEXT);
CREATE TABLE IF NOT EXISTS cashflow(t INTEGER PRIMARY KEY,cash INTEGER,inventory INTEGER,listed INTEGER,incoming INTEGER,realized INTEGER,equity INTEGER);
CREATE TABLE IF NOT EXISTS error_logs(id INTEGER PRIMARY KEY,t INTEGER,level TEXT,component TEXT,message TEXT);
CREATE TABLE IF NOT EXISTS local_exports(t INTEGER,kind TEXT,payload TEXT,PRIMARY KEY(t,kind));
CREATE TABLE IF NOT EXISTS backtest_results(id INTEGER PRIMARY KEY,t INTEGER,kind TEXT,details TEXT);
CREATE TABLE IF NOT EXISTS import_log(item_id INTEGER PRIMARY KEY,attempt INTEGER,success INTEGER,detail TEXT);
CREATE TABLE IF NOT EXISTS research_signals(t INTEGER,item_id INTEGER,strategy TEXT,details TEXT,PRIMARY KEY(t,item_id,strategy));
'''
def connect(p):
    p.parent.mkdir(parents=True,exist_ok=True); db=sqlite3.connect(p,timeout=30); db.row_factory=sqlite3.Row
    db.execute('PRAGMA journal_mode=WAL'); db.executescript(SCHEMA+targeted.SCHEMA); return db

def getmeta(db,k,default=None):
    r=db.execute('SELECT value FROM meta WHERE key=?',(k,)).fetchone(); return json.loads(r[0]) if r else default

def setmeta(db,k,v): db.execute('INSERT OR REPLACE INTO meta VALUES (?,?)',(k,D(v)))
def log(db,t,component,msg,level='ERROR'): db.execute('INSERT INTO error_logs(t,level,component,message) VALUES(?,?,?,?)',(t,level,component,str(msg)[:2000]))
def csv_rows(path):
    with open(path,encoding='utf-8-sig',newline='') as f: return list(csv.DictReader(f))
def ts(s):
    x=dt.datetime.fromisoformat(s.replace('Z','+00:00'))
    if x.tzinfo is None: raise ValueError('Timestamp vereist UTC/offset')
    return int(x.timestamp())
from functools import lru_cache
@lru_cache(maxsize=4)
def getzone(name): return ZoneInfo(name)
def z(c):
    try: return getzone(c['timezone'])
    except Exception: raise ValueError('Tijdzone niet beschikbaar. Windows: py -3 -m pip install tzdata')
def local(t,c): return dt.datetime.fromtimestamp(t,UTC).astimezone(z(c))
def reset_bucket(t,c):
    d=local(t,c); return ((d.weekday()-c['reset_weekday'])%7 - (d.hour<c['reset_hour'] and d.weekday()==c['reset_weekday']))%7

def conf():
    c=json.loads((ROOT/'config.json').read_text(encoding='utf-8-sig')); old.validate(c); z(c)
    # Defaults preserve existing config.json after UPDATE.bat.
    for key,value in {'daily_min_days':5,'daily_min_win_rate':.7,'daily_min_net_roi_pct':8,
                      'daily_capital_pct':75,'daily_item_pct':35}.items():c.setdefault(key,value)
    if type(c['daily_min_days']) is not int or not 5<=c['daily_min_days']<=30:raise ValueError('daily_min_days')
    if not 0.5<=c['daily_min_win_rate']<=1:raise ValueError('daily_min_win_rate')
    if not 0<=c['daily_min_net_roi_pct']<=50:raise ValueError('daily_min_net_roi_pct')
    if not 0<c['daily_capital_pct']<=100-c['reserve_pct']:raise ValueError('daily_capital_pct / reserve_pct')
    if not 0<c['daily_item_pct']<=c['daily_capital_pct']:raise ValueError('daily_item_pct')
    for k in ['history_items_per_cycle','history_max_items','min_pattern_days','min_pattern_weeks','reset_weekday','reset_hour','max_hold_hours','local_scan_max_age_minutes']:
        if type(c[k]) is not int or c[k]<0: raise ValueError(k)
    if not 0<=c['reset_weekday']<=6 or not 0<=c['reset_hour']<=23 or c['min_pattern_days']<2 or c['min_pattern_weeks']<2: raise ValueError('Pattern/reset instellingen')
    if set(c['strategy_weights'])!={'direct','intraday','weekly'} or any(type(v) not in (float,int) or v<0 or not math.isfinite(v) for v in c['strategy_weights'].values()) or sum(c['strategy_weights'].values())>100: raise ValueError('strategy_weights')
    return c

def register(db,c):
    import hashlib
    vid=hashlib.sha256((VERSION+D({k:v for k,v in c.items() if k not in ('wow_folder','account_folder')})).encode()).hexdigest()[:16]
    db.execute('INSERT OR IGNORE INTO strategy_versions VALUES(?,?,?)',(vid,VERSION,D({k:v for k,v in c.items() if k not in ('wow_folder','account_folder')})))
    if getmeta(db,'cash') is None:
        start=round(c['starting_gold']*10000); setmeta(db,'cash',start); setmeta(db,'starting',start); setmeta(db,'realized',0)
    return vid

GROUPS={2589:'1-19',2840:'1-19',2770:'1-19',2592:'20-29',2771:'20-29',4306:'30-39',2772:'30-39',4338:'40-49',3858:'40-49',3860:'40-49',14047:'50-59',10620:'50-59',12359:'50-59',8170:'50-59',16204:'60',16203:'60',13463:'60',13465:'60',13467:'60',13468:'60'}
def item(db,i,x):
    db.execute('''INSERT INTO items VALUES(?,?,?,?,?,?,?) ON CONFLICT(id) DO UPDATE SET name=excluded.name,category=COALESCE(excluded.category,items.category),item_level=COALESCE(excluded.item_level,items.item_level),required_level=COALESCE(excluded.required_level,items.required_level),vendor=COALESCE(excluded.vendor,items.vendor)''',(i,x.get('name') or f'Item {i}',x.get('cls'),x.get('lvl'),x.get('required_level'),x.get('vendor',x.get('sell')),GROUPS.get(i)))
def obs(db,i,t,x,source='tk'):
    db.execute('INSERT OR IGNORE INTO price_history VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)',(i,t,source,x.get('ask'),x.get('ask2'),x.get('listed'),x.get('depth5'),x.get('sold'),x.get('sure'),x.get('median'),x.get('value'),x.get('added'),x.get('cancelled'),x.get('expired')))
def save_market(db,t,m,received,source='tk'):
    cur=db.execute('INSERT OR IGNORE INTO market_snapshots VALUES(?,?,?,?)',(t,received,source,D(m)))
    if not cur.rowcount:return False
    for i,x in m.items():
        item(db,i,x); obs(db,i,t,{**x,'sold':x.get('sold', (x.get('volume_history') or [None])[-1])},source)
    return True

def parse_history(db,data,i,clock):
    h=data['house'];
    if (h['key'],h['region'],h['faction'],h['grp'])!=(MARKET,'eu','alliance',1): raise ValueError('Wrong market')
    x=data['item'];
    if x['id']!=i: raise ValueError('Wrong item')
    item(db,i,x)
    s=data['series']; times=s['t']; fields=data['f'];
    if 'ask' not in fields or len(set(fields))!=len(fields): raise ValueError('Unknown hourly fields')
    if not all(len(s[k])==len(times) for k in fields): raise ValueError('History array mismatch')
    for j,ms in enumerate(times):
        t=ms//1000
        if 0<t<=clock: obs(db,i,t,{k:s[k][j] for k in fields})
    for r in data.get('daily',{}).get('rows',[]):
        f=data['daily']['f']; assert len(f)==len(r); a=dict(zip(f,r)); t=a['d']//1000
        if 0<t<=clock: db.execute('INSERT OR REPLACE INTO daily_candles VALUES(?,?,?,?)',(i,t,'tk',D(a)))
    bt=data.get('bookT');
    if bt and bt//1000<=clock:
        for p,q,n in data.get('book',[]):
            if min(p,q,n)>0: db.execute('INSERT OR REPLACE INTO order_book VALUES(?,?,?,?,?)',(i,bt//1000,p,q,n))
    for ms,p,q,sure in data.get('trades',[]):
        if 0<ms//1000<=clock and min(p,q)>0: db.execute('INSERT OR REPLACE INTO sales_history VALUES(?,?,?,?,?)',(i,ms//1000,p,q,sure))
    return len(times)

def import_history(db,c,m,clock,limit=None):
    # Small rotating watchlist, no bulk crawling. Retry after >=24h, successful history after 7d.
    ranked=sorted((i for i,x in m.items() if not x.get('nc') and type(x.get('vol24')) is int and x['vol24']>=c['min_daily_volume']),key=lambda i:-m[i]['vol24'])
    ids=list(dict.fromkeys(c['watchlist']+ranked))[:c['history_max_items']]
    done=0
    for i in ids:
        a=db.execute('SELECT attempt,success FROM import_log WHERE item_id=?',(i,)).fetchone()
        if a and (clock-a[0]<86400 or (a[1] and clock-a[1]<7*86400)): continue
        if done >= (c['history_items_per_cycle'] if limit is None else limit): break
        done+=1
        try:
            data=json.loads(old.get(f'{BASE}/m/{MARKET}/item/{i}?hours=720'))
            with db: n=parse_history(db,data,i,clock); db.execute('INSERT OR REPLACE INTO import_log VALUES(?,?,?,?)',(i,clock,clock,f'{n} hourly rows'))
        except Exception as e:
            with db: db.execute('INSERT OR REPLACE INTO import_log VALUES(?,?,?,?)',(i,clock,a[1] if a else 0,str(e)[:500])); log(db,clock,'history',f'{i}: {e}')
            break # back off on error
        time.sleep(2)
    return done

def profile(db,i,t,c,source='tk'):
    """Only completed local days, observations strictly earlier than t; normalize by day median."""
    current=local(t,c).date(); days=defaultdict(list)
    for r in db.execute('SELECT t,ask FROM price_history WHERE item_id=? AND source=? AND t>=? AND t<? AND ask>0 ORDER BY t',(i,source,t-30*86400,t)):
        d=local(r[0],c)
        if d.date()<current: days[d.date()].append((r[0],r[1]))
    hours=defaultdict(list); weeks=defaultdict(list); bases=[]
    for day,rows in days.items():
        if len({local(q,c).hour for q,p in rows})<12: continue
        b=st.median(p for q,p in rows); bases.append((day,b))
        byhour=defaultdict(list); byweek=defaultdict(list)
        for q,p in rows: byhour[local(q,c).hour].append(p/b); byweek[reset_bucket(q,c)].append(p/b)
        for k,rs in byhour.items(): hours[k].append(st.median(rs))
    # weekly comparison normalized by completed reset week (not by day, which would erase weekly pattern)
    weekdays=defaultdict(lambda:defaultdict(list))
    for day,rows in days.items():
        if len(rows)<12: continue
        for q,p in rows:
            d=local(q,c); bucket=reset_bucket(q,c); start=d.date()-dt.timedelta(days=bucket+(1 if d.weekday()==c['reset_weekday'] and d.hour<c['reset_hour'] else 0))
            # explicit reset anchor computed in local calendar
            start=d.date()-dt.timedelta(days=(d.weekday()-c['reset_weekday'])%7)
            if d.weekday()==c['reset_weekday'] and d.hour<c['reset_hour']: start-=dt.timedelta(days=7)
            weekdays[start][bucket].append(p)
    for start,buckets in weekdays.items():
        if len(buckets)<7 or start+dt.timedelta(days=7)>=current: continue
        med=st.median(st.median(v) for v in buckets.values())
        for k,v in buckets.items(): weeks[k].append(st.median(v)/med)
    baseline=st.median(v for day,v in sorted(bases)[-7:]) if bases else None
    return baseline,{k:(len(v),st.median(v)) for k,v in hours.items()},{k:(len(v),st.median(v)) for k,v in weeks.items()}

def research(db,i,x,t,c,source):
    base,h,w=profile(db,i,t,c,source); out=[]
    for kind,buckets,minimum in [('intraday',h,c['min_pattern_days']),('weekly',w,c['min_pattern_weeks'])]:
        for k,(n,ratio) in buckets.items(): db.execute('INSERT OR REPLACE INTO patterns VALUES(?,?,?,?,?,?)',(i,t,kind,k,n,ratio))
        if not base: continue
        here=local(t,c).hour if kind=='intraday' else reset_bucket(t,c)
        eligible=[(k,n,v) for k,(n,v) in buckets.items() if n>=minimum and k!=here]
        if here not in buckets or buckets[here][0]<minimum or not eligible: continue
        k,n,v=max(eligible,key=lambda a:a[2]); cur=buckets[here][1]; gap=(k-here)%(24 if kind=='intraday' else 7)
        target=int(base*v); conf=min(.85,min(n,buckets[here][0])/(minimum*2))
        if gap and v>cur*1.05: out.append((kind,target,gap*(1 if kind=='intraday' else 24),conf,{'bucket':k,'samples':n,'baseline':base,'current_ratio':cur,'future_ratio':v}))
    return out

def totals(db):
    cash=getmeta(db,'cash',0); realized=getmeta(db,'realized',0)
    inv=db.execute("SELECT COALESCE(SUM(cost),0) FROM inventory WHERE status='held'").fetchone()[0]
    listed=db.execute("SELECT COALESCE(SUM(cost+deposit),0) FROM inventory WHERE status='listed'").fetchone()[0]
    incoming=db.execute('SELECT COALESCE(SUM(amount),0) FROM incoming').fetchone()[0]
    return dict(cash=cash,inventory=inv,listed=listed,incoming=incoming,realized=realized,equity=cash+inv+listed+incoming)
def ledger(db,t,lot,action,delta=0,profit=0,detail=None):
    db.execute('INSERT INTO transactions(t,lot_id,item_id,strategy,action,cash_delta,profit,qty,details) VALUES(?,?,?,?,?,?,?,?,?)',(t,lot['id'],lot['item_id'],lot['strategy'],action,delta,profit,lot.get('qty',0),D(detail or {})))
    setmeta(db,'cash',getmeta(db,'cash')+delta); setmeta(db,'realized',getmeta(db,'realized')+profit)
def resolve(db,lot,t,outcome,profit): db.execute('UPDATE predictions SET outcome=?,actual_profit=?,resolved=? WHERE decision_id=? AND resolved IS NULL',(outcome,profit,t,lot['decision_id']))
def settle(db,t):
    for r in db.execute('SELECT * FROM incoming WHERE eta<=?',(t,)).fetchall():
        a=dict(r); ledger(db,t,a,'MAIL',a['amount']); db.execute('DELETE FROM incoming WHERE id=?',(a['id'],))
    for r in db.execute("SELECT * FROM inventory WHERE status='listed' AND expires<=?",(t,)).fetchall():
        a=dict(r); ledger(db,t,a,'EXPIRE',profit=-a['deposit']); resolve(db,a,t,'expired',-a['deposit']); db.execute("UPDATE inventory SET status='held',deposit=0 WHERE id=?",(a['id'],)); db.execute('DELETE FROM paper_sale_checks WHERE lot_id=?',(a['id'],))
def mark_cash(db,t):
    a=totals(db); db.execute('INSERT OR REPLACE INTO cashflow VALUES(?,?,?,?,?,?,?)',(t,a['cash'],a['inventory'],a['listed'],a['incoming'],a['realized'],a['equity']))
    if a['cash']<0 or a['equity']!=getmeta(db,'starting')+a['realized']: raise RuntimeError(f'Ledger invariant failed: {a}')

def decision(db,t,snap,i,strategy,action,reason,vid,ask=None,target=None,qty=0,roi=None,confidence=None,details=None):
    return db.execute('INSERT INTO trade_decisions(t,snapshot,item_id,strategy,action,reason,ask,target,quantity,roi,confidence,version,details) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)',(t,snap,i,strategy,action,reason,ask,target,qty,roi,confidence,vid,D(details or {}))).lastrowid

def cycle(db,c,t,m,clock,vid,source='tk'):
    if t<=getmeta(db,'last_trade_snapshot',0) or not 0<=clock-t<=c['max_snapshot_age_minutes']*60: return False
    # Observe sale before expiry only at a later actual sample, after listing. Volume is inferred, not an execution report.
    settle(db,clock)
    for r in db.execute("SELECT * FROM inventory WHERE status='listed'").fetchall():
        a=dict(r); x=m.get(a['item_id'],{}); units=x.get('sold');
        if units is None and x.get('volume_history'): units=x['volume_history'][-1]
        if units is None and source=='demo': units=100
        # One public asking-price snapshot is NOT evidence our own listing sold.
        # Require two independent consecutive hourly quotes above target; this
        # remains a hypothetical paper fill, not a real confirmed sale.
        eligible=(t-getmeta(db,'last_trade_snapshot',0)<=9000 and t-3600>=a['list_at']
                  and t<a['expires'] and type(units) is int and units//10>=a['qty']
                  and type(x.get('ask')) is int and x['ask']>=a['target'])
        if not eligible:
            db.execute('DELETE FROM paper_sale_checks WHERE lot_id=?',(a['id'],))
            continue
        seen=db.execute('SELECT last_t,consecutive FROM paper_sale_checks WHERE lot_id=?',(a['id'],)).fetchone()
        confirmed=(seen is not None and 1800<=t-seen['last_t']<=9000 and seen['consecutive']>=1)
        if not confirmed:
            db.execute('INSERT OR REPLACE INTO paper_sale_checks VALUES (?,?,?,?)',(a['id'],t,t,1))
            continue
        amount=a['proceeds']*a['qty']+a['deposit']; profit=amount-a['cost']-a['deposit']
        ledger(db,clock,a,'SELL_MODEL',profit=profit,detail={'observed_ask':x['ask'],'inferred_sold':units,'target':a['target'],'model_fill':'two_consecutive_quotes_no_real_execution'})
        db.execute('INSERT INTO incoming VALUES(?,?,?,?,?)',(a['id'],a['item_id'],amount,clock+int(c['mail_delay_minutes']*60),a['strategy']))
        resolve(db,a,clock,'model_sold',profit)
        db.execute('DELETE FROM paper_sale_checks WHERE lot_id=?',(a['id'],))
        db.execute('DELETE FROM inventory WHERE id=?',(a['id'],))
    for r in db.execute("SELECT * FROM inventory WHERE status='held' AND list_at<=? AND expires>?",(clock,clock)).fetchall():
        a=dict(r); dep=a['deposit'];
        if getmeta(db,'cash')<dep: continue
        ledger(db,clock,a,'LIST',-dep); db.execute("UPDATE inventory SET status='listed' WHERE id=?",(a['id'],))
    for r in db.execute("SELECT * FROM inventory WHERE status='held' AND expires<=?",(clock,)).fetchall():
        a=dict(r); # retain expired inventory; never silently liquidate
        resolve(db,a,clock,'not_listed',0)
    direct={a['id']:a for a in old.candidates(m,c)}; proposals=[]
    # Only imported hourly histories qualify for daily patterns.
    # Completed prior local days only; never today's partial prices.
    imported={r[0] for r in db.execute('SELECT item_id FROM import_log WHERE success>0')}
    daily_plans={i:daily.analyse(db,i,t,c,source) for i in imported.intersection(m)}
    hour=local(clock,c).hour
    for i,x in m.items():
        ask=x.get('ask'); v=x.get('vol24'); depth=x.get('depth5'); ven=x.get('vendor'); ask2=x.get('ask2')
        common=not x.get('nc') and x.get('cls') in ('Trade Goods','Consumable','Consumables') and all(type(n) is int for n in (ask,v,depth,ven,ask2)) and ask>0 and depth>0 and ven>=0 and v>=c['min_daily_volume'] and x.get('flowHours',0) is not None and x.get('flowHours',0)>=12 and ask2>=ask
        if not common:
            decision(db,clock,t,i,'screen','SKIP','quality/liquidity/depth',vid,ask=ask,details={'vol24':v,'depth5':depth,'ask2':ask2}); continue
        before_proposals=len(proposals)
        timing=daily.opportunity(daily_plans.get(i),ask,hour,c,ven) if i in daily_plans else None
        signals=([timing] if timing else [])+([('direct',direct[i]['target'],0,.55,{'baseline':'24h provider sparkline'})] if i in direct else [])+research(db,i,x,t,c,source)
        for strategy,target,hold,confidence,detail in signals:
            if hold>=c['max_hold_hours']:
                decision(db,clock,t,i,strategy,'SKIP','holding horizon limit',vid,ask,target,depth,confidence=confidence,details=detail); continue
            proceeds=target-math.ceil(target*c['cut_pct']/100); dep=math.ceil(ven*c['deposit_vendor_pct']/100); roi=(proceeds-ask-dep)/ask*100
            detail.update({'vol24':v,'depth5':depth,'deposit_per_unit':dep,'hold_hours':hold,'fee_pct':c['cut_pct'],'net_sale_per_unit':proceeds})
            min_roi=c['daily_min_net_roi_pct'] if strategy=='daily' else c['min_roi_pct']
            if roi<min_roi:
                decision(db,clock,t,i,strategy,'SKIP','minimum net ROI incl deposit risk',vid,ask,target,depth,roi,confidence,detail); continue
            qty=(min(depth,max(1,v//6)) if strategy=='daily' else
                 depth if strategy=='direct' else min(depth if ask2*100>ask*105 else 1,max(1,v//24)))
            # Rank by expected NET copper after fees, adjusted for confidence.
            item_pct=c['daily_item_pct'] if strategy=='daily' else c['max_item_pct']
            equity=totals(db)['equity']
            rank_qty=min(qty,int(equity*item_pct/100/(ask+dep)))
            value=max(0,proceeds-ask-dep)*max(0,rank_qty)
            score=value*confidence/(1+hold/24)
            proposals.append((score,i,strategy,target,hold,confidence,detail,ask,qty,dep,proceeds,roi))
        if i not in direct and len(proposals)==before_proposals: decision(db,clock,t,i,'screen','SKIP','no eligible signal',vid,ask=ask)
    count=0
    for score,i,strategy,target,hold,confidence,detail,ask,qty,dep,proceeds,roi in sorted(proposals,reverse=True,key=lambda p:(p[0],-p[1],p[2])):
        a=totals(db); reason=None
        exposure=db.execute('SELECT COALESCE(SUM(cost+deposit),0) FROM inventory WHERE strategy=?',(strategy,)).fetchone()[0]+db.execute('SELECT COALESCE(SUM(amount),0) FROM incoming WHERE strategy=?',(strategy,)).fetchone()[0]
        item_limit=c['daily_item_pct'] if strategy=='daily' else c['max_item_pct']
        strategy_limit=c['daily_capital_pct'] if strategy=='daily' else c['strategy_weights'][strategy]
        # Scale proposal quantities to available funds rather than reject
        # large high-profit opportunities. Deposits and cash reserve count.
        allowed=max(0,min(a['equity']*item_limit/100,
                          a['equity']*strategy_limit/100-exposure,
                          a['cash']-a['equity']*c['reserve_pct']/100))
        original_qty=qty
        qty=min(qty,math.floor(allowed/(ask+dep))) if ask+dep>0 else 0
        cost=ask*qty; deposit=dep*qty
        detail['proposed_qty']=original_qty
        detail['allocated_copper']=cost+deposit
        if db.execute('SELECT 1 FROM inventory WHERE item_id=? UNION SELECT 1 FROM incoming WHERE item_id=?',(i,i)).fetchone(): reason='item occupied'
        elif count>=c['max_purchases_per_cycle']: reason='cycle limit'
        elif qty<=0: reason='allocation / reserve / strategy cap'
        did=decision(db,clock,t,i,strategy,'SKIP' if reason else 'BUY_MODEL',reason or 'eligible paper order',vid,ask,target,qty,roi,confidence,detail)
        if reason: continue
        lot=dict(id=uuid.uuid4().hex,item_id=i,name=m[i]['name'],strategy=strategy,qty=qty,cost=cost,deposit=deposit,target=target,proceeds=proceeds,bought=clock,list_at=clock+int(hold*3600),expires=clock+int((hold+c['auction_hours'])*3600),status='listed' if hold==0 else 'held',decision_id=did)
        db.execute('INSERT INTO inventory VALUES(:id,:item_id,:name,:strategy,:qty,:cost,:deposit,:target,:proceeds,:bought,:list_at,:expires,:status,:decision_id)',lot)
        # Held lots pay deposit only when listed; cash checked again then.
        ledger(db,clock,lot,'BUY_MODEL',-cost-(deposit if hold==0 else 0),detail=detail)
        db.execute('INSERT INTO predictions(decision_id,t,horizon,target,expected_profit,confidence) VALUES(?,?,?,?,?,?)',(did,clock,lot['expires'],target,proceeds*qty-cost,confidence)); count+=1
    setmeta(db,'last_trade_snapshot',t); mark_cash(db,clock); return True

def import_population(db,path):
    rows=csv_rows(path); count=0
    with db:
        for r in rows:
            if r['market']!=MARKET: raise ValueError('Population wrong market')
            t=ts(r['observed_at']); a,b,n=int(r['level_min']),int(r['level_max']),int(r['characters']); src=r['source'].strip()
            if not 1<=a<=b<=60 or n<0 or not src or t>old.now(): raise ValueError('Invalid census row')
            db.execute('INSERT OR REPLACE INTO population_history VALUES(?,?,?,?,?)',(t,a,b,n,src)); count+=1
    return count

def import_events(db,path):
    with db:
        for r in csv_rows(path): db.execute('INSERT OR REPLACE INTO game_events VALUES(?,?,?,?)',(ts(r['at']),r['name'],r['kind'],r['source']))

def population_radar(db,t):
    # Group changes are a proxy for progression, NOT a forecast of item price.
    rows=db.execute('SELECT * FROM population_history WHERE t<=? ORDER BY t',(t,)).fetchall(); buckets=defaultdict(dict)
    for r in rows: buckets[(r['level_min'],r['level_max'])][r['t']]=r['characters']
    out=[]
    for (a,b),series in buckets.items():
        times=sorted(series); last=times[-1]; older=[x for x in times if x<=last-3*86400]; prev=older[-1] if older else None
        n=series[last]; growth=(n/series[prev]-1)*100 if prev and series[prev]>0 else None
        ids=db.execute('SELECT id,name FROM items WHERE group_name=?',(f'{a}-{b}' if a!=b else str(a),)).fetchall()
        for i,name in ids:
            if growth is not None: db.execute('INSERT OR REPLACE INTO research_signals VALUES(?,?,?,?)',(t,i,'population',D({'group':f'{a}-{b}','growth_pct':growth,'latest':last,'baseline':prev,'advisory_only':True})))
        out.append((f'{a}-{b}',n,round(growth,1) if growth is not None else '—',old.stamp(last),', '.join(x[1] for x in ids)))
    return out

def recipe_update(db,clock):
    if clock-getmeta(db,'recipe_attempt',0)<7*86400:return
    setmeta(db,'recipe_attempt',clock); db.commit()
    try:
        data=json.loads(old.get(BASE+'/recipes')); assert isinstance(data['recipes'],list)
        with db:
            for r in data['recipes']:
                db.execute('INSERT OR REPLACE INTO crafting_recipes VALUES(?,?,?)',(r['id'],D(r),clock))
            setmeta(db,'vendor_prices',data.get('vendor',{}))
    except Exception as e:
        with db: log(db,clock,'recipes',e)

def crafting_radar(db,m,c,t):
    out=[]; vendors=getmeta(db,'vendor_prices',{})
    for row in db.execute('SELECT payload FROM crafting_recipes'):
        try:
            r=json.loads(row[0]); result=m.get(r.get('item')); qty=r['qty']; costs=[]
            if not result or type(qty) is not int or qty<=0 or type(result.get('ask')) is not int:continue
            for i,n in r['r']:
                x=m.get(i,{}); options=[p for p in (x.get('ask'),vendors.get(str(i))) if type(p) is int and p>0];
                if not options or type(n) is not int or n<=0:break
                costs.append(min(options)*n)
            else:
                cost=sum(costs); value=result['ask']*qty; profit=value-math.ceil(value*c['cut_pct']/100)-cost
                if cost>0 and profit>0:
                    out.append((r['id'],r['name'],r['prof'],cost,profit,profit/cost*100,result.get('vol24')))
        except (KeyError,TypeError,ValueError): continue
    out.sort(key=lambda x:-x[4]); return out[:30]

def capture_local(db,c,clock):
    a,msg=old.load_local(c)
    for k in ('wallet','mail','scan'):
        if k not in a:continue
        v=a[k]; t=v[0]
        if t>clock+300: log(db,clock,'local','Future timestamp');continue
        # Own read-only export; scan raw values intentionally separate from trusted market price history.
        db.execute('INSERT OR IGNORE INTO local_exports VALUES(?,?,?)',(t,k,D(v)))
        if k=='wallet': msg+=f' | wallet {old.gold(v[1])} ({v[2]}, {old.stamp(t)})'
        if k=='mail': msg+=f' | incoming {old.gold(v[1])}; klaar {old.gold(v[2])} ({old.stamp(t)})'
        if k=='scan': msg+=f' | {len(v[3])} items in raw scan ({old.stamp(t)}); niet gebruikt voor modelorders'
    p,_=old.saved_path(c)
    if p:
        try:
            if p.stat().st_size<=30_000_000:
                text=p.read_text(encoding='utf-8',errors='replace')
                n=targeted.import_log(db,text,clock)
                msg+=f' | {n} nieuwe gerichte observaties'
                for k,(t,v) in coach.extras(text).items():
                    if 0<t<=clock+300:
                        db.execute('INSERT OR IGNORE INTO local_exports VALUES(?,?,?)',(t,k,D(v)))
                        if k=='browseSummary':
                            msg+=f' | Auctionator summary: {v.count(";")} itemregels ({old.stamp(t)}), alleen marktobservaties'
        except OSError as e: log(db,clock,'coach export',e)
    # GetMoney can become 0g during logout teardown; don't silently treat
    # that as confirmed real budget when the coach recently saw a balance.
    recent=db.execute("SELECT t,payload FROM local_exports WHERE kind='coach' ORDER BY t DESC LIMIT 1").fetchone()
    wallet=db.execute("SELECT t,payload FROM local_exports WHERE kind='wallet' ORDER BY t DESC LIMIT 1").fetchone()
    if recent and wallet and 0<=wallet['t']-recent['t']<=120:
        try:
            values=json.loads(recent['payload']).split('|')
            amount=int(values[2])
            saved=json.loads(wallet['payload'])[1]
            if saved==0 and amount>0:
                msg+=f' | WAARSCHUWING: wallet-export 0g bij logout; coach registreerde {old.gold(amount)}. Niet gebruiken als live koopbudget.'
        except (TypeError,ValueError,KeyError,IndexError): pass
    return msg

def demo(db,c,t,step):
    # 35 full synthetic days, varied relative time/weekday; no contamination with actual data.
    ids=[2589,2840,765,4306,3356,3575]; names=['Linen Cloth','Copper Bar','Silverleaf','Silk Cloth','Kingsblood','Iron Bar']
    def data(i,j,q):
        d=local(q,c); base=1200+j*200; mult=(.72 if 5<=d.hour<=10 else 1.30 if 18<=d.hour<=22 else 1.0)*(1.12 if reset_bucket(q,c) in (0,1) else .93)
        return max(1,int(base*mult))
    if not getmeta(db,'demo_seeded'):
        for j,i in enumerate(ids):
            item(db,i,{'name':names[j],'cls':'Trade Goods','vendor':10})
            for q in range(t-35*86400,t,3600): obs(db,i,q,{'ask':data(i,j,q),'sold':100,'depth5':5,'listed':200},'demo')
        setmeta(db,'demo_seeded',True)
    m={}
    for j,i in enumerate(ids):
        a=data(i,j,t); m[i]=dict(id=i,name=names[j],cls='Trade Goods',nc=False,ask=a,ask2=a+700,depth5=5,listed=200,vol24=2400,flowHours=24,vendor=10,history=[data(i,j,q) for q in range(t-23*3600,t+1,3600)],volume_history=[100]*24,sold=100)
    return m

def history_backtest(db,c):
    # Price-target hit test on imported hourly observations; no virtual fill or capital claims.
    result=defaultdict(lambda:[0,0,0,0]); rows=db.execute('SELECT DISTINCT item_id,source FROM price_history').fetchall()
    for i,src in rows:
        series=db.execute('SELECT t,ask,sold FROM price_history WHERE item_id=? AND source=? AND ask>0 ORDER BY t',(i,src)).fetchall()
        if len(series)<48:continue
        # Evaluate once/day per item to avoid excessive overlap.
        seen=set()
        for t,ask,sold in series:
            day=local(t,c).date()
            if day in seen or t>series[-1][0]-24*3600:continue
            seen.add(day); base,h,w=profile(db,i,t,c,src)
            if not base:continue
            for kind,buckets,min_n,period,scale,here in [('intraday',h,c['min_pattern_days'],24,1,local(t,c).hour),('weekly',w,c['min_pattern_weeks'],7,24,reset_bucket(t,c))]:
                opts=[(k,n,r) for k,(n,r) in buckets.items() if k!=here and n>=min_n]
                if not opts or here not in buckets or buckets[here][0]<min_n:continue
                k,n,r=max(opts,key=lambda a:a[2]); target=int(base*r); hold=(k-here)%period*scale; end=t+(hold+c['auction_hours'])*3600
                if end>series[-1][0] or (target*(1-c['cut_pct']/100)-ask)/ask*100<c['min_roi_pct']:continue
                future=[p for q,p,s in series if t+hold*3600<=q<=end and q>t]
                a=result[kind]; a[0]+=1
                if len(future)<2:a[3]+=1;continue
                a[1]+=1; a[2]+=int(max(future)>=target)
    return {'model':'price target only; not fills/profit; retrospective imported TK data','strategies':{k:{'signals':a[0],'evaluated':a[1],'target_hits':a[2],'missing_followup':a[3]} for k,a in result.items()}}

def replay(db,c):
    # Actual recorded snapshots; never copy future historical or population data into replay.
    with tempfile.TemporaryDirectory() as f:
        out=connect(pathlib.Path(f)/'replay.sqlite'); vid=register(out,c); n=0
        for r in db.execute('SELECT * FROM market_snapshots ORDER BY t'):
            t=r['t']; m={int(k):v for k,v in json.loads(r['payload']).items()}; clock=max(t,r['received']); save_market(out,t,m,clock,r['source']); settle(out,clock); cycle(out,c,t,m,clock,vid,r['source']); mark_cash(out,clock); n+=1
        result={'model':'forward-only replay of saved market snapshots, no historical bootstrap','snapshots':n,**totals(out)}; out.close();return result

def export(db,folder,c):
    path=folder/'ForeverTrader-Diagnostics.zip'; tmp=path.with_suffix('.tmp'); clean={k:v for k,v in c.items() if k not in ('wow_folder','account_folder')}
    with tempfile.TemporaryDirectory() as f:
        p=pathlib.Path(f)/'trader.sqlite'; dst=sqlite3.connect(p); db.commit(); db.backup(dst); dst.close()
        with zipfile.ZipFile(tmp,'w',zipfile.ZIP_DEFLATED) as zz:
            zz.write(p,'trader.sqlite'); zz.writestr('config.json',D(clean)); zz.writestr('version.json',D({'version':VERSION,'market':MARKET,'exported_at':old.now(),'mode':folder.name}))
            for name in ['trade_decisions','predictions','transactions','cashflow','error_logs','backtest_results','import_log','population_history','research_signals','local_exports','targeted_observations']:
                cur=db.execute(f'SELECT * FROM {name}'); buff=io.StringIO(); w=csv.writer(buff); w.writerow([a[0] for a in cur.description]); w.writerows(cur); zz.writestr(name+'.csv',buff.getvalue())
            cur=db.execute('SELECT strategy,COUNT(*) events,SUM(profit) realized FROM transactions GROUP BY strategy'); buff=io.StringIO(); w=csv.writer(buff); w.writerow([a[0] for a in cur.description]); w.writerows(cur); zz.writestr('strategy_performance.csv',buff.getvalue())
    os.replace(tmp,path); return path

def strategy_stats(db):
    return db.execute("""SELECT d.strategy,COUNT(*) closed,SUM(actual_profit) realized,SUM(expected_profit) expected,ROUND(AVG(actual_profit-expected_profit),1) avg_error,ROUND(100.0*SUM(actual_profit)/NULLIF(SUM(d.ask*d.quantity),0),2) roi,ROUND(AVG((resolved-p.t)/3600.0),2) hours FROM predictions p JOIN trade_decisions d ON d.id=p.decision_id WHERE resolved IS NOT NULL GROUP BY d.strategy""").fetchall()

def dashboard(db,folder,c,clock,status,localmsg,m,mode):
    def table(headers,rows):return '<div class="scroll"><table><thead><tr>'+''.join(f'<th>{old.esc(x)}</th>' for x in headers)+'</tr></thead><tbody>'+''.join('<tr>'+''.join(f'<td>{old.esc(v if v is not None else "—")}</td>' for v in row)+'</tr>' for row in rows)+'</tbody></table></div>'
    a=totals(db); cards=''.join(f'<div class="metric"><small>{old.esc(k)}</small><strong>{old.gold(v)}</strong></div>' for k,v in a.items())
    coverage=db.execute('SELECT COUNT(DISTINCT item_id),COUNT(*),MIN(t),MAX(t) FROM price_history').fetchone(); num,obsn,first,last=coverage
    coverage_text=f'{num} items · {obsn} prijswaarnemingen · {old.stamp(first)} tot {old.stamp(last)}. Dekking verschilt per item.'
    dec=db.execute("SELECT d.t,COALESCE(i.name,d.item_id),strategy,action,reason,ask,target,quantity,ROUND(roi,1) FROM trade_decisions d LEFT JOIN items i ON d.item_id=i.id WHERE action!='SKIP' ORDER BY d.id DESC LIMIT 50")
    signals=db.execute("SELECT COALESCE(i.name,d.item_id),strategy,reason,ask,target,ROUND(roi,1),ROUND(confidence,2) FROM trade_decisions d LEFT JOIN items i ON d.item_id=i.id WHERE roi IS NOT NULL ORDER BY d.id DESC LIMIT 80")
    strat=db.execute('SELECT strategy,COUNT(*),SUM(profit),SUM(CASE WHEN action=\'SELL_MODEL\' THEN 1 ELSE 0 END) FROM transactions GROUP BY strategy').fetchall()
    pat=db.execute('''SELECT i.name,p.kind,p.bucket,p.n,ROUND(p.ratio,3) FROM patterns p JOIN items i ON p.item_id=i.id WHERE p.asof=(SELECT MAX(asof) FROM patterns q WHERE q.item_id=p.item_id AND q.kind=p.kind) ORDER BY p.n DESC,p.item_id,p.kind,p.bucket LIMIT 180''')
    back=db.execute('SELECT kind,details FROM backtest_results ORDER BY id DESC LIMIT 4'); errors=db.execute('SELECT t,component,message FROM error_logs ORDER BY id DESC LIMIT 10'); imp=db.execute('SELECT item_id,detail,success FROM import_log ORDER BY attempt DESC LIMIT 30')
    perf=strategy_stats(db); pp=population_radar(db,clock); cr=crafting_radar(db,m,c,clock) if clock-getmeta(db,'last_trade_snapshot',0)<=c['max_snapshot_age_minutes']*60 else []; ev=db.execute('SELECT t,name,kind,source FROM game_events WHERE t>=? ORDER BY t LIMIT 20',(clock-7*86400,))
    targetrows=db.execute('SELECT t,item_id,kind,ask,units,rows FROM targeted_observations ORDER BY t DESC,rowid DESC LIMIT 100').fetchall()
    # Day-planning is informational even with no eligible live trades.
    # Complete past days only; 3.3 does not promise profit from a daily spread.
    dailyrows=[]
    imported=[r[0] for r in db.execute('SELECT item_id FROM import_log WHERE success>0 ORDER BY item_id')]
    planned_ids=list(dict.fromkeys(list(c['watchlist'])+imported))[:100]
    src='demo' if mode=='demo' else 'tk'
    hour=local(clock,c).hour
    for i in planned_ids:
        p=daily.analyse(db,i,clock,c,src)
        if not p:continue
        ask=m.get(i,{}).get('ask')
        if not p['eligible']: state='Onvoldoende herhaalbaar'
        elif p['buy_start']<=hour<p['buy_end'] and type(ask) is int and ask<=p['ceiling'] and clock-getmeta(db,'last_trade_snapshot',0)<5400:
            state='KOOPVENSTER: live AH-prijs controleren'
        elif p['buy_start']<=hour<p['buy_end']:state='Koopvenster, maar prijs niet bevestigd'
        elif hour>=p['sell_start']:state='Verkoopvenster (alleen bij echte voorraad)'
        elif hour<p['buy_start']:state='Wachten op koopvenster'
        else:state='Koopvenster voorbij'
        name=m.get(i,{}).get('name') or (db.execute('SELECT name FROM items WHERE id=?',(i,)).fetchone() or [i])[0]
        dailyrows.append((p['eligible'],p['conservative_net_roi'],(
            name,i,f"{p['buy_start']:02d}:00–{p['buy_end']:02d}:00",
            f"{p['sell_start']:02d}:00–{p['sell_end']:02d}:00",
            old.gold(p['ceiling']),old.gold(p['target']),p['samples'],
            f"{100*p['win_rate']:.0f}%",f"{p['conservative_net_roi']:+.1f}%",
            state)))
    dailyrows.sort(key=lambda x:(x[0],x[1]),reverse=True)
    dailytable=table(['Item','ID','Inkoop (NL)','Verkoop (NL)','Max koop/st','Doel/st','Dagen','Winrate','Conservatieve ROI na cut','Advies'],
                     [r[2] for r in dailyrows]) if dailyrows else '<p>Nog niet genoeg volledige dagen met uurdata. Historische imports lopen door.</p>'
    eligible_count=sum(bool(r[0]) for r in dailyrows)
    daynotice=f"{eligible_count} van {len(dailyrows)} items voldoen aan de historische daghandelfilter. Dit zijn geen gegarandeerde AH-verkopen."
    body=f'''<!doctype html><html lang="nl"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><meta http-equiv="refresh" content="30"><title>ForeverTrader 3.3.0</title><style>body{{font:15px system-ui;background:#101720;color:#e7eef6;margin:auto;padding:24px;max-width:1450px}}h1{{font-size:32px;margin:0}}h2{{font-size:19px;margin-top:28px}}p,small{{color:#a8b6c7}}a{{color:#90caf9}}.grid{{display:grid;grid-template-columns:repeat(auto-fit,minmax(155px,1fr));gap:10px}}.metric{{padding:14px;background:#202c3a;border-radius:8px}}strong{{display:block;color:#e9c172;font-size:22px}}.scroll{{overflow:auto;max-height:450px}}table{{border-collapse:collapse;width:100%;background:#192432}}th,td{{padding:9px;border-bottom:1px solid #334155;text-align:left;white-space:nowrap}}th{{position:sticky;top:0;background:#263547}}.notice{{border-left:4px solid #e9c172;padding:12px;background:#1b2936}}nav a{{margin-right:14px}}</style><h1>ForeverTrader 3.3.0</h1><p>EU PvP Alliance · {old.esc('FICTIEVE DEMO' if mode=='demo' else 'PAPER TRADING · geen echte orders')} · {old.stamp(clock)}</p><nav><a href="#signals">Signalen</a><a href="#patterns">Patronen</a><a href="#research">Research</a><a href="#diagnostic">Diagnostiek</a></nav><p class="notice">{old.esc(status)}<br>{old.esc(localmsg)}<br>{old.esc(coverage_text)}</p><div class="grid">{cards}</div>{coach.panel(db,c,clock,mode)}<p class="notice"><b>LET OP:</b> Paper winst is uitsluitend boekwinst uit een simulatie, niet echt verdiend gold. Vanaf v3.2 vereisen modelverkopen twee opeenvolgende marktsnapshots op of boven de doelprijs; dat bewijst nog steeds geen echte verkoop. Oude paper trades uit eerdere versies blijven in je database staan. Onverkochte voorraad staat tegen kostprijs.</p><h2 id="daily">Dagplanning: goedkoop inkopen, later verkopen</h2><p>Vaste lokale tijdvensters (Europe/Amsterdam) uit gekoppelde prijswaarnemingen van minimaal vijf volledige voorgaande dagen. Winrate en netto prijsverschil komen uit <b>historische vraagprijzen</b>, niet uit bevestigde aankopen of verkopen. Voor echte gold: actuele AH-prijs en beschikbare aantallen altijd eerst controleren. Strategie 'daily' mag in paper maximaal {c['daily_capital_pct']}% van equity gebruiken, met maximaal {c['daily_item_pct']}% per item en {c['reserve_pct']}% cashreserve.</p><p>{old.esc(daynotice)}</p>{dailytable}<h2>Gerichte itemzoekopdrachten</h2><p>Eigen AH-observaties, apart van publieke historie. Bij reload/logout naar desktop. Geen bewezen verkoopvolume of paper fills.</p>{table(['Tijd UTC','ItemID','Type','Laagste / stuk c','Aantal','Regels'],targetrows)}<h2 id="signals">Handelsbeslissingen</h2>{table(['Tijd','Item','Strategie','Actie','Reden','Koop c','Doel c','Aantal','ROI %'],dec)}<h2>Recente beoordeelde signalen</h2>{table(['Item','Strategie','Reden','Koop c','Doel c','ROI %','Heuristische score'],signals)}<h2>Voorraad</h2>{table(['Item','Strategie','Aantal','Kostprijs','Doel c','Status','Plaatsen','Verloopt'],[(r['name'],r['strategy'],r['qty'],old.gold(r['cost']),r['target'],r['status'],old.stamp(r['list_at']),old.stamp(r['expires'])) for r in db.execute('SELECT * FROM inventory')])}<h2>Incoming gold</h2>{table(['ItemID','Bedrag','Verwacht','Strategie'],[(r['item_id'],old.gold(r['amount']),old.stamp(r['eta']),r['strategy']) for r in db.execute('SELECT * FROM incoming')])}<h2>Resultaat per strategie</h2>{table(['Strategie','Events','Gerealiseerd copper','Modelverkopen'],strat)}<h2>Voorspelling versus resultaat (afgeronde modelorders)</h2>{table(['Strategie','Afgerond','Werkelijk c','Verwacht c','Gem. fout c','ROI %','Gem. uren'],perf)}<h2 id="patterns">Prijsprofielen (ratio t.o.v. baseline)</h2><p>Uur 0–23 lokale tijd; weekly bucket 0 = resetdag. Alleen eerdere afgeronde periodes.</p>{table(['Item','Model','Bucket','Samples','Ratio'],pat)}<h2 id="research">Populatie radar</h2><p>CSV-import, geen directe live census-API. Verandering in waargenomen characters, geen bewijs van vraag.</p>{table(['Level','Characters','Groei %','Laatste','Gekoppelde items'],pp)}<h2>Content kalender</h2>{table(['Tijd UTC','Event','Type','Bron'],ev)}<h2>Crafting radar (indicatief)</h2>{table(['Recept ID','Recept','Profession','Kosten c','Winst c','ROI %','Vol24'],[(i,n,p,cost,profit,round(roi,1),vol) for i,n,p,cost,profit,roi,vol in cr])}<h2>Backtests</h2>{table(['Type','Resultaat'],back)}<h2 id="diagnostic">Historische imports</h2>{table(['ItemID','Status','Succes UTC'],imp)}<h2>Fouten</h2>{table(['Tijd UTC','Component','Melding'],errors)}<h2>Diagnostiek</h2><p>Start EXPORT-DIAGNOSTICS.bat voor een consistente ZIP van database en logs. Een bestaande export: <a href="ForeverTrader-Diagnostics.zip">download</a> (alleen na export). Bronnen: <a href="https://auctionhouse.tk.gg/data/">TK Auction House</a> · <a href="https://classicarmory.gg/forever/census">Classic Armory Census</a>. Externe gegevens zijn niet realtime. Prijzen in copper tenzij anders vermeld.</p></html>'''
    old.atomic(folder/'dashboard.html',body)

def market_wait_status(db, clock):
    """Show the persisted fetch cooldown and last result, even after a restart.

    The whole-market provider permits hourly polling; don't silently retry it on
    every 30-second dashboard refresh or after restarting the application.
    """
    last_attempt = getmeta(db, 'market_attempt', 0)
    last_error = getmeta(db, 'market_last_error', '')
    latest = db.execute('SELECT t FROM market_snapshots ORDER BY t DESC LIMIT 1').fetchone()
    last = f"Laatste opgeslagen snapshot: {old.stamp(latest['t'])}" if latest else 'Nog geen opgeslagen marktdata'
    if last_attempt and clock < last_attempt + 3600:
        next_at = old.stamp(last_attempt + 3600)
        if last_error:
            return f"{last} | Laatste API-fout: {last_error} | Nieuwe poging: {next_at}"
        return f"{last} | Volgende API-poging: {next_at} (max. 1x/uur)"
    return f"{last} | API-aanvraag staat klaar"

def main():
    p=argparse.ArgumentParser(); p.add_argument('--demo',action='store_true'); p.add_argument('--once',action='store_true'); p.add_argument('--no-browser',action='store_true'); p.add_argument('--ahl',action='store_true',help='legacy flag; no persistent AHledger data'); p.add_argument('--export',action='store_true'); p.add_argument('--backtest',action='store_true'); p.add_argument('--population'); p.add_argument('--events'); p.add_argument('--history-only',action='store_true'); args=p.parse_args()
    c=conf(); mode='demo' if args.demo else 'paper'; folder=ROOT/'data'/mode; db=connect(folder/'trader.sqlite'); vid=register(db,c); db.commit()
    # Read-only export can run concurrently; snapshot via SQLite backup. Other writers use process lock.
    if args.export: print(export(db,folder,c)); db.close();return
    lock=folder/'run.lock'
    try:
        fd=os.open(lock,os.O_CREAT|os.O_EXCL|os.O_WRONLY); os.write(fd,str(os.getpid()).encode());os.close(fd)
    except FileExistsError: db.close();raise SystemExit('Al actief. Sluit trader; verwijder run.lock uitsluitend na controle.')
    try:
        if args.population: print('Imported',import_population(db,args.population)); return
        if args.events: import_events(db,args.events); print('Events imported');return
        row=db.execute('SELECT * FROM market_snapshots ORDER BY t DESC LIMIT 1').fetchone(); m={int(k):v for k,v in json.loads(row['payload']).items()} if row else {}; status=market_wait_status(db,old.now()); opened=False
        if args.backtest:
            for kind,val in [('price_target',history_backtest(db,c)),('recorded_replay',replay(db,c))]:
                db.execute('INSERT INTO backtest_results(t,kind,details) VALUES(?,?,?)',(old.now(),kind,D(val))); print(kind,D(val))
            db.commit(); dashboard(db,folder,c,old.now(),'Backtests opgeslagen','',m,mode);db.commit(); return
        if args.history_only:
            print('Historische items geprobeerd:',import_history(db,c,m,old.now()));return
        if not args.demo and not getmeta(db,'events_seeded'):
            import_events(db,ROOT/'examples'/'events.csv'); setmeta(db,'events_seeded',True);db.commit()
        while True:
            clock=old.now(); source='demo' if args.demo else 'tk'; fresh=False
            if args.demo:
                clock=max(clock,getmeta(db,'demo_clock',0)+3600); setmeta(db,'demo_clock',clock); t=clock; m=demo(db,c,t,0); fresh=save_market(db,t,m,clock,source);status='Gesimuleerde markt, 1 uur per stap'
            elif clock-getmeta(db,'market_attempt',0)>=3600:
                setmeta(db,'market_attempt',clock);db.commit()
                try:
                    t,new=old.parse_market(json.loads(old.get(old.URL))); clock=old.now(); fresh=save_market(db,t,new,clock,source)
                    if fresh and t>=getmeta(db,'last_trade_snapshot',0):m=new
                    else:fresh=False
                    status=f"Snapshot {old.stamp(t)} | {len(new)} items | {'new' if fresh else 'duplicate/old'}"
                    setmeta(db,'market_last_error','')
                    db.commit()
                except Exception as e:
                    db.rollback(); log(db,clock,'market',e); setmeta(db,'market_last_error',str(e)[:300]);status=f'Markt ophalen mislukt: {e} | Volgende poging na 1 uur';db.commit();fresh=False
            else:
                status=market_wait_status(db,clock)
            try:
                with db:
                    settle(db,clock)
                    if fresh: cycle(db,c,t,m,clock,vid,source)
                    mark_cash(db,clock)
            except Exception as e:
                db.rollback();log(db,clock,'paper engine',e);db.commit();status+=' | engine error; no orders committed'
            if fresh and not args.demo:
                import_history(db,c,m,clock); recipe_update(db,clock)
            with db:
                lm='Demo, geen echte WoW-data' if args.demo else capture_local(db,c,clock)
                dashboard(db,folder,c,clock,status,lm,m,mode)
            print(old.stamp(clock),status,flush=True)
            if not opened and not args.no_browser:webbrowser.open((folder/'dashboard.html').as_uri());opened=True
            if args.once:break
            time.sleep(15 if args.demo else 30)
    except KeyboardInterrupt: print('Gestopt; database bewaard.')
    finally:db.close();lock.unlink(missing_ok=True)
if __name__=='__main__':main()
