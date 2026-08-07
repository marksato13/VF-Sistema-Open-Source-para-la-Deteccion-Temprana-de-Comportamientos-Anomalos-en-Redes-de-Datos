# Modelado reproducible

`calibrate_pm_f1_v1.py` implementa el preflight y la única calibración permitida
por `PM-F1-v1`. Su selector construye por nombre las 87 campañas R01–R03 de
`train` y las 29 campañas R04 de `validation`; no enumera el directorio de
ledgers y no abre R05.

El preflight valida Git, versiones, los 116 bundles fuente, conteos, orden,
destino y selección, pero no ejecuta `fit` ni `score_samples`:

```bash
commit="$(git rev-parse HEAD)"
PPI_ARTIFACTS_ROOT=/srv/ppi-evidence/artifacts \
.venv/bin/python scripts/modeling/calibrate_pm_f1_v1.py \
  --preflight \
  --protocol PM-F1-v1 \
  --expected-git-commit "$commit"
```

`--execute-once` vuelve a validar todo y crea por defecto
`$PPI_ARTIFACTS_ROOT/models/pm-f1-v1-calibration`. El destino debe ser nuevo,
estar dentro de la raíz de artefactos y no se reemplaza. La ejecución escribe
en un temporal protegido por lock y lo renombra al final. No debe usarse hasta
que el preflight, la revisión adversarial y la autorización documental estén
cerrados.

Los artefactos incluyen selección canónica, scores R04, scores de estabilidad,
seis modelos `joblib`, manifest y `SHA256SUMS`. Los hashes de los tres CSV se
calculan antes de derivar colas, umbrales o rankings. Cargar `joblib` sólo está
permitido en el entorno exacto registrado en el manifest.
