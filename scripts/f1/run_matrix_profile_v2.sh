#!/usr/bin/env bash
set -euo pipefail

# Lanzador seguro: conserva el orquestador F1 y selecciona explícitamente los
# contratos v2. La ejecución oficial seguirá bloqueada hasta que el runner
# acepte ambos contratos y el piloto valide el almacenamiento.
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
exec "$ROOT/scripts/f1/run_matrix_profile.py" \
  --matrix "$ROOT/configs/campaigns/multilayer-v2-normal.json" \
  --feature-schema "$ROOT/configs/features/multilayer-v2.json" "$@"
