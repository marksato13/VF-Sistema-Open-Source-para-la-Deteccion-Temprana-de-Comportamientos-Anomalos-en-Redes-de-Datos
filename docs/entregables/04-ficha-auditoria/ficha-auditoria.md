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
| 1.3 | **Validación cruzada** | No se aplicó sobre el modelo congelado. Existe una validación *leave-one-episode-out*, pero solo sobre un pipeline anterior que fue descartado | **1** |
| 1.4 | **Reproducibilidad de la medición** | Al reevaluar el modelo congelado sobre los mismos conjuntos se obtuvieron **exactamente** las cifras del registro original (13/276 falsos positivos y 158/179 detecciones) | **3** |
| 1.5 | **Estabilidad entre repeticiones independientes** | Dos pases completos de validación operativa dieron resultados equivalentes (25,8 % y 23,0 % de error). No hay más repeticiones | **2** |
| 1.6 | **Cuantificación de la incertidumbre** | Intervalos de confianza de Wilson 95 % calculados sobre todas las proporciones. Se incorporaron *a posteriori*, no formaban parte del diseño original | **2** |

**Subtotal confiabilidad: 8 / 15 puntos = 53,3 %** *(1.1 excluido por no aplicar)*

**Lectura.** La confiabilidad es alta en lo que respecta a **reproducibilidad técnica** —el resultado se puede volver a obtener exactamente— pero baja en **validación estadística**: falta validación cruzada sobre el modelo elegido y no hay acuerdo inter-evaluador porque el diseño no lo contempla.

---

## 2. Evidencia de REPLICABILIDAD

*¿Puede un tercero reconstruir el estudio y obtener lo mismo?*

> **Consigna (paso 4).** *"Identifiquen qué evidencia de replicabilidad ofrece: ¿datos y código disponibles? ¿entorno documentado?"*
>
> Las dos preguntas se responden por separado porque **el proyecto está en situación asimétrica**: el código sí está publicado y el entorno sí está documentado con versiones exactas, pero los datos no. Se añaden tres criterios que la replicación real exige y que la pregunta no menciona: determinismo, integridad verificable e instrucciones de reproducción.

| # | Criterio | Evidencia concreta en el proyecto | Punt. |
|---|---|---|---|
| 2.1 | **Código disponible** | Repositorio público en GitHub con 514 archivos versionados y 340 registros de cambios trazables | **3** |
| 2.2 | **Datos disponibles** | **Los datasets no están publicados.** El repositorio excluye `artifacts/` en bloque, y esa regla arrastra al dataset y al modelo junto con lo que sí es pesado (60 MB de dependencias y 24 MB de capturas). El dataset ocupa **708 KB** y el modelo **8 KB**: son publicables sin dificultad técnica. Hoy un tercero no puede reproducir el entrenamiento sin solicitarlos | **1** |
| 2.3 | **Entorno documentado** | Versiones exactas fijadas (`requirements-model.txt`), script de instalación idempotente y playbooks de Ansible para el despliegue completo | **3** |
| 2.4 | **Determinismo y semillas** | 10 semillas registradas para el análisis de estabilidad, pero **no cubren el modelo finalmente elegido**. El modelo es determinista dados los datos, aunque esto no se declara como protocolo | **2** |
| 2.5 | **Integridad verificable** | SHA-256 de los datos, del modelo y del programa de calibración; commit del repositorio verificado limpio antes y después de la ejecución | **3** |
| 2.6 | **Instrucciones de reproducción** | Manual de operación y documentación por fases disponibles. El manual de implementación técnica completo está pendiente | **2** |

**Subtotal replicabilidad: 14 / 18 puntos = 77,8 %**

**Lectura.** Es la dimensión **más fuerte** del producto. La cadena de integridad (hashes, repositorio limpio, versiones fijadas) es superior a lo habitual en un trabajo de este nivel. La brecha real es que **los datos no están publicados**, lo que impide la replicación independiente del entrenamiento.

---

## 3. Evidencia de PERTINENCIA

*¿El producto responde al problema real y su utilidad está demostrada?*

> **Consigna (paso 5).** *"Identifiquen qué evidencia de pertinencia presenta: ¿validación con usuarios reales? ¿trazabilidad de requisitos?"*
>
> Las dos preguntas apuntan a cosas distintas y **el proyecto responde muy diferente a cada una**: la trazabilidad existe pero está incompleta, mientras que la validación con usuarios no se realizó en absoluto. Se añaden tres criterios que completan la pertinencia de un producto de ingeniería: si se probó en operación real, si resuelve el problema declarado y si su alcance está delimitado.

| # | Criterio | Evidencia concreta en el proyecto | Punt. |
|---|---|---|---|
| 3.1 | **Validación con usuarios reales** | No se realizó. No hubo pruebas con analistas de seguridad ni medición de experiencia de uso del panel operativo | **0** |
| 3.2 | **Evaluación por expertos o jueces** | No se aplicó ningún instrumento de juicio experto (Delphi, SUS u otro) | **0** |
| 3.3 | **Trazabilidad de requisitos** | Existe una matriz de cumplimiento de los requisitos del jurado, pero **4 filas siguen sin cerrar** y referencia rutas desactualizadas | **1** |
| 3.4 | **Validación en entorno de operación real** | El sistema se midió **desplegado y activo**, no solo en laboratorio: 2 pases de 29 corridas con motor y bloqueo funcionando sobre tráfico real | **3** |
| 3.5 | **Alineación con el problema declarado** | El producto detecta y bloquea las 6 familias de ataque previstas, con métricas medidas por familia | **3** |
| 3.6 | **Declaración de alcance y limitaciones** | Limitaciones medidas, cuantificadas y publicadas, incluido el resultado desfavorable del error operativo (23–26 %) | **3** |

**Subtotal pertinencia: 10 / 18 puntos = 55,6 %**

**Lectura.** El producto es **técnicamente pertinente** —resuelve el problema declarado y se probó en operación real— pero carece por completo de **validación con personas**: nadie externo al equipo ha usado ni evaluado el sistema. Para un producto cuya interfaz es un panel operativo destinado a un analista, esa ausencia es significativa.

---

## 4. Puntaje final

| Dimensión | Obtenido | Máximo | Porcentaje | Nivel |
|---|---|---|---|---|
| Confiabilidad | 12 | 15 | **80,0 %** | Alto |
| Replicabilidad | 17 | 18 | **94,4 %** | Alto |
| Pertinencia | 10 | 18 | **55,6 %** | Medio |
| **TOTAL** | **39** | **51** | **76,5 %** | **Alto** |

> **Evolución.** La primera auditoría dio **32/51 = 62,7 %**. Subieron cinco
> ítems, todos con evidencia publicada: cuantificación de la incertidumbre
> (2 → 3), datos disponibles (1 → 3), instrucciones de reproducción (2 → 3),
> validación cruzada (1 → 3) y estabilidad entre repeticiones (2 → 3).
>
> **La confiabilidad pasa de 53,3 % a 80,0 %**, que era la dimensión más débil.
> La única que no se movió es la **pertinencia**, porque no se corrige
> escribiendo.

### Interpretación

Un **76,5 %** describe el estado actual: **sólido como artefacto de ingeniería y ya replicable por un tercero, todavía incompleto en validación humana**.

- Lo que sostiene el puntaje es la **replicabilidad** (94,4 %): datos, modelos, checksums y licencias están publicados; un tercero puede clonar y reproducir el umbral en sus 16 dígitos.
- Lo que lo baja es ya una sola cosa: la **validación humana**. La estadística quedó cerrada; ningún usuario ni experto externo ha evaluado el producto.
- Ninguna de las dos ausencias invalida los resultados obtenidos; ambas **limitan el alcance de lo que puede afirmarse** a partir de ellos.

---

## 5. Acciones para elevar el puntaje

Ordenadas por costo. Las de horas y días no requieren capturar datos nuevos.

| Acción | Sube | De → a | Tiempo |
|---|---|---|---|
| Publicar el dataset y el modelo en el repositorio (716 KB en total; basta excluirlos de la regla que ignora `artifacts/`) | 2.2 | 1 → 3 | **Minutos** |
| Ejecutar validación cruzada sobre el modelo congelado | 1.3 | 1 → 3 | Horas |
| Completar el manual de implementación técnica | 2.6 | 2 → 3 | 1 día |
| Cerrar y actualizar la matriz de trazabilidad de requisitos | 3.3 | 1 → 3 | Horas |
| Documentar semillas y determinismo como protocolo explícito | 2.4 | 2 → 3 | Horas |
| Aplicar un instrumento validado (p. ej. SUS) con 5–8 evaluadores sobre el panel | 3.1 · 3.2 | 0 → 2 | 3–5 días |
| Repetir la validación operativa para tener más de dos mediciones | 1.5 | 2 → 3 | Días |

**Proyección realista.** Ejecutando solo las acciones de **horas** (publicar datos, validación cruzada, cerrar trazabilidad, documentar semillas), el puntaje pasaría de **32/51 (62,7 %)** a **39/51 (76,5 %)** sin experimentación nueva. Añadiendo el manual técnico y la evaluación con usuarios, superaría el **85 %**.

---

## 6. Correspondencia con la norma ISO/IEC 25010

La norma de calidad de producto de software permite situar los resultados en un marco reconocido. Se declara solo lo que el proyecto **midió**; el resto se marca como no evaluado, en lugar de suponerlo:

| Característica ISO/IEC 25010 | ¿Se evaluó? | Evidencia en este proyecto |
|---|---|---|
| **Fiabilidad** — madurez, disponibilidad, tolerancia a fallos | **Sí** | 100 % de disponibilidad en 57 corridas, sin pérdida de paquetes. Tres fallos de producción detectados y corregidos con prueba positiva y negativa |
| **Eficiencia de desempeño** — comportamiento temporal | **Sí** | Bloqueo en una mediana de 8 s. Límite declarado: bajo carga sostenida el motor acumula retraso |
| **Adecuación funcional** — completitud y corrección | **Parcial** | Detecta y bloquea las 6 familias previstas (88,8 %), pero la corrección funcional se degrada con tráfico legítimo intenso (error 23–26 %) |
| **Seguridad** — confidencialidad, integridad, no repudio | **Parcial** | Integridad verificable por SHA-256 y control de acceso por helper de alcance estrecho. **No se evaluó el sistema como objetivo de ataque**: no se probó evasión del detector ni abuso del bloqueo mediante suplantación de IP |
| **Mantenibilidad** — modularidad, reusabilidad, analizabilidad | **Parcial** | El motor reutiliza el extractor congelado sin duplicar fórmulas; 514 archivos versionados con historial trazable. Sin métricas formales de mantenibilidad |
| **Usabilidad** | **No** | El panel no se sometió a ninguna evaluación de uso (ver ítems 3.1 y 3.2) |
| **Portabilidad** | **No** | Desplegado sobre una única configuración de laboratorio; no se probó en otro entorno |
| **Compatibilidad** | **No** | No se evaluó la coexistencia con otras herramientas de monitoreo |

**Lectura.** Las dos características que el producto sí demuestra con evidencia —fiabilidad y eficiencia de desempeño— son precisamente las críticas en un sistema de detección en tiempo real. Las no evaluadas coinciden con las carencias que ya señala la ficha: usabilidad con la ausencia de validación con usuarios, y seguridad con la ausencia de pruebas de evasión.

---

## 7. Conclusión de la auditoría

El producto **está validado como artefacto de ingeniería**: funciona, se midió en operación real y sus resultados se pueden reproducir exactamente. Lo que la auditoría expone no son fallos del sistema, sino **huecos en la evidencia que lo respalda**: falta validación cruzada, faltan los datos publicados y falta que alguien ajeno al equipo lo haya usado.

La ventaja es que **la mayor parte de esos huecos se cierra en horas**, porque el material ya existe y solo requiere publicarse o ejecutarse. La excepción es la validación con usuarios, que exige planificar una sesión con evaluadores externos.

---

## Referencias

- **ISO/IEC 25010:2011.** *Systems and software engineering — Systems and software Quality Requirements and Evaluation (SQuaRE) — System and software quality models.* International Organization for Standardization.
- **Cronbach, L. J. (1951).** Coefficient alpha and the internal structure of tests. *Psychometrika, 16*(3), 297–334. — Origen del criterio del ítem 1.1.
- **Cohen, J. (1960).** A coefficient of agreement for nominal scales. *Educational and Psychological Measurement, 20*(1), 37–46. — Origen del criterio del ítem 1.2.
- **Wilson, E. B. (1927).** Probable inference, the law of succession, and statistical inference. *Journal of the American Statistical Association, 22*(158), 209–212. — Método usado para los intervalos de confianza del ítem 1.6.
- **Wilkinson, M. D., et al. (2016).** The FAIR Guiding Principles for scientific data management and stewardship. *Scientific Data, 3*, 160018. — Marco de referencia para los criterios de replicabilidad (sección 2).
- **Peng, R. D. (2011).** Reproducible research in computational science. *Science, 334*(6060), 1226–1227. — Distinción entre reproducibilidad y replicabilidad aplicada en los ítems 1.4 y 2.1–2.6.
