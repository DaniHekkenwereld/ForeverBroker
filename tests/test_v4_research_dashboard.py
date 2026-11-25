"""Regressions: market research must label evidence and dashboard must be honest."""
import json
import pathlib
import tempfile
import threading
import urllib.error
import urllib.request
import unittest
from http.server import ThreadingHTTPServer
from unittest.mock import patch

import characters
import trader
import v4_dashboard
import v4_engine
import v4_local_activity
import v4_research
import v4_server


class MarketResearchTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.db=trader.connect(pathlib.Path(self.tmp.name)/'v4.sqlite')
        self.db.executescript(v4_engine.SCHEMA)
        self.now=trader.ts('2026-11-22T12:30:00Z')
        self.cfg=trader.conf()
        self.market={
            1111:{'name':'Recipe <HTML>','cls':'Recipe','nc':False,
                  'ask':10000,'ask2':30000,'median':30000,'vol24':50,
                  'depth5':2,'listed':4,'sure24':7,'flowHours':21,
                  'lastSoldP':20000,'lastSoldT':(self.now-3600)*1000,
                  'vendor':50_000_000},
            2222:{'name':'Sword of Doubt','cls':'Weapon','nc':True,
                  'ask':50000,'ask2':150000,'median':150000,'vol24':8,
                  'depth5':1,'listed':1,'lastSoldP':None,
                  'vendor':5_000_000},
            2589:{'name':'Linen Cloth','cls':'Trade Goods','nc':False,
                  'ask':100,'ask2':100,'median':100,'vol24':999,
                  'depth5':50,'listed':100,'vendor':1},
        }
        for day in range(8):
            for hour in (1,8,12,19):
                t=self.now-(day+1)*86400+hour*3600
                trader.obs(self.db,1111,t,{'ask':20000,'sold':5},'tk')
        trader.save_market(self.db,self.now,self.market,self.now,'tk')
        record=dict(character_key='account:eu-2-110:Mage Pump',
                    realm='eu-2-110',character='Mage Pump',faction='Alliance',
                    last_seen=self.now,gold=500000,wallet_at=self.now,
                    bags={},bags_at=self.now,auctions={},auctions_at=self.now,
                    mail_at=None,mail_pending=None,mail_ready=None,mail_attachments=None)
        with self.db:characters.store(self.db,[record])
        v4_engine.strategy_list(self.db,self.now,self.cfg)
        # The test must commit before its HTTP thread reopens the same DB:
        # otherwise the new manual-ledger schema migration correctly waits
        # on this fixture's uncommitted SQLite writer.
        self.db.commit()

    def tearDown(self):
        self.db.close()
        self.tmp.cleanup()

    def test_evidence_labelled_with_correct_units_and_no_vendor_math(self):
        report=v4_research.build(self.db,self.now,self.cfg)
        self.assertEqual(report['source'],'auctionhouse.tk.gg')
        self.assertEqual(report['snapshot_at'],self.now)
        self.assertEqual(report['market_items'],3)
        self.assertTrue(report['market_fresh'])
        row=next(r for r in report['opportunities'] if r['id']==1111)
        self.assertEqual(row['ask'],10000)
        self.assertEqual(row['hist_median'],20000)
        self.assertGreaterEqual(row['history_days'],8)
        self.assertEqual(row['last_sold_price'],20000)
        self.assertEqual(row['reference_exit'],19000)
        self.assertEqual(row['theoretical_net_before_deposit'],8050)
        self.assertEqual(row['status'],'INTERESSANT — VERIFIËREN')
        # A huge stale vendor price must not suppress ranking or invent profit.
        self.assertNotIn('vendor',row)
        self.assertIn('1111',report['lookup'])


    def test_codex_flash_dip_reaches_vps_research_and_visual_dashboard(self):
        # 31g asks amid 40-42g asks are real market observations, even if the
        # book has zero confirmed sales and insufficient repeatable daily data.
        codex={
            'name':'Codex of Defense','cls':'Recipe','nc':True,
            'ask':310000,'ask2':420000,'listed':10,'depth5':1,
            'vol24':0,'history':[420000]*8+[350000]*2+
                             [420000]*3+[310000]*3+[407700]*8}
        market={**self.market,18357:codex}
        self.db.execute('UPDATE market_snapshots SET payload=? WHERE t=?',
                        (json.dumps(market),self.now))
        self.db.commit()
        report=v4_research.build(self.db,self.now,self.cfg)
        found=next(x for x in report['price_swings']['swings']
                   if x['id']==18357)
        self.assertEqual(found['low_24h'],310000)
        self.assertEqual(found['high_24h'],420000)
        self.assertEqual(found['status'],'DIP — IN GAME CONTROLEREN')
        self.assertEqual(report['intraday']['patterns'],[])
        rendered=v4_dashboard.render([],self.now,report,{})
        self.assertIn('Codex of Defense',rendered)
        self.assertIn('Grote prijsbewegingen (24 uur)',rendered)
        self.assertNotIn('Koop nu',rendered)

    def test_authenticated_research_api_end_to_end(self):
        token='only-a-test-token-that-is-long-enough-for-unit-testing'
        with ThreadingHTTPServer(('127.0.0.1',0),v4_server.Handler) as server:
            server.sync_token=token
            server.db_path=str(pathlib.Path(self.tmp.name)/'v4.sqlite')
            server.cfg=self.cfg
            worker=threading.Thread(target=server.serve_forever,daemon=True)
            worker.start()
            try:
                url=f'http://127.0.0.1:{server.server_port}/api/v4/research'
                with self.assertRaises(urllib.error.HTTPError) as ctx:
                    urllib.request.urlopen(url,timeout=5)
                self.assertEqual(ctx.exception.code,401)
                req=urllib.request.Request(
                    url,headers={'Authorization':'Bearer '+token})
                with urllib.request.urlopen(req,timeout=20) as response:
                    self.assertEqual(response.status,200)
                    report=json.load(response)
                self.assertEqual(report['snapshot_at'],self.now)
                self.assertEqual(report['market'],'eu-2-110')
                self.assertTrue(any(x['id']==1111 for x in report['opportunities']))
            finally:
                server.shutdown()
                worker.join(timeout=3)

    def test_stale_snapshot_is_not_presented_as_current_opportunity(self):
        report=v4_research.build(self.db,self.now+6000,self.cfg)
        self.assertFalse(report['market_fresh'])
        row=next(r for r in report['opportunities'] if r['id']==1111)
        self.assertEqual(row['status'],'VEROUDERD')

    def test_unconfirmed_sale_is_not_assumed_real(self):
        report=v4_research.build(self.db,self.now,self.cfg)
        row=next(r for r in report['opportunities'] if r['id']==2222)
        self.assertEqual(row['status'],'MEER HISTORIE NODIG')
        self.assertIsNone(row['reference_exit'])
        self.assertEqual(row['sale_evidence'],'Alleen geschatte verkoop')

    def test_no_snapshot_is_explicitly_empty(self):
        self.db.execute('DELETE FROM market_snapshots')
        report=v4_research.build(self.db,self.now,self.cfg)
        self.assertEqual(report['opportunities'],[])
        self.assertIsNone(report['snapshot_at'])
        self.assertFalse(report['market_fresh'])


class LocalAddonTests(unittest.TestCase):
    def test_real_AH_book_and_search_history(self):
        now=1800000100
        text=('ForeverTraderDB = {\n'
              ' ["targetLog"] = "1800000000|Alliance|3|1|1111|item|1|2:500:1",\n'
              ' ["v4SearchLog"] = "1800000000:Q:1111:0:0;1800000001:R:1111:250:1",\n'
              ' ["lastAutoSearch"] = "1800000000|1111|1",\n'
              '}\n')
        data=v4_local_activity.from_text(text,now)
        self.assertEqual(len(data['events']),2)
        self.assertEqual(data['events'][0]['kind'],'Resultaat')
        self.assertEqual(data['events'][0]['price'],250)
        self.assertEqual(data['observations'][0]['ask'],250)
        self.assertEqual(data['observations'][0]['units'],2)
        self.assertEqual(data['last_search']['count'],1)

    def test_rejects_garbage_without_executing_lua(self):
        data=v4_local_activity.from_text('ForeverTraderDB = { ["targetLog"]="os.execute(1)" }',1800000100)
        self.assertEqual(data['events'],[])
        self.assertEqual(data['observations'],[])


class DashboardTests(unittest.TestCase):
    def setUp(self):
        self.now=1800000100
        self.strategies=[{'character':'Mage <script>','realm':'eu-2-110',
                          'gold':100001,'last_seen':1800000000,
                          'plan':'FT3|eu-2-110|1800000000|1800086400;1111:0:0:0:0',
                          'actions':[]}]
        self.report={'market_fresh':True,'market_items':1000,
                     'snapshot_at':1800000000,'last_attempt':1800000000,
                     'interesting_count':1,
                     'lookup':{'1111':{'name':'Recipe <script>alert(1)</script>',
                                       'ask':10000,'vol24':50}},
                     'opportunities':[{'id':1111,'name':'Recipe <script>alert(1)</script>',
                      'category':'Recipe','status':'INTERESSANT — VERIFIËREN',
                      'ask':10000,'hist_median':20000,'history_days':5,
                      'history_points':40,'discount_pct':50.0,'vol24':50,'sure24':7,
                      'last_sold_price':19000,'last_sold_at':1800000000,
                      'sale_evidence':'Deels bevestigde verkopen','reference_exit':18000,
                      'max_buy_before_deposit':14000,
                      'theoretical_net_before_deposit':7100,
                      'reason':'historische prijs','suffix_warning':False}]}
        self.activity={'notice':'WoW draait; laatste save, niet live',
                       'game_running':True,'saved_prices':1,
                       'saved_at':1800000001,
                       'observations':[{'id':1111,'at':1800000001,'ask':11000,
                                        'price_rows':2,'units':5}],
                       'last_search':{'id':1111,'at':1800000001,'count':1},
                       'events':[{'id':1111,'at':1800000001,'kind':'Resultaat',
                                  'price':11000,'price_rows':2}]}

    def test_escape_and_real_provenance(self):
        html=v4_dashboard.render(self.strategies,self.now,self.report,self.activity)
        self.assertIn('Market Desk',html)
        self.assertIn('Wat zoekt de addon precies?',html)
        self.assertIn('1 items in de zoeklijst',html)
        self.assertIn('AH-zoeklog en gemeten prijzen',html)
        self.assertIn('laatste save, niet live',html)
        self.assertIn('10g 00s 01c',html)
        self.assertNotIn('<script>alert(1)</script>',html)
        self.assertIn('Recipe &lt;script&gt;',html)
        self.assertNotIn('50000000',html)  # Don't show vendor math.

    def test_search_and_sort_filters(self):
        _,html=v4_dashboard.opportunity_rows(
            self.report['opportunities'],self.now,
            {'mode':'interesting','sort':'signal','q':'1111'})
        self.assertIn('Recipe',html)
        count,html=v4_dashboard.opportunity_rows(
            self.report['opportunities'],self.now,
            {'mode':'interesting','sort':'signal','q':'no match'})
        self.assertEqual(count,0)
        self.assertEqual(html,'')
        affordable,_=v4_dashboard.opportunity_rows(
            self.report['opportunities'],self.now,
            {'mode':'budget','sort':'signal','q':''},budget=10000)
        expensive,_=v4_dashboard.opportunity_rows(
            self.report['opportunities'],self.now,
            {'mode':'budget','sort':'signal','q':''},budget=9999)
        self.assertEqual(affordable,1)
        self.assertEqual(expensive,0)

    def test_exact_copper_format(self):
        self.assertEqual(v4_dashboard.money(14703),'1g 47s 03c')
        self.assertEqual(v4_dashboard.money(80),'0g 00s 80c')
        self.assertEqual(v4_dashboard.money(None),'—')


if __name__=='__main__':
    unittest.main()
