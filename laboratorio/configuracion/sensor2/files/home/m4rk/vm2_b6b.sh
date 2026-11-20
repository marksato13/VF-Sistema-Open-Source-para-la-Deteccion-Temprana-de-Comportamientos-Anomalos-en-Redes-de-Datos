set -u
cd ~/cyberflow
date -u +%FT%TZ
bash scripts/setup/doctor.sh 2>&1 | sed -e 's/\x1b\[[0-9;]*m//g'
echo "== anillo: $(ls /var/lib/ppi-motor-capture/ | wc -l) ficheros, mas viejo $(ls /var/lib/ppi-motor-capture/ | head -1)"
systemctl list-timers --no-pager 'cyberflow-*' | head -5
ls -la artifacts/linea-base/ 2>&1 | tail -3
