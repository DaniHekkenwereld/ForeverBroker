"""Manual, short-lived watchlist handoff. Never executes or claims real orders."""
import json, math, re, html
import targeted

def monitor_rows(snapshot_json, c, excluded=(), limit=20):
    """Read-only item IDs for targeted AH checks; never generate BUY/SELL advice."""
    try:
        market={int(k):v for k,v in json.loads(snapshot_json).items()}
    except (ValueError,TypeError,AttributeError):
        return []
    excluded=set(excluded)
    watch=[]
    for i in set(c['watchlist'])-excluded:
        x=market.get(i)
        if not isinstance(x,dict): continue
        ask,volume=x.get('ask'),x.get('vol24')
        if type(ask) is not int or ask<=0 or x.get('nc') or x.get('cls') not in ('Trade Goods','Consumable','Consumables'):
            continue
        if type(volume) is not int or volume<max(1,c['min_daily_volume']//2):
            continue
        watch.append((volume,i,x))
    out=[]
    for volume,i,x in sorted(watch,key=lambda v:(-v[0],v[1]))[:max(0,limit)]:
        out.append(dict(id=i,name=x.get('name') or f'Item {i}',max=0,qty=0,target=0,hold=0,strategy='monitor',roi=None,live=False))
    return out

def encode_plan(rows,made,expires):
    return f'FT3|eu-2-110|{made}|{expires};'+';'.join(f"{r['id']}:{r['max']}:{r['qty']}:{r['target']}:{r['hold']}" for r in rows)

def build_plan(db,c,clock,mode):
    if mode=='demo': return '',[], 'Demo: geen planning voor echt gold.'
    # The current market snapshot is authoritative; an old trade-decision batch
    # must not be handed off as though it refers to the latest market data.
    latest=db.execute('SELECT t,payload FROM market_snapshots ORDER BY t DESC LIMIT 1').fetchone()
    last_decision=db.execute('SELECT MAX(snapshot) FROM trade_decisions').fetchone()[0]
    t=latest['t'] if latest else last_decision
    if not t or not 0<=clock-t<5400:
        # A stale snapshot must NEVER create a trade recommendation.
        # It can still supply IDs for a short-lived, read-only search queue.
        if latest and 0<=clock-latest['t']:
            watch=monitor_rows(latest['payload'],c)
            if watch:
                for r in watch:r['stale']=True
                age=(clock-latest['t'])//60
                return encode_plan(watch,clock,clock+3600),watch,(
                    f'Marktdata {age} minuten oud. Geen koopadvies; '
                    f'{len(watch)} controle-items om actuele AH-prijzen op te vragen. '
                    'Controle-items zijn alleen zoekopdrachten.'
                )
        return '',[], 'Geen actuele marktsnapshot en geen geschikte controle-items.'
    rows=db.execute('''SELECT d.*,i.name,i.vendor FROM trade_decisions d JOIN items i ON i.id=d.item_id
      WHERE d.snapshot=? AND d.strategy IN ('direct','intraday','weekly') AND d.roi IS NOT NULL AND d.confidence>0 AND d.ask>0 AND d.quantity>0
      AND (d.action='BUY_MODEL' OR d.reason IN ('item occupied','cycle limit','item exposure','cash reserve','strategy cap','minimum net ROI incl deposit risk'))''',(t,)).fetchall()
    out=[];seen=set()
    # Strictly curated materials. An 'observe' entry is not a buy recommendation.
    allowed=set(c['watchlist'])
    def priority(r):
        hold=json.loads(r['details']).get('hold_hours',0)
        return r['roi']*r['confidence']/(1+hold/12)
    for r in sorted(rows,key=priority,reverse=True):
        i=r['item_id'];d=json.loads(r['details']);hold=int(d.get('hold_hours',0)); target=r['target']
        if i not in allowed or i in seen or target is None or not 0<=hold<=168: continue
        dep=max(0,int(d.get('deposit_per_unit',0)));net=target-math.ceil(target*c['cut_pct']/100)-dep
        limit=int(net/(1+c['min_roi_pct']/100)); qty=min(r['quantity'],10000)
        live=targeted.latest(db,i,clock)
        if live is not None:
            qty_live,cost_live=targeted.affordable(live,limit,qty)
            if not qty_live: continue
            effective=cost_live/qty_live; roi=(net/effective-1)*100;qty=qty_live
        else:
            if r['roi']<c['min_roi_pct']:continue
            roi=r['roi']
        if not 0<limit<target<=100000000: continue
        out.append(dict(id=i,name=r['name'],max=limit,qty=qty,target=target,hold=hold,strategy=r['strategy'],roi=roi,live=live is not None));seen.add(i)
        if len(out)>=20:break
    buy_count=len(out)
    # Even without a BUY_MODEL candidate we still need a useful targeted search
    # queue. Monitor entries use all-zero price/quantity fields, so Lua will
    # SEARCH them but NEVER turn them into BUY/SELL advice without a real signal.
    if latest and latest['t']==t and len(out)<20:
        out.extend(monitor_rows(latest['payload'],c,seen,20-len(out)))
    if not out: return '',[], 'Nog geen handelsadviezen of geschikte items voor gerichte prijscontrole.'
    expires=t+5400
    payload=encode_plan(out,t,expires)
    msg=f'{buy_count} koopkansen, {len(out)-buy_count} controle-items. Controle-items geven nooit zelfstandig koopadvies. Prijsreferentie maximaal 90 min geldig.'
    return payload,out,msg

def panel(db,c,clock,mode):
    payload,rows,msg=build_plan(db,c,clock,mode); e=html.escape
    lines=''.join(f'<tr><td>{e(str(r["name"]))}</td><td>{r["qty"]}</td><td>{r["max"]}</td><td>{r["target"]}</td><td>{r["hold"]}</td><td>{e(r["strategy"])}</td><td>{"Oude snapshot" if r.get("stale") else ("LIVE" if r["live"] else "Historisch")}</td><td>{"—" if r["roi"] is None else f"{r['roi']:.1f}%"}</td></tr>' for r in rows)
    return f'''<section class="notice"><h2 style="margin-top:0">In-game handelscoach</h2><p>{e(msg)}</p><p>Open WoW: /ft start, /ft market (eenmalig), /ft plan. Kopieer onderstaande regel, plak in het invoerveld in WoW en druk Enter. Ververs de lijst na nieuwe marktdata. De coach gebruikt direct de verse in-game prijzen; desktop leest die na reload/logout. De coach gebruikt echte wallet, zichtbare mail, bags en gerichte AH-zoekresultaten, maximaal 2 min oud; geen automatische orders.</p><textarea id="coachplan" readonly rows="3" style="width:98%" onclick="this.select()">{e(payload)}</textarea><button onclick="document.getElementById('coachplan').select();navigator.clipboard?.writeText(document.getElementById('coachplan').value).catch(()=>{{}})">Selecteer / kopieer planning</button><p>Prijzen per stuk in copper. Regels met strategie monitor zijn alleen voor gerichte prijscontrole (geen koopadvies).</p><table><tr><th>Item</th><th>Max stuks</th><th>Max koop</th><th>Doel</th><th>Hold uren</th><th>Strategie</th><th>Bron</th><th>ROI</th></tr>{lines}</table></section>'''

def extras(text):
    """Constrained read only parser for new optional strings; never runs Lua."""
    out={}
    for key,fmt in [('browseSummary',r'\d+;\d+:\d+:\d+(?:;\d+:\d+:\d+)*'),('mail3',r'\d+(?:\|\d+){5}'),('coach',r'\d+\|[A-Z_]+(?:\|\d+){5}'),('bags',r'\d+;(?:\d+:\d+(?:;\d+:\d+)*)?'),('owned',r'\d+;(?:\d+:\d+:\d+(?:;\d+:\d+:\d+)*)?'),('coachLog',r'\d+\|[A-Z_]+(?:\|\d+){5}(?:;\d+\|[A-Z_]+(?:\|\d+){5})*')]:
        m=re.search(r'^\s*\["'+key+r'"\]\s*=\s*"('+fmt+r')"\s*,?\s*$',text,re.M)
        if m:
            s=m.group(1); t=int(re.split(r'[|;]',s)[0]);out[key]=(t,s)
    return out
