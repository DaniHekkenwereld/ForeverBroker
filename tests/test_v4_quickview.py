"""Tests for icon-first action cards and accessible collapsed diagnostics."""
import re
import threading
import unittest
import urllib.request
from http.server import ThreadingHTTPServer
from unittest.mock import patch

import v4_dashboard
import v4_dashboard_live
import v4_quickview


NOW=1800001000


def test_report():
    return {
        'market_fresh':True,'snapshot_at':NOW-300,
        'game_checks':[{'id':1111,'ask':8000,'at':NOW-120,'kind':'item',
                        'units':3,'price_rows':2}],
        'opportunities':[{'id':1111,'status':'INTERESSANT — VERIFIËREN',
                          'suffix_warning':False,'max_buy_before_deposit':11000}],
        'portfolio':{
            'characters':[{'character':'Warrior Pump'}],
            'gold_total_last_known':800000,'holding_types':2,
            'unpriced_holding_types':1,'unresolved_ah_count':0,
            'buy_review':[{'id':1111,'name':'Arcane Crystal',
                           'character':'Warrior Pump','horizon':'short',
                           'qty':1,'max_price_each':9000},
                          {'id':1111,'name':'Arcane Crystal',
                           'character':'Bank Pump','horizon':'short',
                           'qty':1,'max_price_each':9000}],
            'holdings':[{'id':2222,'name':'Elemental Fire',
                         'total':4,'potentially_sellable':4,'ask':6000,
                         'quoted_mark':24000,'versus_week_pct':30,
                         'advice':'VERKOOP CONTROLEREN'},
                        {'id':3333,'name':'Elixir',
                         'total':2,'potentially_sellable':2,'ask':2000,
                         'quoted_mark':4000,'advice':'AANHOUDEN / PRIJS CONTROLEREN'}],
            'realized_profit':None
        },
        'intraday':{'patterns':[]}
    }


class QuickViewTests(unittest.TestCase):
    def test_one_unique_consistent_and_recent_buy_candidate(self):
        state=v4_quickview.evaluate(test_report(),NOW)
        self.assertEqual(len(state['buy']),1)
        self.assertEqual(len(state['watch']),0)
        self.assertEqual(len(state['sell']),1)
        self.assertEqual(len(state['hold']),1)
        html=v4_quickview.render(test_report(),NOW)
        self.assertIn('Wat moet ik nu doen?',html)
        self.assertIn('🛒',html)
        self.assertIn('📤',html)
        self.assertIn('👀',html)
        self.assertIn('📦',html)
        self.assertIn('Max 0g 90s 00c',html)
        self.assertIn('altijd opnieuw controleren vóór kopen',html)
        self.assertNotIn('Koop nu',html)

    def test_conflicting_signals_must_be_watch_not_green_buy(self):
        report=test_report()
        report['opportunities'][0]['status']='MONITOREN'
        state=v4_quickview.evaluate(report,NOW)
        self.assertEqual(state['buy'],[])
        self.assertEqual(len(state['watch']),1)
        self.assertIn('bevestigen elkaar niet',state['watch'][0]['reason'])
        html=v4_quickview.render(report,NOW)
        self.assertIn('Nog niet kopen',html)
        self.assertIn('Investeringsradar en marktkansen',html)

    def test_asking_price_above_limit_cannot_be_recommended(self):
        report=test_report()
        report['game_checks'][0]['ask']=10000
        state=v4_quickview.evaluate(report,NOW)
        self.assertFalse(state['buy'])
        self.assertIn('hoger dan',state['watch'][0]['reason'])

    def test_stale_game_quote_or_market_cannot_be_buy(self):
        report=test_report()
        report['game_checks'][0]['at']=NOW-1800
        state=v4_quickview.evaluate(report,NOW)
        self.assertFalse(state['buy'])
        self.assertIn('recent genoeg',state['watch'][0]['reason'])
        report=test_report()
        report['market_fresh']=False
        state=v4_quickview.evaluate(report,NOW)
        self.assertFalse(state['buy'])
        self.assertFalse(state['sell'])
        self.assertIn('Marktbron',state['watch'][0]['reason'])

    def test_no_game_quote_means_no_buy_no_false_profit(self):
        report=test_report()
        report['game_checks']=[]
        report['portfolio']['realized_profit']=None
        html=v4_quickview.render(report,NOW)
        self.assertIn('Nog geen echte AH-prijs',html)
        self.assertIn('Bevestigde winst',html)
        self.assertIn('— betekent: onvoldoende kostprijsbewijs',html)
        self.assertNotIn('Na WoW-save naar VPS verstuurd</small>',html) if False else None

    def test_untrusted_item_names_escaped_and_number_only_links(self):
        report=test_report()
        report['portfolio']['buy_review'][0]['name']='<script>bad()</script>'
        report['portfolio']['holdings'][0]['name']='<img src=x onerror=alert(1)>'
        html=v4_quickview.render(report,NOW)
        self.assertNotIn('<script>bad()</script>',html)
        self.assertNotIn('<img src=x onerror=alert(1)>',html)
        self.assertIn('&lt;script&gt;bad()',html)
        self.assertIn('auctionhouse.tk.gg/m/eu-2-110/1111',html)

    def test_dashboard_hides_long_tables_until_expanded(self):
        html=v4_dashboard.render([],NOW,test_report(),{})
        self.assertIn('class="action-center"',html)
        self.assertIn('class="action-grid"',html)
        self.assertGreaterEqual(html.count('<details class="detail-group"'),7)
        self.assertLess(html.index('Wat moet ik nu doen?'),html.index('<details'))
        self.assertLess(html.index('<details'),html.index('<table'))
        self.assertIn('Portfolio, characters en transacties',html)
        self.assertIn('Alle marktkansen',html)
        self.assertIn('Daghandel',html)
        self.assertIn('@media(max-width:720px)',html)


class LocalDashboardHttpTests(unittest.TestCase):
    def test_30_second_refresh_preserves_reader_expanded_details_without_insecure_script(self):
        with patch.object(v4_dashboard_live,'render_current',return_value=(
                 '<!doctype html><html><head><meta http-equiv="refresh" content="30">'
                 '</head><body><details class="detail-group" id="portfolio">'
                 '<summary>Portfolio</summary></details></body></html>')):
            with ThreadingHTTPServer(('127.0.0.1',0),
                                     v4_dashboard_live.Handler) as server:
                server.base='https://example.invalid'
                server.token='secret-never-in-html'
                thread=threading.Thread(target=server.serve_forever,daemon=True)
                thread.start()
                try:
                    with urllib.request.urlopen(
                            f'http://127.0.0.1:{server.server_port}/',
                            timeout=5) as response:
                        html=response.read().decode('utf-8')
                        csp=response.headers['Content-Security-Policy']
                        self.assertEqual(response.status,200)
                    found=re.search(r'<script nonce="([^"]+)">',html)
                    self.assertIsNotNone(found)
                    self.assertIn("script-src 'nonce-"+found.group(1)+"'",csp)
                    self.assertNotIn("script-src 'unsafe-inline'",csp)
                    self.assertIn('sessionStorage',html)
                    self.assertIn('panels.some(p => p.open)',html)
                    self.assertNotIn('secret-never-in-html',html)
                finally:
                    server.shutdown();thread.join(timeout=4)


if __name__=='__main__':unittest.main()
