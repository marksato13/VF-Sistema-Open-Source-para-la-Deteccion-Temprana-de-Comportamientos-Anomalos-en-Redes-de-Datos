# Consolidación del dataset v2 ampliado — normal + anomalías reales de Kali

- **Fecha:** 2026-08-15/16
- **Ejecutor:** Claude
- **Estado:** dataset consolidado y auditado, `gates.pass=true`. Modelo **NO** reentrenado todavía — ese es el siguiente paso.

## Contexto

Tras el batch de expansión N1/N2 (`179-cierre-batch-expansion-N1-N2.md`) y el nuevo mecanismo de anomalías reales desde Kali (commit `0380cc8`, 114 campañas nuevas + 6 de calibración), se reconstruyó el dataset consolidado por primera vez desde que se congeló originalmente (75 filas normales / 18 anómalas, 2026-08-14).

## Bug encontrado y corregido: `build_multilayer_v2_dataset.py` no escribía `label`

Al reconstruir, la auditoría falló (`anomaly_labels_clean: false`, 179 filas con `label=null`). Investigado: el CSV original congelado sí tenía columna `label` (`anomaly` en las 18 filas), pero `build_multilayer_v2_dataset.py` **nunca la escribe** — su lista de campos (`META`) no la incluye. El archivo original debió construirse con una variante distinta del script o post-procesamiento manual no versionado.

**Corrección:** se agregó `--label {normal,anomaly}` (default `normal`, compatible hacia atrás) a `build_multilayer_v2_dataset.py`, que ahora escribe la columna explícitamente. Verificado: con `--label normal`/`--label anomaly` la auditoría pasa limpio (`gates.pass=true`).

## Mapas de partición

Generados programáticamente a partir de los directorios reales en `features-v2/` (no de un archivo preexistente, dado el salto de 60→220 campañas normales y 12→132 de anomalías):

- **Normal**: `campaign_id → partition_by_repetition[repetición]` extraída por regex del propio `campaign_id` (`F2N-<PERFIL>-R<NN>[-<SUFIJO>]`), usando el mapeo `{"1":"train","2":"train","3":"train","4":"validation","5":"test"}` ya vigente en `configs/campaigns/multilayer-v2-normal.json`. 220/220 campañas mapeadas, 0 sin coincidencia.
- **Anomalías**: todas las `F2A-*` → `evaluation_only` (fijo). 132/132 mapeadas.

Los 2 intentos fallidos y ya reintentados (`F2A-ANOM-KALI-SYN-RATE-50-E01-B`, `F2A-ANOM-KALI-PASSWORD-SPRAY-50-E15-C`) no generaron `features-v2/`, por lo que no entran al mapa — correcto, no hay evidencia huérfana.

## Resultado

| | Antes (2026-08-14, congelado) | Ahora (consolidado) |
|---|---|---|
| Ventanas normales | 75 | **1,373** |
| Episodios normales | 50 | **220** |
| Perfiles normales distintos | 12 | **38** |
| train / validation / test | 44 / 15 / 16 | **824 / 273 / 276** |
| Ventanas anómalas | 18 | **179** |
| Episodios anómalos | 12 | **132** |
| Familias de ataque | 3 (ninguna desde Kali real) | **6 (161/179 ventanas desde Kali real, 18/179 heredadas del mecanismo anterior)** |

Hashes:
- `multilayer-v2-normal.csv`: `3846d44c0fe32ac4b4c98f022adac7c459c6add2c6b95062e6bb3237fe9b28ab`
- `multilayer-v2-anomalies.csv`: `d115ef987cbd845118038314b7c55a7ad4e359ff4ebfd486c0e664ed3d8078c3`

Los archivos anteriores (congelados desde 2026-08-14, 75/18 filas) se conservan en `artifacts/dataset/archive/` (fuera de Git, como todo `artifacts/`), no se eliminó evidencia.

## Auditoría (`audit_multilayer_v2.py`)

```
gates.pass = true
schema_complete = true | no_missing_values = true | no_episode_split = true
normal_labels_clean = true | anomaly_labels_clean = true | partition_values_valid = true
```

Hallazgos no bloqueantes (ya documentados antes, no nuevos):
- `tls_handshake_failure_ratio_60s` sigue constante (`175-limite-tls-handshake-failure-ratio.md`).
- 22 vectores de features duplicados exactos — patrón esperado con campañas de parámetros repetidos, igual que en el dataset original.

## Nota metodológica sobre las 18 filas anómalas heredadas

Las 18 ventanas del mecanismo anterior (`entity_ip=10.20.0.20`, Cliente legítimo, no Kali) se conservan en el CSV consolidado, mezcladas con las 161 nuevas de Kali real. Se recomienda que cualquier evaluación de modelo reporte **ambos** resultados por separado: el conjunto completo de 179 y el subconjunto de 161 genuinamente adversariales (filtrable por `entity_ip=10.20.0.100` o por `episode_id` que empiece con `ANOM-KALI-`), para no presentar ante el jurado una cifra de detección que mezcle procedencias de tráfico metodológicamente distintas sin aclararlo.

## Pendiente

1. Re-entrenar y comparar modelos (Isolation Forest, LOF, OCSVM) sobre el dataset ampliado, con validación leave-one-episode-out (sin la fuga de selección de features corregida el 2026-08-14).
2. Evaluar contra las 6 familias de ataque, reportando el desglose Kali-real vs. heredado.
3. Decisión pendiente sobre `tls_handshake_failure_ratio_60s`.
