set -u
# Seccion Aprendizaje en el panel del Sensor1. NO activa el reentrenamiento:
# no toca configs/cyberflow.local.toml ni crea unidades; solo panel + modulo.
cd ~/cyberflow
SELLO=$(date +%Y%m%d-%H%M%S)
cp -p scripts/engine/dashboard.py "scripts/engine/dashboard.py.bak-$SELLO" && echo "respaldo: dashboard.py.bak-$SELLO"
cp ~/cf-deploy/dashboard.py scripts/engine/dashboard.py
cp ~/cf-deploy/cyberflow_aprendizaje.py scripts/modeling/cyberflow_aprendizaje.py
cp ~/cf-deploy/APRENDIZAJE.md docs/APRENDIZAJE.md 2>/dev/null
echo "dashboard.py $(sha256sum scripts/engine/dashboard.py | cut -c1-16)  aprendizaje $(sha256sum scripts/modeling/cyberflow_aprendizaje.py | cut -c1-16)"
echo "reentrenamiento en el .local.toml: $(grep -c '^\[reentrenamiento\]' configs/cyberflow.local.toml) seccion(es) (0 = activo=false por omision)"
# El estado que vera el panel, leido igual que lo leera el:
.venv/bin/python scripts/modeling/cyberflow_aprendizaje.py --config configs/cyberflow.local.toml estado | head -c 600; echo
sudo -n systemctl restart ppi-dashboard && echo "reiniciado"
sleep 4
echo "estado: $(systemctl is-active ppi-dashboard)"
sudo -n /usr/bin/journalctl --no-pager -u ppi-dashboard -n 8 --since '-1min' 2>&1 | tail -4
echo "RESPALDO=dashboard.py.bak-$SELLO"
