"""v3.2 regression checks: conservative paper fills and invalid logout wallet."""
import pathlib
import tempfile
import unittest
from unittest.mock import patch

import trader as ft
import legacy as old


class V32Reliability(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.db = ft.connect(pathlib.Path(self.temp.name) / 'test.sqlite')
        self.c = ft.conf()
        self.vid = ft.register(self.db, self.c)
        self.t = ft.ts('2026-11-21T08:00:00Z')

    def tearDown(self):
        self.db.close()
        self.temp.cleanup()

    def test_no_paper_fill_after_only_one_favourable_quote(self):
        t = self.t
        _, m = old.demo_market(t, 0)
        ft.save_market(self.db, t, m, t, 'demo')
        ft.cycle(self.db, self.c, t, m, t, self.vid, 'demo')
        self.assertEqual(self.db.execute('select count(*) from inventory').fetchone()[0], 5)
        for x in m.values():
            x.update(ask=10000, ask2=11000, sold=1000, depth5=0, vol24=0)
        ft.cycle(self.db, self.c, t + 3600, m, t + 3600, self.vid, 'demo')
        self.assertEqual(ft.totals(self.db)['incoming'], 0)
        self.assertEqual(self.db.execute('select count(*) from paper_sale_checks').fetchone()[0], 5)

    def test_bad_followup_quote_resets_confirmation(self):
        t = self.t
        _, m = old.demo_market(t, 0)
        ft.save_market(self.db, t, m, t, 'demo')
        ft.cycle(self.db, self.c, t, m, t, self.vid, 'demo')
        for x in m.values():
            x.update(ask=10000, ask2=11000, sold=1000, depth5=0, vol24=0)
        ft.cycle(self.db, self.c, t + 3600, m, t + 3600, self.vid, 'demo')
        for x in m.values(): x['ask'] = 1
        ft.cycle(self.db, self.c, t + 7200, m, t + 7200, self.vid, 'demo')
        self.assertEqual(self.db.execute('select count(*) from paper_sale_checks').fetchone()[0], 0)
        for x in m.values(): x['ask'] = 10000
        ft.cycle(self.db, self.c, t + 10800, m, t + 10800, self.vid, 'demo')
        self.assertEqual(ft.totals(self.db)['incoming'], 0)
        ft.cycle(self.db, self.c, t + 14400, m, t + 14400, self.vid, 'demo')
        self.assertGreater(ft.totals(self.db)['incoming'], 0)

    def test_wallet_zero_after_logout_is_flagged(self):
        t = self.t
        self.db.execute("INSERT INTO local_exports VALUES (?,?,?)", (t + 20, 'wallet', '[1800000020,0,"Alliance","3"]'))
        self.db.execute("INSERT INTO local_exports VALUES (?,?,?)", (t, 'coach', f'"{t}|AH|560000|0|0|0|0"'))
        with patch.object(ft.old, 'load_local', return_value=({}, 'geen export')), patch.object(ft.old, 'saved_path', return_value=(None, '')):
            message = ft.capture_local(self.db, self.c, t + 30)
        self.assertIn('WAARSCHUWING', message)
        self.assertIn('56.0000g', message)


if __name__ == '__main__':
    unittest.main()
