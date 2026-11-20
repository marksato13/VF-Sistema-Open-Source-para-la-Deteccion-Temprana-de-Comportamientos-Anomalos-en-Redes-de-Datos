#!/usr/bin/env bash
# Solo para suricata-comparator; ejecutar con sudo desde la consola SSH.
set -Eeuo pipefail
[[ $EUID -eq 0 ]] || { echo 'Ejecutar con sudo bash.'; exit 1; }
[[ $(hostname) == suricata-comparator ]] || { echo 'Host incorrecto'; exit 1; }
[[ $(cat /sys/class/net/ens37/address) == 00:0c:29:c8:ad:ec ]] || { echo 'MAC incorrecta'; exit 1; }
systemctl is-active --quiet systemd-networkd
ip -4 addr show dev ens34 | grep -q '10.10.60.13/24'
[[ -z $(ip -4 addr show dev ens37 | grep 'inet ' || true) ]] || { echo 'Captura tiene IPv4: revisar'; exit 1; }
NETWORK=/etc/systemd/network/10-suricata-capture.network
SYSCTL=/etc/sysctl.d/90-suricata-capture.conf
[[ ! -e $NETWORK && ! -e $SYSCTL ]] || { echo 'Ya existe configuracion: revisar antes de repetir'; exit 1; }
BACKUP=$(mktemp -d /root/suricata-capture-backup.XXXXXXXX)
cp -a /etc/netplan "$BACKUP/netplan"
cp -a /etc/systemd/network "$BACKUP/network"
ip -br addr > "$BACKUP/addresses-before.txt"
ip route > "$BACKUP/routes-before.txt"
OLD_IPV6=$(sysctl -n net.ipv6.conf.ens37.disable_ipv6)
MGMT_BEFORE=$(ip -4 addr show dev ens34)
ROUTE_BEFORE=$(ip -4 route show default)
rollback() {
  echo "Fallo: retirando solo los dos archivos creados. Respaldo: $BACKUP"
  rm -f "$NETWORK" "$SYSCTL"
  sysctl -w "net.ipv6.conf.ens37.disable_ipv6=$OLD_IPV6" || true
  networkctl reload || true
  echo 'Revisar ens37 en consola; no se reinicio la red de gestion.'
}
trap rollback ERR
install -d -m 755 /etc/systemd/network /etc/sysctl.d
cat > "$NETWORK" <<'EOF'
[Match]
MACAddress=00:0c:29:c8:ad:ec

[Link]
RequiredForOnline=no

[Network]
DHCP=no
LinkLocalAddressing=no
IPv6AcceptRA=no
ConfigureWithoutCarrier=yes
EOF
chmod 644 "$NETWORK"
printf '%s\n' 'net.ipv6.conf.ens37.disable_ipv6 = 1' > "$SYSCTL"
chmod 644 "$SYSCTL"
sysctl -w net.ipv6.conf.ens37.disable_ipv6=1
networkctl reload
networkctl reconfigure ens37
ip link set dev ens37 up
sleep 2
[[ -z $(ip -o addr show dev ens37) ]]
[[ $(sysctl -n net.ipv6.conf.ens37.disable_ipv6) == 1 ]]
[[ $(ip -4 addr show dev ens34) == "$MGMT_BEFORE" ]]
[[ $(ip -4 route show default) == "$ROUTE_BEFORE" ]]
networkctl status ens37 --no-pager | grep -F "$NETWORK"
trap - ERR
echo "Configuracion aplicada; respaldo: $BACKUP"
ip -br addr
ip -s link show dev ens37
echo 'Pendiente: comprobar persistencia tras un reinicio programado.'
