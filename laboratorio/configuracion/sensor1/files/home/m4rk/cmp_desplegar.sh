set -u
cd ~/cyberflow
SELLO=$(date +%Y%m%d-%H%M%S)
mkdir -p scripts/evaluacion docs/evaluacion
cp -p scripts/engine/dashboard.py "scripts/engine/dashboard.py.bak-$SELLO"
cp ~/cf-deploy/dashboard.py scripts/engine/dashboard.py
cp ~/cf-deploy/comparacion.py scripts/evaluacion/comparacion.py
cp ~/cf-deploy/comparacion-suricata.json docs/evaluacion/comparacion-suricata.json
sudo -n systemctl restart ppi-dashboard && sleep 4
echo "panel: $(systemctl is-active ppi-dashboard)"
sudo -n /usr/bin/journalctl --no-pager -u ppi-dashboard -n 2 --since '-1min' | tail -1
.venv/bin/python - <<'EOF'
import sys
sys.path.insert(0, "scripts/engine")
import dashboard as d
r = d.estado_comparacion(None)
print("comparacion:", r.get("error") or {c: "%d/%d" % (r["sin_firma"][c]["detectados"], r["sin_firma"][c]["n"]) for c in r["sin_firma"]})
EOF
echo "RESPALDO=dashboard.py.bak-$SELLO"
