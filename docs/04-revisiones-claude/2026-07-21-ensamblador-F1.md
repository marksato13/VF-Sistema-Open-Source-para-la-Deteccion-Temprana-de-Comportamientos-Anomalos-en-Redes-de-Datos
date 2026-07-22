# Revisión adversarial Claude — ensamblador F1

Fecha: 21 de julio de 2026. Claude Code 2.1.217, modelo Sonnet, modo de planificación sin edición del repositorio.

## CLA-G6-01 — Contrato ligado al commit

1. **Severidad:** alta.
2. **Hecho:** las campañas guardan un commit y un hash de matriz, pero antes no existía un ensamblador que comprobara los bytes de matriz/esquema en ese commit.
3. **Inferencia:** comparar únicamente contra el working tree permitiría mezclar contratos temporalmente diferentes.
4. **Riesgo:** dataset no reproducible o revalidación retroactiva incorrecta.
5. **Prueba:** modificar la matriz después del commit y hacer coincidir ledger/manifiesto con el hash nuevo.
6. **Corrección:** recuperar ambos archivos con `git show <commit>:<ruta>` y recalcular SHA-256.
7. **Efecto secundario:** una evolución legítima del contrato exige nueva versión/campaña; no puede mezclarse silenciosamente.
8. **Estado:** confirmada y corregida; prueba automatizada `test_rejects_matrix_not_present_in_cited_commit`.

## CLA-G6-02 — Estimación frente a PCAP real

1. **Severidad:** alta.
2. **Hecho:** la matriz contiene `estimated_pcap_bytes`, mientras el manifiesto registra bytes reales.
3. **Inferencia:** una desviación superior puede indicar cambio del generador o agotar el almacenamiento.
4. **Riesgo:** captura incompleta o planificación de disco insuficiente.
5. **Prueba:** comparar bytes PCAP verificados con la estimación del perfil.
6. **Corrección:** el ensamblador emite una advertencia cuando el real supera lo estimado y mantiene como fallos duros el límite/truncamiento y la incoherencia remoto/local.
7. **Efecto secundario:** no se rechazan PCAP pequeños porque DNS y HTTP tienen relaciones overhead/payload distintas y la estimación es de capacidad, no una etiqueta estadística.
8. **Estado:** confirmada, corregida como advertencia trazable; pendiente calibrar tolerancias por estrato con datos oficiales.

## CLA-G6-03 — Integridad del manifiesto

1. **Severidad:** media-alta propuesta.
2. **Hecho:** `extraction-report.json` no contiene un hash separado de `manifest.json`.
3. **Inferencia de Claude:** la partición podría editarse sin detección.
4. **Riesgo:** reasignar una campaña a entrenamiento después de capturarla.
5. **Prueba:** editar manifiesto y ejecutar la verificación del bundle.
6. **Corrección aplicada:** verificar primero `campaign/SHA256SUMS`, que ya incluye `manifest.json`, y después recalcular la partición desde matriz/repetición y cruzarla con el ledger.
7. **Efecto secundario:** añadir el mismo hash al reporte sería redundante; SHA sin firma no protege contra un operador que también regenere la lista.
8. **Estado:** inferencia original rechazada parcialmente porque el manifiesto ya estaba cubierto; riesgo confirmado y mitigado mediante verificación obligatoria y cruce independiente.

## CLA-G6-04 — `eligible_training` no autoriza inclusión

1. **Severidad:** crítica.
2. **Hecho:** los dos pilotos tienen `eligible_training_rows=1` porque poseen 60 s de historia, aunque son calibraciones.
3. **Inferencia:** una concatenación directa incorporaría calibraciones al entrenamiento.
4. **Riesgo:** fuga metodológica y métricas no defendibles.
5. **Prueba:** ledger `purpose=calibration`, partición manipulada a `train` y CSV elegible.
6. **Corrección:** exigir `purpose=experiment`, recomputar partición y completar las 135 celdas.
7. **Efecto secundario:** no puede construirse un dataset provisional con los pilotos actuales.
8. **Estado:** confirmada y corregida; prueba automatizada `test_rejects_calibration_even_if_partition_train`.

## Resultado de la revisión

Las observaciones confirmadas se convirtieron en gates y pruebas. Claude no modificó el repositorio ni ejecutó tráfico. Codex implementó y reprodujo las correcciones. Queda pendiente una segunda revisión sobre el commit final publicado.
