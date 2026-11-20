#!/bin/bash
# Campaña B - reversión R0-R5 en srv-dmz (vuelta a sombra). Por omisión MODO=seco: no cambia nada.
#   CF_MODO=real  ejecuta de verdad.        CF_URGENTE=1  apaga el agente ANTES de respaldar (pérdida de SSH).
# R0 respaldo con hash | R1 apagar el agente | R2 quitar el drop-in --aplicar | R3 desinstalar la tabla (helper)
# R4 comprobar que la tabla no está y que nada más cambió | R5 agente de nuevo en sombra (sin --aplicar, sin 'aplicacion').
# (R4b archiva la traza del agente de B, sin borrarla, para que verificar_srvdmz.sh pueda dar «sombra».)
# R6 (E4: el cliente de control alcanza srv-dmz) = b_r6_control.sh en la VM de clientes.
# R7 (publicador de vuelta a sombra y sin estado de la Kali) = b_r7_sensor.sh en el Sensor1, y después
#    CON_SUDO=1 verificar_srvdmz.sh <respaldo PRE-B> en srv-dmz (rc 0).
# rc: 0 todo bien; 10..15 = primer paso R0..R5 que falló (se siguen los demás pasos); 2 uso incorrecto.
set -u
MODO="${CF_MODO:-seco}"
SUDO="${CF_SUDO:-sudo -n}"
UNIDAD="${CF_UNIDAD:-ppi-enforce-agent-v2-dmz}"
DROPIN="${CF_DROPIN:-/etc/systemd/system/${UNIDAD}.service.d/90-campana-b-aplicar.conf}"
HELPER="${CF_HELPER:-/usr/local/sbin/cf-nft-helper}"
TABLA="${CF_TABLA:-cyberflow_dmz}"
DIRB="${CF_DIR_RESPALDO:-/var/lib/cyberflow/reversion-B}"
TRAZA="${CF_TRAZA:-/var/lib/cyberflow/agente/traza.jsonl}"
ESTADO="${CF_ESTADO:-/var/lib/cyberflow/agente/estado.json}"
SYSTEMCTL="${CF_SYSTEMCTL:-systemctl}"
NFT="${CF_NFT:-nft}"
ESPERA="${CF_ESPERA_R5:-5}"
case "$MODO" in seco|real) ;; *) echo "CF_MODO debe ser seco o real" >&2; exit 2;; esac
FALLO=0
marca() { date -u +%Y-%m-%dT%H:%M:%SZ; }
falla() { echo "  FALLO R$1: $2"; [ "$FALLO" = 0 ] && FALLO=$((10 + $1)); }
cambia() {  # orden que modifica el sistema: en seco solo se anuncia
  if [ "$MODO" = real ]; then "$@"; else echo "  SECO: no se ejecuta: $*"; return 0; fi
}
n_aplicaciones() { $SUDO grep -c '"evento": "aplicacion"' "$TRAZA" 2>/dev/null || true; }

echo "== reversión B en srv-dmz, modo=$MODO, $(marca)"
r1() {
  echo "[R1] apagar el agente $UNIDAD"
  cambia $SUDO $SYSTEMCTL stop "$UNIDAD" || falla 1 "no se pudo detener"
  if [ "$MODO" = real ] && [ "$($SYSTEMCTL is-active "$UNIDAD" 2>/dev/null)" = active ]; then falla 1 "sigue activo"; fi
}
r0() {
  echo "[R0] respaldo con hash en $DIRB"
  D="$DIRB/$(date -u +%Y%m%dT%H%M%SZ)"
  if [ "$MODO" = real ]; then
    $SUDO mkdir -p "$D" || { falla 0 "no se creó $D"; return; }
    $SUDO sh -c "$NFT list ruleset > '$D/ruleset.txt'; cp '$D/ruleset.txt' '$D/ruleset.nft'; $NFT list tables > '$D/tablas.txt'; \
printf '%s' '{\"perfil\":\"dmz\",\"operaciones\":[{\"op\":\"listar\"}]}' | $HELPER > '$D/listar.json'; \
cp -p '$ESTADO' '$D/estado.json' 2>/dev/null; cp -p '$TRAZA' '$D/traza.jsonl' 2>/dev/null; \
cp -p '$DROPIN' '$D/dropin.conf' 2>/dev/null; cd '$D' && sha256sum * > SHA256SUMS" || falla 0 "respaldo incompleto"
    $SUDO test -s "$D/SHA256SUMS" || falla 0 "sin SHA256SUMS"
    echo "  respaldo: $D"
  else
    echo "  SECO: se guardarían ruleset, tablas, listar del helper, estado, traza y drop-in con SHA256SUMS"
  fi
}
if [ "${CF_URGENTE:-0}" = 1 ]; then r1; r0; else r0; r1; fi
APL0=$(n_aplicaciones)

echo "[R2] quitar el drop-in --aplicar ($DROPIN)"
cambia $SUDO sh -c "rm -f '$DROPIN' && $SYSTEMCTL daemon-reload" || falla 2 "no se quitó el drop-in"
[ "$MODO" = real ] && [ -e "$DROPIN" ] && falla 2 "el drop-in sigue presente"

echo "[R3] desinstalar la tabla $TABLA con el helper (op desinstalar)"
if [ "$MODO" = real ]; then
  RES=$(printf '%s' '{"perfil":"dmz","operaciones":[{"op":"desinstalar"}]}' | $SUDO "$HELPER" 2>&1)
  echo "  helper: $RES"
  case "$RES" in *'"ok": true'*) ;; *) falla 3 "el helper no devolvió ok";; esac
else
  echo "  SECO: printf '{\"perfil\":\"dmz\",\"operaciones\":[{\"op\":\"desinstalar\"}]}' | $SUDO $HELPER"
fi

echo "[R4] la tabla no está y no cambió nada más"
if [ "$MODO" = real ]; then
  T=$($SUDO $NFT list tables 2>&1)
  echo "$T" | sed 's/^/  /'
  case "$T" in *"$TABLA"*) falla 4 "la tabla $TABLA sigue presente";; esac
  if [ -n "${D:-}" ] && $SUDO test -f "$D/tablas.txt"; then
    ANTES=$($SUDO grep -v "$TABLA" "$D/tablas.txt" | sort); AHORA=$(echo "$T" | grep -v "$TABLA" | sort)
    [ "$ANTES" = "$AHORA" ] || falla 4 "otras tablas cambiaron respecto de R0"
  fi
else
  echo "  SECO: se leería 'nft list tables' y se compararía con el respaldo de R0"
fi

echo "[R4b] archivar la traza del agente de B (no se borra; el verificador de sombra cuenta cualquier 'aplicacion' de la traza viva)"
ARCH="$(dirname "$TRAZA")/traza-B-$(date -u +%Y%m%dT%H%M%SZ).jsonl"
if [ "$MODO" = real ]; then
  if $SUDO test -f "$TRAZA"; then
    $SUDO mv "$TRAZA" "$ARCH" && $SUDO sh -c "sha256sum '$ARCH' > '$ARCH.sha256'" || falla 5 "no se pudo archivar la traza"
    echo "  traza de B archivada en $ARCH (copia con hash en $ARCH.sha256)"
  else
    echo "  no había traza viva"
  fi
else
  echo "  SECO: $TRAZA -> $ARCH (+ .sha256); el agente abriría una traza nueva al arrancar"
fi

echo "[R5] agente de nuevo en sombra"
cambia $SUDO $SYSTEMCTL start "$UNIDAD" || falla 5 "no arrancó"
if [ "$MODO" = real ]; then
  sleep "$ESPERA"
  [ "$($SYSTEMCTL is-active "$UNIDAD" 2>/dev/null)" = active ] || falla 5 "el agente no está activo"
  $SYSTEMCTL show "$UNIDAD" -p ExecStart 2>/dev/null | grep -q -- '--aplicar' && falla 5 "ExecStart aún lleva --aplicar"
  APL1=$(n_aplicaciones)
  [ "${APL1:-0}" = 0 ] || falla 5 "hay eventos 'aplicacion' en la traza nueva tras la vuelta a sombra"
  echo "  activo, sin --aplicar, eventos 'aplicacion' en la traza nueva: ${APL1:-0} (antes de B y durante B: $APL0, archivados)"
else
  echo "  SECO: se arrancaría el agente y se comprobaría ExecStart sin --aplicar y 0 eventos 'aplicacion' en la traza nueva"
fi

echo "== RESULTADO modo=$MODO rc=$FALLO $(marca)"
exit "$FALLO"
