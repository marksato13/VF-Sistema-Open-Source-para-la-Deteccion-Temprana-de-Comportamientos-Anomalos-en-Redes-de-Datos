# Evaluación ciega de anomalías v2

Se ejecutó la matriz `configs/campaigns/multilayer-v2-anomalies.json` después
de congelar las 50 campañas normales. Las tres campañas pasaron el cierre F2,
con evidencia completa, código de escenario 0 y extracción v2 válida:

- `F2A-ANOM-SYN-RATE-10-E01-B`: 1 ventana;
- `F2A-ANOM-DNS-NX-200-E01-B`: 2 ventanas;
- `F2A-ANOM-AUTH-FAIL-50-E01-B`: 2 ventanas.

El conjunto separado está en `artifacts/dataset/multilayer-v2-anomalies.csv`
con `label=anomaly` y `partition=evaluation_only`: 5 ventanas, 3 episodios,
cero valores faltantes. SHA-256:
`ec4572b0c5a296de99c5a4a748f903e1195c956a80e2680337bab4b789b70f9e`.

Estas ventanas no se mezclan con train, validation ni test normales. El
reporte reproducible es `artifacts/dataset/anomaly-build-report.json`.
La evaluación de separabilidad y el entrenamiento del modelo deben ejecutarse
después, sin recalibrar usando estas anomalías.
