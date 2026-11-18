#!/usr/bin/env bash
# [BASTIÓN gadmin] Reversión del relé v2 al estado del respaldo. La ejecuta MARK (sudo). El relé v1 no
# se tocó al instalar y aquí solo se comprueba. Las llaves nuevas NO se borran (se dejan para auditar;
# quedan inútiles en cuanto Sensor1 y srv-dmz retiran su línea de authorized_keys).
#   bash revertir_bastion.sh <RESPALDO_DIR>
set -uo pipefail
R="${1:?respaldo}"
( cd "$R" && sha256sum -c --quiet SHA256SUMS ) || { echo "PARADA el respaldo no verifica"; exit 1; }
dif=0
if ! grep -q '^ppi-relay-eventos.service enabled active$' "$R/unidades-estado.txt"; then
  sudo systemctl disable --now ppi-relay-eventos.service 2>/dev/null
  [ -e "$R/etc-systemd-system/ppi-relay-eventos.service" ] || sudo rm -f /etc/systemd/system/ppi-relay-eventos.service
  grep -q relay-v2 "$R/opt.ls" || sudo rm -rf /opt/cyberflow/relay-v2
  sudo rmdir /opt/cyberflow 2>/dev/null
  sudo systemctl daemon-reload
fi
while read -r u _; do
  printf '%s %s %s\n' "$u" "$(systemctl is-enabled "$u" 2>/dev/null || true)" "$(systemctl is-active "$u" 2>/dev/null || true)"
done < "$R/unidades-estado.txt" | diff "$R/unidades-estado.txt" - || { echo "DIFERENCIA estado de unidades"; dif=1; }
sha256sum -c --quiet "$R/relay-feed.sha256" || { echo "DIFERENCIA relay-feed.sh"; dif=1; }
[ "$dif" = 0 ] && echo "REVERSIÓN OK (traza en ~/relay-v2 conservada)" || exit 1
