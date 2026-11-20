#!/usr/bin/env bash
set -uo pipefail
cd /home/m4rk/cyberflow
TOML=configs/cyberflow.local.toml
echo "== 1. respaldos =="
cp -f artifacts/model/ocsvm_scaled.joblib artifacts/model/ocsvm_scaled.joblib.pre-congelar
cp -f "$TOML" "$TOML.pre-congelar"
echo "== 2. apuntar la config al modelo recalibrado =="
sed -i 's#^modelo = .*#modelo = "artifacts/preliminar/if_recalibrado_desplegable.joblib"#' "$TOML"
sed -i 's#^manifiesto = .*#manifiesto = "artifacts/preliminar/manifest-if-recalibrado.json"#' "$TOML"
sed -i 's#^calibrado_en_esta_red = .*#calibrado_en_esta_red = true#' "$TOML"
grep -q '^detector = ' "$TOML" && sed -i 's#^detector = .*#detector = "if_recalibrado_2026_09"#' "$TOML" || sed -i '/^\[motor\]/a detector = "if_recalibrado_2026_09"' "$TOML"
grep -E '^(modelo|manifiesto|calibrado_en_esta_red|detector) =' "$TOML"
echo "== 3. regenerar unidades + reload + reiniciar motor y panel =="
python3 scripts/setup/cyberflow_config.py --config "$TOML" --escribir >/dev/null
systemctl daemon-reload
systemctl restart ppi-motor ppi-dashboard
sleep 10
echo "== 4. verificar =="
echo "motor: $(systemctl is-active ppi-motor)   panel: $(systemctl is-active ppi-dashboard)"
bash scripts/setup/doctor.sh 2>&1 | sed -n '/7. Calibracion/,/Resumen/p'
