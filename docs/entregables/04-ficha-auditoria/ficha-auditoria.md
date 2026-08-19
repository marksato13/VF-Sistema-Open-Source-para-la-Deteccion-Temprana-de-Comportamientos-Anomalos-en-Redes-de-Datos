# Ficha de auditoría del producto de ingeniería validado

**Proyecto:** Detección temprana de comportamientos anómalos en redes de datos mediante modelos predictivos y un mecanismo de control inline
**Producto auditado:** Sistema de detección de anomalías de red con control inline, desplegado en laboratorio virtualizado (VM02)
**Integrantes:** Rubén Mark Salazar Tocas · Uziel Elias Sauñe Fernandez
**Curso:** Investigación V · **Docente:** Ing. Nemias Saboya Ríos
**Fecha:** 19 de agosto de 2026

> **Nota sobre la rúbrica.** La escala y los ítems que siguen son una reconstrucción razonada del ejercicio propuesto (Momento 5), porque no se dispuso del formato exacto de la ficha proyectada en clase. La estructura de tres dimensiones —confiabilidad, replicabilidad y pertinencia— y el cálculo de puntaje final sí corresponden a la consigna. Si el formato oficial difiere, los puntajes por ítem se trasladan sin recalcular la evidencia.

---

## Escala de valoración

| Puntos | Nivel | Significado |
|---|---|---|
| **3** | Completo | Existe y es verificable por un tercero |
| **2** | Parcial | Existe pero con limitaciones declaradas |
| **1** | Insuficiente | Solo declarado, sin evidencia sólida |
| **0** | Ausente | No se abordó |
| **N/A** | No aplica | El criterio no corresponde al tipo de producto (se excluye del cálculo) |

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
| Confiabilidad | 8 | 15 | **53,3 %** | Medio |
| Replicabilidad | 14 | 18 | **77,8 %** | Alto |
| Pertinencia | 10 | 18 | **55,6 %** | Medio |
| **TOTAL** | **32** | **51** | **62,7 %** | **Medio-alto** |

### Interpretación

Un **62,7 %** describe con precisión el estado del producto: **sólido como artefacto de ingeniería, incompleto como evidencia científica**.

- Lo que sostiene el puntaje es la **replicabilidad** (77,8 %): el trabajo es verificable, versionado y auditable por un tercero.
- Lo que lo baja son dos ausencias distintas: **validación estadística** (sin validación cruzada del modelo elegido) y **validación humana** (ningún usuario o experto externo evaluó el producto).
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

## 6. Conclusión de la auditoría

El producto **está validado como artefacto de ingeniería**: funciona, se midió en operación real y sus resultados se pueden reproducir exactamente. Lo que la auditoría expone no son fallos del sistema, sino **huecos en la evidencia que lo respalda**: falta validación cruzada, faltan los datos publicados y falta que alguien ajeno al equipo lo haya usado.

La ventaja es que **la mayor parte de esos huecos se cierra en horas**, porque el material ya existe y solo requiere publicarse o ejecutarse. La excepción es la validación con usuarios, que exige planificar una sesión con evaluadores externos.
