#!/usr/bin/env bash
# Solo VM comparadora. Instalacion APT desde repo file: local; no usa Internet.
set -Eeuo pipefail
[[ $EUID -eq 0 ]] || { echo 'Ejecutar con sudo bash'; exit 1; }
[[ $(hostname) == suricata-comparator ]] || { echo 'Host incorrecto'; exit 1; }
[[ $(cat /sys/class/net/ens37/address) == 00:0c:29:c8:ad:ec ]]
BASE=/home/adminsuricata
ARCHIVE=$BASE/suricata-offline-20261002.tar.gz
DEBS=$BASE/suricata-debs-20261002
STATE=$BASE/suricata-apt-state-20261002
POLICY=/usr/sbin/policy-rc.d
EXPECTED=4841dbd20a9c0b797095e40c593f7fd74e55639587ad1b77544c92f2b340187c
[[ $(sha256sum "$ARCHIVE" | cut -d' ' -f1) == "$EXPECTED" ]]
[[ -d $DEBS && -f $DEBS/Packages && -f $STATE/sources.list ]]
[[ $(find "$DEBS" -maxdepth 1 -name '*.deb' -type f | wc -l) -eq 70 ]]
grep -Fxq "deb [trusted=yes] file:$DEBS ./" "$STATE/sources.list"
[[ ! -e $POLICY ]] || { echo 'Existe policy-rc.d: revisar manualmente'; exit 1; }
[[ ! -e /etc/suricata ]] || { echo 'Ya existe /etc/suricata: revisar antes de instalar'; exit 1; }
OPTS=(
  -o "Dir::Etc::sourcelist=$STATE/sources.list"
  -o 'Dir::Etc::sourceparts=-'
  -o "Dir::State::lists=$STATE/lists"
  -o "Dir::Cache::archives=$STATE/archives"
  -o 'APT::Sandbox::User=root'
  -o 'APT::Get::List-Cleanup=0'
  -o 'Acquire::Languages=none'
  -o 'Acquire::Retries=0'
)
apt-get "${OPTS[@]}" update
SIM=$(mktemp /root/suricata-preflight.XXXXXXXX)
apt-get "${OPTS[@]}" -s --no-install-recommends install \
  'suricata=1:7.0.3-1build3' 'suricata-update=1.3.0-2' > "$SIM"
[[ -z $(awk '$1 == "Remv" {print $2}' "$SIM") ]] || { echo "Simulacion elimina paquetes: $SIM"; exit 1; }
UPGRADES=$(awk '$1 == "Inst" && $3 ~ /^\[/ {print $2}' "$SIM")
[[ $UPGRADES == libevent-core-2.1-7t64 ]] || { echo "Actualizaciones imprevistas: $UPGRADES ($SIM)"; exit 1; }
grep -q '^Inst suricata (1:7.0.3-1build3 ' "$SIM"
grep -q '^Inst suricata-update (1.3.0-2 ' "$SIM"
echo "Preflight correcto. Unica actualizacion permitida: $UPGRADES; detalle: $SIM"
# Impedir arranque automatico durante el postinst hasta fijar interfaz/reglas.
printf '#!/bin/sh\nexit 101\n' > "$POLICY"
chmod 755 "$POLICY"
trap 'rm -f "$POLICY"' EXIT
DEBIAN_FRONTEND=noninteractive apt-get "${OPTS[@]}" -y --no-install-recommends --no-remove install \
  'suricata=1:7.0.3-1build3' 'suricata-update=1.3.0-2'
suricata -V
if systemctl list-unit-files suricata.service --no-legend | grep -q suricata.service; then
    systemctl disable --now suricata.service
fi
echo 'Suricata instalado pero no activado: pendiente configurar interfaz, reglas y validar suricata -T.'
