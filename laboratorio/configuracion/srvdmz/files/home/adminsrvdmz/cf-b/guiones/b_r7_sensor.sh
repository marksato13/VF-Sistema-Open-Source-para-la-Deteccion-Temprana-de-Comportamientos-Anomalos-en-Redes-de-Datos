#!/bin/bash
# Campaña B - R7 en el Sensor1 (m4rk, sin sudo): el publicador sigue en la configuración de sombra y no queda estado de la Kali.
# Por omisión MODO=seco: solo lee. CF_MODO=real: si queda estado de la Kali, ejecuta la limpieza D5 (d5_episodio.py) y relee.
# Luego, en srv-dmz:  CON_SUDO=1 bash verificar_srvdmz.sh <dir con el ruleset.nft PRE-B>  (rc 0).
# rc: 0 todo bien; 7 alguna comprobación falló (se listan todas).
set -u
MODO="${CF_MODO:-seco}"
UNIDAD="${CF_UNIDAD:-ppi-publicar-feed-v2.service}"
ESTADO="${CF_ESTADO:-$HOME/feed-v2/estado.json}"
FEED="${CF_FEED:-$HOME/feed-v2/feed.json}"
D5="${CF_D5:-$HOME/cf-b/d5_episodio.py}"
SYSTEMCTL="${CF_SYSTEMCTL:-systemctl}"
PY="${CF_PY:-python3}"
ORIGEN=10.10.20.30
mal=0
ok() { echo "  OK    $1"; }
no() { echo "  FALLO $1"; mal=$((mal + 1)); }
estado_kali() {  # imprime cuántas claves de la Kali hay en vigentes+escalada (o ERR)
  $PY -I - "$ESTADO" "$ORIGEN" <<'PYEOF'
import json, sys
try:
    e = json.load(open(sys.argv[1]))
    n = sum(1 for k in e.get("vigentes", {}) if k.split("|", 1)[0] == sys.argv[2])
    n += sum(1 for k in e.get("escalada", {}) if k.split("@", 1)[0] == sys.argv[2])
    print(n)
except Exception:
    print("ERR")
PYEOF
}
echo "== R7 Sensor1 modo=$MODO $(date -u +%FT%TZ)"
U=$($SYSTEMCTL cat "$UNIDAD" 2>/dev/null | grep -v '^[[:space:]]*#')
echo "$U" | grep -q -- '--politica if_senal' && ok "unidad con --politica if_senal" || no "la unidad no lleva --politica if_senal"
echo "$U" | grep -q -- '--aplicar' && no "la unidad del publicador lleva --aplicar" || ok "la unidad no lleva --aplicar"
[ "$($SYSTEMCTL is-active "$UNIDAD" 2>/dev/null)" = active ] && ok "publicador activo" || no "publicador no activo"
N=$(estado_kali)
if [ "$N" = 0 ]; then ok "sin estado de la Kali (vigentes/escalada)"
elif [ "$N" = ERR ]; then no "estado del publicador ilegible"
elif [ "$MODO" = real ] && [ -f "$D5" ]; then
  echo "  limpiando con D5 ($N claves de la Kali)"
  $PY -I "$D5" sensor-limpiar --real --estado "$ESTADO" >/dev/null && sleep "${CF_ESPERA:-5}"
  [ "$(estado_kali)" = 0 ] && ok "estado de la Kali limpiado (copia y d5.jsonl conservados)" || no "el estado de la Kali sigue ahí tras D5"
else no "quedan $N claves de la Kali en el estado del publicador (modo=$MODO)"; fi
$PY -I - "$FEED" "$ORIGEN" <<'PYEOF' && ok "feed vigente y sin entradas de la Kali" || no "feed viejo, ilegible o con entradas de la Kali"
import json, sys, time
f = json.load(open(sys.argv[1]))
assert float(f["expira"]) > time.time() and not [e for e in f["entradas"] if e.get("ip") == sys.argv[2]]
PYEOF
[ "$($SYSTEMCTL is-active logrotate.timer 2>/dev/null)" = active ] && ok "logrotate.timer activo (cierre)" || no "logrotate.timer NO activo: reanudar con cf-4b-rotacion"
[ "$mal" = 0 ] && { echo "== R7 OK rc=0"; exit 0; }
echo "== R7 con $mal fallo(s) rc=7"
exit 7
