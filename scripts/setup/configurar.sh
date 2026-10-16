#!/usr/bin/env bash
# =====================================================================
#  CyberFlow - asistente de configuracion
# ---------------------------------------------------------------------
#  Escribe configs/cyberflow.local.toml adaptado a ESTA maquina, sin
#  editar nada a mano:
#
#      bash scripts/setup/configurar.sh
#
#  Primero presenta las tres modalidades implementadas. Si se elige un
#  sensor, auto-detecta la interfaz de captura y su MAC, propone la red a
#  vigilar y escribe la configuracion. En una terminal pregunta con valores
#  por omision; sin terminal toma los detectados.
# =====================================================================
set -euo pipefail

RAIZ="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
EJEMPLO="$RAIZ/configs/cyberflow.toml"
DESTINO="$RAIZ/configs/cyberflow.local.toml"
SOLO_MODOS=0
for arg in "$@"; do
    [[ "$arg" == "--mostrar-modos" ]] && SOLO_MODOS=1
done

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

mostrar_modalidades() {
    c_tit "Modalidades implementadas de CyberFlow"
    echo "  1) Demo visual"
    echo "       Explora el panel con datos de ejemplo; no captura trafico real."
    echo "  2) Observacion IDS   [recomendado para un sensor por SPAN]"
    echo "       Captura, detecta y registra sin intervenir en el trafico."
    echo "       Modalidad instalada y comprobada en Sensor2."
    echo "  3) Observacion con respuesta distribuida"
    echo "       Sensor por SPAN + feed firmado + relay + agentes en los hosts."
    echo "       Arquitectura vigente de Sensor1."
}

mostrar_modalidades
[[ $SOLO_MODOS -eq 1 ]] && exit 0

preguntar ESCENARIO "modalidad" "2"
case "$ESCENARIO" in
    1)
        echo
        echo "  El demo no instala ni reconfigura el sensor. Ejecuta:"
        echo "    PUERTO=8790 bash scripts/demo.sh"
        exit 0
        ;;
    3)
        MODO="observacion"
        RESPUESTA_DISTRIBUIDA=1
        ;;
    *)
        MODO="observacion"
        RESPUESTA_DISTRIBUIDA=0
        ;;
esac

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
  modalidad     = $([[ $RESPUESTA_DISTRIBUIDA -eq 1 ]] && echo "observacion con respuesta distribuida" || echo "observacion IDS")
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
if [[ $RESPUESTA_DISTRIBUIDA -eq 1 ]]; then
    echo "  Despues de instalar el sensor, despliega por separado:"
    echo "    publicador (sensor) -> relay (bastion) -> agente (host protegido)"
    echo "  Procedimiento: docs/INSTALACION.md, seccion 9"
fi
