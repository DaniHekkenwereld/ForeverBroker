import unittest, tempfile, pathlib, json, sqlite3, zipfile, datetime as dt
from contextlib import closing
import trader as ft
import legacy as old
class V2Tests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.folder=pathlib.Path(self.temp.name);self.db=ft.connect(self.folder/'test.sqlite');self.c=ft.conf();self.vid=ft.register(self.db,self.c);self.t=ft.ts('2026-11-21T08:00:00Z');self.db.commit()
    def tearDown(self):self.db.close();self.temp.cleanup()
    def test_next_market_attempt_keeps_hourly_cadence(self):
        last=ft.ts('2026-11-23T11:27:37Z')
        self.assertEqual(ft.next_market_attempt(last),ft.ts('2026-11-23T12:27:37Z'))
        self.assertEqual(ft.next_market_attempt(ft.ts('2026-11-23T11:22:00Z')),ft.ts('2026-11-23T12:27:00Z'))
        self.assertEqual(ft.next_market_attempt(ft.ts('2026-11-23T11:59:55Z')),ft.ts('2026-11-23T12:59:55Z'))
        self.assertEqual(ft.next_market_attempt(0),0)
    def test_market_history_and_duplicate(self):
        _,m=old.demo_market(self.t,0);self.assertTrue(ft.save_market(self.db,self.t,m,self.t,'demo'));self.assertFalse(ft.save_market(self.db,self.t,m,self.t,'demo'));self.assertEqual(self.db.execute('select count(*) from price_history').fetchone()[0],len(m))
    def test_import(self):
        t=self.t; i=2589; d={'house':{'key':ft.MARKET,'region':'eu','faction':'alliance','grp':1},'item':{'id':i,'name':'Linen'},'f':['ask','sold'],'series':{'t':[t*1000,(t-3600)*1000,(t+3600)*1000],'ask':[10,9,11],'sold':[2,None,3]},'bookT':t*1000,'book':[[10,4,1]],'trades':[[t*1000,10,2,1]],'daily':{'f':['d','open'],'rows':[[t*1000,8]]}}
        ft.parse_history(self.db,d,i,t);ft.parse_history(self.db,d,i,t); self.assertEqual(self.db.execute('select count(*) from price_history').fetchone()[0],2);self.assertEqual(self.db.execute('select count(*) from order_book').fetchone()[0],1);self.assertEqual(self.db.execute('select sure from sales_history').fetchone()[0],1)
        d['house']['grp']=2
        with self.assertRaises((AssertionError,ValueError)):ft.parse_history(self.db,d,i,t)
    def test_profiles_no_future(self):
        m=ft.demo(self.db,self.c,self.t,0); a=ft.profile(self.db,2589,self.t,self.c,'demo');self.assertGreaterEqual(a[1][8][0],5);self.assertGreater(a[1][20][1],a[1][8][1]);self.assertGreaterEqual(a[2][0][0],3)
        for q in range(self.t,self.t+48*3600,3600):ft.obs(self.db,2589,q,{'ask':999999},'demo')
        self.assertEqual(a,ft.profile(self.db,2589,self.t,self.c,'demo'))
    def test_reset_local(self):
        self.assertEqual(ft.reset_bucket(ft.ts('2026-11-18T03:59:00Z'),self.c),6);self.assertEqual(ft.reset_bucket(ft.ts('2026-11-18T04:00:00Z'),self.c),0)
        self.assertEqual(ft.reset_bucket(ft.ts('2026-07-01T03:00:00Z'),self.c),0)
    def test_cycle_ledger_mail_and_expiry(self):
        t=self.t;_,m=old.demo_market(t,0);ft.save_market(self.db,t,m,t,'demo');self.assertTrue(ft.cycle(self.db,self.c,t,m,t,self.vid,'demo'));self.assertFalse(ft.cycle(self.db,self.c,t,m,t+900,self.vid,'demo'))
        a=ft.totals(self.db);self.assertGreater(a['listed'],0);self.assertEqual(a['equity'],a['cash']+a['listed']);self.assertGreaterEqual(a['cash'],200000)
        for x in m.values():x['ask']=10000;x['ask2']=11000;x['sold']=1000
        ft.cycle(self.db,self.c,t+3600,m,t+3600,self.vid,'demo');self.assertEqual(ft.totals(self.db)['incoming'],0)
        self.assertEqual(self.db.execute('select count(*) from paper_sale_checks').fetchone()[0],5)
        ft.cycle(self.db,self.c,t+7200,m,t+7200,self.vid,'demo');a=ft.totals(self.db);self.assertGreater(a['incoming'],0)
        before=a['cash'];ft.settle(self.db,t+7500);self.assertEqual(ft.totals(self.db)['cash'],before)
        ft.settle(self.db,t+10800);self.assertEqual(ft.totals(self.db)['cash'],before+a['incoming'])
        ft.mark_cash(self.db,t+10800);self.assertEqual(self.db.execute("select count(*) from predictions where outcome='model_sold'").fetchone()[0],5)
    def test_held_deposit_and_expiry(self):
        t=self.t; m=ft.demo(self.db,self.c,t,0); c={**self.c,'strategy_weights':{'direct':0,'intraday':80,'weekly':0}};ft.cycle(self.db,c,t,m,t,self.vid,'demo');self.assertGreater(ft.totals(self.db)['inventory'],0);ft.mark_cash(self.db,t)
        for h in range(1,30):
            _,market=old.demo_market(t+h*3600,1)
            for x in market.values(): x['ask']=1;x['sold']=0;x['depth5']=0
            ft.cycle(self.db,c,t+h*3600,market,t+h*3600,self.vid,'demo');ft.mark_cash(self.db,t+h*3600)
        self.assertGreater(self.db.execute("select count(*) from transactions where action='LIST'").fetchone()[0],0); self.assertGreater(self.db.execute("select count(*) from transactions where action='EXPIRE'").fetchone()[0],0)
    def test_population_validation(self):
        p=self.folder/'p.csv';p.write_text('market,observed_at,level_min,level_max,characters,source\neu-2-110,2026-11-05T00:00:00Z,50,59,100,Census\neu-2-110,2026-11-12T00:00:00Z,50,59,200,Census\n');self.assertEqual(ft.import_population(self.db,p),2);ft.item(self.db,14047,{'name':'Runecloth'});out=ft.population_radar(self.db,self.t);self.assertEqual(out[0][2],100); self.assertIn('Runecloth',out[0][4]);p.write_text(p.read_text().replace('eu-2-110','eu-2-113'));self.assertRaises(ValueError,ft.import_population,self.db,p)
    def test_export(self):
        path=ft.export(self.db,self.folder,self.c)
        with zipfile.ZipFile(path) as z:
            self.assertIsNone(z.testzip());self.assertIn('trader.sqlite',z.namelist());self.assertNotIn('wow_folder',json.loads(z.read('config.json')));self.assertIn('trade_decisions.csv',z.namelist());self.assertIn('predictions.csv',z.namelist());p=self.folder/'restored.sqlite';p.write_bytes(z.read('trader.sqlite'))
        # sqlite3 connection context manager commits/rolls back but does not close.
        # Windows locks restored.sqlite until explicitly closed, breaking tearDown.
        with closing(sqlite3.connect(p)) as db:
            self.assertEqual(db.execute('pragma integrity_check').fetchone()[0],'ok')
    def test_backtest_separate(self):
        t=self.t;_,m=old.demo_market(t,0);ft.save_market(self.db,t,m,t,'demo');a=ft.totals(self.db);res=ft.replay(self.db,self.c);self.assertEqual(res['snapshots'],1);self.assertEqual(ft.totals(self.db),a);self.assertEqual(self.db.execute('select count(*) from transactions').fetchone()[0],0)
    def test_stale_data_is_no_order(self):
        _,m=old.demo_market(self.t,0);self.assertFalse(ft.cycle(self.db,self.c,self.t,m,self.t+3*3600,self.vid));self.assertEqual(self.db.execute('select count(*) from transactions').fetchone()[0],0)
if __name__=='__main__':unittest.main()
