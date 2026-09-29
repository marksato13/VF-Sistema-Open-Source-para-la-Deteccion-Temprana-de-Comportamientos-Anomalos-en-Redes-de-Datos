#!/usr/bin/env bash
# =====================================================================
#  CyberFlow - doctor: chequeo de salud del sistema EN MARCHA
# ---------------------------------------------------------------------
#  A diferencia de `instalar.sh --comprobar` (que valida ANTES de
#  instalar), esto revisa un despliegue YA corriendo: servicios,
#  captura, Suricata, motor, acumulador, disco y calibracion. Solo lee,
#  no cambia nada. No necesita sudo para la mayoria de comprobaciones.
#
#      bash scripts/setup/doctor.sh
# =====================================================================
set -uo pipefail

RAIZ="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
CONFIG="${CYBERFLOW_CONFIG:-$RAIZ/configs/cyberflow.local.toml}"
[[ -f "$CONFIG" ]] || CONFIG="$RAIZ/configs/cyberflow.toml"
FALLOS=0; AVISOS=0

ok()    { printf '  \033[32mOK\033[0m    %s\n' "$*"; }
aviso() { printf '  \033[33mAVISO\033[0m %s\n' "$*"; AVISOS=$((AVISOS+1)); }
mal()   { printf '  \033[31mFALLO\033[0m %s\n' "$*"; FALLOS=$((FALLOS+1)); }
tit()   { printf '\n\033[1m%s\033[0m\n' "$*"; }

leer_toml() {
    python3 - "$CONFIG" "$1" "$2" <<'PY' 2>/dev/null
import sys, tomllib
with open(sys.argv[1], 'rb') as fh: cfg = tomllib.load(fh)
v = cfg.get(sys.argv[2], {}).get(sys.argv[3], '')
print(v if not isinstance(v, bool) else str(v).lower())
PY
}

IFAZ=$(leer_toml captura interfaz)
REGISTRO="$RAIZ/$(leer_toml rutas registro)"
DATASET="$RAIZ/$(leer_toml rutas dataset)"
EVE=$(leer_toml rutas eve)
PPORT=$(leer_toml panel puerto)

# --- Servicios -------------------------------------------------------
tit "1. Servicios"
for u in suricata cyberflow-capture-nic ppi-motor-capture ppi-motor ppi-dashboard; do
    est=$(systemctl is-active "$u" 2>/dev/null)
    [[ "$est" == "active" ]] && ok "$u" || mal "$u ($est) -- journalctl -u $u"
done
for t in cyberflow-acumular.timer cyberflow-limpieza.timer; do
    est=$(systemctl is-active "$t" 2>/dev/null)
    [[ "$est" == "active" ]] && ok "$t" || aviso "$t ($est) -- sudo systemctl enable --now $t"
done

# --- Captura ---------------------------------------------------------
tit "2. Captura (interfaz $IFAZ)"
if [[ -r "/sys/class/net/$IFAZ/statistics/rx_packets" ]]; then
    a=$(cat "/sys/class/net/$IFAZ/statistics/rx_packets"); sleep 4
    b=$(cat "/sys/class/net/$IFAZ/statistics/rx_packets")
    d=$((b - a))
    (( d > 0 )) && ok "recibe trafico: +$d paquetes en 4 s" || mal "NO llegan paquetes en 4 s (revisar SPAN/hipervisor)"
else
    aviso "no existe la interfaz $IFAZ o no se puede leer su contador"
fi

# --- Suricata (eve.json) ---------------------------------------------
tit "3. Suricata (eve.json)"
if [[ -r "$EVE" ]]; then
    a=$(stat -c %s "$EVE"); sleep 4; b=$(stat -c %s "$EVE")
    (( b > a )) && ok "eve.json crece (+$((b - a)) bytes en 4 s)" || aviso "eve.json no crecio en 4 s (poco trafico L7?)"
else
    aviso "no se puede leer $EVE (permisos) -- comprueba con sudo"
fi

# --- Motor -----------------------------------------------------------
tit "4. Motor de decision"
if [[ -r "$REGISTRO" ]]; then
    n=$(grep -c '"event": "decision"' "$REGISTRO" 2>/dev/null || echo 0)
    (( n > 0 )) && ok "decidiendo: $n decisiones registradas" || aviso "aun sin decisiones (el motor llena su historia ~230 s primero)"
    if (( n > 0 )); then
        # Python solo EXTRAE los dos numeros de la ultima decision; el veredicto
        # (OK/AVISO) lo da bash, para que el aviso de pcaps cuente en el resumen.
        nums=$(python3 - "$REGISTRO" <<'PY' 2>/dev/null
import sys, json
linea = ""
with open(sys.argv[1], encoding="utf-8", errors="ignore") as f:
    for l in f:
        if '"event": "decision"' in l:
            linea = l
try:
    d = json.loads(linea)
    print(int(d.get("pcaps_ilegibles", 0)), int(d.get("duplicados_espejo", 0)))
except Exception:
    print(0, 0)
PY
)
        il=${nums%% *}; dup=${nums##* }; il=${il:-0}; dup=${dup:-0}
        (( il > 0 )) && aviso "pcaps ilegibles (acumulado desde el arranque): $il" \
                     || ok "sin pcaps ilegibles"
        ok "duplicados de espejo descartados: $dup"
    fi
else
    mal "no existe el registro del motor: $REGISTRO"
fi

# --- Acumulador / dataset -------------------------------------------
tit "5. Linea base (dataset)"
if [[ -f "$DATASET" ]]; then
    filas=$(( $(wc -l < "$DATASET" 2>/dev/null) - 1 ))
    (( filas > 0 )) && ok "$DATASET: $filas filas" || aviso "el dataset existe pero esta vacio"
else
    aviso "aun no hay dataset ($DATASET). Se crea cuando corre cyberflow-acumular.timer"
fi

# --- Disco -----------------------------------------------------------
tit "6. Disco"
uso=$(df --output=pcent "$RAIZ" 2>/dev/null | tail -1 | tr -dc '0-9')
[[ -n "$uso" ]] && { (( uso < 90 )) && ok "uso de disco: ${uso}%" || mal "disco al ${uso}% -- riesgo de llenar /"; } || aviso "no se pudo medir el disco"

# --- Calibracion -----------------------------------------------------
tit "7. Calibracion"
cal=$(leer_toml motor calibrado_en_esta_red)
if [[ "$cal" == "true" ]]; then
    ok "modelo declarado calibrado en esta red"
else
    aviso "modelo SIN calibrar en esta red: las alertas son ruido hasta recalibrar (docs/INSTALACION.md 8)"
fi

# --- Panel -----------------------------------------------------------
tit "8. Panel"
if [[ "$(leer_toml panel activo)" == "true" ]]; then
    if ss -ltn 2>/dev/null | grep -q ":$PPORT"; then ok "escuchando en el puerto $PPORT"; else mal "no escucha en $PPORT -- journalctl -u ppi-dashboard"; fi
fi

# --- Resumen ---------------------------------------------------------
tit "Resumen"
if (( FALLOS == 0 && AVISOS == 0 )); then echo "  Todo sano."
elif (( FALLOS == 0 )); then echo "  Operativo, con $AVISOS aviso(s) que revisar."
else echo "  $FALLOS fallo(s) y $AVISOS aviso(s). Revisa lo marcado en rojo."; fi
(( FALLOS == 0 ))
