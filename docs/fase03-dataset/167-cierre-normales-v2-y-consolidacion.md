# Cierre de campañas normales v2

Fecha de cierre: 2026-08-13.

Se completaron las cinco repeticiones de los diez perfiles normales de la
matriz `multilayer-v2-normal.json`: 50 episodios, todos en fase F2, con
`status=completed`, `evidence.complete=true`, código de escenario 0 y al
menos una fila elegible por campaña. Las campañas de calibración y los
intentos abortados no se incluyeron.

La consolidación se ejecutó con
`scripts/dataset/build_multilayer_v2_dataset.py`, manteniendo cada episodio
en una sola partición:

| Partición | Repeticiones | Episodios | Filas elegibles |
|---|---:|---:|---:|
| train | R01–R03 | 30 | 44 |
| validation | R04 | 10 | 15 |
| test | R05 | 10 | 16 |
| **Total** | **R01–R05** | **50** | **75** |

El CSV consolidado está en:
`artifacts/dataset/multilayer-v2-normal.csv`.

Reporte: `artifacts/dataset/normal-build-report.json`.

SHA-256 del CSV: `be8b71104bda5200a04ee77bdda5c3e164c5ed9a753bfc8c7dae9bb41003e99e`.

Este hito **no significa que el dataset final esté terminado**. Falta
capturar la matriz de anomalías en evaluación ciega, verificar separabilidad
sin recalibrar con test, etiquetar esas ventanas y ejecutar la auditoría de
calidad/modelo. El dashboard queda pospuesto hasta ese cierre.
