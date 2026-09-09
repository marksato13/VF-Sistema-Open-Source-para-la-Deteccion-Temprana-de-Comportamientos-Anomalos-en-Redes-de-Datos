# Estructura de la sección 3 — «Proposed methodology»

**6 de septiembre de 2026** · Decidida por análisis de artículos reales de
IJIES, **no por un marco metodológico importado**.

---

## Por qué no se cita CRISP-DM, DSRM ni ningún marco

Se descargaron y analizaron los cinco artículos semilla de IJIES.
**Ninguno de los cinco cita un marco metodológico.** En esta revista, la
metodología *es el pipeline descrito en orden de ejecución*.

El esqueleto que repiten:

```
3.  Proposed methodology     figura de arquitectura + párrafo de visión general
3.1   Dataset / Data collection
3.2   Data preprocessing        (3.2.1 cleaning · 3.2.2 transformation)
3.x   Feature selection
3.x   El modelo propuesto
4.x   Evaluation metrics
```

Nombres literales encontrados: `3.1 Data collection`, `3.2 Data
pre-processing`, `3.2.1 Data cleaning`, `3.4 Handling outliers using z-score`,
`3.6 Variance thresholding`, `3.11 LightGBM`, `3.12 Feature selection using
VarMiRF`, `3.3 Weight-based voting classifier`, `3.5.2 Deep autoencoder`.

El título de la sección es libre: «Proposed methodology», «The Proposed
method», o directamente el nombre de la técnica.

---

## Cuántas subsecciones: seis

| Medida sobre los 5 artículos | Resultado |
|---|---|
| Secciones de nivel 1 | 5 · 7 · 5 · 7 · 5 → **5 es la norma** |
| Subsecciones de metodología | de 3 a 12, la mayoría entre **3 y 5** |

El que llegó a `3.12` es el más difícil de leer de los cinco: convierte cada
paso del preprocesado en epígrafe propio. Seis es el equilibrio entre seguir
el estilo de la revista y no esconder lo que este trabajo tiene de distinto.

---

## Las seis subsecciones

| | Sección | Qué entra | De dónde sale |
|---|---|---|---|
| 3.1 | **Testbed and traffic generation** | 5 VM, 3 redes, generación controlada y captura | `fase00-infraestructura/`, `fase01-diseno-experimental/` |
| 3.2 | Dataset construction and labeling | 220 episodios, 1.373 ventanas, partición disjunta por episodio | `fase03-dataset/`, `dataset/DATASHEET_MULTILAYER_V2.md` |
| 3.3 | Multi-layer feature extraction | Las 28 variables L3/L4/L7, 27 observables | `fase02-features-multicapa/03-diccionario-multicapa-v2.md` |
| 3.4 | **Detection model and threshold calibration** | OCSVM `ν=0.05`, umbral `1,8126`, `α=0.05`, `k=13` | `fase04-modelado/06-modelo-final-congelado-ocsvm.md` |
| 3.5 | **Real-time engine and inline enforcement** | Motor, nftables, expiración de 120 s | `fase05-motor-tiempo-real/01-diseno-motor-tiempo-real.md` |
| 3.6 | Evaluation protocol | 58 corridas, dos pases, aislamiento | `fase07-validacion-final/02-resultados-f6.md` |

### Las tres decisiones que hay detrás

**Se fusiona el testbed con la captura** (3.1). Es un solo relato: aquí está
la red, así se genera el tráfico. Separarlos obliga al lector a saltar.

**Se fusiona el modelo con su calibración** (3.4). El umbral no se entiende
separado del modelo que lo produce.

**El motor conserva epígrafe propio** (3.5), y esto no es negociable. Es lo
único que **no tiene ninguno de los cinco artículos de IJIES**. Fusionarlo
para parecerse a ellos escondería la aportación.

Si hubiera que bajar a cinco, se fusionan 3.1 y 3.2 en «Testbed and dataset
construction». **No se baja de cinco, y 3.5 no se toca.**

---

## Dónde este trabajo se separa de los cinco, y por qué importa

Los cinco usan **datasets públicos**:

| Artículo | Datos |
|---|---|
| HIDE-6G | CICIDS2019 · NSL-KDD |
| PSO-LightBoost | KDD Cup99 · NSL-KDD · UNSW-NB15 |
| Feature Selection | NSL-KDD · UNSW-NB15 |
| Two-Stage IDS | NSL-KDD · UNSW-NB15 |
| Weight-Based Voting | KDDCUP99 · NSL-KDD · UNSW-NB15 |

Y **ninguno despliega el sistema**. «Real-time» aparece entre 1 y 5 veces por
artículo, siempre como aspiración; «deployment» solo dos veces, en uno solo.
Nadie mide en operación.

Su aportación es distinta: **dataset propio y sistema desplegado que bloquea**.
Las subsecciones 3.1, 3.2 y 3.5 existen precisamente porque ellos no las
necesitan y este trabajo sí.

---

## Cómo se redacta cada subsección

**Abrir con la figura.** Los cinco lo hacen: diagrama de arquitectura y un
párrafo que recorre el flujo de principio a fin. Es lo primero que mira un
revisor.

**Orden de ejecución, no orden lógico.** Sin marco teórico previo: de dónde
salen los datos, cómo se procesan, qué se extrae, qué modelo, cómo se evalúa.

**Cada subsección con su fórmula o su parámetro.** Ellos ponen la ecuación del
z-score y el umbral de varianza. Aquí van `ν=0.05`, umbral `1,8126`, `α=0.05`,
`k=13`, expiración de 120 s.

---

## Artículos analizados

Los cinco de IJIES (INASS), descargados y convertidos a texto el 6 de
septiembre de 2026:

| Artículo | DOI |
|---|---|
| **HIDE-6G: Advanced Intrusion Detection System for Secure 6G Network using Deep Learning** · Hema et al., Vol.17 No.5, 2024 | [`10.22266/ijies2024.1031.37`](https://doi.org/10.22266/ijies2024.1031.37) |
| **Optimizing Intrusion Detection in IoT Networks Using a Hybrid PSO-LightBoost Approach** · Praveen et al., Vol.18 No.3, 2025 | [`10.22266/ijies2025.0430.14`](https://doi.org/10.22266/ijies2025.0430.14) |
| Optimizing Feature Selection Method in Intrusion Detection System | [`10.22266/ijies2024.0630.18`](https://doi.org/10.22266/ijies2024.0630.18) |
| Efficient Two-Stage Intrusion Detection System Based on Hybrid Feature Selection | [`10.22266/ijies2025.0430.16`](https://doi.org/10.22266/ijies2025.0430.16) |
| Analysis of Weight-Based Voting Classifier for Intrusion Detection | [`10.22266/ijies2024.0430.17`](https://doi.org/10.22266/ijies2024.0430.17) |

**El más cercano en forma es HIDE-6G** (`10.22266/ijies2024.1031.37`): es el
único que numera la metodología en profundidad —`3.1 Data collection`,
`3.2 Data pre-processing`, `3.2.1 Data cleaning`, `3.2.2 Data transformation`,
`3.5.2 Deep autoencoder`— y el único cuyo modelo es un autoencoder, más
cercano al enfoque no supervisado de este trabajo que los clasificadores
supervisados de los otros cuatro.

**No es el mismo trabajo:** HIDE-6G usa CICIDS2019 y NSL-KDD, no genera datos
propios y no despliega nada. Sirve como referencia de **forma**, no de fondo.
