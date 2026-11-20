set -u
# Activa el reentrenamiento supervisado en el Sensor1 en todo lo que no pide sudo.
# NO cambia el modelo en uso ni el motor: el temporizador solo prepara candidatos.
cd ~/cyberflow
SELLO=$(date +%Y%m%d-%H%M%S)
PY=.venv/bin/python
CF="$PY scripts/modeling/cyberflow_aprendizaje.py --config configs/cyberflow.local.toml"

echo "== 1. panel y modulo"
cp -p scripts/engine/dashboard.py "scripts/engine/dashboard.py.bak-$SELLO"
cp ~/cf-deploy/dashboard.py scripts/engine/dashboard.py
cp ~/cf-deploy/cyberflow_aprendizaje.py scripts/modeling/cyberflow_aprendizaje.py

echo "== 2. politica en el .local.toml (copia: cyberflow.local.toml.bak-$SELLO)"
cp -p configs/cyberflow.local.toml "configs/cyberflow.local.toml.bak-$SELLO"
if ! grep -q '^\[reentrenamiento\]' configs/cyberflow.local.toml; then
cat >> configs/cyberflow.local.toml <<'EOF'

[reentrenamiento]
# Reentrenamiento SUPERVISADO (docs/APRENDIZAJE.md). Prepara y evalua candidatos
# cada noche; el modelo en uso solo cambia con "promover", a mano.
activo = true
# Particion de la nota L, reconstruida el 2026-10-11 y verificada: mismo sha256
# (bdf6f641...) que anoto ensayo-if-v2.json, el paquete del modelo desplegado.
base = "artifacts/aprendizaje/base/particionado-nota-L.csv"
# Sin ventanas de ataque etiquetadas en esta red todavia: el veredicto quedara en
# EVALUACION_INCOMPLETA hasta que se anadan (p. ej. las de la Kali, nota M).
ataques = ""
EOF
fi
python3 -c "import tomllib;c=tomllib.load(open('configs/cyberflow.local.toml','rb'));print('reentrenamiento:', c['reentrenamiento'])"
$PY scripts/setup/cyberflow_config.py --config configs/cyberflow.local.toml --comprobar

echo "== 3. conjunto de oro"
[ -f artifacts/aprendizaje/oro/oro.csv ] || nice -n 19 $CF oro --desde artifacts/aprendizaje/base/particionado-nota-L.csv | head -12
ls -la artifacts/aprendizaje/oro/

echo "== 4. primer lote real (2026-10-10) y su deriva"
nice -n 19 $CF lote --dia 2026-10-10 | python3 -c "import json,sys;d=json.load(sys.stdin);print({k:d.get(k) for k in ('dia','estado','filas','psi_max','referencia')})"
nice -n 19 $CF deriva --dia 2026-10-10 | python3 -c "import json,sys;d=json.load(sys.stdin);print({k:d.get(k) for k in ('fpr_oro','psi_puntuaciones','tasa_anomala_lote','tasa_alert_motor','senal','estado')})"
$CF verificar | head -3

echo "== 5. unidades del temporizador (para instalar con sudo)"
mkdir -p ~/cf-deploy/unidades
$PY - <<'EOF'
import sys
sys.path.insert(0, "scripts/setup")
import cyberflow_config as cc
from pathlib import Path
u = cc.render(cc.cargar(Path("configs/cyberflow.local.toml")))
for n in ("cyberflow-aprendizaje.service", "cyberflow-aprendizaje.timer"):
    Path.home().joinpath("cf-deploy/unidades", n).write_text(u[n], encoding="utf-8")
    print("preparada", n)
EOF
grep -E 'ExecStart|OnCalendar|--config' ~/cf-deploy/unidades/*

echo "== 6. panel"
sudo -n systemctl restart ppi-dashboard && sleep 4 && echo "panel: $(systemctl is-active ppi-dashboard)"
echo "RESPALDOS: dashboard.py.bak-$SELLO  cyberflow.local.toml.bak-$SELLO"
