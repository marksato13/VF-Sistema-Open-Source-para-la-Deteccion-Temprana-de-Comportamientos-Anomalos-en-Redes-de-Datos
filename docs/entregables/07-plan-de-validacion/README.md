# Plan de validación de resultados

> **Estado: redactado.** El entregable es
> [`plan-de-validacion-de-resultados.md`](plan-de-validacion-de-resultados.md) y su versión presentable
> [`Plan-de-validacion-de-resultados.docx`](Plan-de-validacion-de-resultados.docx)
> (~2 páginas, dentro del límite pedido). Este README documenta **qué pide el
> docente**, para poder auditar el entregable contra la consigna.
>
> Regenerar el Word: `python3 scripts/entregables/generar_plan_validacion_word.py`

Entregable autónomo de la **Sesión 02** del curso Investigación V
(Mg. Nemias Saboya Rios · EP Ingeniería de Sistemas · UPeU).

| | |
|---|---|
| **Momento** | Sesión 02 · Momento 6 · CREA — «Mi plan de validación de resultados» |
| **Formato** | **PDF de 1–2 páginas** |
| **Dónde se sube** | Aula virtual UPeU / sistema de control B-learning |
| **Plazo** | Antes del inicio de la **Sesión 03** |
| **Modalidad** | En equipo |

## Objetivo, en palabras del docente

> «Elaborar, en equipo, un plan de validación de los resultados para tu propia
> investigación o producto de ingeniería, especificando método para cada uno de
> los 3 ejes.»

Los tres ejes son **confiabilidad**, **replicabilidad** y **pertinencia**.

## No confundir con el informe 02

Esta es la distinción que decide si el entregable cumple o no:

| | [`02-validacion-y-confiabilidad/`](../02-validacion-y-confiabilidad/) | **Este documento** |
|---|---|---|
| Tiempo verbal | **Pasado** — qué se hizo | **Futuro** — qué se hará |
| Género | Informe de resultados | **Plan** con cronograma |
| Extensión | ~4 páginas | **1–2 páginas** |
| Pregunta que responde | ¿Qué validez tienen los resultados? | ¿Con qué método los validaré, y cuándo? |

Reutilizar el informe 02 aquí **no cumple la consigna**, aunque el tema sea el mismo.

## Los cuatro puntos obligatorios

Tomados literalmente de las instrucciones del reto autónomo:

| # | Qué pide | Qué debe quedar escrito |
|---|---|---|
| **1** | **Confiabilidad** | Qué prueba estadística se aplicará (Alfa, Kappa, test-retest u otra) **y qué umbral se considerará aceptable** |
| **2** | **Replicabilidad** | **Dónde** se publicarán datos y código, y **qué documentación del entorno** se incluirá |
| **3** | **Pertinencia** | Cómo se validará **con usuarios reales**: pruebas de usabilidad, entrevistas, trazabilidad de requisitos |
| **4** | **Cronograma** | En qué **semana** del proyecto se aplicará cada validación |

El punto 1 exige **umbral declarado de antemano**, no solo el nombre de la
prueba. Es la diferencia entre «aplicaré McNemar» y «aplicaré McNemar exacto
con corrección de Holm y consideraré significativo p < 0,05».

## Rúbrica con la que se calificará

| Criterio | Logro destacado (18–20) |
|---|---|
| Método de confiabilidad | Prueba específica y umbral **justificados con literatura** |
| Plan de replicabilidad | **Repositorio, licencia y documentación del entorno** definidos |
| Plan de validación de pertinencia | Método con usuarios reales **claramente definido y factible** |
| Coherencia con el proyecto | Los 3 ejes **adaptados específicamente** al proyecto propio, no genéricos |
| Cronograma | **Realista y ubicado en fases concretas** del proyecto |
| Redacción y formato | Clara, precisa, **cumple el formato solicitado** |

Dos criterios se pierden por descuido, no por falta de trabajo: **«adaptados
específicamente al proyecto»** —un plan genérico puntúa bajo aunque esté bien
escrito— y **«cumple el formato solicitado»**, que aquí significa no pasar de
2 páginas.

## Material disponible para cada eje

Lo que ya existe y puede citarse, frente a lo que falta:

| Eje | Ya disponible | Falta |
|---|---|---|
| **Confiabilidad** | Intervalos de Wilson 95 % en todas las proporciones · McNemar exacto con corrección de Holm sobre 21 comparaciones · ROC-AUC 0,974 · reproducción **bit a bit** del modelo congelado | Validación cruzada sobre el modelo elegido (`D-03`) · estabilidad por remuestreo (`D-05`) |
| **Replicabilidad** | Dataset, manifiesto y **7 modelos** publicados y verificables con `sha256sum -c` · licencias MIT y CC BY 4.0 · entorno con versiones exactas · [datasheet](../../dataset/DATASHEET_MULTILAYER_V2.md) | Semillas declaradas como protocolo (`D-06`) |
| **Pertinencia** | Matriz de requisitos del jurado | **Todo.** No hay ninguna validación con usuarios (`D-18`) |

> **La pertinencia es el único eje sin nada.** Es también el único criterio de
> la ficha de auditoría del docente que puntúa **0 de 3**, y no se resuelve
> escribiendo: exige personas usando el panel. La acción de menor costo es un
> instrumento **SUS con 5–8 evaluadores**.

## Trazabilidad

| Origen | Documento |
|---|---|
| Debilidades abiertas, con prioridad y esfuerzo | [`../06-plan-de-mejora/`](../06-plan-de-mejora/README.md) |
| Evidencia de confiabilidad ya producida | [`08-significancia-entre-modelos.md`](../../fase04-modelado/08-significancia-entre-modelos.md) |
| Evidencia de replicabilidad ya producida | [`DATASHEET_MULTILAYER_V2.md`](../../dataset/DATASHEET_MULTILAYER_V2.md) · [`SHA256SUMS`](../../dataset/SHA256SUMS) |
| Auditoría del producto en los mismos 3 ejes | [`../04-ficha-auditoria/`](../04-ficha-auditoria/ficha-auditoria.md) |
