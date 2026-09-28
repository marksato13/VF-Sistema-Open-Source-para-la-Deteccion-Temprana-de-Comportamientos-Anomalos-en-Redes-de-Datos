#!/usr/bin/env bash
# Modo demo de CyberFlow: levanta el panel con datos de EJEMPLO, sin red, sin
# sensor y sin login. Sirve para ver cómo funciona el sistema desde un clon
# recién hecho -- reproducibilidad: mismo código + datos incluidos -> se ve igual.
#
#   bash scripts/demo.sh
#   # luego abre http://127.0.0.1:8788
#
set -euo pipefail

RAIZ="$(cd "$(dirname "$0")/.." && pwd)"
cd "$RAIZ"
PY="${PYTHON:-python3}"
RUN="${TMPDIR:-/tmp}/cyberflow-demo"
LOG="$RUN/motor_decision.log"

echo "==> Generando decisiones de ejemplo (relativas a ahora)..."
"$PY" scripts/demo_datos.py --salida "$LOG"

echo "==> Panel demo en http://127.0.0.1:8788   (Ctrl+C para salir)"
exec "$PY" scripts/engine/dashboard.py \
  --demo \
  --log-path "$LOG" \
  --manifest-path artifacts/model/manifest.json \
  --schema configs/features/multilayer-v2.json \
  --schema-extra configs/features/multilayer-v3.json \
  --descripciones configs/features/descripciones.json \
  --dataset artifacts/dataset/multilayer-v2-normal.csv \
  --escenarios configs/escenarios.json \
  --host 127.0.0.1 --port 8788
