# Métricas de clasificación y comparación de los siete modelos

**Fecha de reproducción:** 23 de agosto de 2026

**Protocolo:** `PM-multilayer-v2-v1`

**Modelo actualmente congelado y desplegado:** `ocsvm_scaled`

## Conclusión ejecutiva

Sí: el sistema actual usa `ocsvm_scaled`, un One-Class SVM con kernel RBF y
`nu=0.05`, precedido por `StandardScaler`. El umbral congelado es
`score_samples < 1.8126087939765134`, calibrado únicamente con las 273 ventanas
normales de `validation`.

Las métricas solicitadas sí pueden calcularse y se reprodujeron sin reentrenar
ningún modelo. Sobre el conjunto combinado de 276 ventanas normales de `test` y
179 ventanas anómalas, OCSVM obtuvo:

- **Precision:** 92,40 % — 158 verdaderos positivos entre 171 alertas;
  IC de Wilson 95 %: 87,43 %–95,50 %.
- **Recall o sensibilidad:** 88,27 % — 158/179 anomalías detectadas;
  IC de Wilson 95 %: 82,73 %–92,20 %.
- **F1-score:** **0,9029**.
- **ROC-AUC:** **0,9741**.
- **PR-AUC / Average Precision:** **0,9663**.
- **FPR offline:** 4,71 % — 13/276 ventanas normales alertadas;
  IC de Wilson 95 %: 2,77 %–7,89 %.

OCSVM ocupa el primer lugar de los siete en **precision, recall, F1, ROC-AUC y
PR-AUC**. No es una victoria basada solamente en AUC. Sin embargo, la conclusión
correcta es que constituye el mejor candidato **offline dentro de esta
comparación**, no que sea universalmente superior ni que ya sea seguro para
bloqueo automático en producción.

## 1. Qué se comparó

Se evaluaron siete configuraciones pertenecientes a cuatro familias:

| Configuración | Familia | Rol registrado originalmente |
|---|---|---|
| `if_primary_weighted` | Isolation Forest ponderado por episodio | `primary` |
| `if_uniform` | Isolation Forest uniforme | comparador/sensibilidad |
| `if_scaled_weighted` | Isolation Forest escalado y ponderado | comparador/sensibilidad |
| `if_exact_collapsed` | Isolation Forest entrenado tras colapso exacto | comparador/sensibilidad |
| `lof_scaled` | Local Outlier Factor en modo novelty | comparador |
| `ocsvm_scaled` | One-Class SVM RBF escalado | comparador; después congelado |
| `elliptic_envelope_scaled` | Elliptic Envelope escalado | comparador |

`if_uniform` e `if_exact_collapsed` produjeron el mismo archivo serializado, los
mismos scores y las mismas decisiones. Por ello existen siete configuraciones
registradas, pero esas dos no aportan comportamientos predictivos distintos.

## 2. Conjuntos y definición de las clases

La comparación usa exactamente los conjuntos congelados del manifiesto:

| Uso | Clase | Ventanas | Episodios |
|---|---:|---:|---:|
| `test` normal | Negativa = tráfico normal | 276 | 44 |
| `evaluation_only` | Positiva = anomalía | 179 | 132 |
| Total usado para estas métricas | — | 455 | 176 |

La prevalencia de la clase positiva en esta combinación es 179/455. Es una
composición experimental, no la prevalencia esperable de ataques en una red
real; por eso la precision y el F1 no deben extrapolarse directamente a
producción.

La regla aplicada a todos los modelos fue la congelada:

```text
score_samples < umbral  => anomalía
score_samples >= umbral => normal
```

Para ROC-AUC y PR-AUC se utilizó `-score_samples`, de manera que un valor mayor
represente mayor anomalía. Estas dos métricas emplean el ranking continuo y no
solo la decisión binaria del umbral.

## 3. Resultados completos

Los porcentajes se muestran con dos decimales y las métricas continuas con
cuatro. Los conteos de la siguiente sección son los valores exactos de los que
se derivan.

| Puesto por F1 | Modelo | Precision | Recall | F1 | ROC-AUC | PR-AUC (AP) | FPR test |
|---:|---|---:|---:|---:|---:|---:|---:|
| **1** | **`ocsvm_scaled`** | **92,40 %** | **88,27 %** | **0,9029** | **0,9741** | **0,9663** | **4,71 %** |
| 2 | `if_exact_collapsed` | 88,03 % | 57,54 % | 0,6959 | 0,9241 | 0,8627 | 5,07 % |
| 2 | `if_uniform` | 88,03 % | 57,54 % | 0,6959 | 0,9241 | 0,8627 | 5,07 % |
| 4 | `if_primary_weighted` | 88,99 % | 54,19 % | 0,6736 | 0,8976 | 0,8459 | 4,35 % |
| 4 | `if_scaled_weighted` | 88,99 % | 54,19 % | 0,6736 | 0,8967 | 0,8454 | 4,35 % |
| 6 | `lof_scaled` | 88,51 % | 43,02 % | 0,5789 | 0,9202 | 0,8543 | **3,62 %** |
| 7 | `elliptic_envelope_scaled` | 77,78 % | 27,37 % | 0,4050 | 0,8937 | 0,7902 | 5,07 % |

### 3.1 Matrices de confusión reproducidas

`TP` y `FN` se calculan sobre 179 anomalías; `TN` y `FP`, sobre 276 ventanas
normales de test.

| Modelo | TP | FP | TN | FN | Alertas emitidas |
|---|---:|---:|---:|---:|---:|
| **`ocsvm_scaled`** | **158** | **13** | **263** | **21** | **171** |
| `if_exact_collapsed` | 103 | 14 | 262 | 76 | 117 |
| `if_uniform` | 103 | 14 | 262 | 76 | 117 |
| `if_primary_weighted` | 97 | 12 | 264 | 82 | 109 |
| `if_scaled_weighted` | 97 | 12 | 264 | 82 | 109 |
| `lof_scaled` | 77 | 10 | 266 | 102 | 87 |
| `elliptic_envelope_scaled` | 49 | 14 | 262 | 130 | 63 |

### 3.2 Incertidumbre de las proporciones

| Modelo | Precision, IC Wilson 95 % | Recall, IC Wilson 95 % | FPR, IC Wilson 95 % |
|---|---|---|---|
| **`ocsvm_scaled`** | **92,40 % [87,43–95,50]** | **88,27 % [82,73–92,20]** | **4,71 % [2,77–7,89]** |
| `if_exact_collapsed` | 88,03 % [80,91–92,74] | 57,54 % [50,22–64,55] | 5,07 % [3,05–8,33] |
| `if_uniform` | 88,03 % [80,91–92,74] | 57,54 % [50,22–64,55] | 5,07 % [3,05–8,33] |
| `if_primary_weighted` | 88,99 % [81,74–93,59] | 54,19 % [46,88–61,32] | 4,35 % [2,50–7,44] |
| `if_scaled_weighted` | 88,99 % [81,74–93,59] | 54,19 % [46,88–61,32] | 4,35 % [2,50–7,44] |
| `lof_scaled` | 88,51 % [80,12–93,64] | 43,02 % [35,99–50,34] | 3,62 % [1,98–6,54] |
| `elliptic_envelope_scaled` | 77,78 % [66,09–86,27] | 27,37 % [21,37–34,33] | 5,07 % [3,05–8,33] |

F1, ROC-AUC y PR-AUC no son proporciones binomiales simples; por ello no se les
aplicó un intervalo de Wilson. No se presenta un intervalo bootstrap o DeLong
porque no estaba predefinido en el protocolo y calcularlo después de observar
los resultados introduciría otra decisión analítica posterior.

## 4. Por qué OCSVM resulta mejor en esta comparación

### 4.1 Contra el mejor Isolation Forest por F1

Frente a `if_uniform`/`if_exact_collapsed`, OCSVM obtiene:

- 158 TP frente a 103: **55 anomalías adicionales detectadas**;
- 13 FP frente a 14: **un falso positivo menos**;
- recall de 88,27 % frente a 57,54 %;
- F1 de 0,9029 frente a 0,6959;
- ROC-AUC de 0,9741 frente a 0,9241.

En el punto de operación congelado, OCSVM domina a esas dos variantes: detecta
más anomalías y simultáneamente genera menos falsos positivos.

### 4.2 Contra el Isolation Forest declarado `primary`

Frente a `if_primary_weighted`, OCSVM obtiene:

- 158 TP frente a 97: **61 anomalías adicionales detectadas**;
- 13 FP frente a 12: **un falso positivo adicional**;
- recall de 88,27 % frente a 54,19 %;
- F1 de 0,9029 frente a 0,6736;
- una diferencia de FPR de solo 0,36 puntos porcentuales en test.

La mejora principal no procede de unas pocas ventanas: Isolation Forest no
detectó ninguna de las 31 ventanas `ANOM-KALI-SYN-RATE-50` ni ninguna de las 40
`ANOM-KALI-UDP-PROBE-50`. OCSVM detectó 26/31 y 40/40, respectivamente.

### 4.3 El intercambio que sí existe

OCSVM no es mejor en todas las familias. Su debilidad se encuentra en eventos de
autenticación:

| Familia | OCSVM | IF `primary` |
|---|---:|---:|
| `ANOM-AUTH-FAIL-50` | 3/6 | 5/6 |
| `ANOM-KALI-PASSWORD-SPRAY-50` | 16/29 | 24/29 |
| `ANOM-KALI-SYN-RATE-50` | 26/31 | 0/31 |
| `ANOM-KALI-UDP-PROBE-50` | 40/40 | 0/40 |

LOF consigue el menor FPR offline —10 FP frente a 13 de OCSVM—, pero deja sin
detectar 102/179 anomalías. Ahorrar tres falsos positivos a cambio de perder 81
verdaderos positivos no es un intercambio conveniente para el objetivo de
detección temprana del proyecto.

## 5. Qué métricas importan para este sistema

No existe una sola métrica que decida correctamente un sistema de detección con
bloqueo inline.

| Métrica | Qué responde | Importancia aquí |
|---|---|---|
| **Recall** | ¿Cuántas anomalías reales se detectan? | Esencial para detección temprana; explica la ventaja principal de OCSVM |
| **FPR/especificidad** | ¿Cuánto tráfico legítimo se castiga? | Es una barrera de seguridad porque un FP puede bloquear un host 120 s |
| **Precision** | ¿Cuántas alertas emitidas son realmente anomalías? | Útil para credibilidad de alertas, pero cambia con la prevalencia real |
| **F1** | ¿Qué equilibrio existe entre precision y recall? | Buen resumen offline, pero no incorpora TN ni el costo especial del bloqueo falso |
| **ROC-AUC** | ¿Qué tan bien ordena anomalías frente a normales sin fijar un umbral? | Evalúa separación general; no garantiza que el umbral operativo sea seguro |
| **PR-AUC/AP** | ¿Qué tan bien mantiene precision al recuperar positivos? | Complementa ROC-AUC cuando la clase positiva es menos frecuente |

Para defender la elección, las métricas primarias deben presentarse como una
pareja: **recall alto con FPR comparable**. Precision, F1, ROC-AUC y PR-AUC
refuerzan la conclusión, pero no sustituyen la evaluación del costo operativo.

## 6. La limitación que debe decirse junto con la defensa

El OCSVM fue el mejor candidato **offline**, pero solo este modelo se desplegó en
la validación F6. Por tanto, no existe una comparación operativa equivalente de
los siete modelos.

Además, el FPR del OCSVM aumentó de 4,71 % offline a 25,81 % —16/62, IC 95 %:
16,6 %–37,9 %— en el pase 1 de F6 y a 22,97 % —17/74, IC 95 %:
14,9 %–33,7 %— en el pase 2. Una transferencia legítima `iperf-tcp 200M`
obtuvo score 1,689 y produjo un bloqueo indebido de 120 segundos.

También debe declararse `D-01`: `ocsvm_scaled` fue promovido después de observar
el mismo conjunto de evaluación usado para comparar los siete candidatos,
aunque el manifiesto reservaba el rol principal a `if_primary_weighted`. En
consecuencia, sus métricas son el máximo observado entre candidatos y constituyen
una estimación optimista hasta validarlas en un holdout temporal nuevo.

La conclusión defendible es:

> OCSVM es el mejor detector offline entre las siete configuraciones evaluadas:
> alcanza precision de 92,40 %, recall de 88,27 %, F1 de 0,9029, ROC-AUC de
> 0,9741 y PR-AUC de 0,9663, con un FPR offline comparable de 4,71 %. Su ventaja
> responde principalmente a que cubre SYN-rate y UDP-probe, dos familias con 0 %
> de detección en Isolation Forest. No obstante, la selección fue posterior a la
> evaluación y el FPR aumentó por encima de 22 % con tráfico legítimo pesado; por
> ello está justificado como modelo experimental congelado, pero el bloqueo
> automático fuera del laboratorio requiere recalibración y validación externa.

## 7. Fórmulas utilizadas

```text
Precision = TP / (TP + FP)
Recall    = TP / (TP + FN)
F1        = 2 × Precision × Recall / (Precision + Recall)
FPR       = FP / (FP + TN)
```

ROC-AUC y PR-AUC/AP se calcularon con los scores continuos, no con las etiquetas
binarias. La clase positiva fue siempre anomalía.

## 8. Trazabilidad y reproducción

Fuentes primarias:

| Artefacto | SHA-256 |
|---|---|
| `artifacts/model/manifest.json` | `0a1e8c52dc3282029d9aa1c9a0adbe7cc03c28bbce48bd5b76959e46bdbf5b1b` |
| `artifacts/dataset/multilayer-v2-normal.csv` | `3846d44c0fe32ac4b4c98f022adac7c459c6add2c6b95062e6bb3237fe9b28ab` |
| `artifacts/dataset/multilayer-v2-anomalies.csv` | `d115ef987cbd845118038314b7c55a7ad4e359ff4ebfd486c0e664ed3d8078c3` |

Hashes verificados de los modelos puntuados:

| Modelo | SHA-256 del joblib |
|---|---|
| `ocsvm_scaled` | `af9b50c29f839037b2bda380fc197e017dea482d403c61fa7ae3df79cbff7236` |
| `if_primary_weighted` | `56989fdf01c5d8976708008288ae7ea961443963033640baf20cd8017d6186ba` |
| `if_uniform` | `5c9a877d1bbfd599f60e7bb6cb10075d599da6f4d2187c57cc300e36f84fac09` |
| `if_scaled_weighted` | `37020dc7c7e7e1dfe9f89c0763452093ed00fce0be2553fbe7ea6a7575846144` |
| `if_exact_collapsed` | `5c9a877d1bbfd599f60e7bb6cb10075d599da6f4d2187c57cc300e36f84fac09` |
| `lof_scaled` | `55e9d582cb23ed40c3999f4f6632ab5ec12632a09083d8a2da43a0f157d93a3b` |
| `elliptic_envelope_scaled` | `7641e965f78f8f19446b066f604958e3cf108eec39a32d6569418efb648c131b` |

Los seis comparadores se conservan en el almacén de evidencia de VM01, no como
artefactos congelados del producto:

```text
/srv/ppi-evidence/artifacts/models/pm-multilayer-v2-v1-calibration-7models/models/
```

El cálculo es reproducible con:

```bash
.venv/bin/python scripts/analysis/compare_frozen_models_metrics.py \
  --output /tmp/seven-model-metrics.json
```

El script verifica primero los SHA-256 de datasets y modelos, reproduce los TP y
FP del manifiesto y aborta ante cualquier discrepancia. No entrena, recalibra ni
modifica los artefactos congelados.

## 9. Siguiente prueba necesaria

Para afirmar que OCSVM es también el mejor modelo operativo debe ejecutarse un
holdout temporal nuevo, con tráfico legítimo pesado y los siete modelos en modo
observación sobre exactamente las mismas ventanas. Esa prueba debe comparar al
menos recall, FPR, precision y F1 sin cambiar los umbrales después de mirar sus
resultados.
