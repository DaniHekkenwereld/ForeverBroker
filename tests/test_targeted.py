import pathlib,tempfile,unittest
import trader as ft, coach, targeted
class TargetTests(unittest.TestCase):
 def setUp(self):
  self.temp=tempfile.TemporaryDirectory();self.db=ft.connect(pathlib.Path(self.temp.name)/'test.sqlite');self.c=ft.conf();self.v=ft.register(self.db,self.c);self.t=ft.ts('2026-11-21T08:00:00Z')
 def tearDown(self):self.db.close();self.temp.cleanup()
 def put(self,body,kind='item',t=None,f='Alliance',n=1):
  return targeted.import_log(self.db,f'["targetLog"] = "{t or self.t}|{f}|3|1|2589|{kind}|{n}|{body}",',self.t+200)
 def decision(self,ask=100,roi=30,reason='eligible paper order'):
  ft.item(self.db,2589,{'name':'Linen','vendor':1});ft.decision(self.db,self.t,self.t,2589,'direct','BUY_MODEL' if reason=='eligible paper order' else 'SKIP',reason,self.v,ask,150,20,roi,.6,{'hold_hours':0,'deposit_per_unit':1})
 def test_book(self):
  self.assertEqual(self.put('5:500:3'),1);self.assertEqual(self.put('5:500:3'),0)
  r=targeted.latest(self.db,2589,self.t);self.assertEqual((r['ask'],r['units'],r['rows']),(100,15,3));self.assertEqual(targeted.affordable(r,100,12),(10,1000));self.assertIsNone(targeted.latest(self.db,2589,self.t+120))
 def test_reject_invalid(self):
  self.assertEqual(self.put('5:501:1','commodity'),0);self.assertEqual(self.put('5:500:1',f='Horde'),0);self.assertEqual(self.put('5:500:1',t=self.t+201),0);self.assertEqual(self.put('5:500:1',n=2),0)
 def test_empty_supersedes(self):
  self.put('5:500:1');self.put('',t=self.t+1,n=0);r=targeted.latest(self.db,2589,self.t+1);self.assertIsNone(r['ask']);self.assertEqual(targeted.affordable(r,100,20),(0,0))
 def test_plan_updates(self):
  self.decision();self.put('20:3000:1');self.assertEqual(coach.build_plan(self.db,self.c,self.t,'paper')[1],[])
  self.put('20:1600:1',t=self.t+1);r=coach.build_plan(self.db,self.c,self.t+1,'paper')[1][0];self.assertTrue(r['live']);self.assertGreater(r['roi'],60)
 def test_commodity(self):
  self.put('100:8000:2','commodity');r=targeted.latest(self.db,2589,self.t);self.assertEqual(targeted.affordable(r,80,20),(20,1600))
 def test_new_opportunity(self):
  self.decision(ask=140,roi=0,reason='minimum net ROI incl deposit risk');self.assertEqual(coach.build_plan(self.db,self.c,self.t,'paper')[1],[]);self.put('20:1600:1');self.assertEqual(len(coach.build_plan(self.db,self.c,self.t,'paper')[1]),1)
