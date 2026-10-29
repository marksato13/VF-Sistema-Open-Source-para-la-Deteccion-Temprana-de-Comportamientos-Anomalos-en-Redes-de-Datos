#!/bin/bash
# Arranca la copia de sesion del panel en 127.0.0.1:8799, desprendida de la
# sesion SSH (setsid, stdin desde /dev/null), y espera a que el puerto abra.
cd /home/m4rk/cyberflow || exit 1
if ss -ltn | grep -q 127.0.0.1:8799; then echo "panel ya arriba en 8799"; exit 0; fi
setsid bash -c '/home/m4rk/cyberflow/.venv/bin/python panel_sesion.py >/tmp/ps.log 2>&1 </dev/null' &
for i in $(seq 1 40); do
  if ss -ltn | grep -q 127.0.0.1:8799; then echo "panel_sesion arriba"; exit 0; fi
  sleep 0.5
done
echo "NO abrio 8799"; tail -5 /tmp/ps.log; exit 1
