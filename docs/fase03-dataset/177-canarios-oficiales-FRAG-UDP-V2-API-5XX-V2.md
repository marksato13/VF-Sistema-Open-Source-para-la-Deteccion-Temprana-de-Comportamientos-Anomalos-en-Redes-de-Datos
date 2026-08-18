# Primeros canarios oficiales — `FRAG-UDP-V2` y `API-5XX-V2` (R01)

- **Fecha:** 2026-08-14/15
- **Ejecutor:** Claude, directamente sobre el laboratorio real (mismo patrón que la calibración `CAL-FRAG-UDP-01-R01` de hoy), siguiendo el plan documentado en `176-plan-formalizacion-v2-1.md`.
- **Estado:** ambos canarios **aceptados**, R01 completo para los dos perfiles nuevos. **R02–R05 pendientes** — no se avanza al lote completo sin revisión, siguiendo la misma convención que los 145 perfiles previos del proyecto ("siguiente autorizado: solo preflight independiente de...").

## Mecanismo usado (hallazgo importante sobre la herramienta oficial)

`scripts/f1/preflight_profile.sh` **no soporta la matriz v2** — está fijo internamente a `configs/campaigns/f1-normal-v2.json` (la matriz F1 legacy), sin flag para apuntar a `multilayer-v2-normal.json`. Confirmé que ningún archivo de preflight `F2N-*` existe en `/srv/ppi-evidence/artifacts/preflight/` — los 10 perfiles v2 anteriores nunca pasaron por este script. El mecanismo real y correcto es `scripts/f1/run_matrix_profile.py` invocado directamente con `--matrix configs/campaigns/multilayer-v2-normal.json --feature-schema configs/features/multilayer-v2.json`, que trae sus propios gates (Git limpio y sincronizado con `origin`, almacenamiento oficial montado, 70 s de quietud previa, orquestación completa vía `scripts/campaign/run-f1.sh`). No se intentó forzar `preflight_profile.sh` a soportar v2 — es un cambio de mayor alcance que no correspondía a esta tarea.

## Segundo hallazgo: tres listas blancas de escenarios distintas, no una

Al intentar ejecutar `FRAG-UDP-V2` por primera vez (intento sin sufijo, campaign_id `F2N-FRAG-UDP-V2-R01`), falló con `escenario F1 no permitido: frag-udp` — una lista blanca **separada** dentro de `scripts/campaign/run-f1.sh` (línea 18) que no se había actualizado al agregar el escenario a `run-benign.sh` (commit `3c2a1dc`, hoy) ni al agregarlo a `configs/campaigns/multilayer-v2-normal.json`. Es la tercera lista blanca de escenarios del proyecto — las otras dos (`run-benign.sh`, `scripts/f1/validate_matrix.py::ALLOWED_SCENARIOS`) ya se habían corregido antes. Corregida en el commit `1e0593c`.

El intento fallido (`F2N-FRAG-UDP-V2-R01`, sin sufijo) se rechazó **antes** de crear `campaign_dir`/PCAP — no hay evidencia real que archivar. Su ledger (`status=failed`) se conserva sin tocar, documentando el rechazo. El reintento usó `--attempt-suffix B`, la misma convención que ya usan los 10 perfiles v2 anteriores (todos sus episodios oficiales llevan sufijo `-B`).

## Resultado — `F2N-FRAG-UDP-V2-R01-B`

- `manifest.json`: `status=completed`, `evidence.complete=true`.
- PCAP: 6,584,489 bytes, 6,281 paquetes capturados = parseados (coincide exacto), cero drops de kernel, cero fallos de validación, transferencia verificada por hash.
- EVE: 11 registros, coincide exacto con el checkpoint esperado.
- Dos filas elegibles para entrenamiento (`eligible_training=True` en ambas):

| window_end_utc | fragment_ratio_10s |
|---|---|
| 2026-08-15T04:04:10Z | 0.99260628 |
| 2026-08-15T04:04:20Z | 0.99684236 |

## Resultado — `F2N-API-5XX-V2-R01-B`

- `manifest.json`: `status=completed`, `evidence.complete=true`.
- PCAP: 22,693 bytes, 200 paquetes capturados = parseados, cero drops de kernel, cero fallos de validación.
- EVE: 52 registros, coincide exacto con el checkpoint esperado.
- Una fila elegible para entrenamiento:

| window_end_utc | http_status_5xx_ratio_60s | http_error_ratio_60s |
|---|---|---|
| 2026-08-15T04:07:50Z | **0.15000000** | 0.30000000 |

Coincide exactamente con el resultado de la calibración `CAL-G7-API-5XX-R02` (`0.15`), confirmando reproducibilidad.

## Verificación de no contaminación

- Hashes del dataset ya congelado (`artifacts/dataset/multilayer-v2-normal.csv`, `-anomalies.csv`) verificados **sin cambios** — estos dos canarios generaron features en `artifacts/features-v2/F2N-FRAG-UDP-V2-R01-B/` y `artifacts/features-v2/F2N-API-5XX-V2-R01-B/`, separados del CSV consolidado. **El dataset consolidado NO se reconstruyó** — `scripts/dataset/build_multilayer_v2_dataset.py` no se ejecutó. Esa es una decisión aparte, pendiente, con implicaciones sobre las particiones train/validation/test y sobre el análisis de diagnóstico del pipeline (`docs/fase04-modelado/03-diagnostico-pipeline-multilayer-v2.md`) hecho hoy contra el CSV congelado actual.
- `configs/campaigns/multilayer-v2-normal.json` fue modificado (commit `1fcccba`) para *declarar* los dos perfiles nuevos — eso ya estaba autorizado por el plan v2.1. Ningún episodio previamente congelado se tocó.

## Pendiente explícito

1. **R02–R05 de ambos perfiles** (8 campañas más) — no autorizadas todavía, siguiendo la convención de un paso a la vez.
2. **Reconstrucción del dataset consolidado** (`build_multilayer_v2_dataset.py`) una vez completa la matriz de ambos perfiles — esto cambiará los hashes de `multilayer-v2-normal.csv` (actualmente `be8b711...41003e99e`), invalidando esa referencia usada en todo el trabajo de hoy (diagnóstico del pipeline, tests). Requiere reejecutar la auditoría y probablemente el análisis de diagnóstico del modelo contra el dataset ampliado.
3. **Re-entrenamiento/re-evaluación del modelo oficial** con las 2 (eventualmente hasta 10+) filas nuevas — el usuario indicó que la elección final de modelo se hará comparando resultados empíricos (Isolation Forest vs. LOF vs. OCSVM), no por preferencia; esto aplica también a esta decisión.
