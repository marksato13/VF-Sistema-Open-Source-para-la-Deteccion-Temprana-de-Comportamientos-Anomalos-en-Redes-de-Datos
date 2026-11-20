#!/usr/bin/env bash
# Activar recepcion SPAN persistente solo en la NIC de captura del comparador.
set -Eeuo pipefail
[[ $EUID -eq 0 ]] || { echo 'Ejecutar con sudo bash'; exit 1; }
[[ $(hostname) == suricata-comparator ]] || { echo 'Host incorrecto'; exit 1; }
[[ $(cat /sys/class/net/ens37/address) == 00:0c:29:c8:ad:ec ]] || { echo 'MAC incorrecta'; exit 1; }
NETWORK=/etc/systemd/network/10-suricata-capture.network
[[ -f $NETWORK ]] || { echo 'Falta archivo de captura'; exit 1; }
grep -Fxq '[Link]' "$NETWORK"
grep -Fxq 'MACAddress=00:0c:29:c8:ad:ec' "$NETWORK"
if grep -Fxq 'Promiscuous=yes' "$NETWORK"; then
    echo 'Promiscuous=yes ya existe; no se repite la configuracion'
    exit 0
fi
[[ -z $(grep '^Promiscuous=' "$NETWORK" || true) ]] || { echo 'Hay un valor Promiscuous previo; revisar'; exit 1; }
BEFORE_IP=$(ip -4 addr show dev ens34)
BEFORE_ROUTE=$(ip -4 route show default)
[[ $(sysctl -n net.ipv6.conf.ens37.disable_ipv6) == 1 ]]
BACKUP=$(mktemp -d /root/suricata-promisc-backup.XXXXXXXX)
cp -a "$NETWORK" "$BACKUP/10-suricata-capture.network"
rollback() {
    echo "Fallo; restaurando archivo anterior desde $BACKUP"
    cp -a "$BACKUP/10-suricata-capture.network" "$NETWORK"
    networkctl reload || true
    networkctl reconfigure ens37 || true
    echo 'Verificar estado de ens34/ens37 en consola'
}
trap rollback ERR
sed -i '/^\[Link\]$/a Promiscuous=yes' "$NETWORK"
networkctl reload
networkctl reconfigure ens37
sleep 2
ip -d link show dev ens37 | grep -q 'promiscuity [1-9]'
[[ -z $(ip -o addr show dev ens37) ]]
[[ $(ip -4 addr show dev ens34) == "$BEFORE_IP" ]]
[[ $(ip -4 route show default) == "$BEFORE_ROUTE" ]]
trap - ERR
echo "Promiscuo configurado; respaldo: $BACKUP"
ip -br addr show dev ens37
ip -d link show dev ens37
echo 'RX antes:'
cat /sys/class/net/ens37/statistics/rx_packets
sleep 10
echo 'RX despues de 10 s:'
cat /sys/class/net/ens37/statistics/rx_packets
echo 'Persistencia tras reinicio aun no probada'
