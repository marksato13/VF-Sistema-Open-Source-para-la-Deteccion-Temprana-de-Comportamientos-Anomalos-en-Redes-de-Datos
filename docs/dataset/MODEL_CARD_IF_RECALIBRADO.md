# Model card — Isolation Forest limpio (modelo operativo)

Desplegado y verificado en Sensor1 el **2026-10-19** (`ppi-motor` activo con detector
`if_limpio_2026_10`). **Reemplaza** al `if_recalibrado_2026_09`, que queda de respaldo
para rollback. La [model card OCSVM](MODEL_CARD_OCSVM.md) permanece como evidencia
**histórica del laboratorio**. Esta card se mantiene a mano: **no** se genera con
`generar_cards.py` (que solo produce la del OCSVM desde el manifiesto de laboratorio).

| Propiedad | Estado operativo |
|---|---|
| Identificador | `if_limpio_2026_10` (reemplaza a `if_recalibrado_2026_09`, que queda de respaldo) |
| Artefacto | `artifacts/preliminar/limpio-2026-10/if_limpio_2026_10_desplegable.joblib` (Sensor1) — SHA-256 en `manifest-if-limpio-2026-10.json`, campo `model_sha256` |
| Tipo | `Pipeline` (escalador + Isolation Forest); puntúa ventanas de características crudas con `score_samples` |
| Umbral | `score_samples < −0,569397` alerta; equivale a `decision_function < −0,069397` (offset de −0,5) |
| Calibración | `alpha = 0,05` sobre validation, sin elegir el umbral sobre test; `calibrado_en_esta_red = true` |
| Entradas | 28 variables L3/L4/L7 del esquema v2; una sin observabilidad efectiva (`tls_handshake_failure_ratio_60s`). La capa 2 no entra al scoring |
| Modo | Captura pasiva por SPAN en Sensor1; respuesta por feed firmado y agente `nftables` en el host protegido. No está en línea en el sensor |

**Entrenamiento limpio (sin la ráfaga Kali).** Las 181 ventanas de la Kali que habían
entrado a la línea base (6 rangos de `excluir_ventanas`, entity `10.10.20.30`, incluido el
pico del 27-sep 21:35–22:05 UTC) se **excluyeron del entrenamiento**. Este modelo se entrenó
con tráfico normal, sin ataques etiquetados ni inyectados (detección **no supervisada**).
Reconstrucción reproducible: `reconstruir_limpio.py` sobre
`artifacts/aprendizaje/base/particionado-nota-L.csv`, semilla 20260813, `n_estimators = 500`;
la verificación interna reprodujo el umbral del predecesor (−0,068892) antes de construir
el limpio. El predecesor `if_recalibrado_2026_09`
(SHA-256 `d27f68711fcb0f6657611bd7feb17759bc4fae36b9e61fbd5ca8d1190128125a`) contenía esas
ventanas y queda de respaldo.

**Mediciones del modelo, no del stack completo.** Línea base normal: train 203 967
(204 148 − 181 Kali excluidas), validation 65 633, test 65 421; **FPR sobre test normal
4,53 %**. Sobre el mismo conjunto de ataques de laboratorio y en el umbral de operación, la
detección es **idéntica al predecesor** (el entrenamiento limpio no degrada la detección;
ROC-AUC 0,92 y detección iguales sobre el conjunto compartido, ΔFPR +0,07 pp). Las cifras de
detección por familia y el 64,3 % sobre 84 ventanas activas (nota M) son del predecesor; su
recálculo formal sobre el limpio con `recongelar/` queda **pendiente**, sin cambios
materiales esperados dada la equivalencia. Cambiar el denominador o el escenario cambia la
estimación. No extrapolar a otras redes ni a un «zero-day» universal.

**Sobre la mejora frente al OCSVM.** El paso de 92,4 % a ~4,5 % **no aísla el efecto de
recalibrar**: cambiaron a la vez modelo, datos y alcance (exclusión del plano de control
y deduplicación del espejo). Para atribuirlo a la recalibración habría que puntuar ambos
modelos sobre el mismo conjunto retenido.

**Aporte del sistema híbrido.** La batería posterior de nueve episodios de tres familias
da modelo solo 6/9, heurísticos solos 7/9, combinado 9/9. No atribuir 9/9 al Isolation
Forest. La fuerza bruta confirmada en vivo la detectó el heurístico.

**Limitaciones.** El 4,53 % se midió en test normal retenido; no es garantía de FPR continuo
ni el FPR del sistema completo. F6 dio 22,97–25,81 % con otro modelo y escenario. El modelo
solo no detectó DNS en el piloto de septiembre (ensayo contra un host que no era el resolver);
ese hueco lo cubre el heurístico `dns_entropy`. La comparación de siete candidatos del dataset
anterior y la promoción histórica del OCSVM tras ver el test introducen sesgo de selección;
la elección actual no debe presentarse como preregistrada.

**Fuentes** (evidencia fijada al commit `bb6e91d784622aab52f8b9f579186e50484dfdf6` de
`VF-PPI-TESIS-ORQUESTACION`):
[nota L](https://github.com/marksato13/VF-PPI-TESIS-ORQUESTACION/blob/bb6e91d784622aab52f8b9f579186e50484dfdf6/04-evidencias/cyberflow/L-recalibracion-seco-sensor1-2026-09-29.md) ·
[nota M](https://github.com/marksato13/VF-PPI-TESIS-ORQUESTACION/blob/bb6e91d784622aab52f8b9f579186e50484dfdf6/04-evidencias/cyberflow/M-deteccion-kali-sensor1-2026-09-30.md) ·
[31 — ablación](https://github.com/marksato13/VF-PPI-TESIS-ORQUESTACION/blob/bb6e91d784622aab52f8b9f579186e50484dfdf6/02-metodologia/comparacion-cyberflow-suricata/31-ABLACION-RESULTADO.md) ·
[32 — resumen](https://github.com/marksato13/VF-PPI-TESIS-ORQUESTACION/blob/bb6e91d784622aab52f8b9f579186e50484dfdf6/02-metodologia/comparacion-cyberflow-suricata/32-RESUMEN-RESULTADOS.md) ·
[`../RECONCILIACION-MANIFIESTO-MOTOR.md`](../RECONCILIACION-MANIFIESTO-MOTOR.md).
