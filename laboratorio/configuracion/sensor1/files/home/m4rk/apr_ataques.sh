set -u
cd ~/cyberflow
SELLO=$(date +%Y%m%d-%H%M%S)
cp ~/cf-deploy/cyberflow_aprendizaje.py scripts/modeling/cyberflow_aprendizaje.py
cp -p configs/cyberflow.local.toml "configs/cyberflow.local.toml.bak-$SELLO"
.venv/bin/python - <<'EOF'
import sys
from pathlib import Path
sys.path.insert(0, "scripts/modeling")
import cyberflow_aprendizaje as ap
p = Path("configs/cyberflow.local.toml")
t = p.read_text(encoding="utf-8")
t = ap.fijar_toml(t, "reentrenamiento", "ataques", '"artifacts/aprendizaje/ataques/ataques-nota-M.csv"')
t = ap.fijar_toml(t, "reentrenamiento", "excluir_ventanas",
                  '["10.10.20.30@2026-09-27T21:35:00+00:00/2026-09-27T22:05:00+00:00"]'
                  '  # rafaga de la Kali dentro de la linea base (nota S)')
p.write_text(t, encoding="utf-8")
EOF
sed -n '/^\[reentrenamiento\]/,$p' configs/cyberflow.local.toml | grep -vE '^\s*#'
.venv/bin/python scripts/setup/cyberflow_config.py --config configs/cyberflow.local.toml --comprobar
.venv/bin/python scripts/modeling/cyberflow_aprendizaje.py --config configs/cyberflow.local.toml verificar | head -3
echo "RESPALDO=cyberflow.local.toml.bak-$SELLO"
