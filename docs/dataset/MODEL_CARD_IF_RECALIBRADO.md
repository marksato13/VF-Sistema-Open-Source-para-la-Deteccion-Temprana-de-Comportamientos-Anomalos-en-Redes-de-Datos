# Model card — Isolation Forest recalibrado (modelo operativo)

Estado verificado en Sensor1 el 2026-10-09; no sustituye al manifiesto ni al modelo.
La [model card OCSVM](MODEL_CARD_OCSVM.md) permanece como evidencia **histórica del
laboratorio**. Esta card se mantiene a mano: **no** se genera con `generar_cards.py`
(que solo produce la del OCSVM desde el manifiesto de laboratorio).

| Propiedad | Estado operativo |
|---|---|
| Identificador | `if_recalibrado_2026_09` |
| Artefacto | `artifacts/preliminar/if_recalibrado_desplegable.joblib` (Sensor1) — SHA-256 `d27f68711fcb0f6657611bd7feb17759bc4fae36b9e61fbd5ca8d1190128125a` |
| Tipo | `Pipeline` (escalador + Isolation Forest); puntúa ventanas de características crudas con `score_samples` |
| Umbral | `score_samples < −0,568892` alerta; equivale a `decision_function < −0,068892` (offset de −0,5) |
| Calibración | `alpha = 0,05` sobre validation, sin elegir el umbral sobre test; `calibrado_en_esta_red = true` |
| Entradas | 28 variables L3/L4/L7 del esquema v2; una sin observabilidad efectiva (`tls_handshake_failure_ratio_60s`). La capa 2 no entra al scoring |
| Modo | Captura pasiva por SPAN en Sensor1; respuesta por feed firmado y agente `nftables` en el host protegido. No está en línea en el sensor |

**Mediciones del modelo, no del stack completo.** Línea base normal elegible 337 980
filas (train 204 148, validation 65 633, test 65 421); **FPR sobre test normal 4,45 %**
(nota L). Sobre 78 ventanas activas de ataques Kali en la misma red, 54 detectadas =
**69 %**; HTTP 27/27, escaneo 27/43 y DNS 0/8 (nota M). Cambiar el denominador o el
escenario cambia la estimación. No extrapolar a otras redes ni a un «zero-day»
universal.

**Sobre la mejora frente al OCSVM.** El paso de 92,4 % a 4,45 % **no aísla el efecto de
recalibrar**: cambiaron a la vez modelo, datos y alcance (exclusión del plano de control
y deduplicación del espejo). Para atribuirlo a la recalibración habría que puntuar ambos
modelos sobre el mismo conjunto retenido.

**Aporte del sistema híbrido.** La batería posterior de nueve episodios de tres familias
da modelo solo 6/9, heurísticos solos 7/9, combinado 9/9. No atribuir 9/9 al Isolation
Forest. La fuerza bruta confirmada en vivo la detectó el heurístico.

**Limitaciones.** El 4,45 % se midió en test normal retenido tras la recalibración; no
es garantía de FPR continuo ni el FPR del sistema completo. F6 dio 22,97–25,81 % con
otro modelo y escenario. El modelo solo no detectó DNS en el piloto de septiembre (ensayo
contra un host que no era el resolver). La comparación de siete candidatos del dataset
anterior y la promoción histórica del OCSVM tras ver el test introducen sesgo de
selección; la elección actual no debe presentarse como preregistrada.

**Fuentes** (evidencia fijada al commit `bb6e91d784622aab52f8b9f579186e50484dfdf6` de
`VF-PPI-TESIS-ORQUESTACION`):
[nota L](https://github.com/marksato13/VF-PPI-TESIS-ORQUESTACION/blob/bb6e91d784622aab52f8b9f579186e50484dfdf6/04-evidencias/cyberflow/L-recalibracion-seco-sensor1-2026-09-29.md) ·
[nota M](https://github.com/marksato13/VF-PPI-TESIS-ORQUESTACION/blob/bb6e91d784622aab52f8b9f579186e50484dfdf6/04-evidencias/cyberflow/M-deteccion-kali-sensor1-2026-09-30.md) ·
[31 — ablación](https://github.com/marksato13/VF-PPI-TESIS-ORQUESTACION/blob/bb6e91d784622aab52f8b9f579186e50484dfdf6/02-metodologia/comparacion-cyberflow-suricata/31-ABLACION-RESULTADO.md) ·
[32 — resumen](https://github.com/marksato13/VF-PPI-TESIS-ORQUESTACION/blob/bb6e91d784622aab52f8b9f579186e50484dfdf6/02-metodologia/comparacion-cyberflow-suricata/32-RESUMEN-RESULTADOS.md) ·
[`../RECONCILIACION-MANIFIESTO-MOTOR.md`](../RECONCILIACION-MANIFIESTO-MOTOR.md).
