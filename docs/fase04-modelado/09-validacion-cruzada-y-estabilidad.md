# Validación cruzada por episodio y estabilidad del umbral

> **Generado**: `scripts/modeling/experiments/validacion_cruzada_estabilidad.py`.

Cierra **D-03** y **D-05**. Responde a una sola pregunta: **¿cuánto de lo que se reporta depende de la partición concreta que se usó?**

---

## Protocolo

- El algoritmo **no se re-ajusta**: es el congelado, `OCSVM(rbf, gamma=scale, nu=0.05)` sobre variables estandarizadas.
- **Validación cruzada agrupada por episodio**, 5 pliegues disjuntos. Agrupar es obligatorio: las ventanas de un mismo episodio se solapan y repartirlas al azar produciría fuga.
- Dentro de cada pliegue se **replica el protocolo original**: ajustar con una parte, calibrar el umbral con otra (α = 0,05) y evaluar una vez.
- **Remuestreo bootstrap del umbral por episodio**, B = 1000. Se remuestrean episodios, no ventanas, por la misma razón.
- **Los umbrales de aceptación estaban declarados de antemano** en el plan de validación, no se fijaron al ver el resultado.
- **El modelo congelado no cambia.** Este estudio mide su sensibilidad a la partición; no lo sustituye ni recalibra su umbral.

**Verificación previa:** el modelo reajustado con la partición original reproduce el umbral congelado `1.8126087939765134`. Si no lo hiciera, el script aborta.

---

## D-03 · Validación cruzada por episodio

| Pliegue | Episodios | Ventanas | Umbral | FPR | Detección |
|---:|---:|---:|---:|---:|---:|
| 1 | 44 | 388 | 1,6252 | 4,90 % | 86,0 % |
| 2 | 44 | 234 | 1,7783 | 1,28 % | 86,6 % |
| 3 | 44 | 296 | 1,8020 | 8,78 % | 89,4 % |
| 4 | 44 | 258 | 1,6620 | 5,04 % | 78,8 % |
| 5 | 44 | 197 | 1,8528 | 9,14 % | 86,6 % |
| **Media** | | | | **5,83 %** | **85,5 %** |
| **Desviación** | | | | 3,23 | 4,0 |

**Referencia de un solo paso:** detección 88,3 % [82,7 – 92,2] · FPR 4,71 % [2,8 – 7,9].

> **✅ Cumple el umbral declarado.** La detección media de los pliegues (85,5 %) cae **dentro** del intervalo de Wilson de la evaluación de un solo paso [82,7 – 92,2]. El resultado no depende de la partición concreta que se eligió.

---

## D-05 · Estabilidad del umbral

| | |
|---|---|
| Umbral congelado | `1.8126087939765134` |
| Media del remuestreo | 1,7853 |
| Desviación típica | 0,0732 |
| **Coeficiente de variación** | **4,10 %** (máximo declarado: 5 %) |
| Intervalo percentil 95 % | [1,6496 – 1,8132] |
| **Percentil del umbral congelado** | **52,2** |

> **✅ Cumple el umbral declarado.** Con un coeficiente de variación del 4,10 %, el umbral puede reportarse como **valor puntual**. Aun así conviene acompañarlo de su banda [1,6496 – 1,8132], que es información que el manifiesto no daba.

### Dónde cae el umbral congelado dentro del remuestreo

El umbral congelado `1,8126` cae en el **percentil 52,2** de los 1000 remuestreos: prácticamente en la mediana. **No es un valor atípico ni quedó en un extremo**, que era la sospecha razonable al ver que supera a la media (1,7853).

La explicación está en la forma de la distribución, no en el umbral: el intervalo [1,6496 – 1,8132] es **asimétrico**, con una cola larga hacia abajo. La masa se concentra arriba y unos pocos remuestreos —aquellos en que el azar deja fuera los episodios de tráfico pesado— arrastran la media. Por eso la media queda por debajo de la mediana sin que el umbral sea extremo.

> **Consecuencia para el falso positivo operativo.** Esto **descarta** una hipótesis: la tasa del 23–26 % no se explica por una calibración que hubiera caído en el lado agresivo del rango plausible. El umbral es el típico de su procedimiento. La causa sigue siendo la que ya estaba documentada —el tráfico legítimo pesado está subrepresentado en el conjunto con que se calibró—, y la solución sigue siendo recalibrar incluyéndolo.

---

## Limitación

La validación cruzada reparte los **episodios normales**, pero el conjunto de anomalías es el mismo en los cinco pliegues: no hay suficientes episodios de ataque para repartirlos sin dejar familias enteras fuera de algún pliegue. Por tanto, esto mide la sensibilidad a la partición **del lado normal**, que es donde se ajusta el modelo y se calibra el umbral. La variabilidad del lado de ataque queda sin medir y se declara.
