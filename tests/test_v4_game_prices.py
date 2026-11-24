"""End-to-end acceptance: WoW SavedVariables -> Windows bridge -> VPS quote audit."""
import pathlib
import sqlite3
import tempfile
import unittest

import trader
import v4_bridge
import v4_game_prices

NOW=1800000200


class ExactGameQuoteTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.db=trader.connect(pathlib.Path(self.tmp.name)/'quotes.sqlite')
        self.db.executescript(v4_game_prices.SCHEMA)
    def tearDown(self):
        self.db.close();self.tmp.cleanup()

    def test_saved_ah_result_not_merely_sent_query_is_uploaded(self):
        text=('ForeverTraderDB = {\n'
              '  ["v4SearchLog"] = "1800000010:Q:2589:0:0;'
              '1800000015:R:2589:100:1",\n'
              '  ["targetLog"] = "1800000015|Alliance|3|1|2589|item|1|5:500:1",\n'
              '}\n')
        observed=v4_bridge.game_quotes_from_saved(text,NOW)
        self.assertEqual(len(observed),1)
        self.assertEqual(observed[0]['id'],2589)
        self.assertEqual(observed[0]['ask'],100)
        self.assertEqual(observed[0]['units'],5)
        self.assertEqual(observed[0]['price_rows'],1)
        self.assertEqual(v4_game_prices.store(self.db,'acct',observed,NOW),1)
        self.assertEqual(v4_game_prices.store(self.db,'acct',observed,NOW),0)
        recent=v4_game_prices.recent(self.db,NOW)
        self.assertEqual(len(recent),1)
        self.assertEqual(recent[0]['ask'],100)

    def test_missing_target_log_does_not_create_fake_game_price(self):
        self.assertEqual(v4_bridge.game_quotes_from_saved(
            'ForeverTraderDB={ ["v4SearchLog"] = "1800000000:Q:2589:0:0" }',
            NOW),[])
        self.assertEqual(v4_game_prices.recent(self.db,NOW),[])

    def test_in_game_quote_is_not_live_and_not_always_affordable(self):
        quote={'id':2589,'at':NOW-20,'ask':120,'units':5,'price_rows':1,
               'kind':'item'}
        v4_game_prices.store(self.db,'acct',[quote],NOW)
        ideas=[{'id':2589,'max_price_each':110},
               {'id':7068,'max_price_each':4000}]
        v4_game_prices.annotate(ideas,v4_game_prices.recent(self.db,NOW),NOW)
        self.assertIn('BOVEN INSTAPLIMIET',ideas[0]['game_check'])
        self.assertEqual(ideas[0]['game_ask'],120)
        self.assertIn('NOG GEEN',ideas[1]['game_check'])
        v4_game_prices.annotate(ideas,v4_game_prices.recent(self.db,NOW),NOW+6000)
        self.assertIn('VEROUDERD',ideas[0]['game_check'])

    def test_reject_impossible_game_quote_and_unknown_account(self):
        bad={'id':2589,'at':NOW-30,'ask':-1,'units':1,
             'price_rows':1,'kind':'item'}
        with self.assertRaises(ValueError):
            v4_game_prices.validate([bad],NOW)
        with self.assertRaises(ValueError):
            v4_game_prices.store(self.db,'',[],NOW)


if __name__=='__main__':
    unittest.main()
