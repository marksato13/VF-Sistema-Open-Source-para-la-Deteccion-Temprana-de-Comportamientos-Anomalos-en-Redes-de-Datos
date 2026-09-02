# Informe de validación interna, validación externa y confiabilidad de los resultados

**Proyecto:** Detección temprana de comportamientos anómalos en redes de datos mediante modelos predictivos y un mecanismo de control inline
**Integrantes:** Rubén Mark Salazar Tocas · Uziel Elias Sauñe Fernandez
**Curso:** Investigación V · **Docente:** Ing. Nemias Saboya Ríos
**Fecha:** 19 de agosto de 2026

> **Este documento es el detalle, no el entregable.** Desarrolla en profundidad lo
> que el [informe de evaluación crítica](../01-evaluacion-critica/informe-evaluacion-critica.md)
> —el consolidado de 2–4 páginas— solo puede resumir. Es un informe **en pasado**
> sobre validaciones ya ejecutadas.
>
> **No es el entregable prospectivo de la Sesión 02**, que es el plan
> [`plan-de-validacion-de-resultados.md`](../07-plan-de-validacion/plan-de-validacion-de-resultados.md).
>
> **Toda cifra coincide con el consolidado.** Si alguna discrepa, manda la fuente
> primaria que se cita en cada tabla.

> Informe breve solicitado en la sesión del 12 de agosto. El análisis completo, con las 11 figuras y el detalle de cada hallazgo, está en [`01-evaluacion-critica/`](../01-evaluacion-critica/informe-evaluacion-critica.md) del repositorio del proyecto.

---

## 1. Resumen del estado

| Criterio | Estado | Síntesis |
|---|---|---|
| **Validación interna** | Parcial | Controles anti-fuga reales y verificados, pero el modelo final se eligió observando el conjunto de prueba |
| **Validación externa** | Insuficiente | Medida en operación real y refutada: el error sobre tráfico legítimo pesado es 5 veces mayor que el medido en laboratorio |
| **Confiabilidad** | Alta | Resultados reproducibles: al repetir la evaluación se obtienen las mismas cifras, con hashes y versionado que lo garantizan |

**Lectura general.** Los resultados **sí sostienen** que el sistema detecta y bloquea ataques reales en tiempo real. **No sostienen todavía** que lo haga sin penalizar tráfico legítimo intenso. La debilidad principal no está en la ingeniería del sistema, sino en el diseño estadístico de la evaluación.

---

## 2. Validación interna

*¿Los resultados obtenidos se deben realmente a lo que el estudio dice haber probado?*

> **Qué se pidió evaluar.** El grado en que el diseño garantiza que los resultados observados se deben a la variable estudiada y no a factores ajenos. En un producto de software esto significa verificar tres cosas concretas: que **no exista fuga de datos** (*data leak*), que las **condiciones de prueba estén controladas**, y que la **cantidad de experimentos sea representativa**. Se responde punto por punto a continuación.

### Abordado de manera concreta

| Aspecto | Evidencia verificable |
|---|---|
| Sin fuga de datos entre particiones | Auditoría automática: `no_episode_split = true`; ningún episodio se reparte entre entrenamiento, validación y prueba |
| Sin información futura en las variables | Prueba unitaria: un evento posterior no altera una ventana ya cerrada |
| Umbral fijado antes de ver los datos de prueba | Cuantil α = 0,05 solo sobre validación (k = 13, n = 273); el escalador se ajusta solo con entrenamiento |
| Evaluación en un solo paso, sin reentrenar | Registro sellado con hash del calibrador y del repositorio |
| Detección y corrección de una fuga propia | Un experimento con selección contaminada fue identificado y marcado como *"no debe citarse"* |

### Abordado parcialmente

- **Análisis de sensibilidad.** Se ejecutó con 10 semillas, ponderación por episodio y colapso de duplicados, **pero solo sobre los modelos descartados** (Isolation Forest). El modelo finalmente elegido no recibió ninguna prueba de estabilidad.

### No abordado

- **Selección del modelo sin contaminar la prueba.** El modelo congelado se eligió **después** de observar su desempeño en el conjunto de prueba. El propio registro del proyecto documenta que ese modelo estaba designado como "comparador" y que la política prohibía promoverlo por ganar una métrica posterior. En consecuencia, el 88,3 % de detección es el **máximo entre 7 candidatos evaluados sobre los mismos datos**, sin ningún conjunto reservado que permita una estimación sin sesgo optimista.
- **Pruebas de significancia estadística.** ✅ **Ejecutadas.** McNemar exacto por pares —la prueba correcta cuando los modelos se evalúan sobre las mismas ventanas— con corrección de Holm-Bonferroni sobre las 21 comparaciones. Las **seis del OCSVM son significativas sin excepción**; en cambio **ninguna diferencia de falso positivo lo es** (p mínimo 0,52), así que afirmar que un modelo comete menos falsos positivos que otro no está respaldado por estos datos.

---

## 3. Validación externa

*¿Los resultados se generalizan a otros contextos, poblaciones o condiciones de uso?*

> **Qué se pidió evaluar.** Si los resultados se sostienen fuera de las condiciones en que se midieron: *¿el algoritmo rinde igual sobre otro conjunto de datos?, ¿la arquitectura funciona en un entorno de producción real?* Se pidió revisar además si la **muestra es representativa**, si hay **sesgo**, y si existen problemas de **balanceo de datos o sobreajuste**. Este proyecto pudo responderlo de forma directa, porque el sistema no se quedó en laboratorio: se midió desplegado y en operación.

### Abordado de manera concreta

- **Se midió el sistema completo en operación real**, no solo el modelo en laboratorio: 2 pases de 29 corridas más 2 pruebas de aislamiento, con motor y bloqueo activos.
- **Ataques genuinos** desde una máquina atacante real (Kali) en 6 familias distintas, no simulados por inyección de datos.
- **Se declaró la procedencia heterogénea** de los datos de ataque: 161 ventanas reales y 18 heredadas de otro mecanismo, reportadas por separado (88,8 % frente a 83,3 %).

### Resultado que refuta la generalización

Es el hallazgo más importante y se reporta aunque sea desfavorable:

| Condición de medición | Falsos positivos | IC 95 % |
|---|---|---|
| Laboratorio (conjunto de prueba) | **4,71 %** (13/276) | 2,8 % – 7,9 % |
| Operación real, pase 1 | **25,81 %** (16/62) | 16,6 % – 37,9 % |
| Operación real, pase 2 | **22,97 %** (17/74) | 14,9 % – 33,7 % |

La fuente primaria registra las cifras sin redondear: **25,81 % (16/62) en el pase 1** y **22,97 % (17/74) en el pase 2**, con los intervalos indicados arriba (`docs/fase07-validacion-final/02-resultados-f6.md`). El rango aproximado 23–26 % resume ambos pases y no es un promedio.

![Falsos positivos: laboratorio frente a operación real](../graficas/C1-fpr-offline-vs-operativo.png)

Los intervalos de Wilson son **descriptivos** y las ventanas comparten episodio e historia de hasta 60 s; su no solapamiento no prueba por sí solo una diferencia inferencial independiente. Además se reprodujo **en aislamiento**: una transferencia legítima de 200 Mbit/s generó una ventana que cruzó el umbral y **bloqueó a un cliente legítimo durante 120 segundos**. Otra ventana de la misma transferencia se permitió por apenas 0,0014 puntos de score, lo que indica que el tráfico legítimo intenso cae dentro del margen de decisión del modelo.

### No abordado

- **Partición por sesiones independientes.** La división se hizo por índice de repetición (R01–R03 entrenamiento, R04 validación, R05 prueba), por lo que **los 44 perfiles de tráfico aparecen en las tres particiones**. Se mide repetibilidad del escenario, no generalización a tráfico no visto.
- **Jornada de validación temporal externa.** No existe un conjunto capturado en una fecha distinta y reservado sin participar en entrenamiento ni calibración.
- **Diversidad de escenarios.** Faltan seis escenarios legítimos previstos (SSH, SCP/SFTP, SMB, respaldo, streaming y actualizaciones) y no hay captura multi-sistema-operativo.

---

## 4. Confiabilidad

*¿Repetir el procedimiento produce los mismos resultados?*

> **Qué se pidió evaluar.** La consistencia al repetir la medición. Se señalaron varias vías según el tipo de trabajo: **Alfa de Cronbach** cuando hay instrumentos tipo cuestionario, **acuerdo inter-evaluador** cuando hay jueces, y **estabilidad del comportamiento ante entradas similares** cuando se trata de un sistema. También se pidieron técnicas cuantitativas concretas: **intervalos de confianza**, pruebas de significancia (*t*, Wilcoxon) y métricas de modelo como **F1**. Este proyecto corresponde al tercer caso —es un sistema, no un instrumento de percepción—, por lo que la confiabilidad se evidencia por reproducibilidad y estabilidad, no por Alfa.

### Abordado de manera concreta

| Aspecto | Evidencia |
|---|---|
| **Reproducibilidad verificada** | Al reevaluar el modelo congelado se obtuvieron **exactamente** las mismas cifras del registro original (13/276 y 158/179) |
| Integridad de artefactos | SHA-256 de datos, modelo y programa de calibración; repositorio verificado limpio antes y después |
| Trazabilidad | 330 registros de cambios, 181 documentos de campañas, 162 revisiones independientes |
| Estabilidad operativa | Cero caídas de servicio registradas en 58 corridas (55 verificadas), sin pérdida de paquetes en captura |
| **Determinismo del sistema** | **10 ajustes repetidos** del pipeline elegido produjeron el **mismo SHA-256 y el mismo umbral** (`1.8126087939765134`) |
| **Estabilidad del umbral** | Remuestreo bootstrap por episodio, **B = 1 000**: coeficiente de variación **4,10 %** (máximo declarado 5 %), banda percentil [1,6496 – 1,8132] |
| Consistencia entre repeticiones | Los dos pases de validación operativa dieron resultados equivalentes: **25,81 % (16/62)** en el pase 1 y **22,97 % (17/74)** en el pase 2 |

### Abordado parcialmente

- **Cuantificación de la incertidumbre.** El trabajo original no calculó ninguna medida de dispersión. **Se incorporan en este informe** intervalos de confianza de Wilson al 95 %, que revelan un problema que las cifras puntuales ocultaban:

| Cifra reportada | IC 95 % real | Lectura |
|---|---|---|
| 50 % de detección en fuerza bruta (3/6) | **18,8 % – 81,2 %** | Con n = 6 **no sostiene ninguna conclusión** |
| 55,2 % en password-spray (16/29) | 37,5 % – 71,6 % | Intervalo muy amplio, conclusión débil |
| 88,3 % de detección global (158/179) | 82,7 % – 92,2 % | Sólido |

### No abordado

- **Validación externa del umbral.** La banda de variabilidad se estimó por remuestreo sobre los mismos episodios; **no hay una jornada nueva** que confirme que el umbral sigue siendo válido en otra fecha.
- **Confiabilidad inter-evaluador.** No aplica al diseño actual, que no emplea jueces ni instrumentos de percepción.

> **Corregido el 2 de septiembre de 2026.** Hasta esta revisión este informe
> declaraba como *no abordado* que «la calibración se ejecutó una sola vez; no
> hay repeticiones independientes». **Eso dejó de ser cierto** al ejecutarse el
> análisis de estabilidad: la afirmación se sustituye por la limitación que sí
> sigue vigente, que es la ausencia de jornada externa.

---

## 4 bis. Equivalencia con los tres ejes de la Sesión 02

Este informe se organiza por los criterios de la **Sesión 01** —validez interna,
externa y confiabilidad—. La **Sesión 02** usa otro vocabulario: confiabilidad,
replicabilidad y pertinencia. **No son marcos rivales**: cubren lo mismo con
otro corte. Esta tabla evita que parezca que un documento dice algo distinto del
otro.

| Eje de la Sesión 02 | Dónde está en este informe | Estado |
|---|---|---|
| **Confiabilidad** | Sección 4 completa | **Abordado**: determinismo verificado (10 ajustes, mismo SHA-256), estabilidad del umbral por bootstrap (CV 4,10 %) y dos pases operativos equivalentes |
| **Reproducibilidad** *(mismos datos y código → mismos resultados)* | Sección 4, «Reproducibilidad verificada» | **Abordado**: al reevaluar el modelo congelado salieron exactamente las mismas cifras. Dataset, manifiesto y 7 modelos publicados con SHA-256 |
| **Replicabilidad** *(datos **nuevos**, mismo método → hallazgos consistentes)* | Sección 3, validación externa | **No abordado**: no existe jornada nueva. Es la limitación principal de este informe |
| **Pertinencia** | Sección 5, entre los pendientes | **No abordado**: el instrumento SUS está preparado, sin aplicar |

> **La distinción que más se confunde** es reproducibilidad frente a
> replicabilidad. Este proyecto tiene la primera —cualquiera descarga el
> repositorio y obtiene el mismo resultado— y **no tiene la segunda**, porque
> eso exige datos nuevos. Decirlo así evita la afirmación más común y más
> injustificada en trabajos de este tipo: «nuestros resultados son replicables».

---

## 5. Qué falta y cómo se abordará con el tiempo disponible

Ordenado por relación entre costo y beneficio. **Ninguna acción del bloque A ni B requiere capturar datos nuevos.**

| Prioridad | Acción | Corrige | Tiempo |
|---|---|---|---|
| ~~**A1**~~ | ✅ **Hecha.** Declarada en la model card, antes de cualquier métrica, y en el PPI v2. Declarar explícitamente en la tesis la selección posterior del modelo y que el 88,3 % es una estimación optimista | Validez interna | Horas |
| ~~**A2**~~ | ✅ **Hecha.** Intervalos de Wilson en toda proporción del proyecto. Incorporar los intervalos de confianza a todas las proporciones reportadas | Confiabilidad | Horas |
| ~~**A3**~~ | ✅ **Hecha.** Las familias con n ≤ 6 se reportan con su intervalo y declaración de muestra insuficiente. Sustituir las conclusiones sobre familias con n ≤ 6 por una declaración de muestra insuficiente | Confiabilidad | Horas |
| ~~**A4**~~ | ✅ **Hecha.** Ambas cifras aparecen juntas en la system card y en este informe. Reportar el error operativo (23–26 %) junto al de laboratorio (4,71 %) | Validez externa | Horas |
| ~~**A5**~~ | ✅ **Hecha.** Diccionario de las 28 variables publicado, generado desde el extractor congelado. Publicar el diccionario de fórmulas de las 14 variables nuevas | Validez de constructo | Horas |
| ~~**B1**~~ | ✅ **Ejecutada.** La expansión multicapa queda justificada (66,5 % → 88,8 %, p < 0,001), pero las 8 variables L7 nuevas **no aportan detección medible** y cuestan 5 falsos positivos | Validez de constructo | *hecho* |
| **B2** | Prueba de estabilidad por remuestreo del modelo elegido | Validez interna | Horas |
| ~~**B3**~~ | ✅ **Ejecutada.** McNemar exacto con corrección de Holm sobre 21 comparaciones | Validez interna | *hecho* |
| **C1** | Capturar una jornada nueva y reservarla como validación temporal externa | Validez externa | Días |
| **C2** | Recalibrar el umbral incluyendo tráfico legítimo intenso y repetir la validación operativa | Validez externa | 1–2 semanas |

**Compromiso realista.** Con el tiempo disponible se ejecutarán los bloques **A y B** antes de cerrar la tesis: cubren los dos requisitos formales pendientes y corrigen la principal deficiencia estadística sin requerir experimentación nueva. El bloque **C** se declarará como trabajo futuro, indicando con precisión qué quedaría por demostrar.

---

## 6. Conclusión

Los resultados sostienen una afirmación **acotada y verdadera**: se demostró la viabilidad de detectar comportamientos anómalos y ejercer control en línea en tiempo real sobre una red real, con capacidad discriminante alta (ROC-AUC = 0,974), detección del 88,8 % sobre ataques genuinos y bloqueo en una mediana de 8 segundos.

No sostienen todavía que el sistema sea apto para operación desatendida: sobre tráfico legítimo de alto volumen el error alcanza 23–26 %. Esa limitación **está medida, cuantificada y declarada**, que es la condición que la hace defendible ante una revisión por pares.

La prioridad ya no es corregir la inferencia: **quedó corregida**. Se declaró la selección posterior del modelo, toda proporción lleva su intervalo de confianza, se ejecutó la ablación por capas y se añadieron las pruebas de significancia que faltaban.

Lo que queda es de otro tipo. **La única dimensión sin ninguna evidencia es la pertinencia**: el sistema nunca se sometió a evaluación con usuarios reales. Una prueba de usabilidad con 5–8 evaluadores es la acción de menor costo con mayor efecto, porque cierra a la vez el eje de pertinencia, el criterio correspondiente de la ficha de auditoría y la debilidad registrada en el plan de mejora.

Y **la limitación principal del sistema sigue abierta**: el falso positivo sobre tráfico legítimo pesado no se corrige documentándolo, sino recalibrando el umbral con ese tráfico como normalidad y repitiendo la validación operativa.

---

## Referencias

- **Campbell, D. T., & Stanley, J. C. (1963).** *Experimental and quasi-experimental designs for research.* Rand McNally. — Marco clásico de validez interna y externa aplicado en las secciones 2 y 3.
- **Wilson, E. B. (1927).** Probable inference, the law of succession, and statistical inference. *Journal of the American Statistical Association, 22*(158), 209–212. — Método empleado para todos los intervalos de confianza de este informe.
- **Cronbach, L. J. (1951).** Coefficient alpha and the internal structure of tests. *Psychometrika, 16*(3), 297–334. — Referencia del criterio de consistencia interna, no aplicable a este producto por no emplear instrumentos psicométricos (sección 4).
- **Peng, R. D. (2011).** Reproducible research in computational science. *Science, 334*(6060), 1226–1227. — Distinción entre reproducibilidad y replicabilidad usada en la sección 4.
- **Kapoor, S., & Narayanan, A. (2023).** Leakage and the reproducibility crisis in machine-learning-based science. *Patterns, 4*(9), 100804. — Tipología de fugas de datos y del sesgo por selección de modelo sobre el conjunto de prueba, aplicada en la sección 2.
- **ISO/IEC 25010:2011.** *Systems and software engineering — SQuaRE — System and software quality models.* — Marco de calidad de producto; su correspondencia detallada se desarrolla en la ficha de auditoría del producto.
