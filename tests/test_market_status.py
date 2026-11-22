import pathlib, tempfile, unittest
import trader

class MarketStatusTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.db = trader.connect(pathlib.Path(self.tmp.name)/'market.sqlite')
        self.t = 1800000000
    def tearDown(self):
        self.db.close()
        self.tmp.cleanup()
    def test_no_fetch(self):
        self.assertIn('API-aanvraag staat klaar',trader.market_wait_status(self.db,self.t))
    def test_cooldown_after_restart(self):
        trader.setmeta(self.db,'market_attempt',self.t)
        self.db.commit()
        s=trader.market_wait_status(self.db,self.t+60)
        self.assertIn('max. 1x/uur',s)
        self.assertIn('Nog geen opgeslagen marktdata',s)
    def test_failure_is_visible(self):
        trader.setmeta(self.db,'market_attempt',self.t)
        trader.setmeta(self.db,'market_last_error','HTTP Error 503')
        self.db.commit()
        self.assertIn('HTTP Error 503',trader.market_wait_status(self.db,self.t+120))
        self.assertIn('API-aanvraag staat klaar',trader.market_wait_status(self.db,self.t+3600))
    def test_existing_snapshot_visible(self):
        self.db.execute('INSERT INTO market_snapshots VALUES (?,?,?,?)',(self.t,self.t,'tk','{}'))
        trader.setmeta(self.db,'market_attempt',self.t)
        self.db.commit()
        self.assertIn('Laatste opgeslagen snapshot:',trader.market_wait_status(self.db,self.t+120))

if __name__=='__main__': unittest.main()
