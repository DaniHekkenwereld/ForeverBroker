"""Minimal ForeverTrader character-sync receiver; serve behind HTTPS reverse proxy.

Start with FT_SYNC_TOKEN (>=32 chars), bind to localhost by default. Do not
expose this plain HTTP listener directly to the Internet.
"""
import datetime as dt
import hmac
import json
import os
import pathlib
import sqlite3
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer

import characters

MAX_BYTES=262144
def setup(path):
    root=pathlib.Path(path)
    root.parent.mkdir(parents=True,exist_ok=True)
    db=sqlite3.connect(root,timeout=30)
    db.row_factory=sqlite3.Row
    db.executescript(characters.SCHEMA)
    return db

class Handler(BaseHTTPRequestHandler):
    server_version='ForeverTrader-Sync'
    def log_message(self,format,*args):
        # Do not log account names, character details or tokens.
        return
    def send(self,code,body):
        data=json.dumps(body,separators=(',',':')).encode('utf-8')
        self.send_response(code)
        self.send_header('Content-Type','application/json')
        self.send_header('Content-Length',str(len(data)))
        self.send_header('Cache-Control','no-store')
        self.end_headers()
        self.wfile.write(data)
    def do_GET(self):
        if self.path=='/health':
            self.send(200,{'ok':True})
        else:
            self.send(404,{'error':'Not found'})
    def do_POST(self):
        if self.path!='/api/v1/characters':
            return self.send(404,{'error':'Not found'})
        token=self.server.sync_token
        expected='Bearer '+token
        provided=self.headers.get('Authorization','')
        if not hmac.compare_digest(provided,expected):
            return self.send(401,{'error':'Unauthorized'})
        try:
            size=int(self.headers.get('Content-Length','0'))
            if not 2<=size<=MAX_BYTES:
                raise ValueError('Invalid payload size')
            data=json.loads(self.rfile.read(size))
            rows=data.get('characters')
            if not isinstance(rows,list) or len(rows)>40:
                raise ValueError('Invalid character count')
            now=int(dt.datetime.now(dt.timezone.utc).timestamp())
            good=[]
            for r in rows:
                if not isinstance(r,dict):
                    raise ValueError('Invalid character')
                key=r.get('character_key')
                if not isinstance(key,str) or not 3<=len(key)<=250 or any(c in key for c in '"\\\r\n'):
                    raise ValueError('Invalid character key')
                if not isinstance(r.get('last_seen'),int) or not 0<r['last_seen']<=now+300:
                    raise ValueError('Invalid timestamp')
                for fld in ('realm','character','faction'):
                    val=r.get(fld)
                    if not isinstance(val,str) or not 1<=len(val)<=100:
                        raise ValueError('Invalid identity')
                for fld in ('gold','wallet_at','bags_at','auctions_at','mail_at','mail_pending','mail_ready','mail_attachments'):
                    val=r.get(fld)
                    if val is not None and (type(val) is not int or val<0 or val>9_007_199_254_740_991):
                        raise ValueError('Invalid amount')
                for fld in ('bags','auctions'):
                    value=r.get(fld)
                    if value is not None and (not isinstance(value,dict) or len(value)>2000 or any(
                        not str(i).isdigit() or type(q) is not int or not 0<q<=10_000_000 for i,q in value.items()
                    )):
                        raise ValueError('Invalid items')
                good.append(r)
            db=setup(self.server.db_path)
            try:
                with db:
                    updated=characters.store(db,good)
            finally:
                db.close()
            return self.send(200,{'ok':True,'received':len(good),'updated':updated})
        except (ValueError,TypeError,KeyError,sqlite3.Error,OverflowError):
            return self.send(400,{'error':'Invalid payload'})

def main():
    token=os.environ.get('FT_SYNC_TOKEN','')
    if len(token)<32: raise SystemExit('FT_SYNC_TOKEN ontbreekt of is te kort (minimaal 32 tekens).')
    host=os.environ.get('FT_SYNC_HOST','127.0.0.1')
    port=int(os.environ.get('FT_SYNC_PORT','8765'))
    db_path=os.environ.get('FT_SYNC_DB','data/characters-server.sqlite')
    server=ThreadingHTTPServer((host,port),Handler)
    server.sync_token=token
    server.db_path=db_path
    print('ForeverTrader sync receiver listening on '+host+':'+str(port)+' (HTTPS proxy required)',flush=True)
    server.serve_forever()

if __name__=='__main__':
    main()
