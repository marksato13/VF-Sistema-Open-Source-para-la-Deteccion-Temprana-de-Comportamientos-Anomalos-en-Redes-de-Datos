# Protocolo de modelado y selección F1-v2

Fecha de congelamiento: 4 de agosto de 2026. Versión: `PM-F1-v1`. Estado: definido antes de ejecutar R04.

## Decisión ejecutiva

`IsolationForest` es el detector principal predefinido; no se lo elige comparando resultados de R04 o R05. R01–R03 ajustan exclusivamente transformaciones, modelo y parámetros. R04 calibra una sola frontera de decisión con normalidad independiente. R05 se abre una vez para estimar falsos positivos normales sin cambiar ninguna decisión.

Esta separación resuelve la contradicción histórica G5↔G6: “ajustar el modelo” y “calibrar el umbral operativo” son operaciones distintas. La frase antigua de G5 que incluía el umbral dentro de `train` queda sustituida por este protocolo antes de observar un score de R04. G6 conserva el uso que asignó originalmente a R04.

No se entrenará, calibrará ni comparará un modelo mientras R04 esté incompleta. Durante su recolección sólo se permiten los gates de integridad, captura, recursos, extracción y auditoría ya congelados.

## Datos y unidades

| Partición | Datos | Uso permitido |
|---|---|---|
| `train` | R01–R03: 87 campañas, 224 ventanas normales | ajustar preprocesamiento y detectores |
| `validation` | R04: 29 campañas normales aún no observadas | calibrar el umbral una vez, después de 29/29 |
| `test` | R05: 29 campañas normales retenidas | estimar falsos positivos una vez, después de 29/29 |
| F2 | estrés legítimo fuera de F1 | robustez benigna con modelo ya congelado |
| F3 | anomalías L3/L4/L7 | detección por técnica y capa |
| F4 | benigno + una anomalía | separación y tiempo de detección |

La campaña es la unidad independiente de diseño. Las ventanas de una campaña permanecen juntas. Se reportan resultados por ventana y por campaña porque las ventanas del mismo episodio están correlacionadas; aumentar su número no aumenta en igual medida el tamaño muestral independiente.

## Features y preprocesamiento

- Entrada principal: las catorce features de `multilayer-v1`, en el orden y dominio del esquema congelado. No hay selección automática de variables.
- Isolation Forest principal: sin `StandardScaler`. Es un ensamble de particiones aleatorias, no un método de distancia. La documentación oficial describe selección aleatoria de feature y punto de corte; el score disminuye cuando la observación es más anómala ([API oficial](https://scikit-learn.org/stable/modules/generated/sklearn.ensemble.IsolationForest.html), [artículo original](https://doi.org/10.1109/ICDM.2008.17)).
- Sensibilidad IF escalada: se repetirá con `StandardScaler` ajustado sólo en R01–R03. No reemplaza el resultado principal.
- LOF y One-Class SVM: reciben `StandardScaler` ajustado sólo en R01–R03 porque dependen de vecindades/distancias o de un kernel RBF. El scaler de scikit-learn aprende media y desviación del train y es sensible a outliers ([API oficial](https://scikit-learn.org/stable/modules/generated/sklearn.preprocessing.StandardScaler.html)).
- Ablaciones L3/L4/L7 se reportarán después como sensibilidad predefinida. No se eliminará una feature usando R04, R05, F2, F3 o F4.

## Detectores congelados

No existe una rejilla de búsqueda: el espacio de hiperparámetros es deliberadamente unitario. Con datos exclusivamente normales, escoger una configuración por recall, F1 o “menos alertas” sería imposible o favorecería al detector que acepte todo.

### Principal

```text
IsolationForest(
  n_estimators=500,
  max_samples="auto",
  contamination="auto",
  max_features=1.0,
  bootstrap=false,
  random_state=20260804,
  n_jobs=1,
  warm_start=false
)
```

Se usará `score_samples`, donde un valor menor significa mayor anomalía. No se usará el `offset_` generado por `contamination`; la documentación de scikit-learn indica que ese parámetro define su umbral interno y que `max_samples="auto"` usa `min(256, n)` ([API oficial](https://scikit-learn.org/stable/modules/generated/sklearn.ensemble.IsolationForest.html)). El umbral de este proyecto se calibra por separado en R04.

### Comparadores secundarios

1. `LocalOutlierFactor(n_neighbors=20, novelty=true, contamination="auto", n_jobs=1)` sobre datos escalados. `novelty=true` es obligatorio para puntuar observaciones nuevas y los scores de train no se interpretan como los de inferencia ([API oficial](https://scikit-learn.org/stable/modules/generated/sklearn.neighbors.LocalOutlierFactor.html)).
2. `OneClassSVM(kernel="rbf", gamma="scale", nu=0.05, cache_size=200)` sobre datos escalados ([API oficial](https://scikit-learn.org/stable/modules/generated/sklearn.svm.OneClassSVM.html)).

No se incluye `EllipticEnvelope` porque las catorce variables son una mezcla acotada, discreta y con muchos ceros, sin una hipótesis gaussiana demostrada. No se incluye autoencoder: 224 ventanas de 87 episodios no justifican esa complejidad. LOF y OCSVM no sustituyen a IF por ganar una métrica posterior; cualquier cambio de modelo principal abrirá `PM-F1-v2` y requerirá un test nuevo no observado.

## Regla de umbral R04

El operating point principal se fija en `alpha=0.05` de falsos positivos por ventana normal de validación. Es un objetivo experimental predeclarado, no un SLA de producción ni una garantía poblacional.

Aquí `n` significa explícitamente **número de ventanas elegibles R04**, no número de campañas. Para los `n` scores R04 ordenados de menor a mayor `s(1)..s(n)`:

```text
k = floor(0.05 * n)
threshold = s(k + 1)
alerta si score < threshold
```

La desigualdad es estricta: los empates en el umbral se consideran normales y hacen la regla conservadora. Así, el número observado de alertas de calibración es como máximo `k`. Si `n < 20`, `k=0`; se conserva la regla, se reporta resolución insuficiente y no se cambia `alpha`. Cada detector secundario calibra su propio umbral con exactamente la misma regla.

El informe debe declarar además cuántas campañas distintas originan (a) las primeras `k` posiciones de la cola y (b) las alertas estrictas. Si la cola procede de una o dos campañas, el umbral no cambia post hoc, pero queda marcado como sensible al agrupamiento. Se calibra por ventana porque esa fue la unidad primaria congelada; la incidencia `campañas con ≥1 alerta / 29` se reporta por separado y no se presenta como controlada al 5 %. Como diagnóstico previo sin usar validation, `verify_if_weighting.py` aplicó la misma cola a train: `k=11` procedió de ocho campañas en las seeds `20260804` y `7`, y de ocho campañas en el prefijo/siete entre las alertas estrictas para seed `42`; esto no predice R04.

Este cuantil empírico no se presentará como garantía conformal. Las ventanas se solapan y no son intercambiables; incluso la literatura de inferencia conformal advierte que la dependencia temporal viola esa hipótesis ([Barber y Pananjady, PMLR 2026](https://proceedings.mlr.press/v313/barber26a.html)). Se reportará siempre `n`, `k`, umbral, empates y FPR observado.

## Tres ramas de train

1. **Principal por ventana:** conserva las 224 filas, cada una con peso uno.
2. **Sensibilidad por campaña:** no usa `sample_weight` sin verificar su efecto. `scripts/analysis/verify_if_weighting.py` audita primero las 87 celdas train y reproduce la comparación. Con scikit-learn 1.9.0, CPython 3.14.4 y los 224 vectores actuales, pesos `1/n_filas_campaña` produjeron exactamente los mismos scores y estructuras de árboles que pesos uniformes en las semillas `20260804`, `7` y `42`. `tests/test_if_weighting_verification.py` prueba ponderación, expansión, unidad del cuantil y empates. La firma de la API no basta aunque el código oficial pase el argumento al ensamble ([fuente oficial 1.9.0](https://github.com/scikit-learn/scikit-learn/blob/1.9.0/sklearn/ensemble/_iforest.py)).
3. **Sensibilidad a vectores exactos:** colapsa sólo en train cada vector canónico de catorce valores y conserva el primer representante según matriz, repetición, campaña y ventana. No cambia el dataset fuente.

La rama por campaña usará expansión determinista. En train los episodios emiten `1, 2, 3, 4, 6 o 7` filas; su mínimo común múltiplo es 84. Cada fila de una campaña de `m` filas se replica `84/m` veces, de modo que las 87 campañas aportan 84 registros y la matriz expandida contiene 7,308. Este mecanismo es sólo análisis de sensibilidad: se declarará que la duplicación cambia la multiplicidad observada por los árboles.

Las tres ramas usan los mismos parámetros, seed y datos permitidos. La rama principal sigue siendo la conclusión primaria aunque otra rama mejore una métrica.

## Repetibilidad y estabilidad

- Resultado principal: seed única `20260804`.
- Sensibilidad estocástica: seeds consecutivas `20260804..20260813`; se reportan mediana, mínimo y máximo, sin escoger la mejor.
- `n_jobs=1` para el ajuste de referencia.
- El modelo registra hashes del dataset, matriz, esquema, código y requisitos, además de versiones, parámetros, seed, orden de features, scaler, score y umbral.
- Los artefactos serializados sólo se cargan con el mismo entorno. scikit-learn no admite como contrato cargar modelos entre versiones distintas y recomienda iguales paquetes/versiones ([persistencia oficial](https://scikit-learn.org/stable/model_persistence.html)).

Con 224 filas y `max_samples="auto"`, cada árbol principal recibe las 224 porque `min(256, 224)=224`; la diversidad procede de features y cortes aleatorios, no del submuestreo de filas. Esta propiedad cambia en la expansión de sensibilidad de 7,308 filas, donde cada árbol toma 256.

El entorno de VM01 queda fijado en `requirements-model.txt`: CPython 3.14.4, scikit-learn 1.9.0, NumPy 2.5.1, SciPy 1.18.0, joblib 1.5.3, threadpoolctl 3.6.0 y Narwhals 2.24.0. PyPI declara scikit-learn 1.9.0 compatible con Python 3.11 o superior y clasifica Python 3.14 ([PyPI oficial](https://pypi.org/project/scikit-learn/1.9.0/)).

## Evaluación bloqueada

### Al cerrar R04

Se ajusta cada pipeline desde cero con R01–R03, se generan todos los scores R04 y se fija el umbral. Se escriben hashes antes de inspeccionar ejemplos extremos. No se modifica ninguna feature, parámetro, seed, peso, orden, modelo ni `alpha` a partir de esos scores.

### Al cerrar R05

Se puntúa R05 una sola vez. Se reportan:

- alertas/ventanas y FPR por ventana;
- campañas con al menos una alerta sobre 29;
- distribución de alertas por perfil y estrato;
- resultados principal, por campaña y colapsado;
- campañas distintas que originaron la cola de calibración y sus alertas estrictas;
- vectores vistos/no vistos con igualdad decimal exacta;
- intervalo por bootstrap de campañas, 10,000 remuestras, seed `20260804`, presentado como incertidumbre descriptiva debido a sólo 29 episodios.

No se abre R05 parcialmente para depurar el modelo. Un error de software que invalide la evaluación se conserva como intento fallido; después de corregirlo se necesita una partición de test nueva, no reutilizar R05 como si siguiera sellada.

### F2, F3 y F4

Con el modelo y umbral congelados, F2 reporta FPR benigno de estrés. F3 reporta detección por campaña, por ventana, por capa y tiempo hasta primera alerta. F4 añade precisión, recall, F1 y curvas PR/ROC sólo cuando existan ventanas benignas y anómalas etiquetadas de forma correlacionable. Las métricas se agrupan por campaña; no se usa una división aleatoria de ventanas.

F3/F4 son evaluación, no una nueva validación oculta. Si sus resultados motivan cambiar features, modelo o umbral, el producto se versiona y se recolecta un conjunto final no observado para esa nueva versión.

## Gates de ejecución

R04 puede comenzar sólo si:

1. este documento y su revisión adversarial están publicados;
2. `requirements-model.txt` instala y las versiones coinciden;
3. pasan las pruebas existentes y el escaneo de secretos;
4. el preflight individual vigente vuelve a pasar justo antes de la campaña.

R05 requiere además R04 29/29, calibración atómica reproducible, artefactos con hashes y declaración explícita de congelamiento. Ningún resultado de detección se declara antes de F3/F4.
