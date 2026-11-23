"""ForeverTrader v4 service: 24/7 market history + authenticated strategy API.

Run with Python 3.10+ under systemd and HTTPS (nginx/Caddy) reverse proxy.
NEVER run publicly without TLS or credentials. Not a game automation bot.
"""
import datetime as dt
import hmac
import json
import os
import pathlib
import sqlite3
import threading
import time
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
from urllib.parse import urlsplit

import characters
import legacy
import trader
import v4_engine as v4
import v4_research
import v4_trades

MAX_BODY=300000
UTC=dt.timezone.utc


def open_db(path):
    db=trader.connect(pathlib.Path(path))
    db.executescript(v4.SCHEMA+v4_trades.SCHEMA)
    return db


def validate_characters(rows,now):
    if type(rows) is not list or len(rows)>40:raise ValueError('Invalid characters')
    good=[]
    for x in rows:
        if type(x) is not dict:raise ValueError('Invalid record')
        key=x.get('character_key')
        if not isinstance(key,str) or not 5<=len(key)<=250 or any(c in key for c in '"\\\r\n'):
            raise ValueError('Invalid character key')
        for name in ('character','realm','faction'):
            val=x.get(name)
            if not isinstance(val,str) or not 1<=len(val)<=100 or any(c in val for c in '\r\n"\\'):
                raise ValueError('Invalid name')
        last=x.get('last_seen')
        if type(last) is not int or not 0<last<=now+300:raise ValueError('Invalid last_seen')
        for at in ('wallet_at','bags_at','auctions_at','mail_at',
                   'bank_at','bag_bound_at','equipment_at'):
            t=x.get(at)
            if t is not None and (type(t) is not int or not 0<t<=now+300):
                raise ValueError('Invalid timestamp')
        for keyname in ('gold','mail_pending','mail_ready','mail_attachments'):
            n=x.get(keyname)
            if n is not None and (type(n) is not int or not 0<=n<=9007199254740991):
                raise ValueError('Invalid amount')
        for keyname in ('bags','auctions','bank','bank_bound',
                        'bag_bound','equipment'):
            values=x.get(keyname)
            if values is not None:
                if type(values) is not dict or len(values)>2000:
                    raise ValueError('Invalid item inventory')
                for item,qty in values.items():
                    if not str(item).isdigit() or type(qty) is not int or not 0<qty<=10000000:
                        raise ValueError('Invalid inventory quantity')
        for group,when in (('bank','bank_at'),('bag_bound','bag_bound_at'),
                           ('equipment','equipment_at')):
            if x.get(group) is not None and x.get(when) is None:
                raise ValueError('Portfolio location lacks timestamp')
        if x.get('bank_bound') is not None and x.get('bank_at') is None:
            raise ValueError('Bound bank lacks timestamp')
        for location,bound in (('bank','bank_bound'),('bags','bag_bound')):
            if isinstance(x.get(bound),dict) and isinstance(x.get(location),dict):
                if any(q>x[location].get(i,0) for i,q in x[bound].items()):
                    raise ValueError('Bound items exceed actual inventory')
        good.append(x)
    return good


def fetch_market_once(db,cfg,clock):
    """Respect the shared hourly API cadence, persisted across restarts."""
    due=trader.next_market_attempt(trader.getmeta(db,'market_attempt',0))
    if clock<due:return False
    trader.setmeta(db,'market_attempt',clock)
    db.commit()
    try:
        t,market=legacy.parse_market(json.loads(legacy.get(legacy.URL)))
        with db:
            fresh=trader.save_market(db,t,market,int(time.time()),'tk')
            trader.setmeta(db,'market_last_error','')
        if fresh:
            # Scarce historical imports, never burst requests. Each call
            # respects prior import attempts and the existing source limits.
            trader.import_history(db,cfg,market,int(time.time()))
            db.commit()
        return fresh
    except Exception as e:
        with db:
            trader.setmeta(db,'market_last_error',str(e)[:300])
            trader.log(db,int(time.time()),'v4 market',str(e))
        return False


def market_loop(db_path, cfg, stop_event):
    """All market history is collected independently of player login."""
    while not stop_event.is_set():
        try:
            db=open_db(db_path)
            try:
                fetch_market_once(db,cfg,int(time.time()))
                with db:
                    v4.strategy_list(db,int(time.time()),cfg)
            finally:
                db.close()
        except Exception as e:
            print('v4 worker:',type(e).__name__,str(e)[:200],flush=True)
        stop_event.wait(60)


class Handler(BaseHTTPRequestHandler):
    server_version='ForeverTrader-v4'
    def log_message(self,format,*args):
        # Never emit tokens or character details to access logs.
        return

    def respond(self,status,obj):
        b=json.dumps(obj,ensure_ascii=False,separators=(',',':')).encode('utf-8')
        self.send_response(status)
        self.send_header('Content-Type','application/json; charset=utf-8')
        self.send_header('Content-Length',str(len(b)))
        self.send_header('Cache-Control','no-store')
        self.send_header('X-Content-Type-Options','nosniff')
        self.end_headers();self.wfile.write(b)

    def authorized(self):
        return hmac.compare_digest(self.headers.get('Authorization',''),
                                   'Bearer '+self.server.sync_token)

    def do_GET(self):
        path=urlsplit(self.path)
        if path.path=='/health' and not path.query:
            return self.respond(200,{'ok':True,'version':'4.0.0'})
        if path.path not in ('/api/v4/strategies','/api/v4/research') or path.query:
            return self.respond(404,{'error':'Not found'})
        if not self.authorized():
            return self.respond(401,{'error':'Unauthorized'})
        now=int(time.time())
        try:
            db=open_db(self.server.db_path)
            try:
                if path.path=='/api/v4/research':
                    # No external HTTP requests here; use cached local snapshots.
                    report=v4_research.build(db,now,self.server.cfg)
                else:
                    with db:
                        plans=v4.strategy_list(db,now,self.server.cfg)
            finally:db.close()
        except (sqlite3.Error,ValueError,TypeError,KeyError,OverflowError):
            return self.respond(503,{'error':'Research unavailable'})
        if path.path=='/api/v4/research':
            return self.respond(200,report)
        return self.respond(200,{'version':'4.0.0','generated_at':now,
                                 'market':v4.MARKET,'strategies':plans})

    def do_POST(self):
        path=urlsplit(self.path)
        if path.path!='/api/v4/sync' or path.query:
            return self.respond(404,{'error':'Not found'})
        if not self.authorized():
            # Drain a small unauthorized POST body before closing the socket.
            # Otherwise Windows can see TCP RST instead of HTTP 401 because
            # the server closes with unread inbound request bytes.
            try:
                unauthorized_length=int(self.headers.get('Content-Length','0'))
                if 0<unauthorized_length<=MAX_BODY:
                    self.connection.settimeout(2)
                    self.rfile.read(unauthorized_length)
            except (OSError,ValueError,OverflowError):
                pass
            return self.respond(401,{'error':'Unauthorized'})
        try:
            length=int(self.headers.get('Content-Length','0'))
            if not 2<=length<=MAX_BODY:raise ValueError('Bad length')
            data=json.loads(self.rfile.read(length))
            if not isinstance(data,dict) or data.get('schema')!='FT4SYNC1':
                raise ValueError('Bad schema')
            now=int(time.time())
            chars=validate_characters(data.get('characters'),now)
            sessions=data.get('sessions')
            if type(sessions) is not list or len(sessions)>60:
                raise ValueError('Bad sessions')
            trades=data.get('trades',[])
            if type(trades) is not list or len(trades)>250:
                raise ValueError('Bad manual trade batch')
            # Validate all before committing anything. Client retries are
            # idempotent by character timestamps + session IDs.
            for ses in sessions:
                v4.normalize_session(ses,now)
            for trade in trades:
                v4_trades.validate(trade,now)
            allowed={x['character_key'] for x in chars}
            # A session may refer to a previously recorded offline character;
            # matching a session to this private account is checked below.
            db=open_db(self.server.db_path)
            try:
                with db:
                    old={r['character_key'] for r in characters.read_all(db)}
                    if any(s['character_key'] not in allowed|old for s in sessions):
                        raise ValueError('Unknown character')
                    count=characters.store(db,chars)
                    added=v4.store_sessions(db,sessions,now)
                    trades_added=v4_trades.store(db,trades,now,allowed|old)
                    v4.strategy_list(db,now,self.server.cfg)
            finally:db.close()
            return self.respond(200,{'ok':True,'characters_updated':count,
                                     'sessions_added':added,'trades_added':trades_added})
        except (ValueError,TypeError,OverflowError,sqlite3.Error):
            return self.respond(400,{'error':'Invalid sync data'})


def serve(db_path,cfg,token,host='127.0.0.1',port=8765):
    if len(token)<32:raise ValueError('FT_SYNC_TOKEN must have at least 32 characters')
    db=open_db(db_path);db.close()
    stop_event=threading.Event()
    worker=threading.Thread(target=market_loop,args=(db_path,cfg,stop_event),
                            daemon=True,name='ForeverTrader-market')
    worker.start()
    server=ThreadingHTTPServer((host,port),Handler)
    server.sync_token=token
    server.db_path=db_path
    server.cfg=cfg
    print(f'ForeverTrader v4: HTTP loopback {host}:{port}; put behind HTTPS',flush=True)
    try:server.serve_forever()
    finally:
        stop_event.set()
        server.server_close()
        worker.join(timeout=5)


def main():
    token=os.environ.get('FT_SYNC_TOKEN','')
    if len(token)<32:raise SystemExit('FT_SYNC_TOKEN ontbreekt (minimaal 32 tekens)')
    host=os.environ.get('FT_SYNC_HOST','127.0.0.1')
    if host not in ('127.0.0.1','::1','localhost'):
        raise SystemExit('V4 server mag alleen op loopback luisteren; gebruik een HTTPS reverse proxy')
    port=int(os.environ.get('FT_SYNC_PORT','8765'))
    db_path=os.environ.get('FT_SYNC_DB',str(trader.ROOT/'data'/'paper'/'trader.sqlite'))
    serve(db_path,trader.conf(),token,host,port)


if __name__=='__main__':
    main()
