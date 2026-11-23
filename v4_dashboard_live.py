"""Live, read-only desktop dashboard, fetched directly from the VPS on each refresh.

Only listens on 127.0.0.1. The Bearer token stays in the Python process;
it is never embedded in the HTML and no WoW files are touched.
"""
import html
import http.server
import time
import webbrowser

import v4_bridge
import v4_dashboard


def render_current(base, token, timestamp=None):
    response=v4_bridge.api_request(base,token,'/api/v4/strategies')
    if response.get('version')!='4.0.0' or response.get('market')!='eu-2-110':
        raise ValueError('VPS gaf geen geldige ForeverTrader V4-strategie')
    strategies=response.get('strategies')
    if not isinstance(strategies,list):raise ValueError('Ongeldig strategieoverzicht')
    page=v4_dashboard.render(strategies,int(time.time()) if timestamp is None else timestamp)
    return page.replace('<head>','<head><meta http-equiv="refresh" content="30">',1)


class Handler(http.server.BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        pass  # Do not log credentials or browser queries.

    def do_GET(self):
        if self.path!='/':
            self.send_error(404)
            return
        try:
            body=render_current(self.server.base,self.server.token)
            status=200
        except Exception:
            # Don't expose API secrets, HTTP bodies or VPS diagnostics to browsers.
            body=('<!doctype html><html lang="nl"><head><meta charset="utf-8">'
                  '<meta http-equiv="refresh" content="30"></head><body>'
                  '<h2>ForeverTrader V4: VPS momenteel niet bereikbaar</h2>'
                  '<p>Controleer je Windows-koppeling en de VPS-service. '
                  'Deze pagina probeert het over 30 seconden opnieuw.</p>'
                  '</body></html>')
            status=503
        data=body.encode('utf-8')
        self.send_response(status)
        self.send_header('Content-Type','text/html; charset=utf-8')
        self.send_header('Cache-Control','no-store')
        self.send_header('X-Content-Type-Options','nosniff')
        self.send_header('Referrer-Policy','no-referrer')
        self.send_header('Content-Security-Policy',"default-src 'none'; style-src 'unsafe-inline'; form-action 'none'")
        self.send_header('Content-Length',str(len(data)))
        self.end_headers()
        self.wfile.write(data)


def main():
    base=v4_bridge.base_url()
    if not base:raise SystemExit('FT_V4_URL ontbreekt; voer eerst KOPPEL-V4.bat uit')
    token=v4_bridge.secret()
    with http.server.ThreadingHTTPServer(('127.0.0.1',0),Handler) as server:
        server.base=base
        server.token=token
        url='http://127.0.0.1:'+str(server.server_port)+'/'
        print('ForeverTrader live VPS-dashboard: '+url,flush=True)
        print('Verversing: iedere 30 seconden. Sluiten: Ctrl+C.',flush=True)
        webbrowser.open(url)
        try:server.serve_forever()
        except KeyboardInterrupt:pass


if __name__=='__main__':
    main()
