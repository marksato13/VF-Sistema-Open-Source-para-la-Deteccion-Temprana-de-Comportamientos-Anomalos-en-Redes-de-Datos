#!/usr/bin/env bash
# Prueba corta, solo VM comparadora. Inicia IDS pasivo y lo detiene al salir.
set -Eeuo pipefail
[[ $EUID -eq 0 && $(hostname) == suricata-comparator ]] || { echo 'Usar sudo en suricata-comparator'; exit 1; }
[[ $(cat /sys/class/net/ens37/address) == 00:0c:29:c8:ad:ec ]]
[[ -z $(ip -o addr show dev ens37) ]]
[[ $(systemctl is-enabled suricata.service) == disabled ]]
if systemctl is-active --quiet suricata.service; then
    echo 'Suricata ya estaba activo: no alterar esa sesion'
    exit 1
fi
[[ $(sha256sum /etc/suricata/suricata.yaml | cut -d' ' -f1) == d0ea918591040108586e43fb30e51c3583f6d61f6ed1acd8dff938150b303650 ]]
[[ $(sha256sum /var/lib/suricata/rules/suricata.rules | cut -d' ' -f1) == 7b674459975dd56af2d03363b27df4ad6ff53e724e3c04ff65913701ddd5f4e9 ]]
grep -Fq 'HOME_NET: "[10.10.30.0/24]"' /etc/suricata/suricata.yaml
grep -Fq '  - interface: ens37' /etc/suricata/suricata.yaml
RX_BEFORE=$(cat /sys/class/net/ens37/statistics/rx_packets)
DROP_BEFORE=$(cat /sys/class/net/ens37/statistics/rx_dropped)
MGMT_BEFORE=$(ip -4 addr show dev ens34)
ROUTE_BEFORE=$(ip -4 route show default)
stop_pilot() {
    echo 'Deteniendo IDS de prueba...'
    timeout 45 systemctl stop suricata.service || echo 'ATENCION: revisar manualmente systemctl status suricata'
}
trap stop_pilot EXIT
echo 'Iniciando Suricata IDS en el comparador; sin ataque ni bloqueo.'
timeout 120 systemctl start suricata.service
systemctl is-active --quiet suricata.service
sleep 75
systemctl is-active --quiet suricata.service
python3 - <<'PY'
import collections
import json
from pathlib import Path

path = Path('/var/log/suricata/eve.json')
counts = collections.Counter()
vlans = collections.Counter()
errors = 0
with path.open() as events:
    for line in events:
        try:
            entry = json.loads(line)
        except json.JSONDecodeError:
            errors += 1
            continue
        counts[entry.get('event_type', 'sin-tipo')] += 1
        tags = entry.get('vlan', [])
        for tag in tags if isinstance(tags, list) else [tags]:
            vlans[str(tag)] += 1
print('Eventos EVE por tipo:', dict(counts))
print('VLANs presentes en EVE:', dict(vlans))
print('Lineas JSON invalidas:', errors)
PY
echo "RX: $RX_BEFORE -> $(cat /sys/class/net/ens37/statistics/rx_packets)"
echo "rx_dropped (contador de interfaz): $DROP_BEFORE -> $(cat /sys/class/net/ens37/statistics/rx_dropped)"
echo 'Archivos de log:'
ls -lh /var/log/suricata/eve.json /var/log/suricata/stats.log /var/log/suricata/suricata.log
[[ $(ip -4 addr show dev ens34) == "$MGMT_BEFORE" ]]
[[ $(ip -4 route show default) == "$ROUTE_BEFORE" ]]
[[ -z $(ip -o addr show dev ens37) ]]
echo 'Prueba concluida. El trap detendra el servicio ahora.'
