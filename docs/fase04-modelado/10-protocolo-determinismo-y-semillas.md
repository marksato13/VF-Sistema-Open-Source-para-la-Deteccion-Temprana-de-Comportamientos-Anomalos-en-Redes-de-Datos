# Protocolo de determinismo y semillas

Cierra **D-06**. Hasta ahora el proyecto registraba diez semillas, pero **no
declaraba qué componentes son estocásticos, cuáles no, ni cómo se comprueba**.
Sin esa declaración, «el modelo es determinista» es una afirmación sin respaldo.

## Qué es aleatorio y qué no

| Componente | ¿Estocástico? | Cómo se controla |
|---|---|---|
| `StandardScaler` | **No** | Media y desviación son funciones deterministas de los datos |
| `OneClassSVM` (RBF, `nu=0.05`) | **No** | Optimización convexa resuelta por libsvm; **no acepta `random_state` porque no lo necesita** |
| Cálculo del umbral (cuantil con α) | **No** | Ordenación y selección del índice `⌊α·n⌋` |
| `IsolationForest` (comparadores) | **Sí** | `random_state = 20260817` |
| `LocalOutlierFactor`, `EllipticEnvelope` | **No** en su ajuste | Sin componente aleatoria en la configuración usada |
| Validación cruzada y remuestreo | **Sí** | Semilla `20260826`, fijada en el propio script |

> **El modelo congelado no lleva semilla porque no la admite.** Que un OCSVM no
> exponga `random_state` no es un descuido del protocolo: es que su ajuste no
> tiene componente aleatoria. Fijar una semilla ahí habría dado una falsa
> sensación de control.

## Semillas registradas

Las diez del manifiesto —`20260817` a `20260826`— se usaron para el **análisis
de estabilidad de Isolation Forest**, que es el único de los siete candidatos
con componente aleatoria en su ajuste.

**Se declara explícitamente que no cubren al modelo congelado**, porque este no
las admite. La robustez del OCSVM frente a la partición se midió por otra vía:
validación cruzada agrupada por episodio y remuestreo del umbral, en
[`09-validacion-cruzada-y-estabilidad.md`](09-validacion-cruzada-y-estabilidad.md).

## Verificación, no afirmación

El umbral de aceptación estaba declarado de antemano en el plan de validación:
**SHA-256 idéntico del objeto ajustado en 10 ejecuciones repetidas**.

Se ejecuta con:

```bash
python3 scripts/modeling/experiments/verificar_determinismo.py
```

### Resultado

| | |
|---|---|
| Ejecuciones | 10 |
| **SHA-256 distintos del objeto ajustado** | **1** |
| **Umbrales distintos** | **1** |
| Umbral obtenido | `1.8126087939765134` |
| ¿Coincide con el manifiesto congelado? | **Sí**, en sus 16 dígitos |

**✅ Cumple el umbral declarado.** Diez ajustes independientes producen el
mismo objeto byte a byte y el mismo umbral.

## Qué NO garantiza este resultado

Tres límites que conviene declarar antes de que los señale otro:

**El determinismo es dentro del mismo entorno.** Se verificó con
`scikit-learn 1.9.0` y `numpy 2.5.1`, las versiones fijadas en el manifiesto.
Otra versión de BLAS o de la biblioteca puede alterar el último bit de una
operación en punto flotante y, con ello, el hash.

**Los bytes del archivo publicado pueden diferir del objeto reajustado.**
`artifacts/model/candidates/ocsvm_scaled.joblib` se serializó con parámetros de
compresión distintos, así que su SHA-256 no coincide con el del objeto recién
ajustado en memoria. Lo que sí coincide —y es lo que importa— es **el
comportamiento**: ambos producen el mismo umbral y los mismos recuentos
`13/276` y `158/179`.

**Determinismo no es estabilidad.** Que el mismo dato produzca siempre el mismo
modelo no dice nada sobre qué pasaría con datos ligeramente distintos. Esa es
otra pregunta, y tiene su propia medición en el documento 09.

## Regla para el futuro

Todo experimento que introduzca aleatoriedad **fija su semilla en el propio
script y la registra en su artefacto de salida**. Los tres experimentos
recientes lo cumplen: la ablación no usa aleatoriedad, la significancia
tampoco, y la validación cruzada y el remuestreo declaran `SEMILLA = 20260826`
en el encabezado del script y en el JSON de resultados.
