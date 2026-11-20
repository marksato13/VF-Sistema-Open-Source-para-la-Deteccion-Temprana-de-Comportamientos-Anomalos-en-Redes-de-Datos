#!/usr/bin/env bash
# Regenera las unidades con la plantilla corregida (OnCalendar) y reactiva los
# timers. Ejecutar:  sudo bash ~/aplicar_fix_timers.sh
set -uo pipefail
cd /home/m4rk/cyberflow

echo "== 1. regenerar unidades desde la plantilla corregida =="
python3 scripts/setup/cyberflow_config.py --config configs/cyberflow.local.toml --escribir | sed 's/^/  /'

echo "== 2. recargar systemd =="
systemctl daemon-reload

echo "== 3. reiniciar los timers (para tomar el nuevo OnCalendar) =="
systemctl restart cyberflow-acumular.timer cyberflow-limpieza.timer

echo "== 4. arrancar una pasada del acumulador ahora mismo =="
systemctl start cyberflow-acumular.service

echo "== 5. estado: NEXT debe estar poblado (ya no infinity) =="
systemctl list-timers 'cyberflow-*' --no-pager
