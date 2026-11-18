#!/bin/bash
# Activa --sincronizar en el agente v2 de srv-dmz: «Limpiar» del panel libera tambien el firewall.
set -e
D=/opt/cyberflow/agente-v2
N=/home/adminsrvdmz/cf-demo/agente_enforce_v2.py.sincronizar
C=/etc/systemd/system/ppi-enforce-agent-v2-dmz.service.d/aplicar.conf
echo "e7836c42e4c3a48a58ad0656ac30478ee56272666d70dd6ed7e47d682afb3db7  $N" | sha256sum -c -
[ -f $D/agente_enforce_v2.py.bak-20261118 ] || cp -a $D/agente_enforce_v2.py $D/agente_enforce_v2.py.bak-20261118
[ -f $C.bak-20261118 ] || cp -a $C $C.bak-20261118
install -m 0644 -o root -g root $N $D/agente_enforce_v2.py
grep -q -- "--sincronizar" $C || sed -i 's/--seguir --aplicar$/--seguir --aplicar --sincronizar/' $C
systemctl daemon-reload
systemctl restart ppi-enforce-agent-v2-dmz
sleep 3
systemctl is-active ppi-enforce-agent-v2-dmz
ps -o args= -C python3 | grep agente_enforce_v2 | grep -o -- "--aplicar --sincronizar" && echo "OK: agente con --sincronizar"