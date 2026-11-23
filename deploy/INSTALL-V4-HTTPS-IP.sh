#!/usr/bin/env bash
# Configure trusted HTTPS on a clean Ubuntu VPS without needing a DNS domain.
# Caddy >= 2.10.1 obtains a public Let's Encrypt short-lived IP certificate.
# Only reverse-proxies /health and /api/v4/* to the local v4 server.
set -euo pipefail

IP="${FT_PUBLIC_IP:-136.144.216.107}"

fail() { echo "FOUT: $*" >&2; exit 1; }
[[ "$EUID" -ne 0 ]] || fail "Draai als normale SSH-gebruiker (met sudo), niet als root."
python3 - "$IP" <<'PY'
import ipaddress, sys
ip=ipaddress.ip_address(sys.argv[1])
if ip.version != 4 or not ip.is_global:
    raise SystemExit('FT_PUBLIC_IP moet een publiek IPv4-adres zijn')
PY

command -v sudo >/dev/null || fail 'sudo ontbreekt'
sudo -v

if ! systemctl is-active --quiet forevertrader-v4; then
    fail 'ForeverTrader v4 draait niet. Controleer eerst sudo systemctl status forevertrader-v4.'
fi

if ! command -v caddy >/dev/null 2>&1; then
    if sudo ss -lnt '( sport = :80 or sport = :443 )' | grep -q LISTEN; then
        fail 'Poort 80 of 443 is al bezet; eerst controleren voor we Caddy installeren.'
    fi
    echo '[1/4] Caddy installeren vanuit de officiële pakketbron'
    sudo apt-get update
    sudo apt-get install -y debian-keyring debian-archive-keyring apt-transport-https curl gnupg
    curl -1fsSL https://dl.cloudsmith.io/public/caddy/stable/gpg.key | sudo gpg --batch --yes --dearmor -o /usr/share/keyrings/caddy-stable-archive-keyring.gpg
    curl -1fsSL https://dl.cloudsmith.io/public/caddy/stable/debian.deb.txt | sudo tee /etc/apt/sources.list.d/caddy-stable.list >/dev/null
    sudo chmod 0644 /usr/share/keyrings/caddy-stable-archive-keyring.gpg /etc/apt/sources.list.d/caddy-stable.list
    sudo apt-get update
    sudo apt-get install -y caddy
else
    echo '[1/4] Caddy is al geïnstalleerd'
fi

VERSION="$(caddy version)"
echo "Caddy-versie: $VERSION"
python3 - "$VERSION" <<'PY'
import re,sys
m=re.match(r'^v?(\d+)\.(\d+)\.(\d+)',sys.argv[1])
if not m or tuple(map(int,m.groups())) < (2,10,1):
    raise SystemExit('Caddy minimaal versie 2.10.1 nodig voor publieke IP-certificaten')
PY

echo '[2/4] Caddyfile configureren'
sudo install -d -m 0755 /etc/caddy
if sudo test -f /etc/caddy/Caddyfile; then
    if sudo grep -q '# ForeverTrader v4 IP HTTPS' /etc/caddy/Caddyfile; then
        echo 'Bestaande ForeverTrader-configuratie wordt bijgewerkt.'
    elif sudo grep -q '^:80 {' /etc/caddy/Caddyfile; then
        echo 'Caddy-standaardconfiguratie gevonden.'
    else
        fail 'Er is al een aangepaste Caddy-configuratie; overschrijf die niet automatisch.'
    fi
    sudo cp /etc/caddy/Caddyfile /etc/caddy/Caddyfile.before-forevertrader
fi

TMP="$(mktemp)"
trap 'rm -f "$TMP"' EXIT
cat > "$TMP" <<EOF
# ForeverTrader v4 IP HTTPS — Let's Encrypt shortlived IP certificate
{
    default_sni $IP
}

$IP {
    tls {
        issuer acme {
            profile shortlived
        }
    }
    @api path /health /api/v4/*
    handle @api {
        reverse_proxy 127.0.0.1:8765
    }
    handle {
        respond "Not found" 404
    }
}
EOF
sudo install -m 0644 "$TMP" /etc/caddy/Caddyfile
if ! sudo caddy validate --config /etc/caddy/Caddyfile --adapter caddyfile; then
    if sudo test -f /etc/caddy/Caddyfile.before-forevertrader; then
        sudo cp /etc/caddy/Caddyfile.before-forevertrader /etc/caddy/Caddyfile
    fi
    fail 'Caddyfile is ongeldig; oude configuratie teruggezet indien aanwezig.'
fi

echo '[3/4] HTTPS activeren'
sudo systemctl enable --now caddy
sudo systemctl reload caddy || sudo systemctl restart caddy

echo '[4/4] HTTPS-gezondheid controleren (zonder -k / onveilig omzeilen)'
if curl --fail --silent --show-error --retry 8 --retry-delay 3 --retry-connrefused --max-time 10 "https://${IP}/health"; then
    echo
    echo 'SUCCES: publieke HTTPS-verbinding werkt met geldig certificaat.'
    echo "Adres: https://${IP}"
else
    echo 'De HTTPS-test is nog niet geslaagd. Controleer of 80/443 bij TransIP open staan.'
    echo 'Voor certificaatdiagnose: sudo journalctl -u caddy -n 60 --no-pager'
    exit 1
fi
