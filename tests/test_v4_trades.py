"""Trust-boundary and FIFO tests for manually confirmed trade receipts."""
import pathlib
import sqlite3
import tempfile
import unittest

import v4_bridge
import v4_trades


class TradeLedgerTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.db=sqlite3.connect(pathlib.Path(self.tmp.name)/'trades.sqlite')
        self.db.row_factory=sqlite3.Row
        self.db.executescript(v4_trades.SCHEMA)
        self.now=1800000100
        self.key='account:eu-2-110:Mage Pump'

    def tearDown(self):
        self.db.close();self.tmp.cleanup()

    def row(self,id,side,qty,total,when=None):
        return {'id':'account:'+id,'character_key':self.key,
                'at':self.now-60 if when is None else when,
                'side':side,'item_id':12363,'quantity':qty,
                'total_copper':total}

    def test_fifo_partial_and_idempotent_upload(self):
        trades=[self.row('1','BUY',2,100000,self.now-90),
                self.row('2','BUY',1,100000,self.now-80),
                self.row('3','SELL',2,140000,self.now-70)]
        self.assertEqual(v4_trades.store(self.db,trades,self.now,{self.key}),3)
        self.assertEqual(v4_trades.store(self.db,trades,self.now,{self.key}),0)
        state=v4_trades.summarize(self.db)
        self.assertEqual(state['trade_count'],3)
        self.assertEqual(state['positions'][12363]['known_units'],1)
        self.assertEqual(state['positions'][12363]['known_cost'],100000)
        self.assertEqual(state['reported_realized_net'],40000)
        self.assertEqual(state['unmatched_sales'],0)

    def test_unrecorded_initial_inventory_cannot_invent_profit(self):
        sale=self.row('4','SELL',4,800000)
        self.assertEqual(v4_trades.store(self.db,[sale],self.now,{self.key}),1)
        state=v4_trades.summarize(self.db)
        self.assertEqual(state['unmatched_sales'],1)
        self.assertFalse(state['reported_realized_known'])
        self.assertEqual(state['reported_realized_net'],0)
        self.assertIsNone(state['recent_trades'][0]['realized_net_after_reported_cost'])

    def test_manual_trade_parser_rejects_tampered_and_future(self):
        text=('ForeverTraderDB = {\n'
              ' ["tradesWire"] = "FTTRADE1;eu-2-110_Mage_Pump_1800000000_1|'
              'eu-2-110|Mage Pump|1800000000|BUY|12363|2|100000",\n}')
        rows=v4_bridge.parse_trades(text,1800000100,'account-one')
        self.assertEqual(len(rows),1)
        self.assertEqual(rows[0]['total_copper'],100000)
        self.assertTrue(rows[0]['character_key'].endswith(':Mage Pump'))
        self.assertEqual(v4_bridge.parse_trades('ForeverTraderDB={}',1800000100,'x'),[])
        with self.assertRaises(ValueError):
            v4_bridge.parse_trades(text.replace('|BUY|','|DROP|'),1800000100,'account-one')
        with self.assertRaises(ValueError):
            v4_bridge.parse_trades(text.replace('|2|100000','|-2|100000'),1800000100,'account-one')
        with self.assertRaises(ValueError):
            v4_bridge.parse_trades(text.replace('|1800000000|BUY','|1800000700|BUY'),1800000100,'account-one')

    def test_trade_must_belong_to_known_character(self):
        with self.assertRaises(ValueError):
            v4_trades.store(self.db,[self.row('x','BUY',1,10000)],self.now,{'another'})
        self.assertEqual(v4_trades.summarize(self.db)['trade_count'],0)


if __name__=='__main__':
    unittest.main()
