#!/usr/bin/env bash
# ForeverTrader V4: READ-ONLY VPS preflight. Safe on a shared production VPS.
# Does NOT restart services, inspect passwords, modify files or query databases.
set -u
export LC_ALL=C
echo '=== ForeverTrader V4 read-only VPS check ==='
echo
echo '[User and OS]'
id
uname -srmo 2>/dev/null || uname -a
if test -r /etc/os-release; then
  . /etc/os-release
  printf 'OS: %s\n' "${PRETTY_NAME:-unknown}"
fi
echo
echo '[Python and Git]'
for c in python3 git systemctl ss nginx apache2 caddy; do
  if command -v "$c" >/dev/null 2>&1; then
    printf '%-10s %s\n' "$c" "$(command -v "$c")"
  else
    printf '%-10s unavailable\n' "$c"
  fi
done
python3 --version 2>/dev/null || :
git --version 2>/dev/null || :
echo
echo '[CPU/memory/disk]'
if command -v nproc >/dev/null 2>&1; then printf 'CPU cores: ';nproc;fi
if command -v free >/dev/null 2>&1; then free -h | head -3;fi
df -h / /opt /var 2>/dev/null | awk 'NR==1 || !seen[$1]++'
echo
echo '[Existing service state: read only]'
if command -v systemctl >/dev/null 2>&1; then
  for service in nginx apache2 caddy mysql mariadb php8.3-fpm php8.2-fpm php8.1-fpm; do
    state="$(systemctl is-active "$service" 2>/dev/null || true)"
    if test "$state" = active; then
      printf '%s: active\n' "$service"
    fi
  done
fi
echo
echo '[Listening TCP ports: read only]'
if command -v ss >/dev/null 2>&1; then
  ss -lnt 2>/dev/null | head -35
fi
echo
echo '[Existing deployment folders: existence only]'
for dir in /opt/ForeverBroker /opt/forevertrader /var/www /etc/caddy /etc/nginx /etc/systemd/system; do
  if test -d "$dir"; then printf '%s: exists\n' "$dir";fi
done
echo
echo 'No changes made. Do not share passwords, SSH keys, database contents or .env files.'
