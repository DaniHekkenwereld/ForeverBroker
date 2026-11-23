import pathlib, tempfile, unittest, time, json
import legacy as ft
# Never parse the user's mutable config.json in regression tests. It may be
# rewritten by Windows PowerShell with a UTF-8 BOM or local account settings.
C=json.loads((pathlib.Path(__file__).parent/'fixtures'/'trader_config.json').read_text(encoding='utf-8-sig'))
class TraderTests(unittest.TestCase):
    def test_market_named_fields(self):
        n=ft.now(); f=['vol24','ask','ask2','listed','depth5','flowHours']
        d={'house':{'key':ft.MARKET,'region':'eu','faction':'alliance','grp':1},'t':n*1000,'f':f,'items':[{'id':2589,'o':[100,20,40,50,2,23]}]}
        t,rows=ft.parse_market(d); self.assertEqual(rows[2589]['ask'],20)
        d['house']['faction']='horde'; self.assertRaises(ValueError,ft.parse_market,d)
    def test_ahl(self):
        t,r=ft.parse_ahl('AHL1|forever/pvp/alliance/eu|1793000000|1\n2589:20:18:3420:22:21:18:25:3600'); self.assertEqual(r[2589]['daily'],360)
        self.assertRaises(ValueError,ft.parse_ahl,'AHL1|forever/pvp/horde/eu|1|0')
    def test_cycle_and_duplicates(self):
        t=ft.now(); s=ft.initial(C); _,m=ft.demo_market(t,0)
        self.assertTrue(ft.cycle(s,C,t,m,t)); self.assertGreater(len(s['lots']),0); self.assertEqual(ft.net(s),s['starting']); self.assertGreaterEqual(s['cash'],s['starting']*.2)
        old=s['cash']; self.assertFalse(ft.cycle(s,C,t,m,t+900)); self.assertEqual(s['cash'],old)
        self.assertFalse(ft.cycle(s,C,t+1,m,t+10000))
    def test_incoming_and_settlement(self):
        t=ft.now(); s=ft.initial(C); _,m=ft.demo_market(t,0); ft.cycle(s,C,t,m,t)
        for x in m.values(): x['ask']=10000; x['ask2']=11000
        ft.cycle(s,C,t+3601,m,t+3601); self.assertGreater(len(s['incoming']),0); self.assertGreater(s['realized'],0)
        old=s['cash']; amount=sum(p['amount'] for p in s['incoming']); ft.settle(s,t+3602); self.assertEqual(s['cash'],old)
        ft.settle(s,t+7201); self.assertEqual(s['cash'],old+amount); self.assertEqual(s['incoming'],[]); self.assertEqual(ft.net(s),s['starting']+s['realized'])
    def test_expiry(self):
        t=ft.now(); s=ft.initial(C); _,m=ft.demo_market(t,0); ft.cycle(s,C,t,m,t); deps=sum(x['deposit'] for x in s['lots']); ft.settle(s,t+12*3600)
        self.assertEqual(s['loss'],deps); self.assertTrue(all(x['status']=='inventory' for x in s['lots'])); self.assertEqual(ft.net(s),s['starting']-deps)
    def test_local_parser(self):
        with tempfile.TemporaryDirectory() as d:
            folder=pathlib.Path(d)/'WTF/Account/Test/SavedVariables'; folder.mkdir(parents=True)
            f=folder/'ForeverTrader.lua'; f.write_text('ForeverTraderDB = {\n ["schema"] = "FT1",\n ["wallet"] = "100|200|Alliance|3",\n ["mail"] = "100|50|40",\n ["scan"] = "100|Alliance|3|2;2589:5:100;2589:1:40",\n}\n')
            a,msg=ft.load_local({**C,'wow_folder':d}); self.assertEqual(a['wallet'][1],200); self.assertEqual(a['scan'][3][2589],[(5,100),(1,40)])
            self.assertEqual(a['mail'][1],50)
    def test_crafting(self):
        d={'market':'forever.pvp.alliance.eu','marketStatus':'scanned','pricesAsOf':'2026-11-05T14:02:11.000Z','recipes':[{'recipe':{'name':'Copper','profession':'Smith','skillRequired':1},'result':{'id':1},'cost':100,'margin':25,'unpriced':[]}]}
        t,r=ft.parse_crafting(d); self.assertEqual(r[0]['roi'],25)
        d['market']='wrong'; self.assertRaises(ValueError,ft.parse_crafting,d)
    def test_bad_config(self):
        self.assertRaises(ValueError,ft.validate,{**C,'local_scan_paper_enabled':True})
    def test_dashboard(self):
        with tempfile.TemporaryDirectory() as d:
            t=ft.now(); s=ft.initial(C); _,m=ft.demo_market(t,0); ft.cycle(s,C,t,m,t); path=pathlib.Path(d)/'dash.html'; ft.dashboard(path,s,C,m,{},'no local','<bad>','demo',None,t); text=path.read_text(); self.assertIn('FICTIEVE DEMODATA',text); self.assertIn('&lt;bad&gt;',text)
if __name__=='__main__': unittest.main()
