#!/usr/bin/env bash
# =====================================================================
#  CyberFlow - preparar el bundle offline para un sensor aislado
# ---------------------------------------------------------------------
#  Se ejecuta en una maquina CONECTADA con Ubuntu 24.04 (un host de
#  construccion, o un contenedor `ubuntu:24.04`). NO se ejecuta en el
#  sensor. Produce ./bundle con todo lo que el sensor aislado necesita:
#
#     bundle/debs/               Suricata + dependencias (.deb)
#     bundle/ruedas/             wheels cp314 de requirements-model.txt
#     bundle/python3.14.tar.gz   CPython 3.14.4 (se extrae en /opt)
#
#  Luego se transfiere al sensor y alli se instala sin Internet:
#     tar czf bundle.tgz bundle    # y copiar al sensor
#     # en el sensor:
#     tar xzf bundle.tgz
#     sudo tar -C / -xzf bundle/python3.14.tar.gz
#     sudo apt-get install -y ./bundle/debs/*.deb
#     cp -r bundle/ruedas ~/cyberflow/ruedas
#     cd ~/cyberflow && sudo bash scripts/setup/instalar.sh
#
#      docker run --rm -v "$PWD:/work" -w /work ubuntu:24.04 \
#          bash scripts/setup/preparar-bundle.sh
# =====================================================================
set -euo pipefail

RAIZ="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
DEST="${1:-$RAIZ/bundle}"
PYVER="3.14.4"
export DEBIAN_FRONTEND=noninteractive

echo "==> Preparando bundle offline en $DEST"
mkdir -p "$DEST/debs" "$DEST/ruedas"
apt-get update -qq

echo "==> 1/4  Suricata y dependencias (.deb)"
apt-get install -y -qq --download-only suricata suricata-update
cp -f /var/cache/apt/archives/*.deb "$DEST/debs/" 2>/dev/null || true
echo "    $(ls "$DEST/debs" | wc -l) paquetes .deb"

echo "==> 2/4  Herramientas de compilacion + descarga"
apt-get install -y -qq curl ca-certificates build-essential zlib1g-dev \
    libssl-dev libffi-dev libbz2-dev liblzma-dev libsqlite3-dev \
    libreadline-dev libncurses-dev uuid-dev libgdbm-dev pkg-config

echo "==> 3/4  Compilando CPython $PYVER en /opt/python3.14 (unos minutos)"
cd /tmp
curl -fsSLO "https://www.python.org/ftp/python/$PYVER/Python-$PYVER.tgz"
tar xzf "Python-$PYVER.tgz"
cd "Python-$PYVER"
./configure --prefix=/opt/python3.14 --with-ensurepip=install >/tmp/py-configure.log 2>&1
make -j"$(nproc)" >/tmp/py-make.log 2>&1
make altinstall >/tmp/py-install.log 2>&1
cd /
tar czf "$DEST/python3.14.tar.gz" opt/python3.14
echo "    $(/opt/python3.14/bin/python3.14 --version)"

echo "==> 4/4  Wheels cp314 de requirements-model.txt (resolucion nativa)"
/opt/python3.14/bin/python3.14 -m pip download -q \
    -r "$RAIZ/requirements-model.txt" -d "$DEST/ruedas"
echo "    $(ls "$DEST/ruedas" | wc -l) wheels"

echo
echo "BUNDLE LISTO en $DEST/"
echo "  debs   : $(ls "$DEST/debs" | wc -l) paquetes"
echo "  ruedas : $(ls "$DEST/ruedas" | wc -l) wheels"
echo "  python : python3.14.tar.gz ($(du -h "$DEST/python3.14.tar.gz" | cut -f1))"
echo
echo "Siguiente: transferir '$DEST' al sensor y seguir el encabezado de este script."
