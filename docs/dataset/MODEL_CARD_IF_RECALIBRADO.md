# Ficha del modelo operativo — Isolation Forest recalibrado

Estado verificado en Sensor1 el 2026-10-09; no sustituye al manifiesto ni al modelo. La [ficha OCSVM](MODEL_CARD_OCSVM.md) permanece como evidencia **histórica del laboratorio**.

| Propiedad | Estado operativo |
|---|---|
| Identificador | `if_recalibrado_2026_09` |
| Artefacto | `artifacts/preliminar/if_recalibrado_desplegable.joblib` — SHA-256 `d27f68711fcb0f6657611bd7feb17759bc4fae36b9e61fbd5ca8d1190128125a` |
| Tipo | `Pipeline` (escalador + Isolation Forest), puntúa ventanas de características crudas con `score_samples` |
| Umbral | `score_samples < -0,568892` alerta; equivalente a `decision_function < -0,068892` en el ensayo por el offset de -0,5 |
| Calibración | `alpha=0,05` en validation, sin elegir el umbral sobre test; `calibrado_en_esta_red=true` |
| Entradas | 28 variables L3/L4/L7 del esquema v2; una sin observabilidad efectiva (`tls_handshake_failure_ratio_60s`). L2 no entra al scoring de este modelo. |
| Modo | Captura pasiva SPAN en Sensor1; respuesta posterior por feed firmado y agente nftables en host protegido. No está inline en el sensor. |

**Mediciones del modelo, no del stack completo:** línea base normal elegible 337980 filas (train 204148, validation 65633, test 65421); FPR test normal 4,45 % (nota L). Sobre 78 ventanas activas de ataques Kali en la misma red, 54 detectadas = 69 % global; HTTP 27/27, escaneo 27/43 y DNS 0/8 (nota M). Cambiar el denominador o escenario cambia la estimación. No extrapolar a otras redes ni a un “zero-day” universal.

**Aporte del sistema híbrido:** la batería posterior de nueve episodios de tres familias da modelo solo 6/9, heurísticos solos 7/9, combinación 9/9. No atribuir 9/9 al Isolation Forest. Un ataque de fuerza bruta confirmado en vivo lo detectó el heurístico. Ver `orquestacion-limpio/02-metodologia/comparacion-cyberflow-suricata/31-ABLACION-RESULTADO.md` y `32-RESUMEN-RESULTADOS.md`.

**Limitaciones:** el FPR 4,45 % se midió en test normal retenido tras recalibración, no como garantía de FPR continuo; F6 histórico dio 22,97–25,81 % bajo otro modelo/escenario. El modelo solo no detectó DNS en el piloto de septiembre; las señales de capa 2 quedan fuera del scoring actual. La comparación de siete candidatos del dataset anterior y la promoción histórica de OCSVM tras ver test introducen sesgo de selección; no justificar retrospectivamente la elección actual como si hubiese sido preregistrada.

**Fuentes:** `docs/RECONCILIACION-MANIFIESTO-MOTOR.md`, evidencia L/M y `artifacts/preliminar/ensayo-if-v2.json` en Sensor1 (SHA-256 registrado en la reconciliación). Esta ficha no se genera desde el manifiesto histórico v2; no ejecutar `generar_cards.py` para producirla.
