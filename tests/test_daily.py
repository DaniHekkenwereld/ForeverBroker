"""Regression tests for day-trading windows, evidence and capital allocation."""
import datetime as dt
import pathlib
import tempfile
import unittest
from unittest.mock import patch
from zoneinfo import ZoneInfo

import daily
import coach
import trader as ft


class DailyWindowsTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.db = ft.connect(pathlib.Path(self.temp.name) / 'daily.sqlite')
        self.c = ft.conf()
        self.vid = ft.register(self.db, self.c)
        self.at = int(dt.datetime(2026, 11, 22, 9, tzinfo=ZoneInfo('Europe/Amsterdam')).timestamp())

    def tearDown(self):
        self.db.close()
        self.temp.cleanup()

    def seed(self, trend=True, days=7):
        z = ZoneInfo('Europe/Amsterdam')
        for day in range(15, 15 + days):
            for hour in range(24):
                at = int(dt.datetime(2026, 11, day, hour, tzinfo=z).timestamp())
                ask = (100 if 6 <= hour < 12 else 145 if 17 <= hour < 23 else 125) if trend else 100
                ft.obs(self.db, 2589, at, {'ask': ask, 'sold': 5000}, 'demo')
        ft.item(self.db, 2589, {'name': 'Linen Cloth', 'cls': 'Trade Goods', 'vendor': 1})

    def test_morning_buy_evening_sell(self):
        self.seed()
        p = daily.analyse(self.db, 2589, self.at, self.c, 'demo')
        self.assertTrue(p['eligible'])
        self.assertEqual((p['buy'], p['sell']), ('Ochtend', 'Avond'))
        self.assertEqual(p['samples'], 7)
        self.assertTrue(daily.opportunity(p, 100, 9, self.c, 1))
        self.assertIsNone(daily.opportunity(p, 100, 20, self.c, 1))
        self.assertIsNone(daily.opportunity(p, p['ceiling'] + 1, 9, self.c, 1))

    def test_flat_prices_do_not_trigger_purchases(self):
        self.seed(trend=False)
        p = daily.analyse(self.db, 2589, self.at, self.c, 'demo')
        self.assertFalse(p['eligible'])
        self.assertIsNone(daily.opportunity(p, 100, 9, self.c, 1))

    def test_missing_days_do_not_trigger(self):
        self.seed(days=4)
        self.assertIsNone(daily.analyse(self.db, 2589, self.at, self.c, 'demo'))

    def test_no_future_or_partial_day_leakage(self):
        self.seed(trend=False)
        z = ZoneInfo('Europe/Amsterdam')
        for hour in range(24):
            when = int(dt.datetime(2026, 11, 22, hour, tzinfo=z).timestamp())
            ft.obs(self.db, 2589, when, {'ask': 100 if hour < 12 else 99999}, 'demo')
        p = daily.analyse(self.db, 2589, self.at, self.c, 'demo')
        self.assertFalse(p['eligible'])

    def test_history_import_prioritizes_spread_over_raw_volume(self):
        liquid_flat={'vol24':100000,'depth5':50000,'history':[100]*24}
        swing={'vol24':3000,'depth5':1000,'history':[100]*12+[180]*12}
        self.assertGreater(ft.history_priority(swing,self.c),
                           ft.history_priority(liquid_flat,self.c))
        self.assertEqual(ft.history_priority({'vol24':None,'depth5':None},self.c),(0,0))

    def test_coach_handoffs_daily_beyond_watchlist(self):
        # Model found a vetted daily window for an imported item not on the old
        # 21-item watchlist; it must be reachable in the in-game FT3 plan.
        item_id = 3575
        self.assertNotIn(item_id, self.c['watchlist'])
        ft.item(self.db, item_id, {'name': 'Iron Bar', 'cls': 'Trade Goods', 'vendor': 1})
        ft.decision(self.db, self.at, self.at, item_id, 'daily', 'BUY_MODEL',
                    'eligible paper order', self.vid, 100, 120, 100, 12, .7,
                    {'hold_hours': 8, 'deposit_per_unit': 1,
                     'buy_window': 'Ochtend', 'sell_window': 'Avond'})
        payload, rows, message = coach.build_plan(self.db, self.c, self.at, 'paper')
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]['strategy'], 'daily')
        self.assertIn(';3575:', payload)

    def test_scale_paper_buy_to_budget(self):
        self.seed()
        self.db.execute('INSERT INTO import_log VALUES(?,?,?,?)', (2589, self.at - 3600, self.at - 3600, 'seed'))
        m = {2589: dict(id=2589, name='Linen Cloth', cls='Trade Goods', nc=False,
                       ask=100, ask2=150, depth5=10000, vol24=100000,
                       flowHours=24, vendor=1, sold=10000)}
        ft.save_market(self.db, self.at, m, self.at, 'demo')
        with patch.object(ft.old, 'candidates', return_value=[]), patch.object(ft, 'research', return_value=[]):
            ft.cycle(self.db, self.c, self.at, m, self.at, self.vid, 'demo')
        trades = self.db.execute("SELECT * FROM trade_decisions WHERE strategy='daily' AND action='BUY_MODEL'").fetchall()
        self.assertEqual(len(trades), 1)
        lot = self.db.execute("SELECT * FROM inventory WHERE strategy='daily'").fetchone()
        self.assertGreater(lot['cost'], 10000)
        self.assertLessEqual(lot['cost'] + lot['deposit'], self.c['daily_item_pct'] * 10000)
        self.assertGreaterEqual(ft.totals(self.db)['cash'], 100 * 10000 * self.c['reserve_pct'] / 100)
        self.assertEqual(lot['list_at'] - self.at, 8 * 3600)


if __name__ == '__main__':
    unittest.main()
