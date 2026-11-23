"""ForeverTrader v4 Windows bridge: logout -> VPS, prelogin -> SavedVariables.

Never edit WoW SavedVariables while WoW is running. WoW addons cannot make
network requests, so this bridge runs outside the game. HTTPS is mandatory.
"""
import argparse
import hashlib
import json
import os
import pathlib
import re
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.parse
import urllib.request

import characters
import legacy
import trader
import v4_dashboard
import v4_engine
import v4_server

SESSION=re.compile(r'^\s*\["sessionsWire"\]\s*=\s*"([^"\\]{1,49000})"\s*,?\s*$',re.M)
FT3=re.compile(r'^FT3\|eu-2-110\|\d+\|\d+;(?:\d+:0:0:0:0(?:;|$)){1,20}$')
FIELD=re.compile(r'^([ \t]*)\["(v4PlanBlob|v4ActionsBlob)"\]\s*=\s*"[^"\\]*"\s*,?\s*$',re.M)
ALLOWED_ACTION={'REVIEW_SELL','VERIFY_BUY','CHECK_LISTING','HOLD','WATCH'}


def base_url():
    base=os.environ.get('FT_V4_URL','').strip().rstrip('/')
    if not base:return None
    u=urllib.parse.urlsplit(base)
    if u.scheme!='https' or not u.hostname or u.username or u.password or u.query or u.fragment:
        raise ValueError('FT_V4_URL moet een HTTPS-host zonder query of credentials zijn')
    if u.path not in ('','/'):raise ValueError('FT_V4_URL moet alleen de host bevatten')
    return base


def secret():
    s=os.environ.get('FT_SYNC_TOKEN','')
    if len(s)<32:raise ValueError('FT_SYNC_TOKEN ontbreekt of is te kort')
    return s


def game_running():
    if os.name!='nt':return False
    try:
        p=subprocess.run(['tasklist','/fo','csv','/nh'],capture_output=True,
                         text=True,encoding='utf-8',errors='ignore',timeout=5,check=False)
    except (OSError,subprocess.TimeoutExpired):
        # If process inspection fails, never risk editing a live game file.
        return True
    if p.returncode!=0:return True
    names={'wow.exe','wowclassic.exe','wowclassic_t.exe','wow-64.exe','wowclassic64.exe'}
    for line in p.stdout.splitlines():
        first=line.strip().split(',',1)[0].strip('"').lower()
        if first in names:return True
    return False


def parse_sessions(text, now, account):
    match=SESSION.search(text)
    if not match:return []
    lines=match.group(1).split(';')
    if lines.pop(0)!='FTSESSION1' or len(lines)>40:
        raise ValueError('Ongeldig sessieoverzicht')
    result=[]
    key=hashlib.sha256(account.encode('utf-8')).hexdigest()[:24]
    skipped=0
    for line in lines:
        parts=line.split('|')
        if len(parts)!=9:raise ValueError('Ongeldige sessieregel')
        id,realm,name,start,end,gold_start,gold_end,bags_start,bags_end=parts
        # Earlier addon versions could create a session before the realm/name
        # was available on PLAYER_LOGIN. Skip only those orphan records; keep
        # all valid sessions and character snapshots without altering the file.
        if not realm or not name:
            skipped+=1
            continue
        if not 1<=len(realm)<=100 or not 1<=len(name)<=100:
            raise ValueError('Ongeldige characternaam')
        s=int(start);e=int(end)
        if not 0<s<=e<=now+300:raise ValueError('Ongeldige sessietijd')
        # These are observations, never inferred trades.
        result.append(dict(id=id,character_key=key+':'+realm+':'+name,
                           started_at=s,ended_at=e,
                           gold_start=int(gold_start) if gold_start else None,
                           gold_end=int(gold_end) if gold_end else None,
                           bags_start=characters.parse_counts(bags_start),
                           bags_end=characters.parse_counts(bags_end)))
    if skipped:
        print(f'V4: {skipped} onvolledige sessie(s) zonder characternaam of realm overgeslagen.',flush=True)
    return result


def compatible_sessions(chars,sessions,now):
    """Keep complete sessions linked to exported full character identities.

    Forever v4 previously wrote surname-as-realm and first-name-only records.
    Those old observations cannot be safely assigned to a full-name character,
    so they must not block all present-day character data at the VPS.
    They remain intact in the original WoW SavedVariables file.
    """
    v4_server.validate_characters(chars,now)
    keys={c['character_key'] for c in chars}
    good=[]
    skipped=0
    for entry in sessions:
        if entry['character_key'] not in keys:
            skipped+=1
            continue
        v4_engine.normalize_session(entry,now)
        good.append(entry)
    return good,skipped


def make_blobs(strategies):
    """Serialize ONLY validated data into fixed Lua string fields (no Lua eval)."""
    plans=[];actions=[];n=0
    for s in strategies:
        realm=s.get('realm');name=s.get('character');code=s.get('plan')
        if not (isinstance(realm,str) and isinstance(name,str) and
                1<=len(realm)<=100 and 1<=len(name)<=50):continue
        if any(c in (realm+name) for c in '!?#;"\\\r\n'):continue
        key=realm+'#'+name
        if not isinstance(code,str) or not FT3.fullmatch(code) or len(code)>12000:continue
        decisions=[]
        for row in s.get('actions',[])[:8]:
            if not isinstance(row,dict):continue
            kind=row.get('kind');item=row.get('id');qty=row.get('qty')
            if kind in ALLOWED_ACTION and type(item) is int and 0<item<10000000 and type(qty) is int and 0<qty<=10000:
                decisions.append(f'{kind}:{item}:{qty}')
        item=key+'?'+code
        side=key+'?'+','.join(decisions)
        if sum(map(len,plans))+len(item)>56000 or sum(map(len,actions))+len(side)>56000:
            break
        plans.append(item);actions.append(side);n+=1
    return ('FT4!'+'!'.join(plans) if plans else '',
            'FT4!'+'!'.join(actions) if actions else '',n)


def inject_fields(source,fields):
    """Conservative update; preserve entire existing SavedVariables structure."""
    m=re.search(r'(?m)^ForeverTraderDB\s*=\s*\{',source)
    if not m:raise ValueError('ForeverTraderDB tabel niet gevonden; start addon een keer')
    out=source
    for key,value in fields.items():
        if not isinstance(value,str) or len(value)>60000 or any(c in value for c in '"\\\r\n'):
            raise ValueError('Ongeldige waarde voor '+key)
        field_pattern=re.compile(r'(?m)^[ \t]*\["'+re.escape(key)+r'"\]\s*=\s*"[^"\\]*"\s*,?\s*$')
        replacement='  ["'+key+'"] = "'+value+'",'
        if field_pattern.search(out):
            # Prevent writing a second copy at a deeper nested level.
            if len(field_pattern.findall(out))!=1:raise ValueError('Dubbel sleutelveld '+key)
            out=field_pattern.sub(lambda _:replacement,out,count=1)
        else:
            at=re.search(r'(?m)^ForeverTraderDB\s*=\s*\{',out)
            out=out[:at.end()]+'\n'+replacement+out[at.end():]
    return out


def write_plans(path,text,strategies):
    if game_running():return 'WoW draait; SavedVariables niet aangepast'
    plan,actions,count=make_blobs(strategies)
    if count<=0:return 'Geen nieuwe valide characterplannen'
    data=inject_fields(text,{'v4PlanBlob':plan,'v4ActionsBlob':actions})
    if data==text:return 'Strategie was al actueel'
    # Important: recheck just before disk write to avoid a TOCTOU race.
    if game_running():return 'WoW is gestart; schrijven veilig overgeslagen'
    tmp=None
    try:
        fd,tmp=tempfile.mkstemp(prefix='.v4-plan-',dir=str(path.parent))
        with os.fdopen(fd,'w',encoding='utf-8',newline='') as f:
            f.write(data);f.flush();os.fsync(f.fileno())
        # A rollback copy of the original remains at the same path; do not
        # overwrite saved variables during an active session.
        backup=path.with_name(path.name+'.v4-backup')
        if not backup.exists():backup.write_bytes(path.read_bytes())
        if game_running():return 'WoW is gestart; schrijven veilig overgeslagen'
        os.replace(tmp,path);tmp=None
        return f'{count} serverstrategieën klaar voor de volgende WoW-start'
    finally:
        if tmp is not None:
            try:os.unlink(tmp)
            except OSError:pass


def api_request(base,token,endpoint,payload=None):
    url=base+endpoint
    data=(json.dumps(payload,ensure_ascii=False,separators=(',',':')).encode('utf-8')
          if payload is not None else None)
    headers={'Authorization':'Bearer '+token,'Accept':'application/json'}
    if data is not None:headers['Content-Type']='application/json'
    req=urllib.request.Request(url,data=data,headers=headers,
                               method='POST' if data is not None else 'GET')
    try:
        with urllib.request.urlopen(req,timeout=15) as r:
            if r.status!=200:raise ValueError('VPS retourneerde geen HTTP 200')
            blob=r.read(700000)
            if len(blob)>=700000:raise ValueError('Serverantwoord te groot')
            response=json.loads(blob)
        return response
    except urllib.error.HTTPError as exc:
        # Never print authorization headers, token or the full payload.
        detail=''
        try:
            body=json.loads(exc.read(2048))
            if isinstance(body,dict) and isinstance(body.get('error'),str):
                detail=body['error'][:120]
        except (ValueError,UnicodeError):
            pass
        raise ValueError('VPS '+endpoint+' HTTP '+str(exc.code)+
                         (': '+detail if detail else '')) from None


def account_identity(path):
    """Stable across Windows PCs using the same WoW account directory.

    The parent directory of SavedVariables is the account folder; do not hash
    the entire installation path (which changes between computers).
    """
    account=path.parent.parent.name
    if not account or account in ('.','..'):
        raise ValueError('Ongeldige WoW-accountmap')
    return account


def sync_once(prepared_only=False):
    c=trader.conf()
    path,message=legacy.saved_path(c)
    if not path:return 'Geen SavedVariables: '+message
    base=base_url()
    if not base:return 'FT_V4_URL is niet ingesteld; V4 serververbinding uit'
    token=secret()
    text=path.read_text(encoding='utf-8',errors='replace')
    now=int(time.time())
    account=account_identity(path)
    chars=characters.parse_saved_variables(text,now,account)
    sessions=parse_sessions(text,now,account)
    sessions,skipped=compatible_sessions(chars,sessions,now)
    if skipped:
        print('V4: '+str(skipped)+' oude sessie(s) met afwijkende naam/markt overgeslagen; origineel bewaard.',flush=True)
    if chars or sessions:
        payload={'schema':'FT4SYNC1','characters':chars,'sessions':sessions}
        try:
            response=api_request(base,token,'/api/v4/sync',payload)
        except ValueError as exc:
            # If a legacy session slips through and the VPS rejects this
            # atomic batch, try a CHARACTER-ONLY upload once. The client
            # must never sacrifice correct current gold/bags/auctions because
            # of a previous addon build's bad session identity.
            if chars and sessions and '/api/v4/sync HTTP 400' in str(exc):
                response=api_request(base,token,'/api/v4/sync',
                                     {'schema':'FT4SYNC1','characters':chars,'sessions':[]})
                print('V4: sessiebatch geweigerd; charactergegevens apart gesynchroniseerd. '
                      'De originele sessies blijven bewaard.',flush=True)
                sessions=[]
            else:
                raise
        if response.get('ok') is not True:raise ValueError('Server bevestigde sync niet')
    strategy=api_request(base,token,'/api/v4/strategies')
    if strategy.get('version')!='4.0.0' or strategy.get('market')!='eu-2-110':
        raise ValueError('Verkeerde V4 server/markt')
    plans=strategy.get('strategies')
    if not isinstance(plans,list):raise ValueError('Ongeldig serverantwoord')
    dashboard=v4_dashboard.write(trader.ROOT/'data'/'v4'/'dashboard.html',plans,now)
    result=write_plans(path,text,plans) if not prepared_only else 'Sessies naar VPS gestuurd'
    return f'Verstuurd: {len(chars)} characters, {len(sessions)} sessies. {result} | Dashboard: {dashboard}'


def main():
    p=argparse.ArgumentParser()
    p.add_argument('--once',action='store_true',help='Upload en download eenmalig')
    p.add_argument('--poll',type=int,default=15,help='Controleer iedere N seconden (min 10)')
    a=p.parse_args()
    previous=None;last_try=0;was_running=None
    while True:
        try:
            c=trader.conf();path,_=legacy.saved_path(c)
            game_now=game_running()
            # A logout may flush SavedVariables while WoW stays at character
            # selection. Upload immediately. When WoW later fully exits,
            # download and stage the newest strategy right away.
            just_closed=(was_running is True and game_now is False)
            was_running=game_now
            stamp=path.stat().st_mtime_ns if path and path.exists() else None
            if a.once or stamp!=previous or just_closed or time.time()-last_try>=600:
                message=sync_once()
                print(time.strftime('%H:%M:%S'),message,flush=True)
                # Our own prelogin plan injection updates the file timestamp;
                # record the NEW timestamp to prevent infinite re-sync loops.
                previous=path.stat().st_mtime_ns if path and path.exists() else stamp
                last_try=time.time()
        except Exception as e:
            print(time.strftime('%H:%M:%S'),'V4 bridge:',type(e).__name__,str(e)[:180],flush=True)
            last_try=time.time()
            if a.once:
                raise SystemExit(1)  # Propagate a failed one-shot sync to batch/PowerShell.
        if a.once:return
        time.sleep(max(10,a.poll))


if __name__=='__main__':
    main()
