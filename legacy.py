"""ForeverTrader: read-only market data, local paper portfolio. Python 3.10+."""
import argparse, datetime as dt, html, json, math, os, pathlib, re, sqlite3, statistics, time, urllib.request, webbrowser
from collections import defaultdict
ROOT = pathlib.Path(__file__).resolve().parent
MARKET = 'eu-2-110'
URL = 'https://auctionhouse.tk.gg/api/m/' + MARKET
AHL = 'https://api.ahledger.com/v1/pricetable/forever.pvp.alliance.eu'
CRAFT_URL = 'https://api.ahledger.com/v1/crafting/forever.pvp.alliance.eu'

def now(): return int(time.time())
def gold(c): return f'{c/10000:,.4f}g'
def stamp(t): return dt.datetime.fromtimestamp(t).astimezone().strftime('%d-%m %H:%M:%S') if t else 'onbekend'
def esc(s): return html.escape(str(s))
def get(url):
    req=urllib.request.Request(url, headers={'User-Agent':'ForeverTrader/3.0 (personal research)', 'Accept':'application/json, text/plain'})
    with urllib.request.urlopen(req, timeout=25) as r:
        data=r.read(20_000_001)
        if len(data)>20_000_000: raise ValueError('Response too large')
        return data

def parse_market(d):
    h=d['house']
    if (h.get('key'),h.get('region'),h.get('faction'),h.get('grp')) != (MARKET,'eu','alliance',1): raise ValueError('Market mismatch')
    t=int(d['t'])//1000
    if t<=0 or t>now()+300: raise ValueError('Invalid snapshot timestamp')
    fields=d['f']; required={'ask','ask2','listed','depth5','vol24','flowHours'}
    if not required.issubset(fields) or len(set(fields))!=len(fields): raise ValueError('Unknown API schema')
    items={}
    for x in d['items']:
        if len(x['o'])!=len(fields): raise ValueError('Invalid market row')
        a=dict(zip(fields,x['o'])); i=int(x['id'])
        items[i]={**a,'id':i,'name':x.get('name') or f'Item {i}','cls':x.get('cls'),'lvl':x.get('lvl'),'nc':bool(x.get('nc')),'vendor':x.get('sell'),'history':x.get('s') or [],'volume_history':x.get('v') or []}
    if not items: raise ValueError('Empty snapshot')
    return t,items

def parse_ahl(text):
    lines=text.strip().splitlines(); h=lines[0].split('|')
    if len(h)!=4 or h[:2]!=['AHL1','forever/pvp/alliance/eu']: raise ValueError('Unknown AHledger format or market')
    t=int(h[2]); rows={}
    for line in lines[1:]:
        a=line.split(':')
        if len(a)!=9: raise ValueError('Unknown AHledger row')
        vals=[int(v) if v else None for v in a]
        rows[vals[0]]={'median':vals[1],'min':vals[2],'median7d':vals[4],'median30d':vals[5],'daily':None if vals[8] is None else vals[8]/10}
    if len(rows)!=int(h[3]): raise ValueError('Incomplete AHledger table')
    return t,rows

def parse_crafting(d):
    if d.get('market')!='forever.pvp.alliance.eu': raise ValueError('Craft market mismatch')
    if d.get('marketStatus')!='scanned': return None,[]
    t=int(dt.datetime.fromisoformat(d['pricesAsOf'].replace('Z','+00:00')).timestamp())
    rows=[]
    for x in d['recipes']:
        recipe=x.get('recipe') or {}; result=x.get('result') or {}; cost=x.get('cost'); profit=x.get('margin')
        if type(cost) is not int or type(profit) is not int or cost<=0 or profit<=0 or x.get('unpriced'): continue
        rows.append(dict(name=recipe.get('name','?'),profession=recipe.get('profession','?'),skill=recipe.get('skillRequired'),id=result.get('id'),cost=cost,profit=profit,roi=profit/cost*100))
    return t,sorted(rows,key=lambda x:-x['profit'])[:30]

def saved_path(c):
    if not c['wow_folder']: return None,'WoW-pad nog niet ingesteld'
    p=pathlib.Path(c['wow_folder']).expanduser(); p=p/'_forever_' if (p/'_forever_').is_dir() else p
    accounts=p/'WTF'/'Account'
    if c['account_folder']:
        a=c['account_folder']
        if pathlib.Path(a).name!=a or a in ('.','..'): return None,'Ongeldig accountfolder'
        files=[accounts/a/'SavedVariables'/'ForeverTrader.lua']
    else: files=list(accounts.glob('*/SavedVariables/ForeverTrader.lua'))
    files=[f for f in files if f.is_file()]
    if len(files)!=1: return None,'Geen export gevonden of meerdere accounts; stel account_folder in'
    return files[0],''

def load_local(c):
    p,msg=saved_path(c)
    if not p: return {},msg
    try:
        if p.stat().st_size>30_000_000: raise ValueError('File too large')
        text=p.read_text(encoding='utf-8',errors='replace')
        def field(k):
            m=re.search(r'^\s*\["'+k+r'"\]\s*=\s*"([^"\\]*)"\s*,?\s*$',text,re.M)
            return m.group(1) if m else None
        if field('schema')!='FT1': raise ValueError('Unknown export schema')
        wallet=field('wallet'); scan=field('scan'); mail=field('mail')
        out={}
        if wallet:
            t,g,faction,region=wallet.split('|'); out['wallet']=(int(t),int(g),faction,region)
        if mail:
            t,pending,ready=map(int,mail.split('|')); out['mail']=(t,pending,ready)
        if scan:
            header,*entries=scan.split(';'); t,faction,region,n=header.split('|'); book=defaultdict(list)
            if len(entries)!=int(n): raise ValueError('Incomplete local scan')
            for row in entries:
                i,q,cost=map(int,row.split(':'))
                if min(i,q,cost)<=0: raise ValueError('Bad local listing')
                book[i].append((q,cost))
            out['scan']=(int(t),faction,region,book)
        return out,'Export gelezen (alleen ter controle; geen live transacties)'
    except (OSError,ValueError,TypeError) as e: return {},f'Export fout: {e}'

def validate(c):
    for k in ('starting_gold','min_daily_volume','max_snapshot_age_minutes','max_local_scan_age_minutes','mail_delay_minutes','auction_hours','max_purchases_per_cycle'):
        if not isinstance(c[k],(int,float)) or not math.isfinite(c[k]) or c[k]<=0: raise ValueError(k)
    for k in ('reserve_pct','max_item_pct','min_roi_pct','cut_pct','deposit_vendor_pct'):
        if not isinstance(c[k],(int,float)) or not math.isfinite(c[k]) or not 0<=c[k]<=100: raise ValueError(k)
    if c['cut_pct']>=100 or c['max_item_pct']==0: raise ValueError('Invalid cut/exposure')
    if c['local_scan_paper_enabled'] is not False: raise ValueError('Local scan trading disabled in v1; first validate unit/market on client')

def initial(c):
    cash=round(c['starting_gold']*10000)
    return dict(cash=cash,starting=cash,demo_step=0,lots=[],incoming=[],realized=0,loss=0,events=[],last_snapshot=0)

def event(s,t,msg): s['events']=([{'t':t,'msg':msg}]+s['events'])[:300]
def net(s): return s['cash']+sum(x['amount'] for x in s['incoming'])+sum(x['cost']+x['deposit'] for x in s['lots'])
def settle(s,t):
    for p in s['incoming'][:]:
        if p['eta']<=t:
            s['cash']+=p['amount']; s['incoming'].remove(p); event(s,t,f"Mail ontvangen (paper): {gold(p['amount'])}")
    for x in s['lots']:
        if x['status']=='listed' and x['expires']<=t:
            s['loss']+=x['deposit']; s['realized']-=x['deposit']; event(s,t,f"Verlopen: {x['name']} • deposit verloren {gold(x['deposit'])}"); x['deposit']=0; x['status']='inventory'

def candidates(items,c):
    result=[]
    for i,x in items.items():
        if x['nc'] or x['cls'] not in ('Trade Goods','Consumable','Consumables'): continue
        a,b,d,v,fh,ven=(x.get(k) for k in ('ask','ask2','depth5','vol24','flowHours','vendor'))
        if any(type(n) is not int for n in (a,b,d,v,fh,ven)) or min(a,b,d)<=0 or ven<0 or v<c['min_daily_volume'] or fh<12: continue
        hist=[p for p in x['history'][:-1] if type(p) is int and p>0]
        if len(hist)<8 or b*100<=a*105: continue
        # When next ask > 5% higher, depth5 represents the entire cheapest tier.
        target=min(b-1,int(statistics.median(hist)))
        if target<=0: continue
        proceeds=target-math.ceil(target*c['cut_pct']/100)
        dep=math.ceil(ven*c['deposit_vendor_pct']/100)
        roi=(proceeds-a)/a*100
        if roi<c['min_roi_pct'] or d>max(1,v//24): continue
        result.append(dict(id=i,name=x['name'],ask=a,target=target,qty=d,vol=v,roi=roi,proceeds=proceeds,dep=dep,score=roi*min(v/24/max(d,1),4)))
    return sorted(result,key=lambda x:(-x['score'],x['id']))

def cycle(s,c,t,items,clock):
    settle(s,clock)
    if t<=s['last_snapshot'] or not 0<=clock-t<=c['max_snapshot_age_minutes']*60: return False
    # Model fills only after a later observed hour; never turn predicted listings into incoming immediately.
    for x in s['lots'][:]:
        m=items.get(x['id']); v=m['volume_history'][-1] if m and m['volume_history'] else None
        if x['status']!='listed' or not m or t-3600<x['listed_at'] or t>x['expires'] or type(v) is not int: continue
        if type(m.get('ask')) is int and m['ask']>=x['target'] and v//10>=x['qty'] and t-x['listed_at']>=3600:
            amt=x['proceeds']*x['qty']+x['deposit']; profit=amt-x['cost']-x['deposit']
            s['incoming'].append(dict(amount=amt,eta=clock+int(c['mail_delay_minutes']*60),id=x['id'])); s['realized']+=profit; s['lots'].remove(x); event(s,clock,f"Verkoop simulatie: {x['qty']}x {x['name']}, winst {gold(profit)}")
    occupied={x['id'] for x in s['lots']} | {x['id'] for x in s['incoming']}
    cap=net(s); count=0
    for x in candidates(items,c):
        if x['id'] in occupied: continue
        cost=x['qty']*x['ask']; dep=x['qty']*x['dep']; total=cost+dep
        if total>cap*c['max_item_pct']/100 or total>s['cash']-cap*c['reserve_pct']/100: continue
        s['cash']-=total; s['lots'].append(dict(id=x['id'],name=x['name'],qty=x['qty'],cost=cost,deposit=dep,target=x['target'],proceeds=x['proceeds'],listed_at=clock,expires=clock+int(c['auction_hours']*3600),status='listed'))
        event(s,clock,f"Inkoop + plaatsing simulatie: {x['qty']}x {x['name']} voor {gold(cost)}")
        count+=1
        if count>=c['max_purchases_per_cycle']: break
    s['last_snapshot']=t; return True

def demo_market(t,step):
    ids=[2589,2840,765,4306,3356,3575]
    names=['Linen Cloth','Copper Bar','Silverleaf','Silk Cloth','Kingsblood','Iron Bar']
    data={}
    for idx,(i,name) in enumerate(zip(ids,names)):
        ask=1000+idx*200 if step%3==0 else 1600+idx*250
        data[i]=dict(id=i,name=name,cls='Trade Goods',nc=False,ask=ask,ask2=ask+700,depth5=5,listed=100,vol24=500,flowHours=23,vendor=10,history=[1800+idx*250]*23+[ask],volume_history=[60]*24)
    return t,data

def atomic(p,text):
    tmp=p.with_suffix(p.suffix+'.tmp'); tmp.write_text(text,encoding='utf-8'); os.replace(tmp,p)

def dashboard(path,s,c,items,local,localmsg,status,mode,ahl,clock,craft=None):
    def table(head,rows):
        return '<div class="scroll"><table><thead><tr>'+''.join(f'<th>{esc(h)}</th>' for h in head)+'</tr></thead><tbody>'+''.join('<tr>'+''.join(f'<td>{esc(v)}</td>' for v in r)+'</tr>' for r in rows)+'</tbody></table></div>'
    cs=candidates(items,c) if s['last_snapshot'] and 0<=clock-s['last_snapshot']<=c['max_snapshot_age_minutes']*60 else []; pending=sum(p['amount'] for p in s['incoming']); inv=sum(x['cost'] for x in s['lots'] if x['status']=='inventory'); listed=sum(x['cost']+x['deposit'] for x in s['lots'] if x['status']=='listed')
    cards=[('Beschikbaar',s['cash']),('Voorraad (kostprijs)',inv),('Listed (kost + deposit)',listed),('Incoming',pending),('Kapitaal (boekwaarde)',net(s)),('Gerealiseerd resultaat',s['realized'])]
    blocks=''.join(f'<div class="metric"><small>{esc(k)}</small><strong>{gold(v)}</strong></div>' for k,v in cards)
    localinfo=localmsg
    if 'wallet' in local:
        t,g,f,r=local['wallet']; localinfo+=f' | Echt wallet: {gold(g)} ({f}, regio {r}, {stamp(t)})'
    if 'mail' in local:
        t,p,r=local['mail']; localinfo+=f' | Echt pending: {gold(p)} / klaar in mailbox: {gold(r)} ({stamp(t)}, zichtbare mails)'
    if 'scan' in local:
        t,f,r,book=local['scan']; localinfo+=f' | Scan: {len(book)} itemsoorten / {sum(map(len,book.values()))} regels ({f}, regio {r}, {stamp(t)}). Eenheid/markt nog valideren.'
    def compare(x):
        if not ahl: return '—'
        t,rows=ahl; row=rows.get(x['id'],{}); p=row.get('min'); return gold(p) if p is not None else '—'
    rows=[(x['name'],x['id'],gold(x['ask']),gold(x['target']),x['qty'],f"{x['roi']:.1f}%",x['vol'],compare(x)) for x in cs[:50]]
    localrows=[]
    if 'scan' in local:
        ltime,fac,reg,book=local['scan']
        if fac=='Alliance' and reg=='3' and 0<=clock-ltime<=c['max_local_scan_age_minutes']*60:
            for x in cs[:50]:
                if x['id'] in book:
                    q,total=min(book[x['id']],key=lambda r:r[1]/r[0]); localrows.append((x['name'],x['id'],q,gold(total),gold(total/q),gold(x['ask'])))
    craftrows=[]
    if craft and craft[0] and 0<=clock-craft[0]<=c['max_snapshot_age_minutes']*60:
        craftrows=[(x['name'],x['profession'],x['skill'],gold(x['cost']),gold(x['profit']),f"{x['roi']:.1f}%",items.get(x['id'],{}).get('vol24','—')) for x in craft[1]]
    disclaimer='FICTIEVE DEMODATA'  if mode=='demo' else 'PUBLIEKE MARKTDATA · uitsluitend fictieve transacties'
    ahltxt=f'AHledger vergelijking (snapshot {stamp(ahl[0])})' if ahl else 'AHledger niet opgehaald (optioneel)'
    body=f'''<!doctype html><html lang="nl"><meta charset="utf-8"><meta http-equiv="refresh" content="30"><meta name="viewport" content="width=device-width,initial-scale=1"><title>ForeverTrader v1</title><style>
    *{{box-sizing:border-box}}body{{font:15px system-ui;background:#10151c;color:#e3eaf3;max-width:1250px;margin:auto;padding:24px}}h1{{margin:0;font-size:32px}}h2{{font-size:19px;margin-top:30px}}p,small{{color:#a8b6c7}}a{{color:#91c9fa}}.grid{{display:grid;grid-template-columns:repeat(auto-fit,minmax(170px,1fr));gap:12px}}.metric{{padding:16px;background:#1b2430;border:1px solid #303d4e;border-radius:10px}}strong{{display:block;font-size:23px;margin-top:8px;color:#e4ba63}}table{{width:100%;border-collapse:collapse;background:#1a222d}}th,td{{text-align:left;padding:10px;border-bottom:1px solid #303d4e;white-space:nowrap}}th{{color:#b5c7dc}}.scroll{{overflow:auto}}.notice{{border-left:3px solid #e4ba63;padding:12px;background:#1b2430}}footer{{margin-top:28px}}</style><h1>ForeverTrader <small>v1.0</small></h1><p>EU · PvP · Alliance | {esc(disclaimer)} | bijgewerkt {stamp(clock)}</p><p class="notice">{esc(status)}<br>{esc(ahltxt)}<br>{esc(localinfo)}</p><div class="grid">{blocks}</div><h2>Marktsignalen</h2><p>Historische momentopname; geen garantie dat de prijs nog bestaat. ROI na AH-cut, vóór mogelijk verloren deposit.</p>{table(['Item','ID','Koop / stuk','Doel / stuk','Aantal','ROI','Volume 24h','AHledger min'],rows)}<h2>Eigen scan: controle van prijs per stack</h2><p>Alleen verse Alliance EU-export. Aangenomen eenheid: raw buyout is de totale stackprijs. PvP en eenheid nog in game controleren. Deze vergelijking triggert geen orders.</p>{table(['Item','ID','Stack','Raw buyout','Afgeleid / stuk','TK / stuk'],localrows)}<h2>Crafting radar</h2><p>AHledger advies, niet automatisch ingekocht. Receptkennis, afzet, deposits en opbrengst zelf controleren. Bron: {stamp(craft[0]) if craft and craft[0] else 'niet beschikbaar'}.</p>{table(['Recept','Profession','Skill','Kosten','Winst','ROI','TK volume 24h'],craftrows)}<h2>Paper portfolio</h2>{table(['Item','Aantal','Kostprijs','Doel / stuk','Deposit','Status','Verloopt'],[(x['name'],x['qty'],gold(x['cost']),gold(x['target']),gold(x['deposit']),x['status'],stamp(x['expires'])) for x in s['lots']])}<h2>Incoming gold (paper)</h2>{table(['Bedrag','Verwacht beschikbaar'],[(gold(x['amount']),stamp(x['eta'])) for x in s['incoming']])}<h2>Logboek (paper)</h2>{table(['Tijd','Gebeurtenis'],[(stamp(e['t']),e['msg']) for e in s['events'][:60]])}<footer><p>Bronnen: <a href="https://auctionhouse.tk.gg/m/eu-2-110">TK Auction House</a> · <a href="https://ahledger.com/markets/forever/pvp/alliance/eu">AHledger</a>. Verkoopvolume is geschat. Depositmodel is configureerbaar, werkelijke tarieven nog controleren. Verlopen inventory blijft op kostprijs, niet als beschikbare cash.</p></footer></html>'''
    atomic(path,body)

def main():
    p=argparse.ArgumentParser(); p.add_argument('--demo',action='store_true'); p.add_argument('--once',action='store_true'); p.add_argument('--ahl',action='store_true',help='Optional current AHledger price table, not archived'); p.add_argument('--no-browser',action='store_true'); args=p.parse_args()
    c=json.loads((ROOT/'config.json').read_text()); validate(c); mode='demo' if args.demo else 'paper'; folder=ROOT/'data'/mode; folder.mkdir(parents=True,exist_ok=True)
    db=sqlite3.connect(folder/'trader.sqlite',timeout=2); db.execute('CREATE TABLE IF NOT EXISTS state (id INTEGER PRIMARY KEY CHECK(id=1), payload TEXT NOT NULL)'); db.execute('CREATE TABLE IF NOT EXISTS snapshots (t INTEGER PRIMARY KEY, payload TEXT NOT NULL)'); db.commit()
    lock=folder/'run.lock'; fd=None
    try:
        fd=os.open(lock,os.O_CREAT|os.O_EXCL|os.O_WRONLY); os.write(fd,str(os.getpid()).encode()); os.close(fd); fd=None
    except FileExistsError: raise SystemExit('Er draait al een instantie (of een crash liet run.lock achter). Sluit de andere instantie; verwijder lock alleen na controle.')
    try:
        row=db.execute('SELECT payload FROM state WHERE id=1').fetchone(); s=json.loads(row[0]) if row else initial(c)
        row=db.execute('SELECT payload FROM snapshots ORDER BY t DESC LIMIT 1').fetchone(); items={int(k):v for k,v in json.loads(row[0]).items()} if row else {}
        page=folder/'dashboard.html'; next_fetch=0; ahl=None; craft=None; status='Nog geen marktdata'; opened=False; step=0
        # Persist last attempt to honor hourly rate even across restarts.
        attempt=folder/'last_fetch.txt'
        if not args.demo and attempt.exists(): next_fetch=int(attempt.read_text())+3600
        while True:
            clock=now()
            if args.demo: clock=max(clock,s['last_snapshot']+3601 if s['last_snapshot'] else clock); step=s.get('demo_step',0); s['demo_step']=step+1
            settle(s,clock)
            if args.demo or clock>=next_fetch:
                if not args.demo: atomic(attempt,str(clock)); next_fetch=clock+3600
                try:
                    t,market=demo_market(clock,step) if args.demo else parse_market(json.loads(get(URL)))
                    if t>=s['last_snapshot']:
                        items=market; cycle(s,c,t,items,clock); db.execute('INSERT OR IGNORE INTO snapshots VALUES (?,?)',(t,json.dumps(items))); status=f'Markt snapshot {stamp(t)}; {len(items)} items. Nieuwe paper orders alleen bij nieuwe, verse snapshot.'
                    else: status='Oudere snapshot genegeerd'
                    if args.ahl and not args.demo:
                        try: ahl=parse_ahl(get(AHL).decode('utf-8'))
                        except Exception as e: status+=f' | AHledger niet beschikbaar: {e}'
                        try: craft=parse_crafting(json.loads(get(CRAFT_URL)))
                        except Exception as e: status+=f' | Crafting niet beschikbaar: {e}'
                except Exception as e: status=f'Markt ophalen mislukt: {e}. Geen nieuwe paper orders.'
            local,msg=load_local(c) if not args.demo else ({},'Demo: geen lokale data')
            db.execute('INSERT OR REPLACE INTO state VALUES(1,?)',(json.dumps(s),)); db.commit()
            display_status=status if args.demo else status+f' | Volgende externe aanvraag: {stamp(next_fetch)} | Laatst verwerkt: {stamp(s["last_snapshot"])}'
            dashboard(page,s,c,items,local,msg,display_status,mode,ahl,clock,craft); print(f'{stamp(clock)} | {display_status}',flush=True)
            if not opened and not args.no_browser: webbrowser.open(page.as_uri()); opened=True
            if args.once: break
            time.sleep(15 if args.demo else 900)
    except KeyboardInterrupt: print('Gestopt; data bewaard.')
    finally: db.close(); lock.unlink(missing_ok=True)
if __name__=='__main__': main()
