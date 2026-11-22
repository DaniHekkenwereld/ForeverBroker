"""Integration regression for the private localhost V4 HTTP API."""
import json
import pathlib
import tempfile
import threading
import time
import unittest
import urllib.error
import urllib.request
from http.server import ThreadingHTTPServer

import trader
import v4_server

class HttpV4Tests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.db_path=pathlib.Path(self.tmp.name)/'v4.sqlite'
        self.db=v4_server.open_db(self.db_path)
        self.now=int(time.time())
        self.market={1234:{'name':'Rare Pattern','cls':'Recipe','nc':True,
                           'ask':10000,'ask2':30000,'median':30000,
                           'vol24':12,'depth5':1,'lastSoldP':30000,'vendor':1}}
        trader.save_market(self.db,self.now,self.market,self.now)
        self.db.commit();self.db.close()
        self.server=ThreadingHTTPServer(('127.0.0.1',0),v4_server.Handler)
        self.server.db_path=self.db_path
        self.server.cfg=trader.conf()
        self.server.sync_token='A'*40
        self.thread=threading.Thread(target=self.server.serve_forever,daemon=True)
        self.thread.start()
        self.url=f'http://127.0.0.1:{self.server.server_address[1]}'
    def tearDown(self):
        self.server.shutdown();self.server.server_close();self.thread.join(timeout=5)
        self.tmp.cleanup()
    def req(self,path,method='GET',data=None,token='A'*40):
        headers={'Authorization':'Bearer '+token}
        if data is not None:headers['Content-Type']='application/json'
        raw=json.dumps(data).encode('utf-8') if data is not None else None
        q=urllib.request.Request(self.url+path,data=raw,headers=headers,method=method)
        with urllib.request.urlopen(q,timeout=5) as r:
            return json.loads(r.read())
    def test_login_strategy_roundtrip_and_sessions_idempotent(self):
        self.assertEqual(self.req('/health')['version'],'4.0.0')
        stamp=self.now
        char={'character_key':'account:Forever:Mage','realm':'Forever',
              'character':'Mage','faction':'Alliance','last_seen':stamp,
              'gold':1000000,'wallet_at':stamp,'bags':{'2589':10},
              'bags_at':stamp,'auctions':{},'auctions_at':stamp,
              'mail_at':None,'mail_pending':None,'mail_ready':None,
              'mail_attachments':None}
        ses={'id':'Forever:Mage:1:1','character_key':char['character_key'],
             'started_at':stamp-120,'ended_at':stamp,
             'gold_start':990000,'gold_end':1000000,
             'bags_start':{'2589':5},'bags_end':{'2589':10}}
        payload={'schema':'FT4SYNC1','characters':[char],'sessions':[ses]}
        first=self.req('/api/v4/sync','POST',payload)
        self.assertTrue(first['ok'])
        self.assertEqual(first['sessions_added'],1)
        again=self.req('/api/v4/sync','POST',payload)
        self.assertEqual(again['sessions_added'],0)
        resp=self.req('/api/v4/strategies')
        self.assertEqual(resp['market'],'eu-2-110')
        self.assertEqual(len(resp['strategies']),1)
        self.assertEqual(resp['strategies'][0]['character'],'Mage')
        self.assertTrue(resp['strategies'][0]['plan'].startswith('FT3|eu-2-110|'))
        self.assertIn('1234:0:0:0:0',resp['strategies'][0]['plan'])
    def test_authentication_is_mandatory(self):
        with self.assertRaises(urllib.error.HTTPError) as err:
            self.req('/api/v4/strategies',token='wrong')
        self.assertEqual(err.exception.code,401)
        with self.assertRaises(urllib.error.HTTPError) as err:
            self.req('/api/v4/sync','POST',{'schema':'FT4SYNC1','characters':[],'sessions':[]},token='wrong')
        self.assertEqual(err.exception.code,401)

if __name__=='__main__':unittest.main()
