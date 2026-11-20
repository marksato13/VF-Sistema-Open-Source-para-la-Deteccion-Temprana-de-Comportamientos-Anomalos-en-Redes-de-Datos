#!/bin/bash
# Campaña B - ACTIVACIÓN del agente de srv-dmz (--aplicar) con fin automático. NO se ejecuta sin la orden de inicio de B.
# Por omisión MODO=seco. CF_MODO=real ejecuta. CF_HORAS = duración del fin automático (por omisión 8).
# A0 comprobaciones previas (solo lectura) | A1 instalar la reversión en /opt/cyberflow/campana-b con hash
# A2 drop-in con --aplicar | A3 fin automático cf-b-fin | A4 reiniciar el agente y comprobar.
# rc: 0 ok; 20..24 = primer paso A0..A4 que falló (se detiene en el primero: no se activa nada a medias); 2 uso.
set -u
MODO="${CF_MODO:-seco}"
SUDO="${CF_SUDO:-sudo -n}"
UNIDAD="${CF_UNIDAD:-ppi-enforce-agent-v2-dmz}"
DROPIN="${CF_DROPIN:-/etc/systemd/system/${UNIDAD}.service.d/90-campana-b-aplicar.conf}"
OPT="${CF_OPT:-/opt/cyberflow/campana-b}"
SRC="${CF_SRC_REVERSION:-$(dirname "$0")/b_revertir_srvdmz.sh}"
HORAS="${CF_HORAS:-8}"
SYSTEMCTL="${CF_SYSTEMCTL:-systemctl}"
RUN="${CF_SYSTEMD_RUN:-systemd-run}"
TABLA="${CF_TABLA:-cyberflow_dmz}"
MIN_LIBRE_KB="${CF_MIN_LIBRE_KB:-2097152}"   # 2 GB en srv-dmz (solo trazas pequeñas); los 20 GB del preflight son del Sensor1
OWN="-o root -g root"; [ "${CF_SIN_PROPIETARIO:-0}" = 1 ] && OWN=""   # solo para el banco (no root)
case "$MODO" in seco|real) ;; *) echo "CF_MODO debe ser seco o real" >&2; exit 2;; esac
cambia() { if [ "$MODO" = real ]; then "$@"; else echo "  SECO: no se ejecuta: $*"; return 0; fi; }
stop() { echo "  FALLO A$1: $2"; echo "== RESULTADO modo=$MODO rc=$((20 + $1))"; exit $((20 + $1)); }

echo "== activación B en srv-dmz, modo=$MODO, fin automático a las ${HORAS} h"
echo "[A0] comprobaciones previas (solo lectura)"
[ "$($SYSTEMCTL is-active "$UNIDAD" 2>/dev/null)" = active ] || stop 0 "el agente no está activo"
$SYSTEMCTL show "$UNIDAD" -p ExecStart 2>/dev/null | grep -q -- '--aplicar' && stop 0 "el agente ya lleva --aplicar"
NR=$($SYSTEMCTL show "$UNIDAD" -p NRestarts --value 2>/dev/null); [ "${NR:-x}" = 0 ] || stop 0 "NRestarts=$NR (debe ser 0)"
[ -e "$DROPIN" ] && stop 0 "ya existe $DROPIN"
$SUDO "${CF_NFT:-nft}" list tables 2>/dev/null | grep -q "$TABLA" && stop 0 "la tabla $TABLA ya existe: sin limpiar"
LIBRE=$(df -Pk "${CF_DIR_DISCO:-/var/lib/cyberflow}" 2>/dev/null | awk 'NR==2{print $4}'); [ "${LIBRE:-0}" -ge "$MIN_LIBRE_KB" ] || stop 0 "disco libre ${LIBRE:-?} kB < $MIN_LIBRE_KB"
[ -f "$SRC" ] || stop 0 "no existe el guion de reversión $SRC"
echo "  agente activo en sombra, NRestarts=0, sin drop-in, sin tabla, disco ${LIBRE} kB"

echo "[A1] instalar la reversión en $OPT con hash"
cambia $SUDO sh -c "mkdir -p '$OPT' && install -m 0750 $OWN '$SRC' '$OPT/b_revertir_srvdmz.sh' && sha256sum '$OPT/b_revertir_srvdmz.sh' > '$OPT/SHA256SUMS' && mkdir -p '$OPT/pre-B' && ${CF_NFT:-nft} list ruleset > '$OPT/pre-B/ruleset.nft' && (cd '$OPT/pre-B' && sha256sum ruleset.nft > SHA256SUMS)" || stop 1 "no se instaló la reversión o no se guardó el respaldo PRE-B"
echo "  respaldo PRE-B del ruleset (referencia de verificar_srvdmz.sh tras la reversión): $OPT/pre-B/ruleset.nft"

echo "[A2] drop-in con --aplicar ($DROPIN)"
DROP="[Service]
ExecStart=
ExecStart=/usr/bin/python3 -I /opt/cyberflow/agente-v2/agente_enforce_v2.py --perfil dmz --paquete /var/lib/cyberflow/feed/feed.par --clave-publica /opt/cyberflow/agente-v2/pub.pem --estado /var/lib/cyberflow/agente/estado.json --traza /var/lib/cyberflow/agente/traza.jsonl --helper \"sudo -n /usr/local/sbin/cf-nft-helper\" --aplicar --seguir
"
if [ "$MODO" = real ]; then
  $SUDO mkdir -p "$(dirname "$DROPIN")" && printf '%s' "$DROP" | $SUDO tee "$DROPIN" >/dev/null && $SUDO $SYSTEMCTL daemon-reload || stop 2 "no se escribió el drop-in"
else echo "  SECO: se escribiría el drop-in:"; printf '%s' "$DROP" | sed 's/^/    /'; fi

echo "[A3] fin automático cf-b-fin a las ${HORAS} h (ejecuta la reversión real)"
cambia $SUDO $RUN --on-active="${HORAS}h" --unit=cf-b-fin --setenv=CF_MODO=real --setenv=CF_URGENTE=1 "$OPT/b_revertir_srvdmz.sh" || stop 3 "no se programó el fin"

echo "[A4] reiniciar el agente con --aplicar y comprobar"
cambia $SUDO $SYSTEMCTL restart "$UNIDAD" || stop 4 "no reinició"
if [ "$MODO" = real ]; then
  sleep 5
  [ "$($SYSTEMCTL is-active "$UNIDAD")" = active ] || stop 4 "el agente no quedó activo"
  $SYSTEMCTL show "$UNIDAD" -p ExecStart | grep -q -- '--aplicar' || stop 4 "ExecStart sin --aplicar"
  $SYSTEMCTL is-active cf-b-fin.timer >/dev/null 2>&1 || stop 4 "el fin automático no está programado"
fi
echo "== RESULTADO modo=$MODO rc=0"
exit 0
