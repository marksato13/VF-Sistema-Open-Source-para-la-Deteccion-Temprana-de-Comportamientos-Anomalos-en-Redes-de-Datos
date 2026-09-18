#!/usr/bin/env bash
# =====================================================================
#  CyberFlow - desinstalacion
# ---------------------------------------------------------------------
#      sudo bash scripts/setup/desinstalar.sh            # lo de CyberFlow
#      sudo bash scripts/setup/desinstalar.sh --todo     # ademas Suricata
#      sudo bash scripts/setup/desinstalar.sh --simular  # dice que haria
#
#  Existe por dos razones. La primera es poder deshacer. La segunda, menos
#  obvia y mas importante: sin desinstalador no se puede PROBAR el
#  instalador, y un instalador que nunca ha instalado desde cero no esta
#  probado, esta escrito.
#
#  Lo que NUNCA toca, porque no lo creo CyberFlow y romperlo deja la
#  maquina incomunicada o ciega:
#    - la configuracion de red (netplan, cloud-init)
#    - la sesion SPAN del switch
#    - el grupo de puertos del hipervisor
#    - el usuario, sus claves y su sudo
# =====================================================================
set -euo pipefail

RAIZ="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
TODO=0; SIMULAR=0
for a in "$@"; do
    case "$a" in
        --todo)    TODO=1 ;;
        --simular) SIMULAR=1 ;;
        *) echo "opcion desconocida: $a"; exit 2 ;;
    esac
done
[[ $EUID -eq 0 ]] || { echo "Ejecutelo con sudo."; exit 2; }

hacer() {
    if (( SIMULAR )); then
        printf '  \033[36mharia\033[0m  %s\n' "$*"
    else
        printf '  \033[32m-\033[0m      %s\n' "$*"
        eval "$@" >/dev/null 2>&1 || true
    fi
}
titulo(){ printf '\n\033[1m%s\033[0m\n' "$*"; }

(( SIMULAR )) && echo "MODO SIMULACION: no se ejecuta nada."

titulo "1. Servicios de CyberFlow"
for u in ppi-dashboard ppi-motor ppi-motor-capture cyberflow-capture-nic; do
    if systemctl list-unit-files "$u.service" >/dev/null 2>&1 && \
       [[ -f "/etc/systemd/system/$u.service" ]]; then
        hacer "systemctl disable --now $u.service"
        hacer "rm -f /etc/systemd/system/$u.service /etc/systemd/system/$u.service.anterior"
    fi
done
hacer "systemctl daemon-reload"
hacer "systemctl reset-failed"

titulo "2. Datos de ejecucion"
hacer "rm -rf /var/lib/ppi-motor-capture"
hacer "rm -rf $RAIZ/logs"
hacer "rm -rf $RAIZ/.venv"

titulo "3. Reglas de bloqueo, si las hubiera"
if command -v nft >/dev/null && nft list table inet ppi_enforce >/dev/null 2>&1; then
    hacer "nft delete table inet ppi_enforce"
else
    echo "  -      no hay tabla nftables de CyberFlow"
fi
hacer "rm -f /usr/local/sbin/ppi-enforce /usr/local/sbin/ppi-suricata-metrics"
hacer "rm -f /etc/sudoers.d/ppi-enforce /etc/sudoers.d/ppi-metrics"

if (( TODO )); then
    titulo "4. Suricata (--todo)"
    if [[ -f /etc/suricata/suricata.yaml.orig-cyberflow ]]; then
        hacer "cp /etc/suricata/suricata.yaml.orig-cyberflow /etc/suricata/suricata.yaml"
        echo "         (configuracion original restaurada)"
    fi
    hacer "systemctl disable --now suricata"
    hacer "DEBIAN_FRONTEND=noninteractive apt-get purge -y suricata"
    hacer "apt-get autoremove -y"
    hacer "rm -rf /var/log/suricata"
    hacer "cp /etc/logrotate.d/suricata.orig-cyberflow /etc/logrotate.d/suricata"
else
    titulo "4. Suricata"
    echo "  -      se conserva. Use --todo para quitarlo tambien."
fi

titulo "Lo que NO se ha tocado"
cat <<'FIN'
  - La configuracion de red: netplan y cloud-init siguen igual.
  - La interfaz de captura conserva su estado hasta el proximo reinicio
    (el modo promiscuo lo ponia cyberflow-capture-nic, que ya no existe).
  - La sesion SPAN del switch y el grupo de puertos del hipervisor.
  - El usuario, sus claves SSH y su sudo.
  - CPython 3.14.4 en /opt, si lo compilo. Quitarlo:  rm -rf /opt/python3.14
FIN

titulo "Comprobacion"
RESTOS=0
for u in ppi-dashboard ppi-motor ppi-motor-capture cyberflow-capture-nic; do
    [[ -f "/etc/systemd/system/$u.service" ]] && { echo "  QUEDA /etc/systemd/system/$u.service"; RESTOS=1; }
done
[[ -d /var/lib/ppi-motor-capture ]] && { echo "  QUEDA /var/lib/ppi-motor-capture"; RESTOS=1; }
[[ -d "$RAIZ/.venv" ]] && { echo "  QUEDA $RAIZ/.venv"; RESTOS=1; }
if (( SIMULAR )); then
    echo "  (simulacion: no se comprueba nada de verdad)"
elif (( RESTOS == 0 )); then
    echo "  Limpio. Para reinstalar:  sudo bash scripts/setup/instalar.sh"
fi
