#!/usr/bin/env bash
# [BASTIÓN gadmin] Respaldo del bastión antes de la Etapa 4. Solo lee; escribe en ~/respaldos-etapa4/.
# Sin privilegios (lo puede ejecutar Claude). No copia llaves privadas: solo nombres, permisos y huellas
# de las PÚBLICAS.
#   bash respaldo_bastion.sh
set -uo pipefail
TS=$(date -u +%Y%m%dT%H%M%SZ)
D="$HOME/respaldos-etapa4/bastion-$TS"
mkdir -p "$D" && chmod 0700 "$HOME/respaldos-etapa4" "$D"
UNIDADES="ppi-relay-feed.service ppi-relay-feed.timer ppi-relay-eventos.service"
for u in $UNIDADES; do
  printf '%s %s %s\n' "$u" "$(systemctl is-enabled "$u" 2>/dev/null || true)" "$(systemctl is-active "$u" 2>/dev/null || true)"
done > "$D/unidades-estado.txt"
for u in $UNIDADES; do echo "#### $u"; systemctl cat "$u" 2>&1; systemctl show "$u" -p FragmentPath -p DropInPaths 2>&1; done > "$D/unidades-cat.txt"
mkdir -p "$D/etc-systemd-system"
for f in /etc/systemd/system/ppi-*; do [ -e "$f" ] && cp -a "$f" "$D/etc-systemd-system/"; done
sha256sum "$HOME/relay-feed.sh" > "$D/relay-feed.sha256" 2>&1
cp -a "$HOME/relay-feed.sh" "$D/" 2>/dev/null
ls -la --time-style=full-iso "$HOME/.ssh" | awk '{print $1, $3, $4, $NF}' > "$D/ssh.ls"
for p in "$HOME"/.ssh/*.pub; do ssh-keygen -lf "$p"; done > "$D/ssh-huellas-publicas.txt" 2>&1
cp -a "$HOME/.ssh/config" "$D/ssh-config" 2>/dev/null
cp -a "$HOME/.ssh/known_hosts" "$D/known_hosts" 2>/dev/null
ls -la /opt /opt/cyberflow > "$D/opt.ls" 2>&1
[ -d "$HOME/relay-v2" ] && echo "AVISO ~/relay-v2 ya existe" | tee -a "$D/RESPALDO.txt"
python3 --version > "$D/versiones.txt" 2>&1; openssl version >> "$D/versiones.txt"; systemctl --version | head -1 >> "$D/versiones.txt"
timedatectl show -p NTPSynchronized -p TimeUSec >> "$D/versiones.txt" 2>&1
( cd "$D" && find . -type f ! -name SHA256SUMS -print0 | sort -z | xargs -0 sha256sum > SHA256SUMS )
echo "RESPALDO OK $D" | tee -a "$D/RESPALDO.txt"
