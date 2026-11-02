#!/usr/bin/env bash
# [SRV-DMZ adminsrvdmz] Verificación de SOMBRA en srv-dmz.
#   bash verificar_srvdmz.sh                         # parte sin sudo (Claude)
#   CON_SUDO=1 bash verificar_srvdmz.sh <RESPALDO>   # traza del agente y reglas efectivas (Mark)
# Sombra = ausencia DEMOSTRADA de restricciones aplicadas: (1) ningún agente con --aplicar en ejecución,
# (2) ningún evento "aplicacion" en la traza, (3) el ruleset efectivo igual al del respaldo salvo
# contadores, (4) sin tabla cyberflow_dmz, (5) el agente v1 sigue deshabilitado.
set -uo pipefail
R="${1:-}"
fallo=0
c() { if eval "$2"; then echo "OK    $1"; else echo "FALLO $1"; fallo=1; fi; }
c "agente v2 activo" "systemctl is-active --quiet ppi-enforce-agent-v2-dmz"
c "ningún proceso de agente con --aplicar" "! pgrep -af 'agente_enforce' | grep -q -- '--aplicar'"
c "unidad v2 sin --aplicar" "! systemctl cat ppi-enforce-agent-v2-dmz | grep -q -- '--aplicar'"
c "agente v1 sigue deshabilitado e inactivo" \
  "[ \"\$(systemctl is-enabled ppi-enforce-agent.timer 2>/dev/null)\" = disabled ] && ! systemctl is-active --quiet ppi-enforce-agent.timer && ! systemctl is-active --quiet ppi-enforce-agent.service"
c "feed v2 recibido hace < 60 s" "[ \$(( \$(date +%s) - \$(stat -c %Y /var/lib/cyberflow/feed/feed.json) )) -lt 60 ]"
c "reloj sincronizado" "timedatectl show -p NTPSynchronized --value | grep -qx yes"
if [ "${CON_SUDO:-0}" = 1 ]; then
  T=/var/lib/cyberflow/agente/traza.jsonl
  c "traza con recepciones aceptadas" "sudo grep -q '\"estado\": \"aceptado\"' $T"
  c "NINGÚN evento 'aplicacion' en la traza" "! sudo grep -q '\"evento\": \"aplicacion\"' $T"
  echo "INFO  rechazos por motivo: $(sudo grep -o '"motivo": "[a-z_]*"' $T | sort | uniq -c | tr '\n' ' ')"
  c "sin tabla inet cyberflow_dmz" "! sudo nft list tables | grep -q cyberflow_dmz"
  if [ -n "$R" ]; then
    norm() { sed -E 's/counter packets [0-9]+ bytes [0-9]+/counter/; s/expires [0-9hms.]+//'; }
    c "ruleset efectivo = respaldo (salvo contadores)" "diff <(sudo nft list ruleset | norm) <(norm < $R/ruleset.nft) > /dev/null"
  fi
  c "helper rechaza un perfil ajeno" \
    "echo '{\"perfil\":\"dns\",\"operaciones\":[{\"op\":\"listar\"}]}' | sudo -u cfagente sudo -n /usr/local/sbin/cf-nft-helper | grep -q perfil_no_autorizado"
else
  echo "INFO  pendiente CON_SUDO=1 (Mark): traza del agente, tablas y ruleset efectivos"
fi
[ "$fallo" = 0 ] && echo "VERIFICACIÓN SRV-DMZ OK" || { echo "VERIFICACIÓN SRV-DMZ CON FALLOS"; exit 1; }
