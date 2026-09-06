---
name: ppi-dataset-audit
description: "Audita el dataset multilayer-v2 del PPI: esquema, hashes, filas, episodios, etiquetas, particiones, duplicados, constantes y gates. Usar ante cambios o afirmaciones sobre composición y calidad de datos."
---

# Auditoría del dataset PPI

Lee primero `docs/agent-context/ppi-data-science-context.md` desde la raíz del repositorio.

## Procedimiento

1. Comprueba el árbol con `git status --short --branch`.
2. Ejecuta `sha256sum -c docs/dataset/SHA256SUMS` antes de abrir modelos.
3. Trata como fuentes primarias los CSV, el contrato de variables, el catálogo
   de campañas y el reporte de auditoría.
4. Regenera la auditoría únicamente a una ruta temporal, salvo autorización
   explícita para actualizar el artefacto congelado:

   ```bash
   .venv/bin/python scripts/dataset/audit_multilayer_v2.py \
     --normal artifacts/dataset/multilayer-v2-normal.csv \
     --anomalies artifacts/dataset/multilayer-v2-anomalies.csv \
     --output /tmp/multilayer-v2-audit.json
   ```

5. Compara el resultado temporal con el versionado. Informa filas y episodios,
   particiones, familias, faltantes, constantes, duplicados y cruces.
6. Distingue duplicados dentro de una partición de fuga entre particiones o
   etiquetas. Un gate aprobado no demuestra representatividad externa.

## Salida

Entrega una tabla `control / esperado / observado / fuente / estado`, seguida de
hallazgos por severidad. No modifiques CSV, manifiesto ni modelos.
