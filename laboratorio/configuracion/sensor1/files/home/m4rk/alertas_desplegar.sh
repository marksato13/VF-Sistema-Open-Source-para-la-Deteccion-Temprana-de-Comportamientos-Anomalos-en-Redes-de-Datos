set -u
cd ~/cyberflow
SELLO=$(date +%Y%m%d-%H%M%S)
cp -p scripts/engine/dashboard.py "scripts/engine/dashboard.py.bak-$SELLO"
cp ~/cf-deploy/dashboard.py scripts/engine/dashboard.py
cp ~/cf-deploy/simular_ataque.py scripts/simular_ataque.py
sudo -n systemctl restart ppi-dashboard && sleep 4
echo "panel: $(systemctl is-active ppi-dashboard)"
sudo -n /usr/bin/journalctl --no-pager -u ppi-dashboard -n 3 --since '-1min' | tail -2
# Lo que vera la seccion «IPs bloqueadas ahora», con el Python del panel:
.venv/bin/python - <<'EOF'
import sys, time
from pathlib import Path
sys.path.insert(0, "scripts/engine")
import dashboard as d
dec = d.read_decisions(Path("logs/motor_decision.log"), limit=2000)
v = d.acciones_vigentes(dec, time.time(), Path.home()/"feed/feed.json", Path.home()/"feed/estado.json")
c = d.compute_counters(dec, detector_modelo="if_recalibrado_2026_09")
print("vigentes:", [(x["ip"], x["accion"], x["expira_s"], x["fuente"]) for x in v])
print("ultima hora:", {k: c[k] for k in ("total", "block", "limit", "ips_con_accion")})
EOF
# El simulador debe negarse sobre el registro real:
.venv/bin/python scripts/simular_ataque.py --log logs/motor_decision.log --ventanas 1 --intervalo 0; echo "simulador sobre registro real -> rc=$?"
echo "RESPALDO=dashboard.py.bak-$SELLO"
