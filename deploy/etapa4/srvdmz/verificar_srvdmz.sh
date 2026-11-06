#!/usr/bin/env bash
# [SRV-DMZ adminsrvdmz] Verificación de SOMBRA en srv-dmz.
#   bash verificar_srvdmz.sh                         # procesos y unidades, sin sudo
#   CON_SUDO=1 bash verificar_srvdmz.sh <RESPALDO>   # además traza, tablas y ruleset efectivo (sudo -n)
# Sombra = ausencia DEMOSTRADA de restricciones aplicadas. La decisión la toma estado_sombra.py (2026-11-02.1):
#   identifica los agentes por ejecutable y argumentos (no por grep sobre «pgrep -af», que se contaba a sí mismo),
#   excluye la propia comprobación y sus envoltorios, y trata cualquier lectura fallida como DESCONOCIDO, nunca
#   como cero. rc: 0 sombra, 1 aplicando, 2 desconocido, 3 sombra no conforme (v2 inactivo o v1 activo/habilitado).
set -uo pipefail
R="${1:-}"
AQUI="$(cd "$(dirname "$0")" && pwd)"
fallo=0
# 4A (2026-11-04): cada comprobación sin pipefail (grep -q corta la tubería: SIGPIPE río arriba daba FALLO falso).
c() { if ( set +o pipefail; eval "$2" ); then echo "OK    $1"; else echo "FALLO $1"; fallo=1; fi; }

if [ "${CON_SUDO:-0}" = 1 ]; then
  args=(--alcance completo)
  [ -n "$R" ] && args+=(--respaldo "$R")
else
  args=(--alcance procesos)
fi
python3 -I "$AQUI/estado_sombra.py" "${args[@]}"
rc=$?
case $rc in
  0) echo "OK    estado de sombra demostrado (${args[*]})" ;;
  1) echo "FALLO hay restricciones aplicadas o un agente con --aplicar"; fallo=1 ;;
  2) echo "FALLO estado DESCONOCIDO: alguna lectura falló (no se presume sombra)"; fallo=1 ;;
  3) echo "FALLO sombra no conforme: v2 no activo o v1 activo/habilitado"; fallo=1 ;;
  *) echo "FALLO estado_sombra.py terminó con rc=$rc"; fallo=1 ;;
esac

# comprobaciones de frescura: un error de lectura es FALLO (stat/timedatectl fallan -> la condición es falsa)
# 4A (2026-11-04): /var/lib/cyberflow/feed es 2750 cffeed:cfagente; el operador no puede hacer stat sin sudo
# (FALLO falso en vivo). Con CON_SUDO=1 se lee con sudo -n; sin él, la lectura denegada sigue siendo FALLO.
SUDO_STAT=""; [ "${CON_SUDO:-0}" = 1 ] && SUDO_STAT="sudo -n"
# P4 (2026-11-06): con la entrega por paquete el agente lee feed.par; feed.json deja de actualizarse.
FE=/var/lib/cyberflow/feed/feed.json
systemctl cat ppi-enforce-agent-v2-dmz 2>/dev/null | grep -v '^[[:space:]]*#' | grep -q -- '--paquete' && FE=/var/lib/cyberflow/feed/feed.par
c "feed v2 recibido hace < 60 s ($(basename $FE))" \
  "m=\$($SUDO_STAT stat -c %Y $FE) && [ \$(( \$(date +%s) - m )) -lt 60 ]"
c "reloj sincronizado" "[ \"\$(timedatectl show -p NTPSynchronized --value)\" = yes ]"
if [ "${CON_SUDO:-0}" = 1 ]; then
  T=/var/lib/cyberflow/agente/traza.jsonl
  # 4A: solo motivos NO vacíos (cada recepción aceptada lleva "motivo": "" y se contaba como rechazo).
  echo "INFO  rechazos por motivo: $(sudo -n grep -o '"motivo": "[a-z_][a-z_]*"' $T | sort | uniq -c | tr '\n' ' ') (recepciones: $(sudo -n grep -c '"evento": "recepcion"' $T))"
  # positivo: la orden debe IMPRIMIR el rechazo; si sudo o el helper fallan, grep no lo ve -> FALLO.
  # 4A (2026-11-04): el helper rechaza con rc=1; con pipefail la tubería daba FALLO aunque el rechazo estuviera.
  rech=$(echo '{"perfil":"dns","operaciones":[{"op":"listar"}]}' | sudo -n -u cfagente sudo -n /usr/local/sbin/cf-nft-helper 2>&1) || true
  c "helper rechaza un perfil ajeno" "printf '%s\n' \"\$rech\" | grep -q '\"rechazo\": \"perfil_no_autorizado\"'"
else
  echo "INFO  sin CON_SUDO=1: traza, tablas y ruleset NO verificados (alcance procesos)"
fi
[ "$fallo" = 0 ] && echo "VERIFICACIÓN SRV-DMZ OK" || { echo "VERIFICACIÓN SRV-DMZ CON FALLOS"; exit 1; }
