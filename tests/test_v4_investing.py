"""Investment radar should find a rebound, a falling knife and a long momentum trend."""
import pathlib
import tempfile
import unittest

import trader
import v4_investing


class InvestmentSignals(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.db=trader.connect(pathlib.Path(self.tmp.name)/'history.sqlite')
        self.now=trader.ts('2026-11-22T12:00:00Z')
        self.cfg=trader.conf()
        self.market={}
        for i in (1001,1002,1003):
            ask={1001:15000,1002:10000,1003:14000}[i]
            self.market[i]={'name':f'Ingredient {i}','cls':'Trade Goods',
                            'ask':ask,'ask2':int(ask*1.8),
                            'vol24':60,'depth5':15,'listed':40,
                            'nc':False,'vendor':50_000_000}
        for hours in range(336,-1,-4):
            t=self.now-hours*3600
            for item in self.market:
                if item==1001:
                    price=15000 if hours<=24 else 14000 if hours<=48 else 20000
                elif item==1002:
                    price=10000 if hours<=24 else 14000 if hours<=48 else 20000
                else:
                    price=14000 if hours<=168 else 10000
                trader.obs(self.db,item,t,{'ask':price},'tk')
        self.db.commit()

    def tearDown(self):
        self.db.close()
        self.tmp.cleanup()

    def find(self,id,at=None):
        r=v4_investing.analyze(self.db,self.market,self.now,self.cfg,
                               self.now if at is None else at)
        return next(x for x in r['investments'] if x['id']==id),r

    def test_recovery_dip_has_real_history_but_only_scenario_profit(self):
        r,_=self.find(1001)
        self.assertEqual(r['signal'],'KORT — HERSTEL')
        self.assertGreater(r['change_24h_pct'],5)
        self.assertLess(r['discount_vs_7d_pct'],-15)
        self.assertEqual(r['price_7d'],20000)
        self.assertEqual(r['exit_scenario'],19000)
        self.assertEqual(r['max_buy_before_deposit'],15041)
        self.assertGreater(r['scenario_roi_before_deposit'],20)
        self.assertNotIn('vendor',r)

    def test_falling_knife_never_called_buy_dip(self):
        r,_=self.find(1002)
        self.assertEqual(r['signal'],'DALING — AFWACHTEN')
        self.assertLess(r['change_24h_pct'],-20)

    def test_long_momentum_separate_from_short_rebound(self):
        r,_=self.find(1003)
        self.assertEqual(r['signal'],'LANG — OPWAARTS')
        self.assertGreater(r['change_7d_pct'],25)
        self.assertEqual(r['horizon'],'1–3 weken')
        self.assertIn('Speculatief',r['scenario_basis'])
        self.assertGreater(r['scenario_roi_before_deposit'],20)

    def test_old_snapshot_suppresses_all_opportunities(self):
        r,_=self.find(1001,self.now+7200)
        self.assertEqual(r['signal'],'VEROUDERD')
        self.assertIsNone(r['horizon'])

    def test_commodity_basket_not_claimed_inflation_with_3_items(self):
        _,summary=self.find(1003)
        self.assertIsNone(summary['basket_change_7d_pct'])
        self.assertEqual(summary['basket_item_count'],3)


if __name__=='__main__':
    unittest.main()
