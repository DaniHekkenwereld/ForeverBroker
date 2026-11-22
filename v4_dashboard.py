"""Standalone local read-only V4 dashboard; no remote scripts or credentials."""
import datetime as dt
import html
import os
import pathlib
import tempfile


def escape(v):
    return html.escape(str(v if v is not None else '—'),quote=True)


def money(c):
    return f'{c/10000:,.2f}g' if type(c) is int else 'onbekend'


def stamp(t):
    if type(t) is not int or t<=0:return 'Onbekend'
    return dt.datetime.fromtimestamp(t,dt.timezone.utc).astimezone().strftime('%d-%m %H:%M')


def render(strategies, refreshed):
    parts=[]
    for p in strategies:
        name=escape(p.get('character','?'))
        realm=escape(p.get('realm','?'))
        gold=money(p.get('gold'))
        updated=stamp(p.get('last_seen'))
        market=stamp(p.get('market_t'))
        state='Actueel' if p.get('market_fresh') else 'Marktdata te oud'
        if not p.get('wallet_fresh'):state+='; gold onbekend/verouderd'
        actions=p.get('actions') or []
        rows=[]
        for a in actions:
            kind=a.get('kind')
            description={
                'VERIFY_BUY':'Koopkans controleren',
                'REVIEW_SELL':'Verkopen controleren',
                'CHECK_LISTING':'Eigen veiling controleren',
                'HOLD':'Vasthouden',
                'WATCH':'Volgen'
            }.get(kind,'Onderzoeken')
            profit=money(a.get('model_net')) if kind=='VERIFY_BUY' else '—'
            rows.append('<tr><td>'+escape(description)+'</td><td>'+escape(a.get('name'))+
                        '</td><td>'+escape(a.get('qty','—'))+'</td><td>'+
                        escape(money(a.get('model_buy')) if kind=='VERIFY_BUY' else '—')+
                        '</td><td>'+escape(profit)+'</td><td>'+escape(a.get('reason',''))+'</td></tr>')
        rendered=''.join(rows) or '<tr><td colspan="6">Geen actievoorstellen op basis van de huidige data.</td></tr>'
        parts.append(f'''<section><header><h2>{name} <small>{realm}</small></h2>
        <span>{escape(state)}</span></header><p>Gold (laatst bekend): <b>{escape(gold)}</b>
        · Character gemeten {escape(updated)}
        · Markt {escape(market)} · Zoeklijst: {escape(len((p.get('plan') or '').split(';'))-1 if p.get('plan') else 0)} items</p>
        <div class="scroll"><table><thead><tr><th>Actie</th><th>Item</th><th>Aantal</th>
        <th>Modelinkoop</th><th>Theoretisch netto / stuk</th><th>Waarom</th></tr></thead>
        <tbody>{rendered}</tbody></table></div></section>''')
    content=''.join(parts) or '<p>Nog geen characters. Speel eerst met de v4-addon en log daarna uit.</p>'
    return f'''<!doctype html><html lang="nl"><head><meta charset="utf-8">
    <meta name="viewport" content="width=device-width,initial-scale=1">
    <title>ForeverTrader V4 — Characters & strategie</title>
    <style>body{{font:15px system-ui;color:#dce4f0;background:#111827;max-width:1400px;margin:25px auto;padding:0 18px}}
    h1{{font-size:28px}}h2{{font-size:21px;margin:0}}small,p{{color:#a6b4c8}}small{{font-size:14px}}
    section{{background:#1c293a;padding:16px;border-radius:12px;margin:18px 0}}
    header{{display:flex;justify-content:space-between;gap:20px;flex-wrap:wrap}}
    header span{{color:#dfca88}}.scroll{{overflow:auto}}
    table{{width:100%;border-collapse:collapse}}td,th{{padding:9px 11px;text-align:left;border-bottom:1px solid #344358;white-space:nowrap}}
    td:last-child{{white-space:normal;min-width:280px}}
    th{{color:#c1d4e7}}b{{color:#e9ce93}}</style></head><body>
    <h1>ForeverTrader V4</h1><p>Lokale laatste serverstrategie, ververst: {escape(stamp(refreshed))}.
    De server volgt historische vraagprijzen, geen gegarandeerde verkopen.
    V4 plaatst of koopt nooit automatisch veilingen.</p>{content}
    <p>Controleer alle prijzen en exacte itemvarianten aan het AH. In-game: /ft v4 en /ft auto on.</p>
    </body></html>'''


def write(path,strategies,clock):
    p=pathlib.Path(path)
    p.parent.mkdir(parents=True,exist_ok=True)
    data=render(strategies,clock)
    fd,tmp=tempfile.mkstemp(prefix='.v4-dashboard-',dir=str(p.parent))
    try:
        with os.fdopen(fd,'w',encoding='utf-8') as f:
            f.write(data)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp,p);tmp=None
    finally:
        if tmp:
            try:os.unlink(tmp)
            except OSError:pass
    return p
