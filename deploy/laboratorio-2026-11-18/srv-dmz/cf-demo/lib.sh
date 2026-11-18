#!/bin/bash
# Liberacion humana (v2): quita la IP de los sets del servidor.
IP=${1:?uso: lib.sh IP}
echo "{\"perfil\":\"dmz\",\"operaciones\":[{\"op\":\"quitar\",\"set\":\"bloqueados\",\"ip\":\"$IP\"},{\"op\":\"quitar\",\"set\":\"limitados\",\"ip\":\"$IP\"}]}" | sudo -n /usr/local/sbin/cf-nft-helper >/dev/null
echo "  -> IP $IP liberada del firewall del servidor"
