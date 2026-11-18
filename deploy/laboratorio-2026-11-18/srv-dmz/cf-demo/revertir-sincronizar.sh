#!/bin/bash
# Deshace instalar-sincronizar.sh: vuelve al agente y drop-in de antes.
set -e
D=/opt/cyberflow/agente-v2
C=/etc/systemd/system/ppi-enforce-agent-v2-dmz.service.d/aplicar.conf
cp -a $D/agente_enforce_v2.py.bak-20261118 $D/agente_enforce_v2.py
[ -f $C.bak-20261118 ] && cp -a $C.bak-20261118 $C
systemctl daemon-reload
systemctl restart ppi-enforce-agent-v2-dmz
sleep 3
systemctl is-active ppi-enforce-agent-v2-dmz
sha256sum $D/agente_enforce_v2.py