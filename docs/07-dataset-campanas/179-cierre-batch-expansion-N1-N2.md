# Cierre del batch de expansión N1/N2 — 138 campañas oficiales

- **Fecha:** 2026-08-15
- **Ejecutor:** Claude, directamente sobre el laboratorio real, vía `scripts/f1/run_matrix_profile.py` en un driver secuencial (sin código nuevo en el proyecto, solo un script de orquestación temporal fuera del repo).
- **Estado:** **138/138 campañas completadas, 0 fallos, 0 reintentos necesarios.**

## Alcance

Completó las R02–R05 de los dos canarios abiertos el 2026-08-14 (`FRAG-UDP-V2`, `API-5XX-V2`) y ejecutó R01–R05 completas de los 26 perfiles nuevos diseñados en `178-plan-expansion-variantes-N1-N2.md`. 28 perfiles distintos en total en este batch (26 nuevos + 2 completados).

## Verificación independiente (no solo el exit code del script)

- **190/190 manifiestos** en `/srv/ppi-evidence/artifacts/campaigns/F2N-*` (incluye los 60 de la matriz original de 12 perfiles + los 130 de este batch) tienen `status=completed`, `evidence.complete=true` y `pcap_kernel_drops=0` — verificado leyendo cada manifiesto directamente, no solo confiando en el resumen del script.
- **190 directorios de campaña únicos** en `features-v2/` — cero duplicados de `campaign_id`.
- **Dataset congelado sin cambios**: hashes de `multilayer-v2-normal.csv` (`be8b711...41003e99e`) y `multilayer-v2-anomalies.csv` (`d8bf293...4ada761a`) idénticos antes y después del batch completo.
- **`git status` limpio** al terminar — el driver no escribió nada dentro del repositorio (vive en el scratchpad de la sesión, fuera de Git).
- **Disco**: 47 GB usados de 147 GB en el volumen de evidencia (34%), 93 GB libres.

## Resultado cuantitativo

| | Antes del batch (dataset congelado) | Ahora (capturado, sin consolidar) |
|---|---|---|
| Ventanas normales | 75 | **377** |
| Episodios | 50 | **190** |
| Perfiles distintos | 12 | **38** |

**+302 ventanas nuevas (+403%)** — más del salto proyectado en el plan (~207 ventanas estimadas; el resultado real fue mayor porque varios perfiles nuevos, sobre todo los de concurrencia HTTP y TCP a tasas altas, produjeron más de las ~1.5 ventanas/episodio asumidas en la estimación conservadora).

Todas las 377 filas tienen `eligible_training=True`.

## Lo que NO cambió todavía

- **El dataset consolidado no se reconstruyó.** `artifacts/dataset/multilayer-v2-normal.csv` sigue siendo el de 75 filas/50 episodios. Las 377 filas viven repartidas en `artifacts/features-v2/F2N-*/multilayer-v2.csv`, sin combinar.
- **Ninguna partición train/validation/test se recalculó** con los episodios nuevos.
- **El modelo no se reentrenó.**

## Siguiente paso pendiente de decisión

1. Reconstruir el dataset consolidado (`scripts/dataset/build_multilayer_v2_dataset.py`) — esto cambia los hashes de referencia usados en todo el trabajo de diagnóstico de hoy (`05-diagnostico-pipeline-multilayer-v2.md`).
2. Re-auditar (`audit_multilayer_v2.py`) el dataset ampliado — duplicados, cruces entre particiones, features constantes.
3. Re-entrenar y comparar modelos (Isolation Forest, LOF, OCSVM) sobre el dataset ampliado, siguiendo la instrucción del usuario de decidir el modelo final por desempeño empírico, no por preferencia.
