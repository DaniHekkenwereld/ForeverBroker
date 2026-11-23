"""ForeverTrader 1.0 beta portfolio, bank and intraday acceptance tests."""
import pathlib
import sqlite3
import tempfile
import unittest

import characters
import daily
import trader
import v4_daily_radar
import v4_investing
import v4_portfolio
import v4_portfolio_ui
import v4_research
import v4_server


NOW=1800000000


class BankSyncTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.db=sqlite3.connect(pathlib.Path(self.tmp.name)/'portfolio.sqlite')
        self.db.row_factory=sqlite3.Row
        self.db.executescript(characters.SCHEMA)
    def tearDown(self):
        self.db.close();self.tmp.cleanup()

    def raw(self,bank_timestamp=True):
        char='|'.join([str(NOW),'eu-2-110','Mage Pump','Alliance',
                       '500000',str(NOW),str(NOW),'14344:2',
                       str(NOW),'',str(NOW),'0','0','0'])
        row='|'.join([str(NOW),'eu-2-110','Mage Pump',
                      str(NOW) if bank_timestamp else '',
                      '12363:5,16203:3' if bank_timestamp else '',
                      '16203:3' if bank_timestamp else '',
                      str(NOW),'14344:2',str(NOW),'18832:1'])
        return ('ForeverTraderDB = {\n'
                ' ["charactersWire"] = "FTCHAR1;'+char+'",\n'
                ' ["stockWire"] = "FTSTOCK1;'+row+'",\n}\n')

    def test_all_locations_import_and_merge_with_original_character(self):
        text=self.raw()
        chars=characters.parse_saved_variables(text,NOW+10,'account')
        stocks=characters.parse_stock_wire(text,NOW+10,'account')
        self.assertEqual(len(chars),1)
        chars[0].update(stocks[chars[0]['character_key']])
        v4_server.validate_characters(chars,NOW+10)
        self.assertEqual(characters.store(self.db,chars),1)
        row=characters.read_all(self.db)[0]
        self.assertEqual(row['bags'],{'14344':2})
        self.assertEqual(row['bag_bound'],{'14344':2})
        self.assertEqual(row['bank'],{'12363':5,'16203':3})
        self.assertEqual(row['bank_bound'],{'16203':3})
        self.assertEqual(row['equipment'],{'18832':1})
        self.assertEqual(row['bank_at'],NOW)
        # Old export does not clear independently timed bank observations.
        original=characters.parse_saved_variables(text,NOW+10,'account')
        self.assertEqual(characters.store(self.db,original),0)
        self.assertEqual(characters.read_all(self.db)[0]['bank']['12363'],5)

    def test_never_accept_bank_without_valid_measurement_time(self):
        with self.assertRaises(ValueError):
            characters.parse_stock_wire(self.raw(bank_timestamp=False).replace(
                '|||' ,'|12363:5||',1),NOW+10,'account')

    def test_server_rejects_bound_count_greater_than_owned_count(self):
        text=self.raw()
        chars=characters.parse_saved_variables(text,NOW+10,'account')
        chars[0].update(characters.parse_stock_wire(text,NOW+10,'account')
                        [chars[0]['character_key']])
        chars[0]['bank_bound']={'12363':6}
        with self.assertRaises(ValueError):
            v4_server.validate_characters(chars,NOW+10)


class PortfolioAdviceTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.db=trader.connect(pathlib.Path(self.tmp.name)/'market.sqlite')
        self.now=trader.ts('2026-11-22T12:00:00Z')
        self.cfg=trader.conf()
        self.market={
            12363:{'name':'Arcane Crystal','cls':'Trade Goods','ask':15000,
                   'vol24':40},
            16203:{'name':'Greater Eternal Essence','cls':'Trade Goods',
                   'ask':8000,'vol24':80},
            14344:{'name':'Large Brilliant Shard','cls':'Trade Goods',
                   'ask':10000,'vol24':60},
            18832:{'name':'Equipped Weapon','cls':'Weapon','ask':200000,'vol24':2},
        }
        self.warrior=dict(character_key='acc:eu-2-110:Warrior Pump',
            character='Warrior Pump',realm='eu-2-110',faction='Alliance',
            last_seen=self.now,gold=2_000_000,wallet_at=self.now,
            bags={'14344':2},bags_at=self.now,auctions={},auctions_at=self.now,
            bank={'12363':5,'16203':3},bank_at=self.now,
            bank_bound={'16203':3},bag_bound={'14344':2},
            bag_bound_at=self.now,equipment={'18832':1},equipment_at=self.now,
            mail_at=None,mail_pending=None,mail_ready=None,mail_attachments=None)
        self.mage={**self.warrior,'character_key':'acc:eu-2-110:Mage Pump',
                   'character':'Mage Pump','gold':500_000,'bags':{},
                   'bank':{},'bank_bound':{},'bag_bound':{},'equipment':{}}
        characters.store(self.db,[self.warrior,self.mage])

    def tearDown(self):
        self.db.close();self.tmp.cleanup()

    def test_gold_and_all_items_with_binding_safeguards(self):
        p=v4_portfolio.build(self.db,self.market,self.now,self.now,self.cfg,[])
        self.assertEqual(p['gold_total_last_known'],2_500_000)
        self.assertEqual(p['wallet_count'],2)
        self.assertEqual(p['bank_not_seen'],0)
        held={r['id']:r for r in p['holdings']}
        self.assertEqual(held[12363]['bank'],5)
        self.assertEqual(held[12363]['potentially_sellable'],5)
        self.assertEqual(held[12363]['quoted_mark'],75000)
        self.assertEqual(held[16203]['potentially_sellable'],0)
        self.assertEqual(held[14344]['potentially_sellable'],0)
        self.assertEqual(held[18832]['equipment'],1)
        self.assertIsNone(held[18832]['quoted_mark'])
        self.assertFalse(p['cost_basis_known'])
        self.assertIsNone(p['realized_profit'])
        html=v4_portfolio_ui.render(p,self.now)
        self.assertIn('Warrior Pump',html)
        self.assertIn('Mage Pump',html)
        self.assertIn('Arcane Crystal',html)
        self.assertIn('Gebonden',html)
        self.assertIn('250g 00s 00c',html)

    def test_bank_not_seen_is_flagged_not_treated_as_empty(self):
        self.db.execute('UPDATE character_portfolio SET bank_at=NULL,bank=NULL '
                        'WHERE character_key=?',(self.warrior['character_key'],))
        p=v4_portfolio.build(self.db,self.market,self.now,self.now,self.cfg,[])
        self.assertEqual(p['bank_not_seen'],1)

    def test_dynamic_budget_scales_with_gold(self):
        small=v4_portfolio.allocation(50*10000)
        large=v4_portfolio.allocation(800*10000)
        self.assertGreater(large['long_budget'],small['long_budget'])
        self.assertLess(small['long_budget'],small['short_budget'])
        self.assertGreater(large['long_budget'],large['short_budget'])
        self.assertGreater(large['reserve'],0)

    def test_tier_themes_are_explicit_hypotheses(self):
        p=v4_portfolio.build(self.db,self.market,self.now,self.now,self.cfg,[])
        t=next(x for x in p['themes'] if x['id']==12363)
        self.assertIn('crafting',t['thesis'])
        self.assertEqual(t['event_date'],'2026-12-09')
        self.assertIn('PRIJSIMPACT ONBEWEZEN',t['status'])

    def test_no_stale_buy_signal(self):
        inv={'id':7068,'name':'Elemental Fire','ask':1000,
             'signal':'KORT — HERSTEL','max_buy_before_deposit':1100,
             'exit_scenario':1500,'volume_24h':50,'warning':'historisch goedkoop'}
        p=v4_portfolio.build(self.db,self.market,self.now,self.now+7200,self.cfg,[inv])
        self.assertEqual(p['buy_review'],[])


class IntradayTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.db=trader.connect(pathlib.Path(self.tmp.name)/'timing.sqlite')
        self.now=trader.ts('2026-11-23T07:30:00Z')
        self.cfg=trader.conf()
        self.cfg['daily_min_days']=5
        self.cfg['daily_min_net_roi_pct']=8
        self.cfg['daily_min_win_rate']=.7
        self.market={7068:{'name':'Elemental Fire','ask':1000,
                            'cls':'Trade Goods','vol24':90}}
        # 8 completed days, 24 local hourly quotes/day. Morning buys,
        # evening quotes rise; no future / partial current-day input.
        zone=__import__('zoneinfo').ZoneInfo('Europe/Amsterdam')
        import datetime as dt
        localtoday=dt.datetime.fromtimestamp(self.now,dt.timezone.utc).astimezone(zone).date()
        for day in range(1,9):
            d=localtoday-dt.timedelta(days=day)
            for hour in range(24):
                t=int(dt.datetime(d.year,d.month,d.day,hour,30,tzinfo=zone).timestamp())
                ask=(1000 if 6<=hour<12 else 1600 if 17<=hour<23 else 1200)
                trader.obs(self.db,7068,t,{'ask':ask},'tk')
        self.db.commit()

    def tearDown(self):
        self.db.close();self.tmp.cleanup()

    def test_empirical_morning_buy_evening_sell(self):
        result=v4_daily_radar.build(self.db,self.market,self.now,self.now,self.cfg,
                                    held_ids=[7068])
        self.assertEqual(result['timezone'],'Europe/Amsterdam')
        self.assertTrue(result['patterns'],result)
        p=result['patterns'][0]
        self.assertEqual(p['id'],7068)
        self.assertEqual(p['buy_window'],'Ochtend')
        self.assertEqual(p['sell_window'],'Avond')
        self.assertEqual(p['status'],'NU KOOPPRIJS CONTROLEREN')
        self.assertGreaterEqual(p['paired_days'],5)
        self.assertGreater(p['conservative_net_roi_pct'],8)

    def test_no_imaginary_intraday_opportunity_without_complete_days(self):
        self.db.execute('DELETE FROM price_history')
        result=v4_daily_radar.build(self.db,self.market,self.now,self.now,self.cfg,
                                    held_ids=[7068])
        self.assertEqual(result['patterns'],[])
        self.assertEqual(result['missing_history_count'],1)


if __name__=='__main__':
    unittest.main()
