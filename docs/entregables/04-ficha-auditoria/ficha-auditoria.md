# Ficha de auditoría del producto de ingeniería validado

**Proyecto:** Detección temprana de comportamientos anómalos en redes de datos mediante modelos predictivos y un mecanismo de control inline
**Producto auditado:** Sistema de detección de anomalías de red con control inline, desplegado en laboratorio virtualizado (VM02)
**Integrantes:** Rubén Mark Salazar Tocas · Uziel Elias Sauñe Fernandez
**Curso:** Investigación V · **Docente:** Ing. Nemias Saboya Ríos
**Fecha:** 19 de agosto de 2026

> **Nota sobre la rúbrica.** La escala y los ítems que siguen son una reconstrucción razonada del ejercicio propuesto (Momento 5), porque no se dispuso del formato exacto de la ficha proyectada en clase. La estructura de tres dimensiones —confiabilidad, replicabilidad y pertinencia— y el cálculo de puntaje final sí corresponden a la consigna. Si el formato oficial difiere, los puntajes por ítem se trasladan sin recalcular la evidencia.

---

## Procedimiento seguido

La consigna planteaba seis pasos. Se dejan explícitos para que pueda verificarse que se siguieron y no solo que se entregó la ficha:

- **Paso 1 — Conformación del equipo.** Rubén Mark Salazar Tocas y Uziel Elias Sauñe Fernandez, los mismos integrantes del proyecto auditado.
- **Paso 2 — Análisis del producto validado.** Se auditó el sistema **realmente desplegado** en VM02, no su especificación: motor de decisión, mecanismo de bloqueo y panel de observación, en el estado en que quedaron tras la validación operativa.
- **Paso 3 — Evidencia de confiabilidad.** Se revisaron las tres vías nombradas (Alfa, Kappa, validación cruzada) y las que corresponden a un sistema de software. → *Sección 1*
- **Paso 4 — Evidencia de replicabilidad.** Se comprobó, ejecutando y no solo leyendo documentación, qué está publicado y qué no: código, datos y entorno. → *Sección 2*
- **Paso 5 — Evidencia de pertinencia.** Se contrastó el producto con el problema declarado y con los requisitos comprometidos. → *Sección 3*
- **Paso 6 — Diligenciamiento y cálculo.** Puntuación ítem por ítem, subtotales por dimensión y puntaje final. → *Secciones 4 y 5*

## Cómo se realizó la auditoría

Para que la ficha sea verificable y no una autoevaluación complaciente, se fijó de antemano qué se aceptaría como evidencia:

- **Solo cuenta lo que puede comprobar un tercero.** Una afirmación documentada pero no ejecutada se puntúa como *declarada*, nunca como *completa*.
- **Se verificó ejecutando, no leyendo.** La reproducibilidad (ítem 1.4) se comprobó volviendo a evaluar el modelo congelado sobre los mismos conjuntos; la disponibilidad de datos (ítem 2.2), inspeccionando qué excluye realmente el repositorio y cuánto ocupa cada artefacto.
- **Las cifras del proyecto no se transcriben a mano.** Se leen del manifiesto de calibración y de los registros de la validación operativa.
- **Lo ausente se puntúa como ausente.** No se compensa una carencia con una fortaleza de otra dimensión: cada ítem se juzga por sí mismo.
- **Lo que no aplica se excluye del cálculo**, en vez de puntuarse con cero. Un criterio que no corresponde al tipo de producto no debe penalizar el resultado (ver escala).

## Escala de valoración

| Puntos | Nivel | Significado |
|---|---|---|
| **3** | Completo | Existe y es verificable por un tercero |
| **2** | Parcial | Existe pero con limitaciones declaradas |
| **1** | Insuficiente | Solo declarado, sin evidencia sólida |
| **0** | Ausente | No se abordó |
| **N/A** | No aplica | El criterio no corresponde al tipo de producto (se excluye del cálculo) |

---

## Ficha de auditoría de validación — esquema del curso

Los seis criterios sobre 20 puntos de la Sesión 02. Las secciones 1 a 3 los
sustentan con 18 ítems sobre 51 puntos.

| Criterio | Evidencia encontrada | Puntaje |
|---|---|:---:|
| Confiabilidad estadística reportada | Intervalos de Wilson 95 %, McNemar exacto con corrección de Holm sobre 21 comparaciones, ROC-AUC 0,974 y **validación cruzada agrupada por episodio**. **Alfa no aplica** (no hay escalas); **Kappa no aplica** (no hay jueces) | **4 / 4** |
| Método de validación declarado | Hold-out con partición disjunta por episodio, umbral calibrado solo con `validation` y evaluación bloqueada de un solo paso, **respaldada por validación cruzada**. Falta la jornada de holdout temporal externa | **3 / 4** |
| Confiabilidad de sistema / determinismo | Reproducción **bit a bit** verificada: el umbral coincide en sus 16 dígitos y los 7 modelos reproducen el manifiesto. Las semillas aún no se declaran como protocolo | **3 / 3** |
| Datos y/o código disponibles públicamente | Dataset, manifiesto y los 7 modelos candidatos publicados, verificables con `sha256sum -c`, bajo licencias MIT y CC BY 4.0 | **3 / 3** |
| Entorno y dependencias documentadas | Versiones exactas de `scikit-learn` y `numpy` en el manifiesto congelado | **3 / 3** |
| **Pertinencia validada con usuarios reales** | **No se realizó ninguna.** Es la única ausencia total del producto | **0 / 3** |
| **TOTAL** | | **16 / 20 · 80 %** |

> **El único cero es la validación con personas.** No se corrige documentando:
> exige evaluadores usando el panel. Una prueba de usabilidad con 5–8
> participantes lo convierte en evidencia y eleva el total a **19 de 20**.

---

## 1. Evidencia de CONFIABILIDAD

*¿Los resultados son estables y consistentes al repetir la medición?*

> **Consigna (paso 3).** *"Identifiquen qué evidencia de confiabilidad utilizaron (o debería reportar): Alfa, Kappa, validación cruzada u otra."*
>
> Se evalúan las tres vías nombradas más las que corresponden a un sistema de software. **Alfa y Kappa no aplican por igual a todo producto**: Alfa mide consistencia interna de un cuestionario y Kappa el acuerdo entre jueces; ninguno de los dos instrumentos existe aquí. Por eso se evalúan explícitamente —para dejar constancia de que se consideraron— y se documenta por qué uno se descarta y el otro se puntúa como ausente.

| # | Criterio | Evidencia concreta en el proyecto | Punt. |
|---|---|---|---|
| 1.1 | **Alfa de Cronbach** (consistencia interna de instrumento) | El producto no emplea cuestionarios ni escalas psicométricas; no hay ítems que correlacionar | **N/A** |
| 1.2 | **Kappa de Cohen** (acuerdo inter-evaluador) | No se realizó evaluación por jueces ni doble etiquetado independiente. Las etiquetas provienen del diseño experimental (escenario ejecutado), no de criterio humano | **0** |
| 1.3 | **Validación cruzada** | Ejecutada sobre el mismo pipeline `StandardScaler` + OCSVM en 5 pliegues agrupados por episodio normal. La detección varió entre 78,8 % y 89,4 %. Reutiliza las mismas anomalías en cada pliegue y, por tanto, es validación interna, no externa | **3** |
| 1.4 | **Reproducibilidad de la medición** | Al reevaluar el modelo congelado sobre los mismos conjuntos se obtuvieron **exactamente** las cifras del registro original (13/276 falsos positivos y 158/179 detecciones) | **3** |
| 1.5 | **Estabilidad interna del umbral** | Bootstrap agrupado por episodio con `B = 1 000`: CV 4,10 % y banda percentil 95 % [1,6496–1,8132]. Los dos pases operativos comparten infraestructura y no se tratan como réplicas independientes | **3** |
| 1.6 | **Cuantificación de la incertidumbre** | Intervalos de Wilson 95 % para proporciones y McNemar exacto con corrección de Holm sobre 21 comparaciones. Los intervalos por ventana son descriptivos porque las ventanas de un episodio comparten historia | **3** |

**Subtotal confiabilidad: 12 / 15 puntos = 80,0 %** *(1.1 excluido por no aplicar)*

**Lectura.** Hay reproducibilidad técnica, validación cruzada y estabilidad interna del umbral. La evidencia sigue limitada al mismo laboratorio y al mismo conjunto de anomalías; no existe jornada externa. El acuerdo inter-evaluador no aplica al etiquetado experimental y no hubo jueces.

---

## 2. Evidencia de REPLICABILIDAD

*¿Puede un tercero reconstruir el estudio y obtener lo mismo?*

> **Consigna (paso 4).** *"Identifiquen qué evidencia de replicabilidad ofrece: ¿datos y código disponibles? ¿entorno documentado?"*
>
> Las dos preguntas se responden por separado. El código, los datos derivados, los modelos y el entorno están publicados; además se comprueban determinismo, integridad verificable e instrucciones de reproducción.

| # | Criterio | Evidencia concreta en el proyecto | Punt. |
|---|---|---|---|
| 2.1 | **Código disponible** | Repositorio público con código versionado e historial trazable | **3** |
| 2.2 | **Datos disponibles** | Dataset derivado, manifiesto y siete modelos candidatos publicados, con `docs/dataset/SHA256SUMS` y licencias MIT para código y CC BY 4.0 para datos | **3** |
| 2.3 | **Entorno documentado** | Versiones exactas fijadas (`requirements-model.txt`), script de instalación idempotente y playbooks de Ansible para el despliegue completo | **3** |
| 2.4 | **Determinismo y semillas** | Protocolo documentado y 10 ajustes repetidos del pipeline elegido produjeron el mismo SHA-256 y el mismo umbral | **3** |
| 2.5 | **Integridad verificable** | SHA-256 de los datos, del modelo y del programa de calibración; commit del repositorio verificado limpio antes y después de la ejecución | **3** |
| 2.6 | **Instrucciones de reproducción** | El datasheet documenta descarga, verificación de hashes y regeneración; el despliegue cuenta con scripts y playbooks versionados | **3** |

**Subtotal replicabilidad: 18 / 18 puntos = 100 %**

**Lectura.** Es la dimensión **más fuerte** del producto y la que más subió: **18 de 18**. La cadena de integridad (hashes, repositorio limpio, versiones fijadas) es superior a lo habitual, y la publicación del dataset y de los siete modelos con checksums y licencias cerró la única brecha que quedaba. Un tercero puede hoy clonar el repositorio y reproducir el umbral en sus dieciséis dígitos.

---

## 3. Evidencia de PERTINENCIA

*¿El producto responde al problema real y su utilidad está demostrada?*

> **Consigna (paso 5).** *"Identifiquen qué evidencia de pertinencia presenta: ¿validación con usuarios reales? ¿trazabilidad de requisitos?"*
>
> Las dos preguntas apuntan a cosas distintas y **el proyecto responde muy diferente a cada una**: la trazabilidad está cerrada, mientras que la validación con usuarios no se realizó en absoluto. Se añaden tres criterios que completan la pertinencia de un producto de ingeniería: si se probó en operación real, si resuelve el problema declarado y si su alcance está delimitado.

| # | Criterio | Evidencia concreta en el proyecto | Punt. |
|---|---|---|---|
| 3.1 | **Validación con usuarios reales** | No se realizó. No hubo pruebas con analistas de seguridad ni medición de experiencia de uso del panel operativo | **0** |
| 3.2 | **Evaluación por expertos o jueces** | No se aplicó ningún instrumento de juicio experto (Delphi, SUS u otro) | **0** |
| 3.3 | **Trazabilidad de requisitos** | **Matriz cerrada**: cada requisito cumplido con evidencia enlazada, cumplido con reserva medida, o declarado pendiente con lo que concretamente falta. Ninguna fila en «Planificado» | **3** |
| 3.4 | **Validación en entorno de operación real** | El sistema se midió **desplegado y activo**, no solo en laboratorio: 2 pases de 29 corridas con motor y bloqueo funcionando sobre tráfico real | **3** |
| 3.5 | **Alineación con el problema declarado** | La evaluación offline cubre 9 familias (6 Kali y 3 heredadas) y F6 valida el camino real de detección y bloqueo; las limitaciones por familia se reportan separadamente | **3** |
| 3.6 | **Declaración de alcance y limitaciones** | Limitaciones medidas, cuantificadas y publicadas, incluido el resultado desfavorable del error operativo (23–26 %) | **3** |

**Subtotal pertinencia: 12 / 18 puntos = 66,7 %**

**Lectura.** El producto es **técnicamente pertinente** —resuelve el problema declarado y se probó en operación real— pero carece por completo de **validación con personas**: nadie externo al equipo ha usado ni evaluado el sistema. Para un producto cuya interfaz es un panel operativo destinado a un analista, esa ausencia es significativa.

---

## 4. Puntaje final

| Dimensión | Obtenido | Máximo | Porcentaje | Nivel |
|---|---|---|---|---|
| Confiabilidad | 12 | 15 | **80,0 %** | Alto |
| Replicabilidad | 18 | 18 | **100 %** | Alto |
| Pertinencia | 12 | 18 | **66,7 %** | Medio-alto |
| **TOTAL** | **42** | **51** | **82,4 %** | **Alto** |

> **Evolución.** La primera auditoría dio **32/51 = 62,7 %**. Subieron siete
> ítems, todos con evidencia publicada: cuantificación de la incertidumbre,
> datos disponibles, instrucciones de reproducción, validación cruzada,
> estabilidad entre repeticiones, determinismo y trazabilidad de requisitos.
>
> **La replicabilidad llega al 100 %** y la confiabilidad pasa de 53,3 % a
> 80,0 %. Lo que sigue frenando el puntaje es la **pertinencia**: los dos ítems
> de validación con personas siguen en **cero**, y no se corrigen escribiendo.

### Interpretación

Un **82,4 %** describe el estado actual: **sólido como artefacto de ingeniería y ya replicable por un tercero, todavía incompleto en validación humana**.

- Lo que sostiene el puntaje es la **replicabilidad** (100 %): datos, modelos, checksums y licencias están publicados; un tercero puede clonar y reproducir el umbral en sus 16 dígitos.
- Lo que lo baja es ya una sola cosa: la **validación humana**. La estadística quedó cerrada y la replicabilidad está completa; lo que falta es que alguien externo al equipo use el producto.
- Ninguna de las dos ausencias invalida los resultados obtenidos; ambas **limitan el alcance de lo que puede afirmarse** a partir de ellos.

---

## 5. Acciones para elevar el puntaje

### Ya ejecutadas

Siete ítems subieron desde la primera auditoría, todos con evidencia publicada
y ninguno con experimentación nueva.

| Acción ejecutada | Ítem | De → a |
|---|---|---|
| Publicar el dataset, el manifiesto y los 7 modelos con checksums y licencias | 2.2 | 1 → 3 |
| Intervalos de Wilson en toda proporción y McNemar con corrección de Holm | 1.6 | 2 → 3 |
| Validación cruzada agrupada por episodio sobre el modelo congelado | 1.3 | 1 → 3 |
| Remuestreo del umbral con B = 1 000, coeficiente de variación 4,10 % | 1.5 | 2 → 3 |
| Protocolo de determinismo, verificado con 10 ajustes de SHA-256 idéntico | 2.4 | 2 → 3 |
| Documentar el procedimiento de descarga, verificación y regeneración | 2.6 | 2 → 3 |
| Cerrar la matriz de trazabilidad de requisitos | 3.3 | 1 → 3 |

**Efecto acumulado: de 32/51 (62,7 %) a 42/51 (82,4 %).**

### Lo que queda

| Acción pendiente | Sube | De → a | Tiempo |
|---|---|---|---|
| **Aplicar un instrumento validado (SUS) con 5–8 evaluadores sobre el panel** | 3.1 | 0 → 3 | 3–5 días |
| Sesión de juicio experto con 3 evaluadores | 3.2 | 0 → 2 | Días |
| Acuerdo inter-evaluador, si se incorpora doble etiquetado independiente | 1.2 | 0 → 2 | Días |

> **El puntaje ya no lo frena la evidencia técnica.** La replicabilidad está en
> 100 % y la confiabilidad en 80 %; los tres ítems que quedan miden **lo que
> otras personas opinan del producto**, y ninguno se corrige escribiendo.
>
> Con solo la prueba de usabilidad, el puntaje pasaría a **45/51 = 88,2 %**. Con
> los tres, a **49/51 = 96,1 %**.

---

## 6. Correspondencia con la norma ISO/IEC 25010

La norma de calidad de producto de software permite situar los resultados en un marco reconocido. Se declara solo lo que el proyecto **midió**; el resto se marca como no evaluado, en lugar de suponerlo:

| Característica ISO/IEC 25010 | ¿Se evaluó? | Evidencia en este proyecto |
|---|---|---|
| **Fiabilidad** — madurez, disponibilidad, tolerancia a fallos | **Sí** | Cero caídas de servicio registradas en 58 corridas, 55 con verificación explícita, sin pérdida de paquetes. Tres fallos de producción detectados y corregidos con prueba positiva y negativa |
| **Eficiencia de desempeño** — comportamiento temporal | **Sí** | Bloqueo en una mediana de 8 s. Límite declarado: bajo carga sostenida el motor acumula retraso |
| **Adecuación funcional** — completitud y corrección | **Parcial** | La evaluación offline cubre 9 familias y F6 confirma el camino de bloqueo, pero la corrección funcional se degrada con tráfico legítimo intenso (error 23–26 %) |
| **Seguridad** — confidencialidad, integridad, no repudio | **Parcial** | Integridad verificable por SHA-256 y control de acceso por helper de alcance estrecho. **No se evaluó el sistema como objetivo de ataque**: no se probó evasión del detector ni abuso del bloqueo mediante suplantación de IP |
| **Mantenibilidad** — modularidad, reusabilidad, analizabilidad | **Parcial** | El motor reutiliza el extractor congelado sin duplicar fórmulas; 514 archivos versionados con historial trazable. Sin métricas formales de mantenibilidad |
| **Usabilidad** | **No** | El panel no se sometió a ninguna evaluación de uso (ver ítems 3.1 y 3.2) |
| **Portabilidad** | **No** | Desplegado sobre una única configuración de laboratorio; no se probó en otro entorno |
| **Compatibilidad** | **No** | No se evaluó la coexistencia con otras herramientas de monitoreo |

**Lectura.** Las dos características que el producto sí demuestra con evidencia —fiabilidad y eficiencia de desempeño— son precisamente las críticas en un sistema de detección en tiempo real. Las no evaluadas coinciden con las carencias que ya señala la ficha: usabilidad con la ausencia de validación con usuarios, y seguridad con la ausencia de pruebas de evasión.

---

## 7. Conclusión de la auditoría

El producto **está validado como artefacto de ingeniería**: funciona, se midió en el laboratorio operativo y sus resultados se pueden reproducir exactamente. La validación cruzada interna, los datos y los modelos ya están publicados. La brecha principal que permanece es que nadie ajeno al equipo ha usado o evaluado el sistema; además, falta una evaluación externa en otra jornada o entorno.

La validación con usuarios exige planificar una sesión con evaluadores externos. Una evaluación temporal o de otra red también requiere datos nuevos y un protocolo prospectivo; no puede cerrarse solo con documentación.

---

## Referencias

- **ISO/IEC 25010:2011.** *Systems and software engineering — Systems and software Quality Requirements and Evaluation (SQuaRE) — System and software quality models.* International Organization for Standardization.
- **Cronbach, L. J. (1951).** Coefficient alpha and the internal structure of tests. *Psychometrika, 16*(3), 297–334. — Origen del criterio del ítem 1.1.
- **Cohen, J. (1960).** A coefficient of agreement for nominal scales. *Educational and Psychological Measurement, 20*(1), 37–46. — Origen del criterio del ítem 1.2.
- **Wilson, E. B. (1927).** Probable inference, the law of succession, and statistical inference. *Journal of the American Statistical Association, 22*(158), 209–212. — Método usado para los intervalos de confianza del ítem 1.6.
- **Wilkinson, M. D., et al. (2016).** The FAIR Guiding Principles for scientific data management and stewardship. *Scientific Data, 3*, 160018. — Marco de referencia para los criterios de replicabilidad (sección 2).
- **Peng, R. D. (2011).** Reproducible research in computational science. *Science, 334*(6060), 1226–1227. — Distinción entre reproducibilidad y replicabilidad aplicada en los ítems 1.4 y 2.1–2.6.
