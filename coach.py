"""Manual, short-lived watchlist handoff. Never executes or claims real orders."""
import json, math, re, html
import targeted

def build_plan(db,c,clock,mode):
    if mode=='demo': return '',[], 'Demo: geen planning voor echt gold.'
    t=db.execute('SELECT MAX(snapshot) FROM trade_decisions').fetchone()[0]
    if not t or not 0<=clock-t<5400: return '',[], 'Geen actuele marktsnapshot (< 90 min).'
    rows=db.execute('''SELECT d.*,i.name,i.vendor FROM trade_decisions d JOIN items i ON i.id=d.item_id
      WHERE d.snapshot=? AND d.strategy IN ('direct','intraday','weekly') AND d.roi IS NOT NULL AND d.confidence>0 AND d.ask>0 AND d.quantity>0
      AND (d.action='BUY_MODEL' OR d.reason IN ('item occupied','cycle limit','item exposure','cash reserve','strategy cap','minimum net ROI incl deposit risk'))''',(t,)).fetchall()
    out=[];seen=set()
    # Restrict to curated fungible materials; no gear, random suffixes or arbitrary item variants.
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
        # Published target remains a ceiling, not a prediction of a guaranteed fill.
        if live is not None:
            qty_live,cost_live=targeted.affordable(live,limit,qty)
            if not qty_live: continue
            effective=cost_live/qty_live; roi=(net/effective-1)*100;qty=qty_live
        else:
            if r['roi']<c['min_roi_pct']:continue
            roi=r['roi']
        if not 0<limit<target<=100000000: continue
        out.append(dict(id=i,name=r['name'],max=limit,qty=qty,target=target,hold=hold,strategy=r['strategy'],roi=roi,live=live is not None));seen.add(i)
        if len(out)>=20: break
    expires=t+5400
    payload=f'FT3|eu-2-110|{t}|{expires};'+';'.join(f"{r['id']}:{r['max']}:{r['qty']}:{r['target']}:{r['hold']}" for r in out)
    return payload,out, f'{len(out)} items; prijsreferentie maximaal 90 min geldig; actuele stackprijs zelf controleren.'

def panel(db,c,clock,mode):
    payload,rows,msg=build_plan(db,c,clock,mode); e=html.escape
    lines=''.join(f'<tr><td>{e(str(r["name"]))}</td><td>{r["qty"]}</td><td>{r["max"]}</td><td>{r["target"]}</td><td>{r["hold"]}</td><td>{e(r["strategy"])}</td><td>{"LIVE" if r["live"] else "Historisch"}</td><td>{r["roi"]:.1f}%</td></tr>' for r in rows)
    return f'''<section class="notice"><h2 style="margin-top:0">In-game handelscoach</h2><p>{e(msg)}</p><p>Open WoW: /ft start, /ft market (eenmalig), /ft plan. Kopieer onderstaande regel, plak in het invoerveld in WoW en druk Enter. Ververs de lijst na nieuwe marktdata. De coach gebruikt direct de verse in-game prijzen; desktop leest die na reload/logout. De coach gebruikt echte wallet, zichtbare mail, bags en gerichte AH-zoekresultaten, maximaal 2 min oud; geen automatische orders.</p><textarea id="coachplan" readonly rows="3" style="width:98%" onclick="this.select()">{e(payload)}</textarea><button onclick="document.getElementById('coachplan').select();navigator.clipboard?.writeText(document.getElementById('coachplan').value).catch(()=>{{}})">Selecteer / kopieer planning</button><p>Prijzen per stuk in copper. Verkoopdoel is geen gegarandeerde opbrengst.</p><table><tr><th>Item</th><th>Max stuks</th><th>Max koop</th><th>Doel</th><th>Hold uren</th><th>Strategie</th><th>Bron</th><th>ROI</th></tr>{lines}</table></section>'''

def extras(text):
    """Constrained read only parser for new optional strings; never runs Lua."""
    out={}
    for key,fmt in [('browseSummary',r'\d+;\d+:\d+:\d+(?:;\d+:\d+:\d+)*'),('mail3',r'\d+(?:\|\d+){5}'),('coach',r'\d+\|[A-Z_]+(?:\|\d+){5}'),('bags',r'\d+;(?:\d+:\d+(?:;\d+:\d+)*)?'),('owned',r'\d+;(?:\d+:\d+:\d+(?:;\d+:\d+:\d+)*)?'),('coachLog',r'\d+\|[A-Z_]+(?:\|\d+){5}(?:;\d+\|[A-Z_]+(?:\|\d+){5})*')]:
        m=re.search(r'^\s*\["'+key+r'"\]\s*=\s*"('+fmt+r')"\s*,?\s*$',text,re.M)
        if m:
            s=m.group(1); t=int(re.split(r'[|;]',s)[0]);out[key]=(t,s)
    return out
