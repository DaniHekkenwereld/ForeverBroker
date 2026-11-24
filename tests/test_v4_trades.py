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

    def test_conflicting_same_trade_id_is_rejected(self):
        original=self.row('conflict','BUY',1,10000)
        v4_trades.store(self.db,[original],self.now,{self.key})
        changed={**original,'total_copper':20000}
        with self.assertRaises(ValueError):
            v4_trades.store(self.db,[changed],self.now,{self.key})
        self.assertEqual(v4_trades.summarize(self.db)['positions'][12363]['known_cost'],10000)

    def test_fifo_basis_follows_same_account_character_transfer(self):
        buyer='account:eu-2-110:Mage Pump'
        seller='account:eu-2-110:Warrior Tank'
        other='other:eu-2-110:Bank Alt'
        rows=[
            {**self.row('x1','BUY',2,200000,self.now-90),
             'character_key':buyer},
            {**self.row('x2','SELL',1,140000,self.now-70),
             'character_key':seller},
            {**self.row('x3','SELL',1,190000,self.now-60),
             'character_key':other},
        ]
        self.assertEqual(v4_trades.store(self.db,rows,self.now,
                                         {buyer,seller,other}),3)
        summary=v4_trades.summarize(self.db)
        matched=next(r for r in summary['recent_trades'] if
                     r['character_key']==seller)
        unknown=next(r for r in summary['recent_trades'] if
                     r['character_key']==other)
        self.assertEqual(matched['realized_net_after_reported_cost'],40000)
        self.assertIsNone(unknown['realized_net_after_reported_cost'])
        self.assertEqual(summary['unmatched_sales'],1)

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

    def test_automatic_game_receipts_and_unresolved_mail_wire(self):
        raw=('ForeverTraderDB = {\n'
             ' ["autoTradesWire"] = "FTTRADE2;AH_Mage_1800000000_1|eu-2-110|'
             'Mage Pump|1800000000|BUY|12363|2|100000|AH_BUY;'
             'AH_Mage_1800000005_2|eu-2-110|Mage Pump|1800000005|'
             'SELL|12363|1|80000|AH_MAIL",\n'
             ' ["autoTradeIssuesWire"] = "FTISSUE2;1800000010|eu-2-110|Mage Pump'
             '|SELL|0|3|25000|MAIL_ITEM_UNRESOLVED|Unknown Recipe",\n}\n')
        trades=v4_bridge.parse_trades(raw,self.now,'account-one')
        self.assertEqual(len(trades),2)
        self.assertEqual([r['source'] for r in trades],['AH_BUY','AH_MAIL'])
        issues=v4_bridge.parse_trade_issues(raw,self.now,'account-one')
        self.assertEqual(len(issues),1)
        self.assertEqual(issues[0]['item_name'],'Unknown Recipe')
        self.assertEqual(issues[0]['total_copper'],25000)
        self.assertIsNone(v4_bridge.parse_trade_issues('ForeverTraderDB={}',self.now,'account-one'))
        self.assertEqual(v4_trades.store(self.db,
            [{**row,'character_key':self.key} for row in trades],
            self.now,{self.key}),2)
        s=v4_trades.summarize(self.db)
        self.assertEqual(s['reported_realized_net'],30000)
        self.assertEqual(v4_trades.store(self.db,
            [{**row,'character_key':self.key} for row in trades],
            self.now,{self.key}),0)
        self.assertEqual(v4_trades.sync_issues(self.db,
            [{**issues[0],'character_key':self.key}],{self.key}),1)
        self.assertEqual(len(v4_trades.recent_issues(self.db)),1)
        self.assertEqual(v4_trades.sync_issues(self.db,[],{self.key}),0)
        self.assertEqual(v4_trades.recent_issues(self.db),[])

    def test_pending_seller_invoice_negative_deposit_and_unknown_quantity(self):
        # Real game mail can briefly report 0 received money while a
        # refundable deposit is populated; quantity may be -1 sentinel.
        # This was the user's 'Invalid issue quantity/value' sync blocker.
        raw=('ForeverTraderDB = {\n'
             ' ["autoTradeIssuesWire"] = "FTISSUE2;1800000005|eu-2-110'
             '|Mage Pump|SELL|12363|-1|-500|MAIL_QUANTITY_UNRESOLVED'
             '|Arcane Crystal",\n}')
        parsed=v4_bridge.parse_trade_issues(raw,self.now,'account-one')
        self.assertEqual(len(parsed),1)
        self.assertEqual(parsed[0]['quantity'],-1)
        self.assertEqual(parsed[0]['total_copper'],-500)
        stored={**parsed[0],'character_key':self.key}
        self.assertEqual(v4_trades.sync_issues(self.db,[stored],{self.key}),1)
        self.assertEqual(v4_trades.recent_issues(self.db)[0]['total_copper'],-500)
        self.assertEqual(v4_trades.summarize(self.db)['trade_count'],0)
        self.assertEqual(v4_trades.summarize(self.db)['reported_realized_net'],None)
        # A completed trade with these negative values is still forbidden.
        with self.assertRaises(ValueError):
            v4_trades.validate({**self.row('negative','SELL',1,10000),
                                'total_copper':-500},self.now)

    def test_ambiguous_buy_event_cannot_become_fake_trade(self):
        raw=('ForeverTraderDB = {\n'
             ' ["autoTradeIssuesWire"] = "FTISSUE2;1800000000|eu-2-110'
             '|Mage Pump|BUY|12363|0|0|COST_UNCONFIRMED|",\n}')
        self.assertEqual(v4_bridge.parse_trades(raw,self.now,'account-one'),[])
        issue=v4_bridge.parse_trade_issues(raw,self.now,'account-one')[0]
        self.assertEqual(issue['side'],'BUY')
        self.assertEqual(issue['total_copper'],0)
        self.assertEqual(v4_trades.summarize(self.db)['trade_count'],0)

    def test_trade_must_belong_to_known_character(self):
        with self.assertRaises(ValueError):
            v4_trades.store(self.db,[self.row('x','BUY',1,10000)],self.now,{'another'})
        self.assertEqual(v4_trades.summarize(self.db)['trade_count'],0)


if __name__=='__main__':
    unittest.main()
