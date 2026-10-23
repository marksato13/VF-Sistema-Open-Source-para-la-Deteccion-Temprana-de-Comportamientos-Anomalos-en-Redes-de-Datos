# Auditoría del panel (`scripts/engine/dashboard.py`) — 2026-10-23

Tras desplegar el **modelo limpio `if_limpio_2026_10`**, el panel quedó con textos del modelo
anterior (`if_recalibrado_2026_09`, contaminado). Esta auditoría lista qué está bien, qué está
obsoleto y los valores correctos. Archivo: 513 KB (servidor + HTML/JS embebido).

## Veredicto rápido

- **Sin bug funcional.** `compute_counters(...)` y `resumen_variables(...)` reciben
  `detector_modelo=args.detector_name` / `detector_name=args.detector_name` (líneas 8121, 8193,
  8289), que es el detector vivo `if_limpio_2026_10`. El valor por defecto `"ocsvm_scaled"`
  (6316, 7631, 7782) es **código muerto** (el servicio siempre pasa `--detector-name`). Los
  contadores en vivo (`alert_model`, etc.) son correctos.
- **Aplicado ya (seguro, aislado):** se añadió la etiqueta `if_limpio_2026_10: 'modelo limpio
  (IsolationForest)'` al mapa `DETECTOR_LABEL` (antes el panel mostraba el id crudo del detector
  vivo). Línea ~1560.

## Valores correctos de referencia (modelo desplegado)

| Dato | Valor correcto |
|---|---|
| Identificador | `if_limpio_2026_10` |
| Umbral (score_samples) | **−0,569397** |
| Umbral (decision_function) | **−0,069397** |
| SHA-256 del modelo | `df547da098e51171aa267c8466edc6624bc1bd5c6b602639cc00bd4711a2fd60` (abreviado `df547da0…fd60`) |
| FPR sobre test normal del sensor | **4,53 %** (65 421 ventanas) |
| Artefacto | `artifacts/preliminar/limpio-2026-10/if_limpio_2026_10_desplegable.joblib` |
| Manifiesto | `artifacts/preliminar/limpio-2026-10/manifest-if-limpio-2026-10.json` |

Predecesor (queda de **respaldo**, histórico): `if_recalibrado_2026_09`, umbral −0,568892 /
−0,068892, SHA `d27f6871…125a`. **No** se borra de la narrativa histórica; solo deja de ser el
“desplegado”.

## Textos obsoletos a actualizar (pasada coherente, con despliegue posterior)

| Línea(s) | Dice ahora | Debe decir |
|---|---|---|
| 1058, 1067 | tabla 7-modelos: “IF recalibrado (desplegado)”, FPR **4,45 %** | marcar el desplegado como **limpio**; FPR **4,53 %** (y nota: ROC/detección del predecesor, recómputo exacto pendiente) |
| 2899 | `θ = −0,568892` | `θ = −0,569397` |
| 2939 | `α=0,05 · −0,568892`, `sha256 d27f6871…` | `−0,569397`, `df547da0…fd60` |
| 3035 | `s(x) < −0,568892` | `s(x) < −0,569397` |
| 3345, 3350, 3762 | `score_samples < −0,568892` / `decision_function < −0,068892` | `−0,569397` / `−0,069397` |
| 3600 | `if_recalibrado_*.joblib` | `if_limpio_2026_10_*.joblib` |
| 3757 | “4,45 %”, “54 de 84 (64,3 %)” | FPR **4,53 %**; detección 64,3 % es del predecesor (declarar “recómputo pendiente”) |
| 3765, 3766 | `if_recalibrado_desplegable.joblib`, `manifest-if-recalibrado.json` | `if_limpio_2026_10_desplegable.joblib`, `manifest-if-limpio-2026-10.json` |

**Matices (no cambiar a ciegas):**
- La narrativa OCSVM→IF (1946, 3738, 3744, 3757, 7770) describe la **metodología** y es correcta;
  no se toca salvo la cifra de FPR.
- Las menciones a `if_recalibrado_2026_09` que hablan del **predecesor/respaldo** se conservan; solo
  se actualizan las que afirman “el desplegado”.
- Cambiar el umbral sin el SHA (o al revés) deja el panel **incoherente**: la pasada se hace
  completa, no parcial. Por eso durante la campaña solo se aplicó la etiqueta.

## Seguridad (contexto, no bloqueante)

El panel ya trae autenticación (`scripts/setup/cyberflow_usuarios.py`, scrypt + cookie HMAC, TLS)
y la regla nft que solo deja entrar a `10.10.10.30`. `subprocess.run` se usa con listas de args
(sin `shell=True`), sin `eval/exec`. No se detectaron endpoints de escritura. Sin hallazgos de
seguridad en esta pasada.

## Recomendación

Aplicar la tabla de “textos obsoletos” en **una sola pasada coherente** y **desplegar con
`desplegar_panel.py` al terminar la campaña** (reiniciar `ppi-dashboard` no afecta al motor/feed,
pero se evita durante la medición). La etiqueta del modelo limpio ya quedó aplicada.
</content>
