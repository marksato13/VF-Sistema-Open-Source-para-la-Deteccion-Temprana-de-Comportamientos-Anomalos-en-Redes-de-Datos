#!/bin/bash
# Cierre complementario de la 4A en el BASTIÓN (4-nov-2026). Lo ejecuta Mark con sudo:
#   sudo bash /home/gadmin/cierre4a/cierre4a_bastion.sh
# Retira SOLO el relé v1 (ppi-relay-feed.timer/.service). No toca ppi-relay-eventos (cadena v2),
# ni relay-feed.sh, ni claves, ni el agente v1 de srv-dmz (sigue deshabilitado y no se arranca).
set -euo pipefail
[ "$(id -u)" = 0 ] || { echo "ejecutar con sudo"; exit 2; }
TS=$(date -u +%Y%m%dT%H%M%SZ)
EV=/home/gadmin/cierre4a/sudo-bastion-$TS
mkdir -p "$EV"
exec > >(tee "$EV/salida.txt") 2>&1
echo "== cierre4a bastión inicio $(date -u +%FT%TZ)"
for u in ppi-relay-feed.timer ppi-relay-feed.service ppi-relay-eventos.service; do
  systemctl cat "$u" > "$EV/unidad-$u.txt" 2>&1 || true
  systemctl show "$u" -p ActiveState -p SubState -p UnitFileState -p MainPID -p ExecMainStartTimestamp \
     > "$EV/estado-antes-$u.txt" 2>&1 || true
done
mkdir -p "$EV/etc"; cp -a /etc/systemd/system/ppi-relay-feed.* "$EV/etc/" 2>/dev/null || true
sha256sum /home/gadmin/relay-feed.sh | tee "$EV/relay-feed.sh.sha256"
systemctl list-timers --all --no-pager > "$EV/timers-antes.txt"
echo "== retirar el relé v1"
systemctl disable --now ppi-relay-feed.timer
systemctl stop ppi-relay-feed.service || true
for u in ppi-relay-feed.timer ppi-relay-feed.service ppi-relay-eventos.service; do
  systemctl show "$u" -p Id -p ActiveState -p UnitFileState | tee -a "$EV/estado-despues.txt"
done
systemctl is-active ppi-relay-eventos.service
systemctl list-timers --all --no-pager > "$EV/timers-despues.txt"
grep -c ppi-relay-feed "$EV/timers-despues.txt" || true
chown -R gadmin:gadmin "$EV"
( cd "$EV" && find . -type f ! -name SHA256SUMS -print0 | sort -z | xargs -0 sha256sum > SHA256SUMS )
echo "== fin $(date -u +%FT%TZ) evidencia en $EV"
