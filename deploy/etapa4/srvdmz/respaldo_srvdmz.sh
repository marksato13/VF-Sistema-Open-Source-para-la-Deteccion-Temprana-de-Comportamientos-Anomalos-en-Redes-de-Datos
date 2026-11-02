#!/usr/bin/env bash
# [SRV-DMZ adminsrvdmz] Respaldo de srv-dmz antes de la Etapa 4. Solo lee; escribe en ~/respaldos-etapa4/.
#   bash respaldo_srvdmz.sh               # sin privilegios (lo puede ejecutar Claude)
#   CON_SUDO=1 bash respaldo_srvdmz.sh    # además ruleset nft y sudoers (Mark; adminsrvdmz tiene NOPASSWD,
#                                         # pero la norma reserva sudo a Mark)
set -uo pipefail
TS=$(date -u +%Y%m%dT%H%M%SZ)
D="$HOME/respaldos-etapa4/srvdmz-$TS"
mkdir -p "$D" && chmod 0700 "$HOME/respaldos-etapa4" "$D"
fallo=0
UNIDADES="ppi-enforce-agent.service ppi-enforce-agent.timer ppi-brute-lab.service ppi-enforce-agent-v2-dmz.service"
for u in $UNIDADES; do
  printf '%s %s %s\n' "$u" "$(systemctl is-enabled "$u" 2>/dev/null || true)" "$(systemctl is-active "$u" 2>/dev/null || true)"
done > "$D/unidades-estado.txt"
for u in $UNIDADES; do echo "#### $u"; systemctl cat "$u" 2>&1; done > "$D/unidades-cat.txt"
mkdir -p "$D/etc-systemd-system"
for f in /etc/systemd/system/ppi-*; do [ -e "$f" ] && cp -a "$f" "$D/etc-systemd-system/"; done
ls -la --time-style=full-iso "$HOME/enforce" > "$D/enforce.ls" 2>&1
( cd "$HOME/enforce" 2>/dev/null && find . -maxdepth 2 -type f -print0 | sort -z | xargs -0 sha256sum ) > "$D/enforce.sha256" 2>&1
cp -a "$HOME/.ssh/authorized_keys" "$D/authorized_keys" 2>/dev/null
getent passwd cffeed cfagente > "$D/cuentas.txt"; echo "rc=$?" >> "$D/cuentas.txt"
ls -la /usr/local/bin /usr/local/sbin /opt /etc/cyberflow /var/lib/cyberflow > "$D/rutas.ls" 2>&1
python3 --version > "$D/versiones.txt" 2>&1; openssl version >> "$D/versiones.txt"; ls -l /usr/sbin/nft >> "$D/versiones.txt"
timedatectl show -p NTPSynchronized -p TimeUSec >> "$D/versiones.txt" 2>&1
if [ "${CON_SUDO:-0}" = 1 ]; then
  sudo nft list ruleset > "$D/ruleset.nft" || fallo=1
  sudo nft list tables > "$D/tablas.txt"
  sudo cp -a /etc/sudoers.d "$D/sudoers.d" && sudo chown -R "$(id -u):$(id -g)" "$D/sudoers.d"
  sudo grep -hE '^\s*Defaults' /etc/sudoers /etc/sudoers.d/* > "$D/sudoers-defaults.txt" 2>&1
else
  echo "pendiente CON_SUDO=1: ruleset.nft, tablas, sudoers.d y Defaults (Mark)" | tee -a "$D/RESPALDO.txt"
fi
( cd "$D" && find . -type f ! -name SHA256SUMS -print0 | sort -z | xargs -0 sha256sum > SHA256SUMS )
[ "$fallo" = 0 ] && echo "RESPALDO OK $D" | tee -a "$D/RESPALDO.txt" || { echo "RESPALDO INCOMPLETO $D"; exit 1; }
