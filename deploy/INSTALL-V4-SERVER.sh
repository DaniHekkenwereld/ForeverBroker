#!/usr/bin/env bash
# ForeverTrader v4 bootstrap for a fresh Ubuntu VPS.
# Run as the intended NONROOT Linux user inside a trusted clone:
#   bash deploy/INSTALL-V4-SERVER.sh
# Does not open network ports, change SSH config, install packages, or touch other services.
set -euo pipefail

die() { printf 'FOUT: %s\n' "$*" >&2; exit 1; }
printf '\n=== ForeverTrader v4 - veilige VPS installatie ===\n'

[ "${EUID}" -ne 0 ] || die 'Voer dit uit als je normale SSH-gebruiker, niet als root.'
command -v sudo >/dev/null || die 'sudo ontbreekt.'
command -v systemctl >/dev/null || die 'systemd ontbreekt.'
command -v python3 >/dev/null || die 'Python 3 ontbreekt.'

APP_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd -P)"
cd "$APP_DIR"
[ -f v4_server.py ] && [ -f v4_engine.py ] && [ -f trader.py ] || die 'Voer dit uit vanuit een volledige ForeverBroker-repository.'
if [ ! -f config.json ]; then die 'config.json ontbreekt.';fi

printf 'Gebruiker: %s\nMap: %s\n' "$USER" "$APP_DIR"
python3 --version

printf '\n[1/5] Python-code compileren\n'
python3 -m compileall -q v4_server.py v4_engine.py v4_bridge.py v4_dashboard.py trader.py legacy.py opportunities.py characters.py sync_client.py
printf '[2/5] Regressietests draaien\n'
python3 -m unittest discover -s tests -q || die 'Er zijn falende tests. Er is NIETS als service geinstalleerd. Stuur de foutmelding door.'

printf '\n[3/5] Eigen databasedirectory maken\n'
install -d -m 0700 "$APP_DIR/data/v4"

printf '[4/5] Prive-token en service aanmaken (sudo)\n'
sudo -v
sudo env FT_APP_DIR="$APP_DIR" FT_APP_USER="$USER" python3 - <<'PY'
import grp, os, pathlib, pwd, secrets
from subprocess import run
app=pathlib.Path(os.environ['FT_APP_DIR']).resolve()
username=os.environ['FT_APP_USER']
account=pwd.getpwnam(username)
base=pathlib.Path('/etc/forevertrader')
base.mkdir(mode=0o750,parents=True,exist_ok=True)
os.chown(base,0,account.pw_gid)
os.chmod(base,0o750)
envpath=base/'v4.env'
if not envpath.exists():
    token=secrets.token_urlsafe(48)
    rows=[
        'FT_SYNC_HOST=127.0.0.1',
        'FT_SYNC_PORT=8765',
        f'FT_SYNC_DB={app}/data/v4/trader.sqlite',
        f'FT_SYNC_TOKEN={token}'
    ]
    fd=os.open(envpath,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o640)
    with os.fdopen(fd,'w',encoding='ascii') as f:
        f.write('\n'.join(rows)+'\n')
    print('Nieuwe willekeurige privésleutel gemaakt. Deze wordt NIET hier afgedrukt.')
else:
    print('Bestaande /etc/forevertrader/v4.env behouden; sleutel NIET vervangen.')
os.chown(envpath,0,account.pw_gid)
os.chmod(envpath,0o640)
service=pathlib.Path('/etc/systemd/system/forevertrader-v4.service')
unit=f"""[Unit]
Description=ForeverTrader V4 AH history and strategy service
Wants=network-online.target
After=network-online.target

[Service]
Type=simple
User={username}
Group={grp.getgrgid(account.pw_gid).gr_name}
WorkingDirectory={app}
EnvironmentFile={envpath}
Environment=PYTHONUNBUFFERED=1
ExecStart=/usr/bin/python3 -u {app}/v4_server.py
Restart=on-failure
RestartSec=10
NoNewPrivileges=true
PrivateTmp=true
ProtectSystem=strict
ReadWritePaths={app}/data
UMask=0077

[Install]
WantedBy=multi-user.target
"""
if '\n' in str(app) or '\n' in username or ' ' in str(app):
    raise SystemExit('Installeer de repository onder een pad zonder spaties of nieuwe regels.')
service.write_text(unit,encoding='utf-8')
os.chmod(service,0o644)
print('Systemd service aangemaakt; geen externe poorten geopend.')
PY

printf '[5/5] Starten als systemd-service\n'
sudo systemctl daemon-reload
sudo systemctl enable --now forevertrader-v4.service
printf '\n=== Status (zonder geheimen) ===\n'
sudo systemctl --no-pager --full status forevertrader-v4.service | head -22 || true
printf '\n=== Loopback gezondheidscheck ===\n'
python3 - <<'PY'
import json, time, urllib.request
for i in range(15):
    try:
        with urllib.request.urlopen('http://127.0.0.1:8765/health',timeout=3) as resp:
            data=json.loads(resp.read(2048))
        if data.get('ok') is True and data.get('version')=='4.0.0':
            print('OK:',data)
            break
    except Exception:
        time.sleep(1)
else:
    print('Geen gezondheidsreactie. Bekijk: sudo journalctl -u forevertrader-v4 -n 40 --no-pager')
PY

printf '\nDe server-API is ALLEEN lokaal bereikbaar op 127.0.0.1:8765.\n'
printf 'Voor synchronisatie vanaf Windows moet later een HTTPS-proxy worden ingericht.\n'
printf 'Houd de FT_SYNC_TOKEN privé; plak hem nooit in de chat of GitHub.\n'
