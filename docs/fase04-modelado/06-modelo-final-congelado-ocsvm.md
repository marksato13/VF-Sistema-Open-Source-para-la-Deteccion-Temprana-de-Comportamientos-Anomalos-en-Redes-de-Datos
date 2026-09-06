# Modelo final congelado: OCSVM

- **Fecha:** 2026-08-17
- **Estado:** **CONGELADO — confirmado por el usuario.** Cierra la fase de modelado del proyecto.

## Decisión

Modelo final: `ocsvm_scaled` — `OneClassSVM(kernel="rbf", gamma="scale", nu=0.05, cache_size=200)` sobre features estandarizadas (`StandardScaler` ajustado solo con `train`).

**Artefactos oficiales** (versionados en `artifacts/model/` y conservados también en `/srv/ppi-evidence/artifacts/models/pm-multilayer-v2-v1-calibration-7models/`):
- `models/ocsvm_scaled.joblib` — pipeline completo (scaler + detector) ya ajustado.
- `manifest.json` — hiperparámetros, hashes de datos/código/entorno, umbral, resultados de evaluación completos.
- `SHA256SUMS` — verificado íntegro.

**Umbral operativo:** `score < 1.8126` → alerta (calibrado con `alpha=0.05` sobre las 273 ventanas de `validation`, desigualdad estricta, sin empates en el punto de corte más allá de lo ya reportado en el manifiesto).

**Desempeño medido** (evaluación bloqueada, una sola vez, `test`=276 ventanas benignas nunca vistas + `evaluation_only`=179 ventanas de **9 familias**: 6 de Kali y 3 heredadas):
- FPR benigno: 4.71% (13/276)
- Detección global: 88.3% (158/179)
- Detección Kali real: 88.8% (143/161)
- Punto débil conocido y declarado: `ANOM-AUTH-FAIL-50` (50%) y `ANOM-KALI-PASSWORD-SPRAY-50` (55%) — ataques de autenticación fallida son donde OCSVM es más débil de los 7 modelos probados.

## Por qué OCSVM y no Isolation Forest

Ver `05-resultado-calibracion-multilayer-v2-v1.md` para el comparativo completo de 7 modelos. Resumen: Isolation Forest tiene un punto ciego real y medido (0% de detección en `ANOM-KALI-SYN-RATE-50` y `ANOM-KALI-UDP-PROBE-50`, 71 ventanas), que OCSVM sí resuelve (84% y 100% respectivamente). Elección hecha por desempeño empírico medido en una única evaluación bloqueada, según instrucción explícita del usuario — no es la conclusión por defecto del protocolo heredado (`PM-F1-v1` mantenía IF fijo por diseño; aquí se decidió explícitamente lo contrario, con evidencia).

## Qué significa "congelado"

- No se reentrena, ni se cambian hiperparámetros, ni se reevalúa contra `test`/`evaluation_only` sin abrir una versión nueva (`PM-multilayer-v2-v2`) con datos no observados.
- El motor de decisión en tiempo real carga directamente `models/ocsvm_scaled.joblib` — no reimplementa el modelo, no lo reentrena en producción.
- Si el motor en producción revela un problema real (falsos positivos operativos, deriva de features), la corrección es una nueva versión del protocolo con evaluación nueva, no un ajuste silencioso del `.joblib` ya congelado.

## Siguiente paso

Motor de decisión en tiempo real (VM02), reusando directamente `scripts/features/extract_multilayer_v2.py` para evitar la duplicación manual de lógica que tuvo el MVP anterior. Ver hoja de ruta completa en `04-protocolo-modelado-multilayer-v2-y-hoja-de-ruta.md`.
