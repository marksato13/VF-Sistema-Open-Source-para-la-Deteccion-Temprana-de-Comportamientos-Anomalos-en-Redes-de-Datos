# Plan de validación de resultados

**Proyecto:** Sistema open source para la detección temprana de comportamientos anómalos en redes de datos
**Autores:** Rubén Mark Salazar Tocas · Uziel Elias Sauñe Fernandez
**Curso:** Investigación V · Sesión 02 · EP Ingeniería de Sistemas, UPeU

> **Entregable de la Sesión 02.** Este documento es el plan prospectivo de validación de resultados solicitado en esa sesión; el informe en pasado de validaciones ya ejecutadas corresponde al documento [`02-validacion-y-confiabilidad`](../02-validacion-y-confiabilidad/informe-validacion-confiabilidad.md).

El producto es un sistema desplegado que **decide y bloquea tráfico en tiempo real**, no un instrumento de medición por escalas. Por eso la confiabilidad se valida sobre las decisiones del modelo y el determinismo del sistema: no existen ítems de escala que correlacionar, así que **Alfa de Cronbach no aplica** al producto.

## 1 · Confiabilidad

| Prueba | Aplicada a | Umbral aceptable |
|---|---|---|
| **Intervalo de Wilson 95 %** ✔ | Toda proporción reportada | Se reporta **siempre**; una familia con `n < 10` no sostiene conclusión propia |
| **McNemar exacto + Holm-Bonferroni** ✔ | Comparación por pares entre modelos y entre configuraciones de variables | **p < 0,05 tras corregir.** Sin corrección, 21 comparaciones dan ≈66 % de probabilidad de un falso hallazgo |
| **Validación cruzada agrupada por episodio** | Modelo congelado OCSVM | La detección media de los pliegues debe caer **dentro del intervalo de Wilson** de la evaluación de un solo paso |
| **Bootstrap por episodio**, B = 1 000 | Umbral 1,8126087939765134 | **Coeficiente de variación < 5 %**; por encima, se reporta como banda y no como valor puntual |
| **Determinismo** | Ajuste completo del modelo | **SHA-256 idéntico** del `.joblib` en 10 ejecuciones |

*Wilson se prefiere al intervalo normal con proporciones extremas y muestras pequeñas —el caso de las familias con `n = 6`—. McNemar es la prueba pareada correcta porque ambos modelos se evalúan sobre las mismas ventanas, y la binomial exacta evita la aproximación ji² con recuentos bajos. Agrupar por episodio es obligatorio: las ventanas del mismo episodio se solapan y repartirlas al azar produciría fuga.*

## 2 · Replicabilidad

| Elemento | Dónde | |
|---|---|:---:|
| Código | GitHub, licencia **MIT** | ✔ |
| Dataset, manifiesto y **los 7 modelos candidatos** | Mismo repositorio, licencia **CC BY 4.0** | ✔ |
| Integridad | `sha256sum -c docs/dataset/SHA256SUMS` | ✔ |
| Entorno | Versiones exactas de `scikit-learn` y `numpy` en el manifiesto congelado | ✔ |
| Documentación | *Datasheet* de 11 secciones, *model card*, *system card* y diccionario de las 28 variables | ✔ |
| **Depósito citable con DOI** | Zenodo, versionado y enlazado al repositorio | pendiente |
| **Semillas y determinismo como protocolo** | Protocolo de modelado | pendiente |

**Umbral aceptable:** quien clone el repositorio debe reproducir el umbral `1,8126087939765134` **en sus 16 dígitos** y los recuentos `13/276` de falso positivo y `158/179` de detección. Cualquier desviación invalida la replicación. El criterio ya se cumple internamente: los siete modelos publicados, recargados y verificados por SHA-256, reproducen el manifiesto de forma exacta.

## 3 · Pertinencia

Es el **único eje sin evidencia** a la fecha.

| Método | Instrumento | Umbral aceptable |
|---|---|---|
| **Prueba de usabilidad** | System Usability Scale, 10 ítems, **5–8 evaluadores** con perfil de administración de redes | **SUS ≥ 68**, media de referencia de la literatura. Por debajo, se rediseña el panel antes de la defensa |
| **Tareas observadas** | 4 tareas sobre el panel: localizar una IP bloqueada, leer su expiración, distinguir alerta del modelo de alerta heurística, verificar los servicios | **Tasa de éxito ≥ 80 %** sin ayuda del observador |
| **Entrevista semiestructurada** | 2–3 interesados: asesores y responsable de red | Necesidades cubiertas y no cubiertas; evidencia cualitativa, sin umbral numérico |
| **Trazabilidad de requisitos** | Matriz de requisitos del jurado frente a la solución | **100 % de filas cerradas**: con evidencia o declaradas fuera de alcance |

*Se usa SUS y no una encuesta propia porque es un instrumento validado, con baremo publicado, aplicable con muestras pequeñas y comparable con otros estudios.*

## Cronograma

El cronograma es prospectivo y conserva el estado previsto al redactarse el plan (19 de agosto de 2026). Las actividades se marcan explícitamente como **PLANIFICADAS**; los resultados obtenidos posteriormente deben registrarse en el informe de validación, no reescribirse como si hubieran sido previstos.

| Sem. | Eje | Actividad | Producto verificable | Estado |
|:---:|---|---|---|---|
| **1** | Confiabilidad | Validación cruzada por episodio y bootstrap del umbral | Media y desviación por pliegue; banda del umbral | **PLANIFICADA** |
| **1** | Replicabilidad | Declarar semillas y determinismo | Sección en el protocolo de modelado | **PLANIFICADA** |
| **2** | Pertinencia | Diseñar instrumento y guion de tareas; reclutar evaluadores | Instrumento SUS y guion de sesión | **PLANIFICADA** |
| **2** | Replicabilidad | Depósito en Zenodo | DOI citable | **PLANIFICADA** |
| **3** | Pertinencia | Ejecutar sesiones de usabilidad y entrevistas | Puntaje SUS, tiempos y tasa de éxito | **PLANIFICADA** |
| **3** | Pertinencia | Cerrar la matriz de trazabilidad | Matriz sin filas abiertas | **PLANIFICADA** |
| **4** | Los tres | Integrar la validación al artículo y a la tesis | Sección de validación y limitaciones | **PLANIFICADA** |

El orden responde a dependencias: confiabilidad va primero porque no necesita a nadie más; pertinencia ocupa dos semanas porque depende de coordinar personas.

## Fuera del alcance de este plan

El **falso positivo operativo —25,81 % en el pase 1 y 22,97 % en el pase 2, unos 23–26 %—** sobre tráfico legítimo pesado exige recalibrar con ese tráfico como normalidad y repetir la validación: semanas. La **selección posterior del modelo** exige un protocolo nuevo con evaluación reservada. Ambas se declaran como límite, no se simulan.

> ✔ = ya ejecutado y publicado.
