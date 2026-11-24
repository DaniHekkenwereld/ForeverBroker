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
    def test_saved_wow_ah_price_reaches_vps_and_research_without_duplicate(self):
        stamp=self.now
        char={'character_key':'acct:eu-2-110:Dien Pump',
              'realm':'eu-2-110','character':'Dien Pump',
              'faction':'Alliance','last_seen':stamp,
              'gold':650000,'wallet_at':stamp,
              'bags':{},'bags_at':stamp,'auctions':{},'auctions_at':stamp,
              'mail_at':None,'mail_pending':None,'mail_ready':None,
              'mail_attachments':None}
        price={'id':1234,'at':stamp-20,'kind':'item','ask':8500,
               'units':7,'price_rows':2}
        data={'schema':'FT4SYNC1','characters':[char],
              'sessions':[],'game_quotes':[price]}
        first=self.req('/api/v4/sync','POST',data)
        self.assertTrue(first['ok'])
        self.assertEqual(first['game_quotes_added'],1)
        self.assertEqual(self.req('/api/v4/sync','POST',data)['game_quotes_added'],0)
        research=self.req('/api/v4/research')
        self.assertEqual(research['game_checks'][0]['id'],1234)
        self.assertEqual(research['game_checks'][0]['ask'],8500)
        self.assertEqual(research['portfolio']['game_checks'][0]['price_rows'],2)
        data['game_quotes'][0]['ask']=-1
        with self.assertRaises(urllib.error.HTTPError) as ctx:
            self.req('/api/v4/sync','POST',data)
        self.assertEqual(ctx.exception.code,400)
        # A broken quote batch must not destroy already-synced inventory.
        research=self.req('/api/v4/research')
        self.assertEqual(research['portfolio']['characters'][0]['character'],'Dien Pump')

    def test_forever_full_name_sync_roundtrip(self):
        stamp=self.now
        char={'character_key':'acchash:eu-2-110:Warrior Pump',
              'realm':'eu-2-110','character':'Warrior Pump','faction':'Alliance',
              'last_seen':stamp,'gold':750000,'wallet_at':stamp,
              'bags':{'2589':3},'bags_at':stamp,'auctions':{},
              'auctions_at':stamp,'mail_at':None,'mail_pending':None,
              'mail_ready':None,'mail_attachments':None}
        ses={'id':'eu-2-110:Warrior_Pump:123:1','character_key':char['character_key'],
             'started_at':stamp-120,'ended_at':stamp,
             'gold_start':750000,'gold_end':750000,
             'bags_start':{'2589':3},'bags_end':{'2589':3}}
        response=self.req('/api/v4/sync','POST',{
            'schema':'FT4SYNC1','characters':[char],'sessions':[ses]})
        self.assertTrue(response['ok'])
        self.assertEqual(response['characters_updated'],1)
        self.assertEqual(response['sessions_added'],1)
        plans=self.req('/api/v4/strategies')['strategies']
        self.assertEqual(len(plans),1)
        self.assertEqual(plans[0]['realm'],'eu-2-110')
        self.assertEqual(plans[0]['character'],'Warrior Pump')

    def test_portfolio_bank_and_gold_survive_authenticated_sync_roundtrip(self):
        stamp=self.now
        base={'realm':'eu-2-110','faction':'Alliance','last_seen':stamp,
              'wallet_at':stamp,'bags_at':stamp,'auctions':{},'auctions_at':stamp,
              'mail_at':None,'mail_pending':None,'mail_ready':None,
              'mail_attachments':None}
        warrior={**base,'character_key':'acct:eu-2-110:Warrior Pump',
                 'character':'Warrior Pump','gold':2000000,
                 'bags':{'14344':2},'bag_bound':{'14344':2},
                 'bag_bound_at':stamp,'bank':{'12363':5,'16203':3},
                 'bank_bound':{'16203':3},'bank_at':stamp,
                 'equipment':{'18832':1},'equipment_at':stamp}
        mage={**base,'character_key':'acct:eu-2-110:Mage Pump',
              'character':'Mage Pump','gold':500000,'bags':{}}
        trades=[
            {'id':'acct:trade-1','character_key':warrior['character_key'],
             'at':stamp-60,'side':'BUY','item_id':12363,
             'quantity':2,'total_copper':100000},
            {'id':'acct:trade-2','character_key':warrior['character_key'],
             'at':stamp-30,'side':'SELL','item_id':12363,
             'quantity':1,'total_copper':120000},
        ]
        accepted=self.req('/api/v4/sync','POST',{
            'schema':'FT4SYNC1','characters':[warrior,mage],
            'sessions':[],'trades':trades})
        self.assertTrue(accepted['ok'])
        self.assertEqual(accepted['trades_added'],2)
        research=self.req('/api/v4/research')
        p=research['portfolio']
        self.assertEqual(p['gold_total_last_known'],2500000)
        self.assertEqual(p['realized_profit'],70000)
        self.assertEqual(p['trade_count'],2)
        self.assertEqual(self.req('/api/v4/sync','POST',{
            'schema':'FT4SYNC1','characters':[warrior,mage],
            'sessions':[],'trades':trades})['trades_added'],0)
        self.assertEqual(len(p['characters']),2)
        owned={r['id']:r for r in p['holdings']}
        self.assertEqual(owned[12363]['bank'],5)
        self.assertEqual(owned[16203]['potentially_sellable'],0)
        self.assertEqual(owned[14344]['bound_bags'],2)
        self.assertEqual(owned[18832]['equipment'],1)
        self.assertEqual(research['intraday']['patterns'],[])
        # Updating a character without a new bank measurement must NOT erase it.
        reduced={k:v for k,v in warrior.items() if k not in
                ('bank','bank_bound','bank_at','equipment','equipment_at')}
        self.assertTrue(self.req('/api/v4/sync','POST',{
            'schema':'FT4SYNC1','characters':[reduced,mage],'sessions':[]})['ok'])
        again=self.req('/api/v4/research')['portfolio']
        self.assertEqual(next(i for i in again['holdings'] if i['id']==12363)['bank'],5)
        with self.assertRaises(urllib.error.HTTPError) as err:
            self.req('/api/v4/research',token='wrong')
        self.assertEqual(err.exception.code,401)

    def test_automatic_ah_receipts_and_unresolved_evidence_sync_replay(self):
        stamp=self.now
        key='acc:eu-2-110:Warrior Pump'
        char={'character_key':key,'realm':'eu-2-110',
              'character':'Warrior Pump','faction':'Alliance','last_seen':stamp,
              'gold':2_000_000,'wallet_at':stamp,'bags':{},'bags_at':stamp,
              'auctions':{},'auctions_at':stamp,
              'mail_at':None,'mail_pending':None,'mail_ready':None,
              'mail_attachments':None}
        buys=[
          {'id':'acc:AH_Warrior_1','character_key':key,
           'at':stamp-90,'side':'BUY','item_id':12363,
           'quantity':2,'total_copper':100000,'source':'AH_BUY'},
          {'id':'acc:AH_Warrior_2','character_key':key,
           'at':stamp-40,'side':'SELL','item_id':12363,
           'quantity':1,'total_copper':80000,'source':'AH_MAIL'},
        ]
        # Pending Forever seller invoice: quantity -1 sentinel and the
        # refundable deposit initially exceeds gold visible in the mail.
        # This MUST NOT reject the full character/bank/portfolio sync.
        issue={'id':'acc:unresolved1','character_key':key,
               'at':stamp-10,'side':'SELL','item_id':0,
               'quantity':-1,'total_copper':-500,
               'reason':'MAIL_QUANTITY_UNRESOLVED','item_name':'Uncached Pattern'}
        payload={'schema':'FT4SYNC1','characters':[char],
                 'sessions':[],'trades':buys,'trade_issues':[issue]}
        response=self.req('/api/v4/sync','POST',payload)
        self.assertEqual(response['trades_added'],2)
        self.assertEqual(response['unresolved_trades'],1)
        report=self.req('/api/v4/research')['portfolio']
        self.assertEqual(report['realized_profit'],30000)
        self.assertEqual(report['unresolved_ah_count'],1)
        self.assertEqual(report['unresolved_ah_events'][0]['item_name'],'Uncached Pattern')
        self.assertEqual(report['unresolved_ah_events'][0]['quantity'],-1)
        self.assertEqual(report['unresolved_ah_events'][0]['total_copper'],-500)
        self.assertEqual(self.req('/api/v4/sync','POST',payload)['trades_added'],0)
        payload['trade_issues']=[]
        self.assertEqual(self.req('/api/v4/sync','POST',payload)['unresolved_trades'],0)
        report=self.req('/api/v4/research')['portfolio']
        self.assertEqual(report['unresolved_ah_count'],0)
        self.assertEqual(report['realized_profit'],30000)

    def test_authentication_is_mandatory(self):
        with self.assertRaises(urllib.error.HTTPError) as err:
            self.req('/api/v4/strategies',token='wrong')
        self.assertEqual(err.exception.code,401)
        with self.assertRaises(urllib.error.HTTPError) as err:
            self.req('/api/v4/sync','POST',{'schema':'FT4SYNC1','characters':[],'sessions':[]},token='wrong')
        self.assertEqual(err.exception.code,401)

if __name__=='__main__':unittest.main()
