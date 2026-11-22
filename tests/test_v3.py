import pathlib,tempfile,unittest,json
import trader as ft
import coach
class CoachTests(unittest.TestCase):
 def setUp(self):
  self.temp=tempfile.TemporaryDirectory();self.db=ft.connect(pathlib.Path(self.temp.name)/'test.sqlite');self.c=ft.conf();self.v=ft.register(self.db,self.c);self.t=ft.ts('2026-11-21T08:00:00Z')
 def tearDown(self):self.db.close();self.temp.cleanup()
 def add(self,i=2589,target=150,hold=0,reason='eligible paper order'):
  ft.item(self.db,i,{'name':'Linen','vendor':1});ft.decision(self.db,self.t,self.t,i,'direct' if not hold else 'intraday','BUY_MODEL' if reason=='eligible paper order' else 'SKIP',reason,self.v,100,target,20,30,.6,{'hold_hours':hold,'deposit_per_unit':1})
 def test_plan(self):
  self.add();p,rows,msg=coach.build_plan(self.db,self.c,self.t,'paper');self.assertEqual(len(rows),1);self.assertIn(';2589:122:20:150:0',p)
  self.assertEqual(coach.build_plan(self.db,self.c,self.t+5400,'paper')[0],'');self.assertEqual(coach.build_plan(self.db,self.c,self.t,'demo')[0],'')
 def test_plan_filters(self):
  self.add(99999);self.add(2589,reason='holding horizon limit');self.add(10620,hold=6);p,rows,_=coach.build_plan(self.db,self.c,self.t,'paper');self.assertEqual([r['id'] for r in rows],[10620]);self.assertEqual(rows[0]['hold'],6)
 def test_cap(self):
  self.add(target=120);_,r,_=coach.build_plan(self.db,self.c,self.t,'paper');self.assertLess(r[0]['max'],100)
 def test_monitor_fallback_with_real_snapshot(self):
  m={2589:{'name':'Linen Cloth','ask':100,'ask2':150,'cls':'Trade Goods','vol24':2000,'nc':False},2592:{'name':'Wool Cloth','ask':200,'ask2':240,'cls':'Trade Goods','vol24':1800,'nc':False}}
  ft.save_market(self.db,self.t,m,self.t,'tk')
  payload,rows,msg=coach.build_plan(self.db,self.c,self.t,'paper')
  self.assertEqual(len(rows),2)
  self.assertTrue(all(r['strategy']=='monitor' and r['max']==0 and r['qty']==0 for r in rows))
  self.assertIn(';2589:0:0:0:0',payload)
  self.assertIn('0 koopkansen',msg)
 def test_stale_market_still_generates_read_only_monitor_plan(self):
  market={2589:{'name':'Linen Cloth','ask':100,'cls':'Trade Goods','vol24':1200,'nc':False},
          2592:{'name':'Wool Cloth','ask':300,'cls':'Trade Goods','vol24':600,'nc':False}}
  ft.save_market(self.db,self.t,market,self.t,'tk')
  self.add(i=2589,target=160)
  now=self.t+7200
  payload,rows,msg=coach.build_plan(self.db,self.c,now,'paper')
  self.assertEqual(len(rows),2)
  self.assertTrue(all(r['strategy']=='monitor' and r['qty']==0 and r['max']==0 and r['target']==0 for r in rows))
  self.assertTrue(all(r['stale'] for r in rows))
  self.assertIn('Geen koopadvies',msg)
  self.assertTrue(payload.startswith(f'FT3|eu-2-110|{now}|{now+3600};'),payload)
  self.assertIn('2589:0:0:0:0',payload)
 def test_stale_ignores_previous_paper_trades(self):
  self.add(i=2589)
  self.assertEqual(coach.build_plan(self.db,self.c,self.t+7200,'paper')[0],'')
 def test_stale_snapshot_without_eligible_items_stays_empty(self):
  ft.save_market(self.db,self.t,{2589:{'name':'Linen Cloth','ask':0,'cls':'Trade Goods','vol24':1000,'nc':False}},self.t,'tk')
  self.assertEqual(coach.build_plan(self.db,self.c,self.t+7200,'paper')[0],'')
 def test_monitor_does_not_become_fake_buy(self):
  m={2589:{'name':'Linen Cloth','ask':100,'cls':'Trade Goods','vol24':2000,'nc':False}}
  ft.save_market(self.db,self.t,m,self.t,'tk')
  _,rows,_=coach.build_plan(self.db,self.c,self.t,'paper')
  self.assertEqual(rows[0]['strategy'],'monitor')
 def test_no_handoff_without_market_or_decision(self):
  self.assertEqual(coach.build_plan(self.db,self.c,self.t,'paper')[0],'')
 def test_local_extras(self):
  a=coach.extras('["mail3"] = "100|20|30|1|0|0",\n["coach"] = "100|MAIL|20|30|0|1|0",\n["bags"] = "100;2589:20",\n["owned"] = "100;2589:1:80",\n["coachLog"] = "100|MAIL|20|30|0|1|0;101|AH|20|0|0|1|0",');self.assertEqual(set(a),{'mail3','coach','bags','owned','coachLog'})
 def test_timing_not_direct_gate(self):
  m=ft.demo(self.db,self.c,self.t,0)
  for x in m.values():x['ask2']=x['ask'];x['depth5']=5000
  ft.save_market(self.db,self.t,m,self.t,'demo');ft.cycle(self.db,self.c,self.t,m,self.t,self.v,'demo')
  self.assertGreater(self.db.execute("select count(*) from trade_decisions where strategy='intraday' and roi is not null").fetchone()[0],0)
  self.assertEqual(self.db.execute("select count(*) from trade_decisions where strategy='direct'").fetchone()[0],0)
if __name__=='__main__':unittest.main()
