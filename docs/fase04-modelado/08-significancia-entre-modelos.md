# Significancia estadística entre los siete modelos

> **Generado**: `scripts/modeling/experiments/significancia_modelos.py`.

Cierra **D-04**. Hasta ahora los modelos se comparaban como puntos desnudos —88,3 % frente a 57,5 %— sin decir si la diferencia es distinguible del azar.

---

## Protocolo

- **No se reentrena nada.** Se cargan los siete objetos ajustados publicados en `artifacts/model/candidates/`, **previa verificación de su SHA-256** contra el manifiesto — son *pickles*, y cargarlos ejecuta código.
- Cada modelo calibra su umbral con la misma regla sobre `validation` (α = 0,05) y **debe reproducir el manifiesto**; si no, el script aborta. Los siete lo hacen.
- **McNemar exacto** por pares sobre las mismas ventanas, en dos preguntas separadas: detección y falso positivo.
- **Corrección de Holm-Bonferroni**: son 21 comparaciones por pares. Sin corregir, la probabilidad de encontrar al menos un «hallazgo» por azar rondaría el 66 %.

---

## Los siete, ordenados por detección

| Modelo | Detección | Kali real | FPR benigno |
|---|---:|---:|---:|
| **`ocsvm_scaled`** | **158/179 = 88,3 %** | 143/161 = 88,8 % | 13/276 = 4,71 % |
| `if_exact_collapsed` | 103/179 = 57,5 % | 90/161 = 55,9 % | 14/276 = 5,07 % |
| `if_uniform` | 103/179 = 57,5 % | 90/161 = 55,9 % | 14/276 = 5,07 % |
| `if_primary_weighted` | 97/179 = 54,2 % | 85/161 = 52,8 % | 12/276 = 4,35 % |
| `if_scaled_weighted` | 97/179 = 54,2 % | 85/161 = 52,8 % | 12/276 = 4,35 % |
| `lof_scaled` | 77/179 = 43,0 % | 65/161 = 40,4 % | 10/276 = 3,62 % |
| `elliptic_envelope_scaled` | 49/179 = 27,4 % | 43/161 = 26,7 % | 14/276 = 5,07 % |

---

## Detección: ¿son distinguibles?

«Solo A» y «Solo B» son las ventanas que **solo** uno de los dos detecta. McNemar solo mira esos desacuerdos: los aciertos y fallos compartidos no informan.

| Par | Solo A | Solo B | p | Umbral Holm | |
|---|---:|---:|---:|---:|---|
| `ocsvm_scaled` vs `elliptic_envelope_scaled` | 111 | 2 | &lt; 0,001 | 0,0024 | **sí** |
| `ocsvm_scaled` vs `lof_scaled` | 81 | 0 | &lt; 0,001 | 0,0025 | **sí** |
| `ocsvm_scaled` vs `if_primary_weighted` | 75 | 14 | &lt; 0,001 | 0,0026 | **sí** |
| `ocsvm_scaled` vs `if_scaled_weighted` | 75 | 14 | &lt; 0,001 | 0,0028 | **sí** |
| `ocsvm_scaled` vs `if_exact_collapsed` | 71 | 16 | &lt; 0,001 | 0,0029 | **sí** |
| `ocsvm_scaled` vs `if_uniform` | 71 | 16 | &lt; 0,001 | 0,0031 | **sí** |
| `if_exact_collapsed` vs `elliptic_envelope_scaled` | 81 | 27 | &lt; 0,001 | 0,0033 | **sí** |
| `if_uniform` vs `elliptic_envelope_scaled` | 81 | 27 | &lt; 0,001 | 0,0036 | **sí** |
| `if_primary_weighted` vs `elliptic_envelope_scaled` | 75 | 27 | &lt; 0,001 | 0,0038 | **sí** |
| `if_scaled_weighted` vs `elliptic_envelope_scaled` | 75 | 27 | &lt; 0,001 | 0,0042 | **sí** |
| `if_exact_collapsed` vs `lof_scaled` | 35 | 9 | &lt; 0,001 | 0,0045 | **sí** |
| `if_uniform` vs `lof_scaled` | 35 | 9 | &lt; 0,001 | 0,0050 | **sí** |
| `lof_scaled` vs `elliptic_envelope_scaled` | 50 | 22 | 0,001 | 0,0056 | **sí** |
| `if_primary_weighted` vs `lof_scaled` | 29 | 9 | 0,002 | 0,0063 | **sí** |
| `if_scaled_weighted` vs `lof_scaled` | 29 | 9 | 0,002 | 0,0071 | **sí** |
| `if_exact_collapsed` vs `if_primary_weighted` | 6 | 0 | 0,031 | 0,0083 | no |
| `if_exact_collapsed` vs `if_scaled_weighted` | 6 | 0 | 0,031 | 0,0100 | no |
| `if_uniform` vs `if_primary_weighted` | 6 | 0 | 0,031 | 0,0125 | no |
| `if_uniform` vs `if_scaled_weighted` | 6 | 0 | 0,031 | 0,0167 | no |
| `if_exact_collapsed` vs `if_uniform` | 0 | 0 | 1,000 | 0,0250 | no |
| `if_primary_weighted` vs `if_scaled_weighted` | 0 | 0 | 1,000 | 0,0500 | no |

---

## Falso positivo: ¿son distinguibles?

| Par | Solo A | Solo B | p | |
|---|---:|---:|---:|---|
| `lof_scaled` vs `elliptic_envelope_scaled` | 9 | 13 | 0,523 | no |
| `if_exact_collapsed` vs `lof_scaled` | 14 | 10 | 0,541 | no |
| `if_uniform` vs `lof_scaled` | 14 | 10 | 0,541 | no |
| `ocsvm_scaled` vs `lof_scaled` | 11 | 8 | 0,648 | no |
| `if_exact_collapsed` vs `if_primary_weighted` | 8 | 6 | 0,791 | no |
| `if_exact_collapsed` vs `if_scaled_weighted` | 8 | 6 | 0,791 | no |
| `if_uniform` vs `if_primary_weighted` | 8 | 6 | 0,791 | no |
| `if_uniform` vs `if_scaled_weighted` | 8 | 6 | 0,791 | no |
| `if_primary_weighted` vs `lof_scaled` | 12 | 10 | 0,832 | no |
| `if_scaled_weighted` vs `lof_scaled` | 12 | 10 | 0,832 | no |
| `if_primary_weighted` vs `elliptic_envelope_scaled` | 12 | 14 | 0,845 | no |
| `if_scaled_weighted` vs `elliptic_envelope_scaled` | 12 | 14 | 0,845 | no |
| `ocsvm_scaled` vs `if_exact_collapsed` | 8 | 9 | 1,000 | no |
| `ocsvm_scaled` vs `if_uniform` | 8 | 9 | 1,000 | no |
| `ocsvm_scaled` vs `if_primary_weighted` | 10 | 9 | 1,000 | no |
| `ocsvm_scaled` vs `if_scaled_weighted` | 10 | 9 | 1,000 | no |
| `ocsvm_scaled` vs `elliptic_envelope_scaled` | 11 | 12 | 1,000 | no |
| `if_exact_collapsed` vs `if_uniform` | 0 | 0 | 1,000 | no |
| `if_exact_collapsed` vs `elliptic_envelope_scaled` | 12 | 12 | 1,000 | no |
| `if_uniform` vs `elliptic_envelope_scaled` | 12 | 12 | 1,000 | no |
| `if_primary_weighted` vs `if_scaled_weighted` | 0 | 0 | 1,000 | no |

---

## Qué contesta esto

### 1 · La ventaja del OCSVM en detección es real

De los 21 pares, **15 muestran diferencia significativa** en detección tras corregir por multiplicidad.

> **Las 6 comparaciones de `ocsvm_scaled` contra los otros seis son significativas, sin excepción.** Su ventaja no es un artefacto de un punto de operación afortunado ni de una comparación elegida a conveniencia.

Esto **no** contradice la advertencia de selección posterior de la model card. Son dos cosas distintas: que el OCSVM detecte más que los demás **sobre estos datos** está ahora respaldado estadísticamente; que ese 88,3 % sea su desempeño esperable **fuera** de estos datos sigue sin estarlo.

### 2 · En falso positivo, los siete son indistinguibles

**Ningún par** alcanza significancia en falso positivo tras la corrección de Holm. Con 276 ventanas benignas y recuentos de 10 a 16 alertas, la muestra no tiene resolución para separar un 3,62 % de un 5,80 %.

> **Consecuencia práctica:** afirmar que un modelo «tiene menos falsos positivos» que otro **no está respaldado por estos datos**. La comparación válida entre los siete es la de detección, no la de FPR.

### 3 · `if_uniform` e `if_exact_collapsed` no son dos modelos

Cero ventanas discordantes (0 y 0), p = 1,000. Comparten SHA-256: **son el mismo objeto ajustado**. Sus dos filas en cualquier tabla comparativa no son dos evidencias independientes, y contarlas como tales infla artificialmente el número de candidatos.

---

## Robustez al agrupamiento por episodio

McNemar supone observaciones independientes, y **las ventanas de un mismo episodio no lo son**: 47 de los 132 episodios aportan dos ventanas correlacionadas. Ignorarlo infla el tamaño muestral efectivo y hace los valores p **anticonservadores**.

Por eso el análisis se repite agregando a nivel de episodio, con dos reglas distintas:

| Unidad de análisis | Unidades | Pares significativos | De los 6 del OCSVM |
|---|---:|---:|---:|
| Ventana (análisis principal) | 179 | 15/21 | 6/6 |
| Episodio · detectado si **alguna** ventana lo detecta | 132 | 15/21 | 6/6 |
| Episodio · detectado si lo detecta **la mayoría** | 132 | 15/21 | 6/6 |

> **La conclusión no cambia bajo ninguna de las tres definiciones.** El agrupamiento es leve —el conglomerado máximo es de dos ventanas— y los efectos son grandes, así que corregir por él no altera qué pares resultan distinguibles.
>
> Se reporta igualmente porque **la objeción es metodológicamente correcta**, y responderla con una medición vale más que argumentar que el sesgo es pequeño.

---

## Limitación

Todas las comparaciones se hacen sobre los **mismos** conjuntos usados en la calibración original, así que los valores absolutos heredan el sesgo optimista declarado en la model card. Lo que estas pruebas sostienen es que **las diferencias entre modelos son reales y no ruido de muestreo** — una afirmación relativa, que es justamente la que faltaba respaldar.
