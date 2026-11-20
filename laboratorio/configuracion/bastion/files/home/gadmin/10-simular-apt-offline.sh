#!/usr/bin/env bash
# Preparar indice APT local y SIMULAR. No instala paquetes ni modifica APT global.
set -Eeuo pipefail
[[ $(hostname) == suricata-comparator ]] || { echo 'Host inesperado'; exit 1; }
[[ $EUID -ne 0 ]] || { echo 'Ejecutar sin sudo'; exit 1; }
ARCHIVE=$HOME/suricata-offline-20261002.tar.gz
DEBS=$HOME/suricata-debs-20261002
STATE=$HOME/suricata-apt-state-20261002
EXPECTED=4841dbd20a9c0b797095e40c593f7fd74e55639587ad1b77544c92f2b340187c
[[ $(sha256sum "$ARCHIVE" | cut -d' ' -f1) == "$EXPECTED" ]]
[[ -d $DEBS ]]
[[ $(find "$DEBS" -maxdepth 1 -name '*.deb' -type f | wc -l) -eq 70 ]]
mkdir -p "$STATE/lists/partial" "$STATE/archives/partial"
apt-ftparchive packages "$DEBS" | sed "s|Filename: $DEBS/|Filename: ./|" > "$DEBS/Packages"
printf 'deb [trusted=yes] file:%s ./\n' "$DEBS" > "$STATE/sources.list"
OPTS=(
  -o "Dir::Etc::sourcelist=$STATE/sources.list"
  -o 'Dir::Etc::sourceparts=-'
  -o "Dir::State::lists=$STATE/lists"
  -o "Dir::Cache::archives=$STATE/archives"
  -o "APT::Sandbox::User=$(id -un)"
  -o 'APT::Get::List-Cleanup=0'
  -o 'Acquire::Languages=none'
)
apt-get "${OPTS[@]}" update
apt-get "${OPTS[@]}" -s --no-install-recommends install suricata suricata-update | tee "$STATE/simulation.txt"
echo "Simulacion guardada en $STATE/simulation.txt; NO se ha instalado Suricata"
