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
    PYV=$(python3 -c 'import sys; print("%d.%d.%d"%sys.version_info[:3])')
    if python3 -c 'import sys; sys.exit(0 if sys.version_info >= (3,11) else 1)'; then
        ok "Python $PYV"
    else
        mal "Python $PYV - hace falta 3.11 o superior (tomllib)"
    fi
else
    mal "python3 no encontrado"
fi

FALTAN_PAQUETES=""
for b in tcpdump suricata ethtool; do
    if command -v "$b" >/dev/null; then
        ok "$b"
    elif (( SOLO_COMPROBAR )); then
        mal "$b no instalado"
    else
        aviso "$b no instalado: se instalara"
        FALTAN_PAQUETES="$FALTAN_PAQUETES $b"
    fi
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
titulo "2.1 Interprete que ejecutara el motor"
# ---------------------------------------------------------------------
# Lo que importa no es el python3 del sistema, sino el del entorno virtual con
# el que arranca el motor. En scikit-learn 1.7.2 IsolationForest acepta
# sample_weight y lo ignora en silencio, asi que una diferencia de version no
# da error: da otro resultado. Ver docs/INSTALACION.md, anexo B.
PYMAN=$(python3 -c "import json;print(json.load(open('$RAIZ/artifacts/model/manifest.json'))['runtime']['python'])" 2>/dev/null || echo "")
PYBASE=$(leer_toml rutas python)
PYMOTOR="$RAIZ/${ENTORNO:-.venv}/bin/python"

buscar_interprete() {
    [[ -n "$PYBASE" && -x "$PYBASE" ]] && return
    [[ -n "$PYMAN" ]] || return
    local corta="${PYMAN%.*}" c
    for c in "/opt/python${corta}/bin/python${corta}"              "/usr/local/bin/python${corta}" "/usr/bin/python${corta}"; do
        if [[ -x "$c" ]] && [[ "$("$c" -c 'import sys;print("%d.%d.%d"%sys.version_info[:3])')" == "$PYMAN" ]]; then
            PYBASE="$c"; return
        fi
    done
}

REHACER_VENV=0
if [[ -x "$PYMOTOR" ]]; then
    PYUSO=$("$PYMOTOR" -c 'import sys; print("%d.%d.%d"%sys.version_info[:3])')
    echo "  entorno existente: $PYMOTOR"
    if [[ -n "$PYMAN" && "$PYUSO" != "$PYMAN" ]]; then
        buscar_interprete
        if [[ -n "$PYBASE" && -x "$PYBASE" ]]; then
            # Las ruedas compiladas son especificas de la version: un entorno
            # de otra no puede instalarlas, y ademas daria otros resultados.
            aviso "el entorno es $PYUSO y hay un $PYMAN disponible: se rehara"
            REHACER_VENV=1
            PYUSO="$PYMAN"
        fi
    fi
else
    # Aun no hay entorno: hay que decidir con que interprete se creara.
    buscar_interprete
    [[ -n "$PYBASE" && -x "$PYBASE" ]] || PYBASE="$(command -v python3)"
    PYUSO=$("$PYBASE" -c 'import sys; print("%d.%d.%d"%sys.version_info[:3])')
    echo "  se creara con: $PYBASE"
fi
if [[ -z "$PYMAN" ]]; then
    aviso "no se pudo leer la version del manifiesto"
elif [[ "$PYUSO" == "$PYMAN" ]]; then
    ok "CPython $PYUSO, coincide con el manifiesto"
else
    aviso "el manifiesto se genero con CPython $PYMAN, y aqui se usaria $PYUSO"
    echo "        Sirve para desplegar y ver el sistema funcionando."
    echo "        NO sirve para calibrar ni para publicar ninguna cifra."
    echo "        Ver docs/INSTALACION.md, anexo B."
fi

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
    # Cuenta lo que llega. Si no llega nada puede ser que la interfaz aun no
    # este en modo promiscuo -sin el, la vNIC descarta el espejo porque ninguna
    # trama va dirigida a su MAC- y eso lo arregla el propio instalador. Hay
    # que distinguirlo de que no llegue nada de verdad, que ya no es cosa
    # nuestra sino del hipervisor o del switch.
    contar() { local a b; a=$(cat "/sys/class/net/$IFAZ/statistics/rx_packets")
               sleep 5; b=$(cat "/sys/class/net/$IFAZ/statistics/rx_packets")
               echo $((b - a)); }
    LLEGAN=$(contar)
    if (( LLEGAN == 0 )); then
        PROM=$(cat "/sys/class/net/$IFAZ/flags")
        if (( (PROM & 0x100) == 0 )); then
            if (( SOLO_COMPROBAR )); then
                aviso "no recibe trafico, pero tampoco esta en modo promiscuo"
                echo "        El instalador lo activa. Para comprobarlo ahora:"
                echo "          sudo ip link set $IFAZ promisc on"
            else
                echo "  ...   sin modo promiscuo; activandolo para comprobar"
                ip link set "$IFAZ" up promisc on
                LLEGAN=$(contar)
            fi
        fi
    fi
    if (( LLEGAN > 0 )); then
        ok "recibe trafico: $LLEGAN paquetes en 5 s"
    elif (( SOLO_COMPROBAR == 0 )); then
        mal "NO recibe trafico ni en modo promiscuo"
        echo "        El problema esta fuera de esta maquina. Si es una VM,"
        echo "        revise el grupo de puertos del hipervisor: VLAN 4095,"
        echo "        modo promiscuo, cambios de MAC y transmisiones"
        echo "        falsificadas, todo en ACEPTAR. Ver docs/INSTALACION.md 2.3"
        echo "        Y que el switch siga espejando: show monitor session all"
    fi
else
    mal "la interfaz $IFAZ no existe. Candidatas sin IP:"
    for i in $(ls /sys/class/net | grep -v '^lo$'); do
        ip -4 addr show "$i" 2>/dev/null | grep -q 'inet ' || \
            echo "        $i  (MAC $(cat /sys/class/net/$i/address))"
    done
fi

# ---------------------------------------------------------------------
titulo "4. Suricata (estado actual)"
# ---------------------------------------------------------------------
EVE=$(leer_toml rutas eve)
if ! command -v suricata >/dev/null && (( SOLO_COMPROBAR == 0 )); then
    aviso "aun no instalado: se instalara y configurara en el paso 6"
elif systemctl is-active --quiet suricata; then
    ok "servicio activo"
    if [[ -f "$EVE" ]]; then
        A=$(wc -l < "$EVE"); sleep 5; B=$(wc -l < "$EVE")
        (( B > A )) && ok "$EVE crece" || aviso "$EVE no crecio en 5 s (puede ser normal con poco trafico)"
    else
        mal "no existe $EVE"
    fi
    if grep -qE "^\s*-\s*interface:\s*$IFAZ" /etc/suricata/suricata.yaml 2>/dev/null; then
        ok "af-packet apunta a $IFAZ"
    elif (( SOLO_COMPROBAR )); then
        mal "af-packet NO apunta a $IFAZ en /etc/suricata/suricata.yaml"
    else
        aviso "af-packet no apunta a $IFAZ: se corregira en el paso 6"
    fi
elif (( SOLO_COMPROBAR )); then
    mal "suricata no esta activo"
else
    aviso "suricata no activo: se configurara y arrancara en el paso 6"
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
titulo "6. Suricata (instalacion y configuracion)"
# ---------------------------------------------------------------------
if [[ -n "${FALTAN_PAQUETES// /}" ]]; then
    echo "  instalando:$FALTAN_PAQUETES"
    DEBIAN_FRONTEND=noninteractive apt-get install -y -qq $FALTAN_PAQUETES >/dev/null 2>&1 \
        || { mal "fallo la instalacion de$FALTAN_PAQUETES"
             echo "        Sin salida a Internet, vea docs/INSTALACION.md, anexo A."; exit 1; }
    ok "instalado$FALTAN_PAQUETES"
fi

SURICONF=/etc/suricata/suricata.yaml
if [[ -f "$SURICONF" ]]; then
    [[ -f "$SURICONF.orig-cyberflow" ]] || cp "$SURICONF" "$SURICONF.orig-cyberflow"
    RED=$(leer_toml red red_entidades)

    # HOME_NET: lo que el motor considera "dentro".
    sed -i "s|^\( *\)HOME_NET:.*|\1HOME_NET: \"[$RED]\"|" "$SURICONF"

    # af-packet: la interfaz de captura, y sin validar sumas de verificacion.
    # En trafico espejado las sumas vienen calculadas por la NIC del emisor y
    # llegan invalidas; validarlas descartaria paquetes buenos.
    python3 - "$SURICONF" "$IFAZ" <<'PY'
import re, sys
ruta, ifaz = sys.argv[1], sys.argv[2]
texto = open(ruta, encoding='utf-8').read()
i = texto.find('\naf-packet:')
if i == -1:
    sys.exit('no se encontro la seccion af-packet')
j = texto.find('\n  - interface:', i)
k = texto.find('\n', j + 1)
linea = '\n  - interface: %s\n    checksum-checks: no' % ifaz
resto = texto[k:]
resto = re.sub(r'\n    checksum-checks:[^\n]*', '', resto, count=1)
open(ruta, 'w', encoding='utf-8').write(texto[:j] + linea + resto)
PY
    ok "HOME_NET=[$RED], af-packet=$IFAZ, checksum-checks=no"

    # El paquete espera que suricata-update haya poblado el fichero de reglas,
    # y sin el "suricata -T" avisa y devuelve error. CyberFlow no necesita
    # reglas -consume eventos de flujo y de protocolo, no alertas por firma-,
    # pero el fichero tiene que existir. Vacio es suficiente y es honesto:
    # declara que no hay deteccion por firma, en vez de simularla.
    if [[ ! -f /var/lib/suricata/rules/suricata.rules ]]; then
        install -d -m 0755 /var/lib/suricata/rules
        : > /var/lib/suricata/rules/suricata.rules
        aviso "sin reglas de deteccion por firma (fichero vacio creado)"
        echo "        CyberFlow no las necesita. Para la comparacion con Wazuh"
        echo "        si hacen falta:  sudo suricata-update"
    fi

    if suricata -T -c "$SURICONF" >/dev/null 2>&1; then
        ok "configuracion valida"
    else
        mal "suricata -T no pasa:"
        suricata -T -c "$SURICONF" 2>&1 | tail -5 | sed 's/^/        /'
        echo "        Original en $SURICONF.orig-cyberflow"
        exit 1
    fi

    # Tope de registros: eve.json puede llenar la raiz en una rafaga, y un /
    # lleno tumba la maquina entera, incluido el SSH de gestion.
    if [[ -f /etc/logrotate.d/suricata ]] && ! grep -q maxsize /etc/logrotate.d/suricata; then
        [[ -f /etc/logrotate.d/suricata.orig-cyberflow ]] || \
            cp /etc/logrotate.d/suricata /etc/logrotate.d/suricata.orig-cyberflow
        sed -i 's/^\(\s*\)rotate .*/\1daily\n\1maxsize 500M\n\1rotate 7/' /etc/logrotate.d/suricata
        ok "rotacion diaria con tope de 500 MB"
    fi

    systemctl enable --now suricata >/dev/null 2>&1
    systemctl restart suricata
    sleep 8
    systemctl is-active --quiet suricata && ok "servicio activo" || {
        mal "suricata no arranco"; journalctl -u suricata -n 5 --no-pager | sed 's/^/        /'; exit 1; }
else
    mal "no existe $SURICONF"
    exit 1
fi

# ---------------------------------------------------------------------
titulo "7. Entorno de Python"
# ---------------------------------------------------------------------
# El motor escribe aqui, y systemd monta esta ruta con ReadWritePaths: si no
# existe, la unidad falla con 226/NAMESPACE antes de ejecutar una sola linea.
REGDIR="$RAIZ/$(dirname "$(leer_toml rutas registro)")"
install -d -o "$USUARIO" -g "$USUARIO" -m 0750 "$REGDIR"
ok "directorio de registro: $REGDIR"

VENV="$RAIZ/${ENTORNO:-.venv}"
(( REHACER_VENV )) && { rm -rf "$VENV"; ok "entorno anterior eliminado"; }
if [[ ! -d "$VENV" ]]; then
    sudo -u "$USUARIO" "$PYBASE" -m venv "$VENV" || {
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
titulo "8. Unidades de systemd"
# ---------------------------------------------------------------------
python3 "$RAIZ/scripts/setup/cyberflow_config.py" --config "$CONFIG" --escribir | sed 's/^/  /'
systemctl daemon-reload
UNIDADES="cyberflow-capture-nic ppi-motor-capture ppi-motor"
[[ "$(leer_toml panel activo)" == "True" ]] && UNIDADES="$UNIDADES ppi-dashboard"
systemctl enable --now $UNIDADES >/dev/null 2>&1
sleep 20

titulo "9. Comprobacion final"
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
