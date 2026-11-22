"""Whole-market discovery regression tests (no trades, no external API)."""
import pathlib
import tempfile
import unittest
from unittest.mock import patch

import trader as ft
import opportunities
import coach


class AllMarketRadarTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.db=ft.connect(pathlib.Path(self.tmp.name)/'trader.sqlite')
        self.c=ft.conf()
        self.t=ft.ts('2026-11-22T13:00:00Z')

    def tearDown(self):
        self.db.close()
        self.tmp.cleanup()

    @staticmethod
    def markets():
        # All types have nc=True; old trader would ignore every one of them.
        return {
            6475:dict(id=6475,name='Pattern: Deviate Scale Gloves',cls='Recipe',
                      nc=True,ask=2000,ask2=20400,median=20400,vol24=11,
                      depth5=1,vendor=10,lastSoldP=2000),
            15744:dict(id=15744,name='Pattern: Wicked Leather Headband',cls='Recipe',
                       nc=True,ask=15090,ask2=34890,median=34890,vol24=13,
                       depth5=1,vendor=10,lastSoldP=34890),
            13260:dict(id=13260,name='Wind Dancer Boots',cls='Armor',
                       nc=True,ask=89999,ask2=226999,median=226999,vol24=2,
                       depth5=1,vendor=10,lastSoldP=90000),
            1607:dict(id=1607,name='Soulkeeper',cls='Weapon',
                      nc=True,ask=82222,ask2=140000,median=140000,vol24=6,
                      depth5=1,vendor=10,lastSoldP=55001),
            2589:dict(id=2589,name='Linen Cloth',cls='Trade Goods',
                      nc=False,ask=100,ask2=100,median=100,vol24=1000,
                      depth5=10,vendor=10),
        }

    def test_all_categories_and_budget_status(self):
        rows,stats=opportunities.rank_market(self.markets(),self.c,budget_gold=20)
        self.assertEqual(stats['seen'],5)
        self.assertEqual(stats['priced'],5)
        self.assertEqual(stats['spread_positive'],4)
        self.assertEqual({r['id'] for r in rows},{6475,15744,13260,1607})
        self.assertTrue(all(r['affordable'] for r in rows))
        self.assertEqual(next(r for r in rows if r['id']==6475)['net_per_unit'],17322)
        self.assertTrue(next(r for r in rows if r['id']==13260)['suffix_risk'])

    def test_candidate_cannot_become_buy_plan(self):
        m=self.markets()
        ft.save_market(self.db,self.t,m,self.t)
        payload,rows,msg=coach.build_plan(self.db,self.c,self.t,'paper')
        ids={r['id'] for r in rows}
        self.assertIn(15744,ids)
        self.assertIn(13260,ids)
        self.assertTrue(all(r['strategy']=='monitor' and
                            r['qty']==0 and r['max']==0 and r['target']==0 for r in rows))
        self.assertIn(';15744:0:0:0:0',payload)
        self.assertIn('0 koopkansen',msg)

    def test_missing_second_ask_or_no_profit_is_not_a_fake_opportunity(self):
        m={
            1:dict(id=1,name='Only one item',cls='Recipe',nc=True,
                   ask=10000,median=10000,vol24=5),
            2:dict(id=2,name='Two same listings',cls='Weapon',nc=True,
                   ask=10000,ask2=10000,median=10000,vol24=5),
        }
        rows,stats=opportunities.rank_market(m,self.c)
        self.assertEqual(rows,[])
        self.assertEqual(stats['seen'],2)

    def test_rare_item_history_import_has_priority_over_stale_watchlist(self):
        m=self.markets()
        # Existing watchlist would otherwise hog the three scarce hourly imports.
        seen=[]
        def fail_get(url):
            seen.append(url)
            raise RuntimeError('test: no live API')
        with patch.object(ft.old,'get',side_effect=fail_get),patch.object(ft.time,'sleep'):
            ft.import_history(self.db,self.c,m,self.t,limit=1)
        self.assertEqual(len(seen),1)
        self.assertIn('/item/',seen[0])
        self.assertNotIn('/item/2589?',seen[0])

    def test_market_cost_above_budget_still_shows_on_radar(self):
        m={42:dict(name='Rare Recipe',cls='Recipe',nc=True,
                   ask=250000,ask2=500000,median=480000,vol24=3,
                   depth5=1,vendor=1,lastSoldP=480000)}
        rows,_=opportunities.rank_market(m,self.c,budget_gold=20)
        self.assertEqual(len(rows),1)
        self.assertFalse(rows[0]['affordable'])


if __name__=='__main__':
    unittest.main()
