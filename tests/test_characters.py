import pathlib
import sqlite3
import tempfile
import unittest
from unittest import mock

import characters
import sync_client

NOW=1800000000

class CharacterSnapshotTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.db=sqlite3.connect(pathlib.Path(self.temp.name)/'characters.sqlite')
        self.db.row_factory=sqlite3.Row
        self.db.executescript(characters.SCHEMA)
    def tearDown(self):
        self.db.close()
        self.temp.cleanup()
    def export(self,rows):
        return '-- SavedVariables from game\nForeverTraderDB = {\n' + (
            '  ["charactersWire"] = "FTCHAR1;'+';'.join(rows)+'",\n') + '}\n'
    @staticmethod
    def row(time,name,gold,bags='2589:20',wallet_at=None):
        t=str(time)
        return '|'.join([t,'Forever',name,'Alliance',str(gold),
                         str(wallet_at or time),t,bags,t,'',t,'0','0','0'])
    def test_two_characters_are_persisted_separately(self):
        payload=self.export([self.row(NOW,'Mage',1000000,'2589:20,4306:6'),
                             self.row(NOW-50,'Warrior',200000,'2770:15')])
        data=characters.parse_saved_variables(payload,NOW,'account-a')
        self.assertEqual(len(data),2)
        self.assertEqual(characters.store(self.db,data),2)
        stored=characters.read_all(self.db)
        self.assertEqual(len(stored),2)
        self.assertEqual(stored[0]['character'],'Mage')
        self.assertEqual(stored[0]['gold'],1000000)
        self.assertEqual(stored[1]['bags'],{'2770':15})
    def test_stale_character_does_not_overwrite_fresher_wallet(self):
        first=characters.parse_saved_variables(
            self.export([self.row(NOW,'Mage',1000000)]),NOW,'account-a')
        characters.store(self.db,first)
        old=characters.parse_saved_variables(
            self.export([self.row(NOW-100,'Mage',1)]),NOW,'account-a')
        self.assertEqual(characters.store(self.db,old),0)
        self.assertEqual(characters.read_all(self.db)[0]['gold'],1000000)
    def test_invalid_and_unbounded_export_is_rejected(self):
        with self.assertRaises(ValueError):
            characters.parse_saved_variables(self.export(
                [self.row(NOW,'Mage',1000000,'2589:-1')]),NOW,'acc')
        self.assertEqual(characters.parse_saved_variables(
            'ForeverTraderDB = {}',NOW,'acc'),[])
        with self.assertRaises(ValueError):
            characters.parse_saved_variables(self.export(
                [self.row(NOW+400,'Mage',10)]),NOW,'acc')
    def test_no_sync_without_private_credentials(self):
        self.db.execute('CREATE TABLE meta (key TEXT PRIMARY KEY,value TEXT)')
        self.db.commit()
        with mock.patch.dict('os.environ',{},clear=True):
            self.assertIn('niet ingesteld',sync_client.sync(self.db,NOW))


if __name__=='__main__':
    unittest.main()
