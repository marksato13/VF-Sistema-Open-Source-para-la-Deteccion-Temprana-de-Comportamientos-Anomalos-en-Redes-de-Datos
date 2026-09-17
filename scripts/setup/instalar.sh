#!/usr/bin/env bash
# =====================================================================
#  CyberFlow - instalacion desde un clon recien hecho
# ---------------------------------------------------------------------
#  Un solo comando desde el repositorio clonado hasta el motor corriendo.
#
#      sudo bash scripts/setup/instalar.sh
#      sudo bash scripts/setup/instalar.sh --comprobar   # solo diagnostica
#
#  Sustituye a configs/sensor/install-ppi-motor.sh, que estaba cableado a
#  un usuario, unas rutas y una interfaz concretos y no funcionaba en
#  ninguna otra maquina. Aqui todo sale de configs/cyberflow.toml.
# =====================================================================
set -euo pipefail

RAIZ="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
CONFIG="${CYBERFLOW_CONFIG:-$RAIZ/configs/cyberflow.local.toml}"
[[ -f "$CONFIG" ]] || CONFIG="$RAIZ/configs/cyberflow.toml"
SOLO_COMPROBAR=0
[[ "${1:-}" == "--comprobar" ]] && SOLO_COMPROBAR=1

ok()    { printf '  \033[32mOK\033[0m    %s\n' "$*"; }
aviso() { printf '  \033[33mAVISO\033[0m %s\n' "$*"; }
mal()   { printf '  \033[31mFALLO\033[0m %s\n' "$*"; FALLOS=$((FALLOS+1)); }
titulo(){ printf '\n\033[1m%s\033[0m\n' "$*"; }
FALLOS=0

leer_toml() {  # leer_toml seccion clave
    python3 - "$CONFIG" "$1" "$2" <<'PY'
import sys, tomllib
with open(sys.argv[1], 'rb') as fh:
    cfg = tomllib.load(fh)
print(cfg.get(sys.argv[2], {}).get(sys.argv[3], ''))
PY
}

# ---------------------------------------------------------------------
titulo "1. Requisitos del sistema"
# ---------------------------------------------------------------------
[[ $EUID -eq 0 ]] || { echo "Ejecutelo con sudo."; exit 2; }
command -v systemctl >/dev/null && ok "systemd" || mal "systemd no encontrado"

if command -v python3 >/dev/null; then
    PYV=$(python3 -c 'import sys; print("%d.%d"%sys.version_info[:2])')
    if python3 -c 'import sys; sys.exit(0 if sys.version_info >= (3,11) else 1)'; then
        ok "Python $PYV"
    else
        mal "Python $PYV - hace falta 3.11 o superior (tomllib)"
    fi
else
    mal "python3 no encontrado"
fi

for b in tcpdump suricata ethtool; do
    command -v "$b" >/dev/null && ok "$b" || mal "$b no instalado  (apt-get install $b)"
done
command -v nft >/dev/null && ok "nftables" || aviso "nftables no instalado (solo hace falta en modo bloqueo)"

# ---------------------------------------------------------------------
titulo "2. Configuracion"
# ---------------------------------------------------------------------
echo "  usando: $CONFIG"
if [[ "$CONFIG" == *"/cyberflow.toml" ]]; then
    aviso "esta usando la configuracion de ejemplo. Copiela antes de tocarla:"
    echo "        cp configs/cyberflow.toml configs/cyberflow.local.toml"
fi
if python3 "$RAIZ/scripts/setup/cyberflow_config.py" --config "$CONFIG" --comprobar >/dev/null 2>&1; then
    ok "configuracion valida"
else
    mal "la configuracion tiene problemas:"
    python3 "$RAIZ/scripts/setup/cyberflow_config.py" --config "$CONFIG" --comprobar 2>&1 | sed 's/^/        /'
fi

IFAZ=$(leer_toml captura interfaz)
MAC_ESPERADA=$(leer_toml captura mac_esperada)
MODO=$(leer_toml motor modo)
USUARIO=$(leer_toml rutas usuario)
ENTORNO=$(leer_toml rutas entorno)

# ---------------------------------------------------------------------
titulo "3. Interfaz de captura: $IFAZ"
# ---------------------------------------------------------------------
if ip link show "$IFAZ" >/dev/null 2>&1; then
    ok "existe"
    MAC_REAL=$(cat "/sys/class/net/$IFAZ/address")
    if [[ -n "$MAC_ESPERADA" && "$MAC_REAL" != "$MAC_ESPERADA" ]]; then
        mal "la MAC no coincide: esperada $MAC_ESPERADA, real $MAC_REAL"
        echo "        Linux renumera las interfaces al anadir o quitar adaptadores."
        echo "        Compruebe con 'ip -br link' cual es la de captura de verdad."
    else
        ok "MAC $MAC_REAL"
    fi
    if ip -4 addr show "$IFAZ" | grep -q 'inet '; then
        mal "tiene direccion IPv4. La interfaz de captura no debe tenerla"
    else
        ok "sin IPv4, como debe ser"
    fi
    # ¿le llega algo?
    A=$(cat "/sys/class/net/$IFAZ/statistics/rx_packets"); sleep 5
    B=$(cat "/sys/class/net/$IFAZ/statistics/rx_packets")
    if (( B > A )); then
        ok "recibe trafico: $((B-A)) paquetes en 5 s"
    else
        mal "NO recibe trafico (rx_packets no crece en 5 s)"
        echo "        Si es una VM, revise el grupo de puertos del hipervisor:"
        echo "        VLAN 4095, modo promiscuo, cambios de MAC y transmisiones"
        echo "        falsificadas, todo en ACEPTAR. Ver docs/INSTALACION.md 2.3"
    fi
else
    mal "la interfaz $IFAZ no existe. Candidatas sin IP:"
    for i in $(ls /sys/class/net | grep -v '^lo$'); do
        ip -4 addr show "$i" 2>/dev/null | grep -q 'inet ' || \
            echo "        $i  (MAC $(cat /sys/class/net/$i/address))"
    done
fi

# ---------------------------------------------------------------------
titulo "4. Suricata"
# ---------------------------------------------------------------------
EVE=$(leer_toml rutas eve)
if systemctl is-active --quiet suricata; then
    ok "servicio activo"
    if [[ -f "$EVE" ]]; then
        A=$(wc -l < "$EVE"); sleep 5; B=$(wc -l < "$EVE")
        (( B > A )) && ok "$EVE crece" || aviso "$EVE no crecio en 5 s (puede ser normal con poco trafico)"
    else
        mal "no existe $EVE"
    fi
    grep -qE "^\s*-\s*interface:\s*$IFAZ" /etc/suricata/suricata.yaml 2>/dev/null \
        && ok "af-packet apunta a $IFAZ" \
        || mal "af-packet NO apunta a $IFAZ en /etc/suricata/suricata.yaml"
else
    mal "suricata no esta activo"
fi

# ---------------------------------------------------------------------
titulo "5. Modo: $MODO"
# ---------------------------------------------------------------------
if [[ "$MODO" == "bloqueo" ]]; then
    aviso "modo BLOQUEO: el motor cortara trafico con nftables."
    echo "        Solo tiene sentido si esta maquina esta EN EL CAMINO del"
    echo "        trafico. Con un espejo SPAN observa pero no enruta, y las"
    echo "        reglas solo afectarian a la propia maquina."
    [[ "$(cat /proc/sys/net/ipv4/ip_forward)" == "1" ]] \
        && ok "ip_forward activo (la maquina enruta)" \
        || mal "ip_forward = 0: esta maquina NO enruta. Revise el modo"
else
    ok "modo observacion: no se tocara nftables"
fi

# ---------------------------------------------------------------------
if (( SOLO_COMPROBAR )); then
    titulo "Resultado"
    (( FALLOS == 0 )) && { echo "  Todo listo para instalar."; exit 0; }
    echo "  $FALLOS comprobacion(es) fallida(s). Corrijalas antes de instalar."
    exit 1
fi
(( FALLOS == 0 )) || { titulo "Instalacion detenida"
    echo "  $FALLOS comprobacion(es) fallida(s). Corrijalas y vuelva a ejecutar."
    echo "  Para diagnosticar sin instalar:  sudo bash $0 --comprobar"; exit 1; }

# ---------------------------------------------------------------------
titulo "6. Entorno de Python"
# ---------------------------------------------------------------------
VENV="$RAIZ/${ENTORNO:-.venv}"
if [[ ! -d "$VENV" ]]; then
    sudo -u "$USUARIO" python3 -m venv "$VENV" || {
        echo "  Falló la creacion del entorno. Instale python3-venv:"
        echo "    apt-get install -y python3-venv"; exit 1; }
fi
if [[ -d "$RAIZ/ruedas" ]]; then
    ok "instalando sin red desde ruedas/"
    sudo -u "$USUARIO" "$VENV/bin/python" -m pip install -q --no-index \
        --find-links "$RAIZ/ruedas" -r "$RAIZ/requirements-model.txt"
else
    sudo -u "$USUARIO" "$VENV/bin/python" -m pip install -q -r "$RAIZ/requirements-model.txt"
fi
ok "dependencias instaladas"

MODELO="$RAIZ/$(leer_toml rutas modelo)"
sudo -u "$USUARIO" "$VENV/bin/python" - "$MODELO" <<'PY' || exit 1
import sys, warnings, joblib
with warnings.catch_warnings(record=True) as w:
    warnings.simplefilter("always")
    m = joblib.load(sys.argv[1])
    avisos = [str(x.message) for x in w if "version" in str(x.message)]
print("  \033[32mOK\033[0m    modelo cargado: %d variables" % getattr(m, "n_features_in_", -1))
if avisos:
    print("  \033[33mAVISO\033[0m la version de scikit-learn no es la del manifiesto.")
    print("        Sirve para probar. NO para publicar cifras.")
    print("        Ver docs/INSTALACION.md, anexo B.")
PY

# ---------------------------------------------------------------------
titulo "7. Unidades de systemd"
# ---------------------------------------------------------------------
python3 "$RAIZ/scripts/setup/cyberflow_config.py" --config "$CONFIG" --escribir | sed 's/^/  /'
systemctl daemon-reload
UNIDADES="cyberflow-capture-nic ppi-motor-capture ppi-motor"
[[ "$(leer_toml panel activo)" == "True" ]] && UNIDADES="$UNIDADES ppi-dashboard"
systemctl enable --now $UNIDADES >/dev/null 2>&1
sleep 20

titulo "8. Comprobacion final"
for u in $UNIDADES; do
    systemctl is-active --quiet "$u" && ok "$u activo" || mal "$u NO arranco: journalctl -u $u"
done
REGISTRO="$RAIZ/$(leer_toml rutas registro)"
sleep 15
if [[ -s "$REGISTRO" ]]; then
    ok "el motor esta decidiendo: $(grep -c '"event": "decision"' "$REGISTRO" 2>/dev/null || echo 0) decisiones"
else
    aviso "aun no hay decisiones. El motor necesita llenar su historia primero."
fi

titulo "Instalado"
cat <<FIN
  Ver decisiones:     tail -f $REGISTRO
  Ver el servicio:    journalctl -u ppi-motor -f
  Diagnosticar:       sudo bash $0 --comprobar

  ANTES DE CREERSE UNA ALERTA: el umbral publicado esta calibrado para otra
  red. Sin recalibrar, la tasa de falsos positivos medida en un despliegue
  distinto fue del 92,4 %. Ver docs/GUIA-USUARIO.md
FIN
