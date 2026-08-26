# Model card — OCSVM `multilayer-v2`

> **Generada**, no redactada a mano: `scripts/entregables/generar_cards.py`, desde `artifacts/model/manifest.json`.

Responde por **el modelo**. Los datos están en [`DATASHEET_MULTILAYER_V2.md`](DATASHEET_MULTILAYER_V2.md) y el sistema desplegado en [`SYSTEM_CARD_MOTOR.md`](SYSTEM_CARD_MOTOR.md).

---

## 1 · Detalles del modelo

| | |
|---|---|
| **Algoritmo** | One-Class SVM sobre variables estandarizadas |
| **Identificador** | `ocsvm_scaled` |
| **Hiperparámetro** | `nu = 0.05` |
| **Umbral de decisión** | `score < 1.8126087940` → `ALERT` |
| **Criterio de calibración** | Cuantil con `alpha = 0.05`, fijado **solo** sobre `validation` |
| **Entradas** | 28 variables, orden fijado por contrato |
| **Protocolo** | `PM-multilayer-v2-v1` |
| **Entorno** | scikit-learn 1.9.0 · numpy 2.5.1 |
| **Congelado el** | 2026-08-17 · commit `9467066a8d85` |
| **SHA-256** | `af9b50c29f839037b2bda380fc197e017dea482d403c61fa7ae3df79cbff7236` |

El escalador y el modelo se ajustaron **solo con `train`**; el umbral se calibró una única vez con `validation`; `test` y las anomalías se puntuaron una sola vez.

---

## 2 · Uso previsto

**Previsto.** Marcar como anómala una ventana de 10 s de comportamiento de una IP iniciadora, dentro del laboratorio para el que se calibró, como componente del motor de decisión documentado en la system card.

**No previsto.** Desplegarlo en una red de producción sin recalibrar; usarlo sobre tráfico de otra topología, otro conjunto de servicios u otra distribución de carga; o interpretar sus métricas como desempeño esperado fuera del laboratorio.

**Fuera de alcance.** No identifica el tipo de ataque, no atribuye intención y no sustituye a un IDS por firmas. Decide una sola cosa: si el comportamiento de esa IP en esa ventana se parece o no a la normalidad aprendida.

---

## 3 · La advertencia que va antes de cualquier métrica

> **El modelo se eligió después de observar el conjunto de prueba.**

El propio manifiesto registra la política que lo prohibía:

> «if_primary_weighted es la conclusion principal; LOF/OCSVM y las demas ramas IF son comparadores/sensibilidad y no lo reemplazan por ganar una metrica posterior en test o evaluation_only.»

`ocsvm_scaled` figura ahí como **comparador**, no como conclusión. Fue promovido por ganar la comparación posterior, que es exactamente lo que esa política impedía.

**Consecuencia, sin rodeos:** las cifras de abajo son el **máximo sobre siete candidatos** evaluados en los mismos conjuntos, sin datos reservados. Son una estimación **optimista**, no insesgada. La corrección real —un protocolo nuevo con criterio fijado de antemano y una evaluación no observada— es trabajo pendiente.

---

## 4 · Métricas

Punto de operación único, evaluación bloqueada de un solo paso. Intervalos de Wilson al 95 %.

| Métrica | Valor | IC 95 % | Base |
|---|---|---|---|
| Detección global | **88,3 %** | [82,7 – 92,2] | 158/179 ventanas |
| Detección · ataques genuinos (Kali) | **88,8 %** | [83,0 – 92,8] | 143/161 ventanas |
| Detección · ventanas heredadas | **83,3 %** | [60,8 – 94,2] | 15/18 ventanas |
| **Falso positivo** (`test` benigno) | **4,71 %** | [2,8 – 7,9] | 13/276 ventanas |
| Episodios de ataque alcanzados | 119/132 | — | episodios |

**ROC-AUC = 0,974**, calculada re-puntuando el modelo congelado. Hereda el mismo sesgo optimista de la sección 3: se apoya en los conjuntos usados para seleccionarlo.

> **Las ventanas heredadas se reportan aparte a propósito.** No son ataques genuinos, sino tráfico del cliente legítimo reetiquetado en una generación anterior. La cifra que debe citarse es la de **Kali real**.

---

## 5 · Desempeño por familia

| Familia | Detección | IC 95 % | |
|---|---|---|---|
| NXDOMAIN (heredada) | 6/6 = **100 %** | [61 – 100] | ✅ |
| Entropía DNS | 21/21 = **100 %** | [85 – 100] | ✅ |
| Escaneo de puertos | 20/20 = **100 %** | [84 – 100] | ✅ |
| Escaneo amplio 1–1000 | 20/20 = **100 %** | [84 – 100] | ✅ |
| Sondeo UDP | 40/40 = **100 %** | [91 – 100] | ✅ |
| SYN rechazados (heredada) | 6/6 = **100 %** | [61 – 100] | ✅ |
| Ráfaga de SYN | 26/31 = **84 %** | [67 – 93] | ⚠️ |
| Rociado de contraseñas | 16/29 = **55 %** | [38 – 72] | 🔴 |
| Fallo de autenticación (heredada) | 3/6 = **50 %** | [19 – 81] | 🔴 |

**El punto ciego está declarado:** las familias de **fallo de autenticación** son las peores. Tiene explicación estructural — un rociado de contraseñas genera poco volumen y su firma vive en la capa 7, no en el caudal de paquetes. Por eso el motor añade un detector heurístico L7 específico (ver system card).

> **Cuidado con los intervalos.** 3 familias tienen `n = 6`. En `ANOM-AUTH-FAIL-50` el «50 %» es literalmente **3 de 6**, con un intervalo de **19 % a 81 %**. No sostiene ninguna conclusión por sí solo.

---

## 6 · Comparación de los siete candidatos

Todos evaluados sobre los mismos conjuntos, con el mismo criterio de umbral.

| Modelo | FPR benigno | Detección global | Detección Kali |
|---|---:|---:|---:|
| **`ocsvm_scaled`** | 4.71 % | **88.3 %** | 88.8 % |
| `if_exact_collapsed` | 5.07 % | 57.5 % | 55.9 % |
| `if_uniform` | 5.07 % | 57.5 % | 55.9 % |
| `if_primary_weighted` | 4.35 % | 54.2 % | 52.8 % |
| `if_scaled_weighted` | 4.35 % | 54.2 % | 52.8 % |
| `lof_scaled` | 3.62 % | 43.0 % | 40.4 % |
| `elliptic_envelope_scaled` | 5.07 % | 27.4 % | 26.7 % |

**Por qué OCSVM y no Isolation Forest.** No por regla general, sino por puntos ciegos medidos: las ramas de Isolation Forest detectan **0 de 31** ventanas de ráfaga SYN y **0 de 40** de sondeo UDP. OCSVM resuelve ambas. A cambio, IF acierta el 100 % en las familias de autenticación donde OCSVM falla. **No hay un ganador limpio: hay un intercambio**, y se eligió el lado que cubre los ataques de mayor volumen.

> `if_uniform` e `if_exact_collapsed` comparten SHA-256: son **el mismo objeto ajustado**. Sus dos filas no son dos evidencias independientes.

Los siete objetos ajustados se publican en `artifacts/model/candidates/`, verificables con `sha256sum -c docs/dataset/SHA256SUMS`.

---

## 7 · Limitaciones

| # | Limitación |
|---|---|
| 1 | **Selección posterior sobre el conjunto de prueba** (sección 3). Es la limitación principal. |
| 2 | **El falso positivo de 4.71 % no se sostiene en operación**: F6 midió 23–26 % sobre tráfico legítimo pesado. Ver system card. |
| 3 | **Sin validación cruzada** sobre este modelo; la que existe es de un pipeline descartado. |
| 4 | **Sin análisis de estabilidad** del OCSVM: las diez semillas registradas cubren Isolation Forest, no el modelo elegido. El umbral 1,8126 se reporta sin banda de variabilidad. |
| 5 | **Ajustado sin ponderación** pese a que 5 de 132 episodios concentran el 31,7 % de las filas de entrenamiento, y los cinco son transferencias lentas de 1 GB. |
| 6 | **La significancia entre modelos ya está medida**: las 6 comparaciones del OCSVM son significativas tras Holm, pero **ninguna diferencia de falso positivo lo es**. Ver [`08-significancia-entre-modelos.md`](../fase04-modelado/08-significancia-entre-modelos.md). |
| 7 | **La ablación por capas ya está ejecutada** y matiza este contrato: la expansión multicapa es significativa (p < 0,001), pero las 8 variables L7 nuevas **no aportan detección medible y cuestan 5 falsos positivos**. Ver [`07-ablacion-multicapa.md`](../fase04-modelado/07-ablacion-multicapa.md). |
| 8 | **Un solo punto de operación.** No hay segundo umbral, así que la respuesta es binaria: permitir o bloquear. |

---

## 8 · Recomendaciones para quien lo reutilice

- **Recalibra el umbral** con tráfico propio antes de cualquier despliegue. El valor 1,8126 es específico de esta red y esta carga.
- **Cita la detección sobre Kali real**, no la global.
- **Acompaña toda proporción de su intervalo**; con `n = 6` los puntos engañan.
- **Verifica el SHA-256 antes de cargar el `.joblib`**: es un *pickle* y cargarlo ejecuta código.
- **No lo uses como única defensa.** Es un detector de comportamiento, complementario a un IDS por firmas.
