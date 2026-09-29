#!/usr/bin/env bash
# =====================================================================
#  CyberFlow - asistente de configuracion
# ---------------------------------------------------------------------
#  Escribe configs/cyberflow.local.toml adaptado a ESTA maquina, sin
#  editar nada a mano:
#
#      bash scripts/setup/configurar.sh
#
#  Auto-detecta la interfaz de captura (la que no tiene IP y recibe el
#  espejo) y su MAC, propone la red a vigilar desde la subred de gestion,
#  y pregunta el modo. En una terminal pregunta con valores por omision;
#  sin terminal (tuberia/automatizacion) toma los detectados.
# =====================================================================
set -euo pipefail

RAIZ="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
EJEMPLO="$RAIZ/configs/cyberflow.toml"
DESTINO="$RAIZ/configs/cyberflow.local.toml"
FORZAR=0
[[ "${1:-}" == "--forzar" ]] && FORZAR=1

c_ok() { printf '  \033[32m%s\033[0m\n' "$*"; }
c_tit(){ printf '\n\033[1m%s\033[0m\n' "$*"; }

# ¿Hay una terminal real para preguntar? Se comprueba UNA vez abriendo /dev/tty;
# si no (tuberia, automatizacion), el asistente toma los valores detectados.
HAY_TTY=0
if { true < /dev/tty; } 2>/dev/null; then HAY_TTY=1; fi

# Pregunta con valor por omision; sin terminal, usa el valor por omision.
preguntar() {  # preguntar NOMBREVAR "texto" "def"
    local __v="$1" texto="$2" def="$3" resp=""
    if [[ $HAY_TTY -eq 1 ]]; then
        read -r -p "  $texto [$def]: " resp < /dev/tty || resp=""
    fi
    printf -v "$__v" '%s' "${resp:-$def}"
}

# --- Detectar interfaz de captura ------------------------------------
c_tit "1. Interfaz de captura"
CANDIDATAS=()
for i in $(ls /sys/class/net | grep -v '^lo$'); do
    ip -4 addr show "$i" 2>/dev/null | grep -q 'inet ' && continue   # con IP: no es de captura
    CANDIDATAS+=("$i")
done
[[ ${#CANDIDATAS[@]} -gt 0 ]] || { echo "  No hay ninguna interfaz sin IP. Anade la NIC del espejo."; exit 1; }

# Mide rx en 2 s para marcar cual recibe el espejo.
DEFECTO_IFAZ="${CANDIDATAS[0]}"; MEJOR=-1
declare -A DELTA
for i in "${CANDIDATAS[@]}"; do
    a=$(cat "/sys/class/net/$i/statistics/rx_packets"); sleep 0.7
    b=$(cat "/sys/class/net/$i/statistics/rx_packets")
    DELTA["$i"]=$((b - a))
    printf '  %-10s MAC %s  rx +%s/0.7s\n' "$i" "$(cat /sys/class/net/$i/address)" "${DELTA[$i]}"
    if (( DELTA["$i"] > MEJOR )); then MEJOR=${DELTA[$i]}; DEFECTO_IFAZ="$i"; fi
done
preguntar IFAZ "interfaz de captura" "$DEFECTO_IFAZ"
MAC="$(cat "/sys/class/net/$IFAZ/address")"
c_ok "interfaz $IFAZ (MAC $MAC)"

# --- Red a vigilar ---------------------------------------------------
c_tit "2. Red a vigilar (HOME_NET)"
IPGEST="$(ip -o -4 addr show 2>/dev/null | awk '$2!="lo"{print $4}' | head -1 | cut -d/ -f1)"
if [[ "$IPGEST" =~ ^([0-9]+)\.([0-9]+)\. ]]; then
    DEFECTO_RED="${BASH_REMATCH[1]}.${BASH_REMATCH[2]}.0.0/16"
else
    DEFECTO_RED="10.10.0.0/16"
fi
preguntar RED "rango de entidades a puntuar" "$DEFECTO_RED"
c_ok "red $RED"

# --- Escenario de despliegue -----------------------------------------
c_tit "3. Escenario de despliegue"
echo "  1) Observacion por espejo SPAN   [recomendado]"
echo "       el sensor recibe un espejo, fuera del camino: puntua y registra."
echo "       Cero riesgo sobre la red; nftables no se toca."
echo "  2) En linea con bloqueo (IPS)"
echo "       el sensor ENRUTA el trafico y ademas corta con nftables."
echo "       Solo si esta maquina esta en el camino del trafico."
echo "  3) Personalizado (elegir el modo a mano)"
preguntar ESC "escenario" "1"
case "$ESC" in
    2)
        MODO="bloqueo"
        echo "  AVISO: bloqueo solo tiene sentido si esta maquina ENRUTA el trafico."
        echo "         Con un espejo SPAN observa pero no corta nada (y no avisa)."
        if [[ "$(cat /proc/sys/net/ipv4/ip_forward 2>/dev/null)" == "1" ]]; then
            c_ok "ip_forward=1: la maquina enruta"
        else
            echo "  AVISO: ip_forward=0: esta maquina NO enruta ahora mismo. Revisa el modo."
        fi
        ;;
    3)
        preguntar MODO "modo (observacion/bloqueo)" "observacion"
        [[ "$MODO" == "bloqueo" || "$MODO" == "observacion" ]] || MODO="observacion"
        ;;
    *)
        MODO="observacion"
        ;;
esac
c_ok "modo $MODO"

# --- Usuario y raiz --------------------------------------------------
preguntar USUARIO "usuario del servicio" "${SUDO_USER:-$(whoami)}"
preguntar RAIZ_CFG "raiz del repositorio" "$RAIZ"

# --- Escribir el .toml ----------------------------------------------
c_tit "4. Resumen"
cat <<RES
  interfaz      = $IFAZ
  mac_esperada  = $MAC
  red_entidades = $RED
  modo          = $MODO
  usuario       = $USUARIO
  raiz          = $RAIZ_CFG
  panel         = 127.0.0.1 (solo local; se abre por tunel SSH)
RES
if [[ $HAY_TTY -eq 1 ]]; then
    read -r -p "  Escribir configs/cyberflow.local.toml? [s/N]: " OK < /dev/tty || OK="n"
    [[ "$OK" =~ ^[sS]$ ]] || { echo "  cancelado."; exit 0; }
fi
if [[ -f "$DESTINO" ]]; then
    cp -f "$DESTINO" "$DESTINO.bak.$(date +%s)"
    echo "  (copia previa guardada)"
fi
cp -f "$EJEMPLO" "$DESTINO"
sed -i "s|^interfaz = .*|interfaz = \"$IFAZ\"|"           "$DESTINO"
sed -i "s|^mac_esperada = .*|mac_esperada = \"$MAC\"|"    "$DESTINO"
sed -i "s|^red_entidades = .*|red_entidades = \"$RED\"|"  "$DESTINO"
sed -i "s|^modo = .*|modo = \"$MODO\"|"                   "$DESTINO"
sed -i "s|^usuario = .*|usuario = \"$USUARIO\"|"          "$DESTINO"
sed -i "s|^raiz = .*|raiz = \"$RAIZ_CFG\"|"               "$DESTINO"
sed -i "s|^direccion = .*|direccion = \"127.0.0.1\"|"     "$DESTINO"
# "El propio sensor" en la lista de exclusion: adaptalo a ESTA maquina, para que
# su trafico de gestion no se puntue como si fuera una entidad de la red.
[[ -n "$IPGEST" ]] && sed -i "s|\"10.10.60.11/32\"|\"$IPGEST/32\"|" "$DESTINO"

c_ok "escrito $DESTINO"
if python3 "$RAIZ/scripts/setup/cyberflow_config.py" --config "$DESTINO" --comprobar >/dev/null 2>&1; then
    c_ok "configuracion validada"
else
    echo "  AVISO: la configuracion no valida; revisa:"
    python3 "$RAIZ/scripts/setup/cyberflow_config.py" --config "$DESTINO" --comprobar 2>&1 | sed 's/^/    /'
fi
echo
echo "  Siguiente:  sudo bash scripts/setup/instalar.sh --comprobar"
