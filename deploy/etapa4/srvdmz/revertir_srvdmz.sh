#!/usr/bin/env bash
# [SRV-DMZ adminsrvdmz] Reversión del agente v2 al estado del respaldo. La ejecuta MARK (sudo).
# En sombra no hay tabla cyberflow_dmz; si existiera (no debería), se desinstala con el propio helper.
# La traza y el estado del agente se COPIAN a ~/respaldos-etapa4 antes de borrar /var/lib/cyberflow.
#   bash revertir_srvdmz.sh <RESPALDO_DIR>
set -uo pipefail
R="${1:?respaldo}"
( cd "$R" && sha256sum -c --quiet SHA256SUMS ) || { echo "PARADA el respaldo no verifica"; exit 1; }
dif=0
EV="$HOME/respaldos-etapa4/srvdmz-evidencia-$(date -u +%Y%m%dT%H%M%SZ)"; mkdir -p "$EV"
sudo systemctl disable --now ppi-enforce-agent-v2-dmz.service 2>/dev/null
sudo cp -a /var/lib/cyberflow/agente /var/lib/cyberflow/feed "$EV/" 2>/dev/null && sudo chown -R "$(id -u):$(id -g)" "$EV"
if sudo nft list tables | grep -q cyberflow_dmz; then
  echo '{"perfil":"dmz","operaciones":[{"op":"desinstalar"}]}' | sudo /usr/local/sbin/cf-nft-helper
fi
sudo rm -f /etc/sudoers.d/cf-nft-helper /usr/local/sbin/cf-nft-helper /usr/local/bin/cf-feed-ssh.sh \
  /etc/systemd/system/ppi-enforce-agent-v2-dmz.service /etc/cyberflow/nft-helper.perfil
sudo rm -rf /opt/cyberflow/agente-v2 /var/lib/cyberflow
sudo rmdir /opt/cyberflow /etc/cyberflow 2>/dev/null
sudo userdel cffeed; sudo userdel cfagente; sudo groupdel cfagente 2>/dev/null; sudo groupdel cffeed 2>/dev/null
sudo visudo -c > /dev/null || { echo "DIFERENCIA visudo -c"; dif=1; }
sudo systemctl daemon-reload
while read -r u _; do
  printf '%s %s %s\n' "$u" "$(systemctl is-enabled "$u" 2>/dev/null || true)" "$(systemctl is-active "$u" 2>/dev/null || true)"
done < "$R/unidades-estado.txt" | diff "$R/unidades-estado.txt" - || { echo "DIFERENCIA estado de unidades"; dif=1; }
diff <(sudo ls /etc/sudoers.d) <(ls "$R/sudoers.d") > /dev/null || { echo "DIFERENCIA sudoers.d"; dif=1; }
norm() { sed -E 's/counter packets [0-9]+ bytes [0-9]+/counter/; s/expires [0-9hms.]+//'; }
diff <(sudo nft list ruleset | norm) <(norm < "$R/ruleset.nft") > /dev/null || { echo "DIFERENCIA ruleset"; dif=1; }
getent passwd cffeed cfagente > /dev/null && { echo "DIFERENCIA quedan cuentas"; dif=1; }
[ "$dif" = 0 ] && echo "REVERSIÓN OK (traza del agente copiada en $EV)" || exit 1
