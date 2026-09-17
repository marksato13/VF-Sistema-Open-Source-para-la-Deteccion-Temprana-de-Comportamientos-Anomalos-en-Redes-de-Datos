#!/usr/bin/env bash
# Regenera los checksums de los artefactos publicados.
# Verificar desde la raiz del repositorio:  sha256sum -c docs/dataset/SHA256SUMS
set -euo pipefail
cd "$(dirname "$0")/../.."
sha256sum \
  artifacts/dataset/multilayer-v2-normal.csv \
  artifacts/dataset/multilayer-v2-anomalies.csv \
  artifacts/dataset/multilayer-v2-audit-report.json \
  artifacts/dataset/partition-map-normal-v2.json \
  artifacts/model/manifest.json \
  artifacts/model/ocsvm_scaled.joblib \
  artifacts/model/candidates/*.joblib \
  > docs/dataset/SHA256SUMS
echo "docs/dataset/SHA256SUMS regenerado:"
cat docs/dataset/SHA256SUMS
