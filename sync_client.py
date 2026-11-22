"""Opt-in TLS uploader for character snapshots. No game memory or passwords."""
import hashlib
import json
import os
import time
import urllib.parse
import urllib.request

import characters

def sync(db, clock, log=None):
    url=os.environ.get('FT_SYNC_URL','').strip()
    token=os.environ.get('FT_SYNC_TOKEN','').strip()
    if not url or not token:
        return 'Server-synchronisatie niet ingesteld'
    parts=urllib.parse.urlsplit(url)
    if (parts.scheme!='https' or not parts.hostname or parts.username or
            parts.password or parts.query or parts.fragment or
            parts.path!='/api/v1/characters' or len(token)<32):
        return 'Ongeldige serverconfiguratie: HTTPS URL en lange privésleutel verplicht'
    rows=characters.read_all(db)
    if not rows:
        return 'Nog geen opgeslagen charactergegevens'
    payload=json.dumps({'schema':'FTCHAR1','characters':rows},
                       ensure_ascii=False,sort_keys=True,separators=(',',':')).encode('utf-8')
    if len(payload)>250_000:
        return 'Te veel charactergegevens voor veilig uploaden'
    fingerprint=hashlib.sha256(payload).hexdigest()
    state=db.execute("SELECT value FROM meta WHERE key='character_sync_state'").fetchone()
    try: old=json.loads(state[0]) if state else {}
    except (ValueError,TypeError): old={}
    if old.get('hash')==fingerprint and clock-old.get('sent_at',0)<3600:
        return 'Server heeft deze charactergegevens al'
    if clock-old.get('attempt_at',0)<300:
        return 'Server-synchronisatie wacht op herprobeertijd'
    db.execute("INSERT OR REPLACE INTO meta(key,value) VALUES ('character_sync_state',?)",
               (json.dumps({'hash':old.get('hash'),'sent_at':old.get('sent_at',0),'attempt_at':clock}),))
    db.commit()
    request=urllib.request.Request(url,data=payload,method='POST',
                headers={'Content-Type':'application/json','Authorization':'Bearer '+token,
                         'User-Agent':'ForeverTrader-CharacterSync/1.0'})
    try:
        with urllib.request.urlopen(request,timeout=12) as result:
            if result.status!=200: raise ValueError('Server gaf geen 200')
            answer=json.loads(result.read(4096))
            if answer.get('ok') is not True:
                raise ValueError('Server bevestigde synchronisatie niet')
    except (OSError,ValueError) as e:
        if log: log(db,clock,'character sync',str(e))
        return 'Synchronisatie mislukt; nieuwe poging later'
    db.execute("INSERT OR REPLACE INTO meta(key,value) VALUES ('character_sync_state',?)",
               (json.dumps({'hash':fingerprint,'sent_at':clock,'attempt_at':clock}),))
    db.commit()
    return f'{len(rows)} characters veilig gesynchroniseerd ({time.strftime("%H:%M:%S")})'
