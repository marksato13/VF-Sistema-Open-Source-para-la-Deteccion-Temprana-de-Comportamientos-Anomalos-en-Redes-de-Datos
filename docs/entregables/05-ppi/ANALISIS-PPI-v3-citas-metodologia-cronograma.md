# Análisis del PPI · citas, metodología, cronograma y extensión

**Fecha:** 26 de agosto de 2026
**Alcance:** desde la sección 2 (Metodología) en adelante, más el sistema de citas
**Estado:** ✅ **aplicadas al documento** el 26 de agosto de 2026

> Respaldo previo en `PPI Editar_actual.backup-20260826-before-v3.docx`.
> Integridad verificada tras editar: 434 párrafos, 11 tablas y **las 4 imágenes
> intactas**. Las ecuaciones se generaron en **OMML nativo de Word**, no como
> texto ni como imagen, para que se vean como ecuaciones.

> **Sobre gestores bibliográficos.** No hay integración con Zotero ni con
> ningún gestor. Lo que sí se hizo aquí: **verificar cada DOI propuesto**
> resolviéndolo, para no citar nada de memoria. El PPI menciona Mendeley, no
> Zotero.

---

## A · Citas y referencias

### A-01 · El PPI no tiene lista de referencias 🔴 CRÍTICO

**Hecho.** Donde debería estar la bibliografía solo hay una nota de trabajo:

> «De acuerdo al estilo de la revista escogida y con el uso de un gestor
> bibliográfico (Mendeley)»

**No hay ni una sola entrada bibliográfica.** Las 24 URL que le siguen
pertenecen al Anexo A (documentación técnica), no a referencias académicas.

**Además, conviven tres sistemas de cita incompatibles en el cuerpo:**

| Sistema | Ejemplo | Cuántas |
|---|---|---|
| Numérico | `[39]`, `[43]` | 5 distintas, apuntando a una lista que no existe |
| Título entre paréntesis | `(Anomaly detection using unsupervised (25))` | Varias — parecen campos de Mendeley sin renderizar |
| Narrativo sin año | «Vempati et al. proponen…» | 9 autores |

**Riesgo.** Un dictaminador abre la última página y no encuentra bibliografía.
Es de los defectos que se detectan en treinta segundos y descalifican sin
entrar en el contenido.

**Propuesta.** Reconstruir la lista completa en el estilo de la revista
objetivo. **BEEI usa IEEE numérico**, que además es el sistema que el cuerpo ya
empezó a usar. Unificar los tres sistemas en ese.

### A-02 · La matemática que se explica es la del modelo descartado 🔴 CRÍTICO

**Hecho.** El PPI dedica **21 párrafos (p102–p122)** a las ecuaciones de
Isolation Forest —longitud de camino, factor de normalización, número armónico,
constante de Euler-Mascheroni— y **cero** a la formulación del OCSVM, que es el
modelo desplegado.

**Inferencia.** Es un resto del PPI original, cuando Isolation Forest era el
modelo previsto. Codex actualizó correctamente el **texto** que lo rodea —queda
declarado como comparador descartado— pero **no sustituyó las ecuaciones**.

**Riesgo.** Un jurado pregunta: *«¿por qué me explican la matemática de un
modelo que no usaron, y no la del que usaron?»* No hay buena respuesta.

**Propuesta.**

1. **Sustituir** las ecuaciones de Isolation Forest por la formulación del
   OCSVM: hiperplano de máximo margen respecto al origen en el espacio de
   características, función de decisión, papel de `nu` como cota superior de la
   fracción de valores atípicos y cota inferior de la fracción de vectores de
   soporte, y kernel RBF con `gamma='scale'`.
2. **Reducir Isolation Forest** a un párrafo y una fila en la tabla comparativa.
   Su papel ya no es explicar cómo funciona, sino justificar por qué se descartó.
3. **Conservar el resultado de la ablación** como cierre: el contraste se midió.

**Referencias propuestas, con DOI verificado resolviéndolo:**

| Referencia | Para qué | DOI |
|---|---|---|
| Schölkopf, B., Platt, J. C., Shawe-Taylor, J., Smola, A. J., Williamson, R. C. (2001). *Estimating the support of a high-dimensional distribution*. Neural Computation, 13(7), 1443–1471 | **Formulación canónica del OCSVM.** Es la fuente del algoritmo que implementa `scikit-learn` | `10.1162/089976601750264965` |
| Tax, D. M. J., Duin, R. P. W. (2004). *Support Vector Data Description*. Machine Learning, 54(1), 45–66 | Formulación esférica equivalente; útil para explicar la frontera | `10.1023/B:MACH.0000008084.60811.49` |
| Liu, F. T., Ting, K. M., Zhou, Z.-H. (2008). *Isolation Forest*. ICDM | Se **conserva**, pero citada como el comparador descartado | `10.1109/ICDM.2008.17` |

**Referencia adicional recomendada.** Existe literatura reciente que compara
**Isolation Forest frente a One-Class SVM** para seguridad de red. Citarla
convierte la decisión de este proyecto en una discusión con antecedentes, en
vez de una preferencia interna.

---

## B · Metodología — inconsistencias

### B-01 · No existe la sección 2.2 🟠

**Hecho.** La numeración salta de **2.1 Diseño Metodológico** a
**2.3 Arquitectura de la propuesta**.

**Riesgo.** Un salto de numeración sugiere que se eliminó una sección sin
renumerar. Es lo primero que nota un revisor de forma.

**Propuesta.** Renumerar 2.3→2.2, 2.4→2.3 y sucesivas; **o** recuperar el 2.2
si faltaba «Población y muestra», que es lo habitual en esa posición y hoy
aparece disperso en 2.5.1.

### B-02 · El título de 2.1 arrastra una anotación de trabajo 🟡

**Hecho.** «2.1 Diseño Metodológico **- aplicada con enfoque cuantitativo**».
Igual ocurre en 2.7: «Aspectos Éticos **(Conducta responsable e investigación -
15% de coincidencia)**».

**Riesgo.** Son recordatorios del autor para sí mismo, no títulos. El «15 % de
coincidencia» delata además el criterio antiplagio, que no va en un título.

**Propuesta.** «2.1 Diseño metodológico» y «2.7 Aspectos éticos».

### B-03 · El diseño pre-experimental está bien planteado ✅

**Verificado, sin hallazgo.** GE–X–O declarado con precisión, el tratamiento X
definido como **el sistema integrado** y no como el modelo aislado, y las
observaciones O enumeradas. Las cifras del diseño muestral —1 373/179 ventanas,
220/132 episodios, 44 perfiles— **coinciden con los artefactos**.

Se registra por dos motivos: para no dar la impresión de que todo está mal, y
porque una revisión que solo enumera defectos no permite distinguir lo sólido
de lo frágil.

---

## C · Cronograma (3.1) 🔴

**Hecho.** La tabla tiene tres defectos, todos visibles a simple vista:

| # | Defecto |
|---|---|
| 1 | **Doce actividades sin una sola marca.** Todo «DESARROLLO TÉCNICO» y todo «REDACCIÓN Y CIERRE» aparecen vacíos, pese a estar ejecutados |
| 2 | **Dos columnas de mes sin etiqueta**, al final de la tabla |
| 3 | **Termina en junio de 2026**, pero el trabajo real —campañas, F6, congelado del modelo, validación— ocurrió entre **julio y agosto de 2026** |

**Riesgo.** El cronograma dice que el desarrollo técnico no se hizo. Es lo
contrario de lo que el resto del documento demuestra, y la contradicción está
en la misma página que el presupuesto.

**Propuesta.** Reconstruirlo con las fechas reales, que son trazables en el
repositorio:

| Etapa | Meses | Evidencia |
|---|---|---|
| Formulación y revisión bibliográfica | Ago–Dic 2025 | — |
| Metodología y diseño | Dic 2025 – Mar 2026 | `docs/fase01-diseno-experimental/` |
| Entorno de laboratorio | Abr–Jun 2026 | `docs/fase00-infraestructura/` |
| Captura e instrumentación | Jul–Ago 2026 | `docs/fase03-dataset/` (180 documentos) |
| Preparación de datos y variables | Ago 2026 | `docs/fase02-features-multicapa/` |
| Modelado, comparación y congelado | Ago 2026 | `docs/fase04-modelado/` |
| Integración y control inline | Ago 2026 | `docs/fase05-motor-tiempo-real/` |
| Validación experimental (F6) | Ago 2026 | `docs/fase07-validacion-final/` |
| Redacción y cierre | Ago–Set 2026 | — |

**Además:** ampliar las columnas hasta **setiembre de 2026** y eliminar las dos
sin etiqueta. Una tabla de 28×13 es difícil de leer; agrupar por etapa la
reduce a unas 9 filas sin perder información.

---

## D · Extensión: qué unir, qué reducir, qué convertir

### D-01 · La sección 1.2.3 es desproporcionada 🟠

**Hecho.** «Brecha identificada y valor agregado» ocupa **2 382 palabras en 91
párrafos** — más que toda la metodología junta.

**Propuesta.** Reducir a ~800 palabras y trasladar el detalle a **una tabla
comparativa**: qué resuelve cada trabajo previo, qué deja sin resolver, y qué
aporta este proyecto. Ya existen dos tablas parecidas (la 1 y la 2) que podrían
absorberlo.

### D-02 · 2.7.5 Beneficios y Riesgos → tabla ✅ propuesta concreta

**Hecho.** Quince párrafos de viñetas sueltas en tres bloques: beneficios,
riesgos y mitigaciones. El lector tiene que emparejarlos mentalmente.

**Propuesta.** Una sola tabla que **empareje cada riesgo con su mitigación**,
que es la relación que importa:

| Riesgo identificado | Severidad | Medida de mitigación |
|---|---|---|
| Falso positivo sobre tráfico legítimo pesado — **medido**: 22,97 % [14,9–33,7] y 25,81 % [16,6–37,9] | **Alta** | Modo de observación hasta recalibrar; expiración nativa a los 120 s limita el daño de cada bloqueo |
| Configuración inadecuada del control inline | Media | Validación supervisada de reglas antes de cada corrida; entorno aislado sin impacto en producción |
| Exposición de identificadores técnicos | Media | Anonimización de salidas; PCAP y EVE completos fuera del repositorio |

Y los beneficios en tres o cuatro viñetas, que no necesitan tabla.

**Efecto:** de 15 párrafos a una tabla de 3 filas más 4 viñetas. Y el
emparejamiento riesgo–mitigación queda explícito en vez de implícito.

### D-03 · Secciones unibles 🟡

| Unir | En | Por qué |
|---|---|---|
| 2.6.1 Software (36 palabras) + 2.6.2 Técnicas de procesamiento (70) | Una sola sección | Juntas no llegan a 110 palabras; separadas parecen relleno |
| 2.7.1 Comité de Ética (98) + 2.7.4 Conflictos de interés (80) | «Declaraciones formales» | Ambas son declaraciones administrativas breves |

### D-04 · Dónde convienen diagramas en vez de texto

| Sección | Propuesta |
|---|---|
| **2.4 Fases de elaboración** (6 subsecciones, ~1 090 palabras) | Un **diagrama de flujo de las 6 fases** con su entrada y salida, más una tabla de una fila por fase. Ya existe `docs/entregables/diagramas/` con draw.io |
| **2.6.5 Integración análisis–operación** | El **diagrama del flujo extremo a extremo** que Codex identificó como faltante: `PCAP/EVE → ventanas causales → 28 definidas/27 efectivas → StandardScaler–OCSVM → PERMIT/ALERT/BLOCK → nftables`. **Ninguno de los 11 PNG existentes lo representa** |
| **2.3 Arquitectura** | Ya usa `E1-topologia.png`. Correcto, sin cambios |

---

## E · Anexos con enlaces al repositorio

**Hecho.** El Anexo A lista documentación oficial de las herramientas
(Suricata, etc.), pero **no enlaza la evidencia propia del proyecto**.

**Propuesta.** Añadir un **Anexo B — Evidencia reproducible**, con enlaces
navegables:

| Qué | Ruta en el repositorio |
|---|---|
| Datasheet del corpus | `docs/dataset/DATASHEET_MULTILAYER_V2.md` |
| Model card del OCSVM congelado | `docs/dataset/MODEL_CARD_OCSVM.md` |
| System card del motor desplegado | `docs/dataset/SYSTEM_CARD_MOTOR.md` |
| Diccionario de las 28 variables | `docs/fase02-features-multicapa/03-diccionario-multicapa-v2.md` |
| Ablación por capas | `docs/fase04-modelado/07-ablacion-multicapa.md` |
| Significancia entre modelos | `docs/fase04-modelado/08-significancia-entre-modelos.md` |
| Validación cruzada y estabilidad | `docs/fase04-modelado/09-validacion-cruzada-y-estabilidad.md` |
| Validación operativa (F6) | `docs/fase07-validacion-final/02-resultados-f6.md` |
| Verificación de integridad | `docs/dataset/SHA256SUMS` |

Sustituir así los bloques de texto que hoy describen procedimientos: **un
enlace a evidencia verificable pesa más que un párrafo que la resume**.

---

## Resumen y orden sugerido

| # | Acción | Severidad | Coste |
|---|---|---|---|
| **1** | Reconstruir la lista de referencias y unificar el sistema de cita | 🔴 | 2–3 h |
| **2** | Sustituir la matemática de Isolation Forest por la del OCSVM | 🔴 | 2 h |
| **3** | Reconstruir el cronograma con fechas reales | 🔴 | 1 h |
| **4** | Renumerar por el salto de 2.2 y limpiar los títulos | 🟠 | 20 min |
| **5** | Convertir 2.7.5 en tabla riesgo–mitigación | 🟡 | 30 min |
| **6** | Reducir 1.2.3 y trasladar el detalle a tabla | 🟠 | 1–2 h |
| **7** | Añadir el Anexo B con enlaces al repositorio | 🟡 | 30 min |
| **8** | Diagrama del flujo extremo a extremo | 🟡 | 1 h |
| **9** | Unir las secciones cortas | ⚪ | 20 min |

**Los tres primeros son los que un dictaminador detecta sin leer el
contenido**: falta de bibliografía, matemática del modelo equivocado y un
cronograma que dice que el desarrollo no se hizo.

---

## Estado de aplicación

| # | Acción | Estado |
|---|---|---|
| 1 | Lista de referencias | ⚠️ **Parcial** — tres entradas con DOI verificado; el resto queda declarado como pendiente de exportar desde Mendeley |
| 2 | Matemática del OCSVM en lugar de Isolation Forest | ✅ Aplicada |
| 3 | Cronograma con fechas reales | ✅ Aplicada |
| 4 | Renumeración por el salto de 2.2 y limpieza de títulos | ✅ Aplicada |
| 5 | 2.6.5 como tabla riesgo–mitigación | ✅ Aplicada |
| 6 | Reducir 1.2.3 | ⏳ Pendiente |
| 7 | Anexo B con enlaces al repositorio | ✅ Aplicada |
| 8 | Diagrama del flujo extremo a extremo | ⏳ Pendiente |
| 9 | Unir secciones cortas | ⏳ Pendiente |

### Por qué la bibliografía quedó parcial

**No se inventó ninguna referencia.** Se incorporaron las tres cuyo DOI se
verificó resolviéndolo —Schölkopf et al. (2001), Tax y Duin (2004) y Liu et al.
(2008)— y las demás quedan enumeradas por autor y tema en una nota dentro del
propio documento.

Completar el resto exige la biblioteca Mendeley del autor: son trabajos que él
seleccionó y que solo él puede identificar sin ambigüedad. Fabricar entradas
con DOI plausibles habría sido mucho peor que dejar la carencia declarada.
