# Diagnóstico experimental del pipeline Isolation Forest multilayer-v2

- **Fecha:** 2026-08-14
- **Autor:** Claude (implementación inicial delegada a un agente interno; revisión adversarial, corrección de un hallazgo de fuga metodológica y verificación independiente hechas por Claude).
- **Script:** `scripts/modeling/experiments/diagnose_v2_pipeline.py` (diagnóstico, no reemplaza `scripts/modeling/train_multilayer_v2.py`).
- **Salida:** `artifacts/dataset/multilayer-v2-pipeline-diagnosis.json` (gitignored, como el resto de `artifacts/`).
- **Dataset usado:** `artifacts/dataset/multilayer-v2-normal.csv` (SHA-256 `be8b711...41003e99e`) y `multilayer-v2-anomalies.csv` (SHA-256 `d8bf293...4ada761a`) — congelados, verificados sin cambios antes y después de esta tarea.

## Origen

`train_multilayer_v2.py` (modelo oficial, 28 features, `IsolationForest(n_estimators=500, contamination='auto', max_features=1.0, random_state=20260813)`) obtiene ROC-AUC≈0.6007 / AP≈0.6124 por ventana, y 0/12 por episodio. Un análisis rápido previo (Cohen's d univariante) mostró que 14 a 18 de las 28 features oficiales separan razonablemente bien normal vs. anomalía, lo que planteó la pregunta de si el techo de AUC es del *pipeline* o de la *muestra*. Esta tarea investiga esa brecha sin tocar el modelo oficial ni el dataset congelado.

## Hallazgo metodológico encontrado durante la revisión (importante)

La primera versión de este script seleccionaba las top-N features por Cohen's d calculado entre `train+validation` (normal) y **las mismas 18 ventanas de `evaluation_only`** que luego se usaban para medir ROC-AUC/AP de esa selección. Esto es fuga por selección de features: las etiquetas de las anomalías de evaluación influyeron qué features se conservan, y luego el desempeño se midió sobre esas mismas anomalías. El resultado optimista de esa primera versión (top-15 → ROC-AUC=0.7674, AP=0.8234) **no es una estimación válida de generalización** y no debe citarse.

Se corrigió agregando una validación *leave-one-episode-out* (sección `4b` del reporte): para cada uno de los 12 episodios anómalos, el ranking de Cohen's d se recalcula usando solo los otros 11 episodios, se ajusta Isolation Forest con `train`/`validation` ya congelados y ese subconjunto de features, y se evalúa únicamente contra el episodio retenido + el `test` normal completo. Los scores de las 12 particiones se agrupan (pooled) en un único ROC-AUC/AP por N. Esta es la cifra que debe citarse si se compara contra el 0.6007 oficial. La sección `4` (con fuga) se conserva en el JSON solo con fines de trazabilidad del error, marcada explícitamente con `4_WARNING_selection_bias`.

## Resultados (cifras honestas, verificadas por Claude ejecutando el script corregido)

**1) Escalado** (28 features oficiales, `max_samples='auto'`):
- Sin escalar: ROC-AUC=0.60417, AP=0.61573
- Con `StandardScaler`: ROC-AUC=0.60069, AP=0.61236 (coincide con el 0.6007 oficial, confirma que el pipeline oficial escala)

Conclusión: el escalado no explica el techo de AUC — con o sin él, el resultado es prácticamente el mismo.

**2) `max_samples`** (`'auto'`, 32, 20; escalado y sin escalar, 6 combinaciones): la mejor combinación es `scaled=False, max_samples='auto'` (ROC-AUC=0.60417), esencialmente igual al resultado base. `max_samples` no explica el techo de AUC.

**3) Redundancia entre features separables:** 14/28 features con |Cohen's d|>0.5 entre `train+validation` (normal) y evaluation_only (anomalías): `dns_nxdomain_ratio_60s`, `flow_attempt_rate_10s`, `dns_query_rate_60s`, `unique_dns_name_ratio_60s`, `mean_ip_len_10s`, `large_ip_ratio_10s`, `http_request_rate_60s`, `flow_duration_mean_30s`, `http_auth_failure_ratio_60s`, `syn_rate_10s`, `rst_ratio_10s`, `byte_rate_10s`, `packet_rate_10s`, `unique_dst_ip_ratio_30s`. De estas, 6 pares tienen |Pearson r|>0.8 (correlación calculada solo sobre `train+validation`, nunca sobre `test`), formando 1 clúster de features redundantes entre sí (probablemente las derivadas de volumen: `packet_rate_10s`/`byte_rate_10s` y afines). Esto sugiere que las 14 features separables representan menos de 14 señales verdaderamente independientes.

**4b) Top-N con validación honesta (leave-one-episode-out, 12 episodios evaluados por N):**

| N features | ROC-AUC | Average Precision |
|---|---|---|
| 5 | 0.5622 | 0.2477 |
| 10 | 0.5098 | 0.3870 |
| 15 | **0.6701** | 0.3335 |
| 28 (oficial) | 0.6215 | 0.1358 |

Conclusión honesta: reducir a las top-15 features por Cohen's d mejora el ROC-AUC de forma modesta (0.60→0.67) frente a usar las 28, **pero empeora sustancialmente la average precision** (0.61 oficial → 0.33 aquí). AP es mucho más sensible al ranking de los positivos y aquí es inestable entre folds (cada uno de los 12 episodios retenidos selecciona un subconjunto de features ligeramente distinto). **No hay una mejora clara e inequívoca por selección de features** — hay un trade-off, no una solución.

**5) Dilución por episodio** (usando el modelo top-15 de la sección 4, con el sesgo ya señalado — solo la proporción es informativa, no la tasa absoluta): de las ventanas individualmente marcadas como anómalas por ese modelo, solo 1 se pierde al promediar sus features con el resto de su episodio antes de puntuar. Esto es consistente con el mecanismo ya confirmado antes (7/18 por ventana vs. 0/12 por episodio en el modelo oficial): agregar por episodio diluye la señal de ventanas individualmente anómalas cuando comparten episodio con ventanas de cola/calma.

## Conclusión general

Ninguna de las tres hipótesis de "arreglo fácil del pipeline" (escalado, `max_samples`, selección de features) explica por sí sola el techo de AUC≈0.60 del modelo oficial. La selección de features vía Cohen's d, evaluada honestamente, da una mejora modesta e inconsistente (mejor ROC-AUC, peor AP), no una solución. Esto refuerza — no descarta — la hipótesis de que la limitación principal es la **composición de la muestra anómala**: solo 18 ventanas de 12 episodios, 3 familias de ataque tipo flood/volumen, altamente correlacionadas dentro de cada episodio. La redundancia entre features (punto 3) también sugiere que, aunque se generen las anomalías de fragmentación/TLS pendientes (Tareas 3-4 de `NEXT-TASK-FOR-CODEX.md`), el beneficio marginal de dos features más puede ser menor de lo esperado si terminan correlacionadas con las que ya existen — algo a verificar cuando esas calibraciones tengan evidencia real.

## Limitaciones de este diagnóstico

- No sustituye ni reemplaza el modelo oficial `train_multilayer_v2.py`; ningún cambio de este documento se aplicó al pipeline de producción ni a `multilayer-v2-model-report-expanded.json`.
- La validación leave-one-episode-out con solo 12 episodios sigue siendo una muestra pequeña; los intervalos de confianza no se calcularon y las cifras de AP en particular muestran alta varianza entre folds.
- La sección `4` (con fuga) se conserva en el JSON de salida únicamente por trazabilidad del error metodológico encontrado durante esta revisión — no debe citarse en ningún informe o defensa.
