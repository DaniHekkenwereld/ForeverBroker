"""Read-only view of the addon AH search history saved by the WoW client.

WoW only flushes SavedVariables on logout/reload. Never call these entries
live prices while the game is running, and NEVER write to its save file.
"""
import pathlib
import re
import sqlite3
import time

import legacy
import targeted
import trader
import v4_bridge

TRACE=re.compile(r'(?m)^\s*\["v4SearchLog"\]\s*=\s*"([0-9QR:;]*)"\s*,?\s*$')
LAST_SEARCH=re.compile(r'(?m)^\s*\["lastAutoSearch"\]\s*=\s*"([0-9|]*)"\s*,?\s*$')


def from_text(text,clock,limit=60):
    entries=[]
    m=TRACE.search(text)
    if m:
        for line in m.group(1).split(';')[-150:]:
            fields=line.split(':')
            if len(fields)!=5:continue
            t,kind,item,price,rows=fields
            if kind not in ('Q','R'):continue
            try:t,item,price,rows=(int(t),int(item),int(price),int(rows))
            except ValueError:continue
            if not 0<t<=clock+300 or not 0<item<=10_000_000:continue
            if not 0<=price<=100_000_000_000 or not 0<=rows<=10000:continue
            entries.append({'at':t,'kind':'Resultaat' if kind=='R' else 'Zoekopdracht',
                            'id':item,'price':price if kind=='R' else None,
                            'price_rows':rows if kind=='R' else None})
    # The old addon only stored one lastAutoSearch and a bounded targetLog.
    # The strict existing parser validates units/stack totals; avoid duplicating
    # parsing logic with different math or making claims about bogus numbers.
    db=sqlite3.connect(':memory:')
    db.row_factory=sqlite3.Row
    try:
        db.executescript(targeted.SCHEMA)
        targeted.import_log(db,text,clock)
        observations=[dict(r) for r in db.execute(
            'SELECT t,item_id,kind,ask,units,rows FROM targeted_observations '
            'ORDER BY t DESC,item_id LIMIT 80')]
    finally:
        db.close()
    newest={}
    for row in observations:
        newest.setdefault(row['item_id'],{
            'id':row['item_id'],'at':row['t'],'ask':row['ask'],
            'units':row['units'],'price_rows':row['rows'],
            'kind':row['kind'],
        })
    last=LAST_SEARCH.search(text)
    last_search=None
    if last:
        try:
            t,item,count=map(int,last.group(1).split('|'))
            if 0<t<=clock+300 and 0<item<=10_000_000 and 0<=count<=100000:
                last_search={'at':t,'id':item,'count':count}
        except (TypeError,ValueError):
            pass
    return {'events':list(reversed(entries[-limit:])),
            'observations':list(newest.values()),
            'last_search':last_search,
            'saved_prices':len(newest)}


def load(clock=None):
    clock=int(time.time()) if clock is None else clock
    report={'available':False,'saved_at':None,'game_running':None,
            'events':[],'observations':[],'last_search':None,'saved_prices':0,
            'notice':'Geen lokale WoW-gegevens gevonden.'}
    try:
        cfg=trader.conf()
        path,message=legacy.saved_path(cfg)
        report['game_running']=v4_bridge.game_running()
        if not path:
            report['notice']=message or report['notice']
            return report
        stat=path.stat()
        if stat.st_size>8_000_000:
            report['notice']='SavedVariables groter dan toegestane 8MB'
            return report
        text=path.read_text(encoding='utf-8',errors='replace')
        report.update(from_text(text,clock))
        report['available']=True
        report['saved_at']=int(stat.st_mtime)
        report['notice']=('WoW draait: deze zoekgegevens zijn de laatste '
                          'opgeslagen versie, NIET de huidige in-game sessie.'
                          if report['game_running'] else
                          'Gegevens van de laatste WoW-save; geen live AH-feed.')
    except (OSError,ValueError,sqlite3.Error) as exc:
        report['notice']='Lokale SavedVariables niet leesbaar ('+type(exc).__name__+')'
    return report
