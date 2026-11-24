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

AUTO_TRADE_WIRE=re.compile(r'^\s*\["autoTradesWire"\]\s*=\s*"([^"\\]{1,59000})"\s*,?\s*$',re.M)
AUTO_ISSUE_WIRE=re.compile(r'^\s*\["autoTradeIssuesWire"\]\s*=\s*"([^"\\]{1,19500})"\s*,?\s*$',re.M)
TRADE_WIRE=re.compile(r'^\s*\["tradesWire"\]\s*=\s*"([0-9A-Za-z|:;_. -]{1,59000})"\s*,?\s*$',re.M)
SESSION=re.compile(r'^\s*\["sessionsWire"\]\s*=\s*"([^"\\]{1,49000})"\s*,?\s*$',re.M)
FT3=re.compile(r'^FT3\|eu-2-110\|\d+\|\d+;(?:\d+:0:0:0:0(?:;|$)){1,20}$')
FIELD=re.compile(r'^([ \t]*)\["(v4PlanBlob|v4ActionsBlob)"\]\s*=\s*"[^"\\]*"\s*,?\s*$',re.M)
ALLOWED_ACTION={'REVIEW_SELL','VERIFY_BUY','CHECK_LISTING','HOLD','WATCH',
                'INVEST_SHORT','INVEST_LONG'}


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


def parse_trades(text,now,account):
    """Decode legacy manual entries and automatic AH purchase/sale receipts."""
    identity=hashlib.sha256(account.encode('utf-8')).hexdigest()[:24]
    rows=[]
    seen=set()
    for rx,header,length,legacy in (
        (TRADE_WIRE,'FTTRADE1',8,'addon_manual'),
        (AUTO_TRADE_WIRE,'FTTRADE2',9,None)):
        match=rx.search(text)
        if not match:continue
        lines=match.group(1).split(';')
        if lines.pop(0)!=header or len(lines)>250:
            raise ValueError('Ongeldig trade exportformaat')
        for line in lines:
            data=line.split('|')
            if len(data)!=length:raise ValueError('Ongeldige trade export regel')
            trade_id,realm,name,at,side,item,qty,amount=data[:8]
            if not 1<=len(realm)<=100 or not 1<=len(name)<=100 or any(
                    c in realm+name for c in '";\\|\r\n'):
                raise ValueError('Ongeldige trade-identiteit')
            key=identity+':'+trade_id
            if key in seen:raise ValueError('Dubbele trade-ID')
            seen.add(key)
            row=dict(id=key,character_key=identity+':'+realm+':'+name,
                     at=int(at),side=side,item_id=int(item),
                     quantity=int(qty),total_copper=int(amount),
                     source=(data[8] if length==9 else legacy))
            import v4_trades
            v4_trades.validate(row,now)
            rows.append(row)
    return rows


def parse_trade_issues(text,now,account):
    """Unresolved game-reported purchases/sales; never invent transaction data."""
    match=AUTO_ISSUE_WIRE.search(text)
    if not match:return None
    lines=match.group(1).split(';')
    if lines.pop(0)!='FTISSUE2' or len(lines)>100:
        raise ValueError('Ongeldige onvolledige AH-waarnemingen')
    identity=hashlib.sha256(account.encode('utf-8')).hexdigest()[:24]
    result=[]
    invalid=0
    for idx,line in enumerate(lines):
        # These are *incomplete* game observations, NOT executed orders.
        # A malformed mail/sentinel must never prevent all character, bank
        # and confirmed trade data from synchronising. The original
        # SavedVariables file is left untouched for later diagnosis.
        try:
            fields=line.split('|')
            if len(fields)!=9:raise ValueError('Ongeldige onvolledige AH-regel')
            at,realm,name,side,item,qty,amount,reason,item_name=fields
            row=dict(id=identity+':'+hashlib.sha256(
                    (line+':'+str(idx)).encode('utf-8')).hexdigest()[:22],
                character_key=identity+':'+realm+':'+name,
                at=int(at),side=side,item_id=int(item),quantity=int(qty),
                total_copper=int(amount),reason=reason,item_name=item_name)
            import v4_trades
            v4_trades.validate_issue(row,now)
            result.append(row)
        except (ValueError,TypeError,OverflowError):
            invalid+=1
    if invalid:
        print('V4: '+str(invalid)+' ongeldige/onvolledige AH-waarneming(en) '
              'overgeslagen; ruwe SavedVariables blijven bewaard. '
              'Gold, bank en bewezen transacties synchroniseren gewoon.',flush=True)
    return result if result or not invalid else None


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
                if kind in ('INVEST_SHORT','INVEST_LONG'):
                    limit=row.get('max_buy_before_deposit')
                    target=row.get('reference_sell')
                    if (type(limit) is int and 0<limit<=100000000000 and
                            type(target) is int and 0<target<=100000000000):
                        decisions.append(f'{kind}:{item}:{qty}:{limit}:{target}')
                else:
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
            # Portfolio research can legitimately contain thousands of
            # account-wide holdings; cap the response at 3 MiB instead of
            # silently rejecting normal large inventories.
            limit=3*1024*1024
            blob=r.read(limit+1)
            if len(blob)>limit:raise ValueError('Serverantwoord te groot (>3 MiB)')
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


def game_quotes_from_saved(text,clock):
    """Read verified exact-item books, not raw arbitrary Q/R search events.

    Parses the addon's saved targetLog after WoW wrote SavedVariables.
    A game quote is never a sale and never a live price feed.
    """
    import v4_local_activity  # local import avoids circular module reference
    parsed=v4_local_activity.from_text(text,clock,limit=120)
    result=[]
    for row in parsed.get('observations',[]):
        if row.get('ask') is None:continue
        result.append({'id':row['id'],'at':row['at'],'kind':row['kind'],
                       'ask':row['ask'],'units':row['units'],
                       'price_rows':row['price_rows']})
    return result[:120]


def send_sync(base,token,chars,sessions,trades=None,issues=None,game_quotes=None):
    """Upload character observations even if a legacy session batch is rejected.

    Return the number of sessions actually accepted for the summary. The
    original SavedVariables file is never altered or pruned by this method.
    """
    if trades is None:trades=[]
    if not chars and not sessions and not trades:return 0
    payload={'schema':'FT4SYNC1','characters':chars,'sessions':sessions,
             'trades':trades}
    if issues is not None:payload['trade_issues']=issues
    if game_quotes is not None:payload['game_quotes']=game_quotes
    try:
        response=api_request(base,token,'/api/v4/sync',payload)
    except ValueError as exc:
        if chars and sessions and '/api/v4/sync HTTP 400' in str(exc):
            safe={'schema':'FT4SYNC1','characters':chars,'sessions':[],
                  'trades':trades}
            if issues is not None:safe['trade_issues']=issues
            if game_quotes is not None:safe['game_quotes']=game_quotes
            response=api_request(base,token,'/api/v4/sync',safe)
            print('V4: sessiebatch geweigerd; charactergegevens apart gesynchroniseerd. '
                  'Originele sessies blijven bewaard.',flush=True)
            sessions=[]
        else:
            raise
    if response.get('ok') is not True:
        raise ValueError('Server bevestigde sync niet')
    return len(sessions)


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
    locations=characters.parse_stock_wire(text,now,account)
    for char in chars:
        char.update(locations.get(char['character_key'],{}))
    if not chars or not any(' ' in x.get('character','').strip() for x in chars):
        raise ValueError('Geen volledige Forever-characternaam in de export. '
                         'Log eenmaal in met de bijgewerkte addon en sluit WoW volledig af.')
    sessions=parse_sessions(text,now,account)
    trades=parse_trades(text,now,account)
    issues=parse_trade_issues(text,now,account)
    game_quotes=game_quotes_from_saved(text,now)
    sessions,skipped=compatible_sessions(chars,sessions,now)
    keys={c['character_key'] for c in chars}
    trades=[trade for trade in trades if trade['character_key'] in keys]
    if issues is not None:
        issues=[issue for issue in issues if issue['character_key'] in keys]
    if skipped:
        print('V4: '+str(skipped)+' oude sessie(s) met afwijkende naam/markt overgeslagen; origineel bewaard.',flush=True)
    uploaded_sessions=send_sync(base,token,chars,sessions,trades,issues,game_quotes)
    strategy=api_request(base,token,'/api/v4/strategies')
    if strategy.get('version')!='4.0.0' or strategy.get('market')!='eu-2-110':
        raise ValueError('Verkeerde V4 server/markt')
    plans=strategy.get('strategies')
    if not isinstance(plans,list):raise ValueError('Ongeldig serverantwoord')
    dashboard=v4_dashboard.write(trader.ROOT/'data'/'v4'/'dashboard.html',plans,now)
    result=write_plans(path,text,plans) if not prepared_only else 'Sessies naar VPS gestuurd'
    return f'Verstuurd: {len(chars)} characters, {uploaded_sessions} sessies, {len(trades)} transacties, {len(issues or [])} onvolledige AH-waarnemingen, {len(game_quotes)} in-game AH-prijzen voor VPS. {result} | Dashboard: {dashboard}'


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
