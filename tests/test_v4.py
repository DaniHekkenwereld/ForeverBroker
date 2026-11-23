"""V4 regression tests: cross-character strategies, history and session safety."""
import pathlib
import tempfile
import unittest
from unittest.mock import patch

import characters
import trader
import v4_engine as v4
import v4_bridge


class V4EngineTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.db=trader.connect(pathlib.Path(self.tmp.name)/'market.sqlite')
        self.db.executescript(v4.SCHEMA)
        self.now=trader.ts('2026-11-22T12:30:00Z')
        self.c=trader.conf()
        self.market={
            1111:{'name':'Rare Recipe','cls':'Recipe','nc':True,
                  'ask':10000,'ask2':30000,'median':30000,'vol24':12,
                  'depth5':1,'lastSoldP':30000,'vendor':10},
            2222:{'name':'Rare Weapon','cls':'Weapon','nc':True,
                  'ask':50000,'ask2':150000,'median':150000,'vol24':0,
                  'depth5':1,'lastSoldP':None,'vendor':10},
            2589:{'name':'Linen Cloth','cls':'Trade Goods','nc':False,
                  'ask':100,'ask2':100,'median':100,'vol24':999,
                  'depth5':50,'vendor':1},
        }
        for day in range(8):
            for hour in (1,8,12,19):
                t=self.now-(day+1)*86400+hour*3600
                if t>=self.now:t-=86400
                trader.obs(self.db,1111,t,{'ask':20000,'sold':5},'tk')
        trader.save_market(self.db,self.now,self.market,self.now,'tk')
        self.db.commit()

    def tearDown(self):
        self.db.close();self.tmp.cleanup()

    def add_character(self,character,gold,bags=None,at=None):
        at=self.now if at is None else at
        record=dict(character_key='account:Forever:'+character,
                    realm='Forever',character=character,faction='Alliance',
                    last_seen=at,gold=gold,wallet_at=at,
                    bags={} if bags is None else bags,bags_at=at,
                    auctions={},auctions_at=at,mail_at=None,
                    mail_pending=None,mail_ready=None,mail_attachments=None)
        with self.db:characters.store(self.db,[record])

    def test_every_character_has_own_strategy_and_real_budget(self):
        self.add_character('Mage',1000000)
        self.add_character('Warrior',80000)
        plan=v4.strategy_list(self.db,self.now,self.c)
        self.assertEqual(len(plan),2)
        mage=next(x for x in plan if x['character']=='Mage')
        warrior=next(x for x in plan if x['character']=='Warrior')
        self.assertEqual(mage['version'],'4.0.0')
        self.assertTrue(mage['wallet_fresh'])
        self.assertTrue(mage['market_fresh'])
        self.assertTrue(any(a['kind']=='VERIFY_BUY' and a['id']==1111 for a in mage['actions']))
        self.assertFalse(any(a['kind']=='VERIFY_BUY' and a['id']==1111 for a in warrior['actions']))
        self.assertIn('1111:0:0:0:0',mage['plan'])
        self.assertNotIn('1111:10000:',mage['plan'])
        self.assertEqual(self.db.execute('SELECT COUNT(*) FROM v4_strategies').fetchone()[0],2)

    def test_inventory_and_auctions_are_not_double_bought(self):
        self.add_character('Mage',1000000,{1111:3})
        s=v4.strategy_list(self.db,self.now,self.c)[0]
        self.assertTrue(any(a['kind']=='REVIEW_SELL' and a['id']==1111 and a['qty']==3 for a in s['actions']))
        self.assertFalse(any(a['kind']=='VERIFY_BUY' and a['id']==1111 for a in s['actions']))
        self.assertNotIn('1111:0:0:0:0',s['plan'])

    def test_old_data_never_authorizes_buy(self):
        self.add_character('Mage',1000000,at=self.now-86400*15)
        s=v4.strategy_list(self.db,self.now,self.c)[0]
        self.assertFalse(s['wallet_fresh'])
        self.assertFalse(any(a['kind']=='VERIFY_BUY' for a in s['actions']))
        self.assertIsNone(s['free_gold_after_reserve'])

    def test_old_market_never_authorizes_buy(self):
        self.add_character('Mage',1000000)
        s=v4.strategy_list(self.db,self.now+6000,self.c)[0]
        self.assertFalse(s['market_fresh'])
        self.assertFalse(any(a['kind']=='VERIFY_BUY' for a in s['actions']))

    def test_session_import_is_idempotent_and_not_profit(self):
        data={'id':'Forever:Mage:123:1','character_key':'account:Forever:Mage',
              'started_at':self.now-3600,'ended_at':self.now,
              'gold_start':100000,'gold_end':150000,
              'bags_start':{'2589':2},'bags_end':{'2589':10}}
        with self.db:
            self.assertEqual(v4.store_sessions(self.db,[data],self.now),1)
            self.assertEqual(v4.store_sessions(self.db,[data],self.now),0)
        result=self.db.execute('SELECT payload FROM v4_sessions').fetchone()[0]
        self.assertIn('"inventory_delta":{"2589":8}',result)
        self.assertIn('"verified_transactions":false',result)

    def test_historical_context_is_required_for_verified_buy_review(self):
        self.add_character('Mage',1000000)
        self.db.execute('DELETE FROM price_history WHERE item_id=1111')
        self.db.commit()
        s=v4.strategy_list(self.db,self.now,self.c)[0]
        self.assertFalse(any(a['kind']=='VERIFY_BUY' for a in s['actions']))
        self.assertIn('1111:0:0:0:0',s['plan'])


class BridgeTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.path=pathlib.Path(self.tmp.name)/'ForeverTrader.lua'
        self.path.write_text('ForeverTraderDB = {\n  ["schema"] = "FT1",\n  ["wallet"] = "123|100000|Alliance|3",\n}\n',encoding='utf-8')
        self.time=1800000000
    def tearDown(self):
        self.tmp.cleanup()
    def test_char_specific_plans_and_safe_saved_variables_update(self):
        a={'realm':'Forever','character':'Mage',
           'plan':'FT3|eu-2-110|1800000000|1800003600;1111:0:0:0:0',
           'actions':[{'kind':'VERIFY_BUY','id':1111,'qty':1}]}
        b={'realm':'Forever','character':'Warrior',
           'plan':'FT3|eu-2-110|1800000000|1800003600;2222:0:0:0:0',
           'actions':[{'kind':'REVIEW_SELL','id':2222,'qty':2}]}
        with patch.object(v4_bridge,'game_running',return_value=False):
            self.assertIn('2 serverstrategieën',v4_bridge.write_plans(
                self.path,self.path.read_text(encoding='utf-8'),[a,b]))
        text=self.path.read_text(encoding='utf-8')
        self.assertEqual(text.count('["v4PlanBlob"]'),1)
        self.assertEqual(text.count('["v4ActionsBlob"]'),1)
        self.assertIn('Forever#Mage?FT3',text)
        self.assertIn('Forever#Warrior?FT3',text)
        self.assertIn('["wallet"] = "123|100000|Alliance|3"',text)
        self.assertTrue(self.path.with_name('ForeverTrader.lua.v4-backup').exists())
        with patch.object(v4_bridge,'game_running',return_value=False):
            self.assertIn('al actueel',v4_bridge.write_plans(self.path,text,[a,b]))
    def test_never_touch_while_game_runs(self):
        raw=self.path.read_text(encoding='utf-8')
        plan={'realm':'Forever','character':'Mage',
              'plan':'FT3|eu-2-110|1800000000|1800003600;1111:0:0:0:0',
              'actions':[]}
        with patch.object(v4_bridge,'game_running',return_value=True):
            self.assertIn('WoW draait',v4_bridge.write_plans(self.path,raw,[plan]))
        self.assertEqual(self.path.read_text(encoding='utf-8'),raw)
    def test_rejects_executable_and_unsafe_plan(self):
        p={'realm':'Forever','character':'Mage','plan':'FT3|...;1111:1:1:2:0','actions':[]}
        self.assertEqual(v4_bridge.make_blobs([p])[2],0)
    def test_legacy_incomplete_session_does_not_block_valid_character_sync(self):
        # An early PLAYER_LOGIN can generate a session with empty identity.
        orphan=':100:1||Mage|100|200|1000|1500||'
        valid='Forever:Mage:101:2|Forever|Mage|101|200|1000|1500||'
        wire='FTSESSION1;'+orphan+';'+valid
        source='ForeverTraderDB = {\n  ["sessionsWire"] = "'+wire+'",\n}\n'
        rows=v4_bridge.parse_sessions(source,200,'account-a')
        self.assertEqual(len(rows),1)
        self.assertEqual(rows[0]['character_key'].split(':')[-2:],['Forever','Mage'])
        self.assertEqual(rows[0]['gold_end'],1500)

    def test_only_incomplete_sessions_are_skipped(self):
        orphan='Forever::100:1|Forever||100|200|1000|1500||'
        source='ForeverTraderDB = {\n  ["sessionsWire"] = "FTSESSION1;'+orphan+'",\n}\n'
        self.assertEqual(v4_bridge.parse_sessions(source,200,'account-a'),[])

    def test_account_identity_is_portable_between_windows_install_paths(self):
        a=pathlib.PureWindowsPath(r'C:\\Games\\WoW\\_forever_\\WTF\\Account\\ACCOUNT#1\\SavedVariables\\ForeverTrader.lua')
        b=pathlib.PureWindowsPath(r'D:\\World of Warcraft\\_forever_\\WTF\\Account\\ACCOUNT#1\\SavedVariables\\ForeverTrader.lua')
        self.assertEqual(v4_bridge.account_identity(a),'ACCOUNT#1')
        self.assertEqual(v4_bridge.account_identity(a),v4_bridge.account_identity(b))

    def test_previous_first_name_session_does_not_reject_full_name_character(self):
        # Older addon used only the first name; Forever v4 now uses first+last.
        now=1800000100
        account='482614058#1'
        source=('ForeverTraderDB = {\\n'
                ' ["charactersWire"] = "FTCHAR1;1800000000|eu-2-110|Mage Pump|Alliance|500000|1800000000|1800000000|||0||||",\\n'
                ' ["sessionsWire"] = "FTSESSION1;eu-2-110:Mage:1800000000:1|eu-2-110|Mage|1800000000|1800000050|400000|500000||",\\n'
                '}\\n')
        chars=characters.parse_saved_variables(source,now,account)
        sessions=v4_bridge.parse_sessions(source,now,account)
        self.assertEqual(len(chars),1)
        self.assertEqual(len(sessions),1)
        usable,skipped=v4_bridge.compatible_sessions(chars,sessions,now)
        self.assertEqual(usable,[])
        self.assertEqual(skipped,1)
        self.assertEqual(chars[0]['character'],'Mage Pump')

    def test_valid_full_name_session_is_kept(self):
        now=1800000100
        account='account-one'
        source=('ForeverTraderDB = {\\n'
                ' ["charactersWire"] = "FTCHAR1;1800000000|eu-2-110|Mage Pump|Alliance|500000|1800000000|1800000000|||0||||",\\n'
                ' ["sessionsWire"] = "FTSESSION1;eu-2-110:Mage_Pump:1800000000:1|eu-2-110|Mage Pump|1800000000|1800000050|400000|500000||",\\n'
                '}\\n')
        chars=characters.parse_saved_variables(source,now,account)
        sessions=v4_bridge.parse_sessions(source,now,account)
        usable,skipped=v4_bridge.compatible_sessions(chars,sessions,now)
        self.assertEqual(skipped,0)
        self.assertEqual(len(usable),1)

    def test_invalid_character_payload_is_caught_before_network(self):
        now=1800000100
        rows=[dict(character_key='x:y:z',realm='eu-2-110',
                   character='Mage Pump',faction='Alliance',last_seen=now+500,
                   wallet_at=None,bags_at=None,auctions_at=None,mail_at=None)]
        with self.assertRaisesRegex(ValueError,'last_seen'):
            v4_bridge.compatible_sessions(rows,[],now)

    def test_session_wire_parser(self):
        text='ForeverTraderDB = {\n ["sessionsWire"] = "FTSESSION1;Forever:Mage:100:1|Forever|Mage|100|200|1000|1500|2589:2|2589:10",\n}\n'
        rows=v4_bridge.parse_sessions(text,200,'account-a')
        self.assertEqual(len(rows),1)
        self.assertEqual(rows[0]['gold_end'],1500)
        self.assertEqual(rows[0]['bags_end'],{2589:10})


if __name__=='__main__':unittest.main()
