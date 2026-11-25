"""Regression: a rare book's 31g -> 40.77g ASK swing must not be invisible.

Detect a one-day flash dip separately from the five-day repeated intraday
strategy. Neither a low asking price nor a recovered high is a proven sale.
"""
import unittest

import trader
import v4_engine
import v4_price_swings
import v4_quickview

NOW=1800000000
ID=18357


def codex(ask=310000):
    return {ID:{
        'name':'Codex of Defense','cls':'Recipe','nc':True,
        'ask':ask,'ask2':420000,'vol24':0,'listed':10,'depth5':1,
        'history':[420000]*8+[350000]*2+[420000]*3+
                  [310000]*3+[407700]*8}}


class RareBookSwingTests(unittest.TestCase):
    def test_rare_item_no_sales_still_flags_real_31g_price_dip(self):
        market=codex()
        out=v4_price_swings.analyze(market,NOW,NOW)
        self.assertEqual(out['active_dips'],1)
        self.assertEqual(out['total_swings'],1)
        row=out['swings'][0]
        self.assertEqual(row['id'],18357)
        self.assertEqual(row['low_24h'],310000)
        self.assertEqual(row['high_24h'],420000)
        self.assertEqual(row['spread_copper'],110000)
        self.assertEqual(row['status'],'DIP — IN GAME CONTROLEREN')
        self.assertGreater(row['swing_pct'],30)

    def test_recovered_dip_is_an_observation_not_buy_signal(self):
        out=v4_price_swings.analyze(codex(407700),NOW,NOW)
        self.assertEqual(out['recovered_dips'],1)
        self.assertEqual(out['active_dips'],0)
        row=out['swings'][0]
        self.assertEqual(row['status'],'DIP VOORBIJ — PRIJS HERSTELD')
        self.assertEqual(row['current_ask'],407700)
        ui=v4_quickview.render({
            'market_fresh':True,'snapshot_at':NOW,
            'price_swings':out,'portfolio':{},
            'opportunities':[],'game_checks':[]},NOW)
        self.assertIn('Codex of Defense',ui)
        self.assertIn('DIP GEZIEN / HERSTELD',ui)
        self.assertNotIn('Instap gemeten',ui)
        self.assertNotIn('Koop nu',ui)

    def test_swing_does_not_require_repeated_complete_days_or_volume(self):
        cfg=trader.conf()
        row=codex()[ID]
        character={
            'character_key':'acct:eu-2-110:Warrior Pump','realm':'eu-2-110',
            'character':'Warrior Pump','faction':'Alliance',
            'gold':2000000,'wallet_at':NOW,'last_seen':NOW,
            'bags':{},'auctions':{},
        }
        swing=v4_price_swings.analyze({ID:row},NOW,NOW)['swings']
        result=v4_engine.build_character(character,{ID:row},NOW,NOW,cfg,
                         history={},investment_candidates=[],swing_candidates=swing)
        self.assertIn(';18357:0:0:0:0',result['plan'])
        self.assertFalse(any(x['kind'] in ('VERIFY_BUY','INVEST_SHORT','INVEST_LONG')
                             for x in result['actions']))
        self.assertFalse(result['warning'] if 'warning' in result else False)

    def test_no_fake_signal_with_thin_history_and_stale_source(self):
        empty=codex()
        empty[ID]['history']=[420000,310000,407700]
        self.assertFalse(v4_price_swings.analyze(empty,NOW,NOW)['swings'])
        stale=v4_price_swings.analyze(codex(),NOW,NOW+7200)
        self.assertFalse(stale['market_fresh'])
        ui=v4_quickview.render({
            'market_fresh':False,'snapshot_at':NOW,
            'price_swings':stale,'portfolio':{}},NOW+7200)
        self.assertNotIn('DIP — IN GAME CONTROLEREN',ui)

    def test_invalid_and_html_name_are_safe(self):
        data=codex()
        data[ID]['name']='<img src=x onerror=alert(1)>'
        good=v4_price_swings.analyze(data,NOW,NOW)
        html=v4_price_swings.render_details(good)
        self.assertIn('18357',html)
        self.assertNotIn('<img src=x onerror=alert(1)>',html)
        self.assertIn('&lt;img',html)
        bad={999:{'ask':0,'history':[0]*24,'name':'Bad'}}
        self.assertEqual(v4_price_swings.analyze(bad,NOW,NOW)['total_swings'],0)


if __name__=='__main__':
    unittest.main()
