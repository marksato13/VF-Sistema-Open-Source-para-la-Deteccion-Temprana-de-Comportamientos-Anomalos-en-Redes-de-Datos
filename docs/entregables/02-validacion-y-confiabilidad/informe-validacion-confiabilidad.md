# Informe de validación de resultados: confiabilidad, replicabilidad y pertinencia

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

---

## 1. Resumen del estado

La Sesión 02 organiza la validación en **tres ejes**. Este informe los sigue en ese
orden y desarrolla cada uno con la evidencia del proyecto.

| Eje de la Sesión 02 | Qué pregunta | Estado |
|---|---|---|
| **Confiabilidad** | ¿Repetir el procedimiento da lo mismo? | **Alta.** Determinismo verificado, umbral estable, dos pases equivalentes |
| **Replicabilidad** | ¿Otro equipo, con datos nuevos, llegaría a lo mismo? | **Parcial.** Hay reproducibilidad completa; **falta replicabilidad** |
| **Pertinencia** | ¿Resuelve el problema real, para quien lo usará? | **Sin evidencia.** Es el único eje sin ninguna medición |

**Lectura general.** Los resultados **sí sostienen** que el sistema detecta y bloquea
ataques reales en tiempo real. **No sostienen todavía** que lo haga sin penalizar
tráfico legítimo intenso, ni que sea pertinente para usuarios reales.

---

## 2. Eje 1 · Confiabilidad

*¿Repetir el procedimiento produce los mismos resultados?*

> **Qué pide la Sesión 02.** Aplicar un método concreto y verificable: **Alfa de
> Cronbach** cuando hay instrumentos tipo cuestionario, **Kappa de Cohen** cuando hay
> jueces clasificando, **test-retest** y **confiabilidad de sistemas** cuando se trata
> de software, y **validación cruzada** sobre el modelo (diapositivas 14 a 17).

### 2.1 Por qué Alfa de Cronbach y Kappa de Cohen no aplican

No se omiten: **no corresponden al tipo de producto**, y conviene decirlo antes de
que se pregunte.

| Prueba | Qué mide | Por qué no aplica aquí |
|---|---|---|
| **Alfa de Cronbach** | Consistencia interna entre los ítems de un instrumento | El producto es un sistema que decide y bloquea, **no tiene ítems de escala** que correlacionar. Se calculará sobre el SUS, que sí tiene 10 ítems |
| **Kappa de Cohen** | Acuerdo entre dos evaluadores más allá del azar | **No hay jueces humanos etiquetando**: las etiquetas vienen del diseño experimental —se sabe qué máquina generó cada tráfico— |

### 2.2 Confiabilidad del sistema: determinismo

Es el equivalente al test-retest para algoritmos, y es la evidencia más fuerte del eje.

| Aspecto | Evidencia verificable |
|---|---|
| **Determinismo del pipeline** | **10 ajustes repetidos** produjeron el **mismo SHA-256** y el mismo umbral, `1.8126087939765134` |
| **Semillas fijadas y reportadas** | `random_state` explícito en el calibrador (`PRIMARY_SEED`), declarado en el manifiesto |
| **Integridad de artefactos** | SHA-256 de datos, modelo y calibrador; repositorio verificado limpio antes y después |
| **Estabilidad operativa** | Cero caídas registradas en 58 corridas (55 con verificación explícita), sin pérdida de paquetes |

### 2.3 Test-retest: dos pases independientes

| Pase | Ventanas benignas | Falsos positivos | IC 95 % |
|---|---:|---|---|
| Pase 1 | 62 | **25,81 %** (16/62) | 16,6 % – 37,9 % |
| Pase 2 (*lag-aware*) | 74 | **22,97 %** (17/74) | 14,9 % – 33,7 % |

Los dos pases dan resultados equivalentes: **el sistema es consistente al repetir la
medición**, aunque el valor sobre el que es consistente sea desfavorable.

### 2.4 Validación cruzada y estabilidad del umbral

| Prueba | Resultado |
|---|---|
| **Validación cruzada agrupada por episodio**, 5 pliegues | Detección entre **78,8 % y 89,4 %** según el pliegue; la media (85,5 %) cae dentro del intervalo de la evaluación de un solo paso |
| **Remuestreo bootstrap del umbral**, B = 1 000 | Coeficiente de variación **4,10 %** (máximo declarado: 5 %); banda percentil 95 % **[1,6496 – 1,8132]** |

### 2.5 Cuantificación de la incertidumbre

El trabajo original no calculó ninguna medida de dispersión. Se incorporaron
**intervalos de Wilson al 95 %** en toda proporción, y revelan un problema que las
cifras puntuales ocultaban:

| Cifra reportada | IC 95 % real | Lectura |
|---|---|---|
| 50 % de detección en fuerza bruta (3/6) | **18,8 % – 81,2 %** | Con n = 6 **no sostiene ninguna conclusión** |
| 55,2 % en password-spray (16/29) | 37,5 % – 71,6 % | Intervalo muy amplio, conclusión débil |
| 88,3 % de detección global (158/179) | 82,7 % – 92,2 % | Sólido |

Las comparaciones entre modelos usan **McNemar exacto** —la prueba correcta cuando se
evalúan sobre las mismas ventanas— con **corrección de Holm-Bonferroni sobre 21
comparaciones**. Las seis del OCSVM son significativas; en cambio **ninguna diferencia
de falso positivo lo es** (p mínimo 0,52).

### No abordado en este eje

- **Validación externa del umbral.** La banda de variabilidad se estimó por remuestreo
  sobre los mismos episodios; **no hay una jornada nueva** que confirme que el umbral
  sigue siendo válido en otra fecha.

> **Corregido el 2 de septiembre de 2026.** Hasta esta revisión este informe declaraba
> como *no abordado* que «la calibración se ejecutó una sola vez; no hay repeticiones
> independientes». **Eso dejó de ser cierto** al ejecutarse el análisis de estabilidad.

---

## 3. Eje 2 · Replicabilidad

*¿Otro equipo, con datos nuevos y el mismo método, llegaría a lo mismo?*

> **Qué pide la Sesión 02.** Prácticas de **ciencia abierta**: principios FAIR,
> repositorio público de código, datos con DOI citable, entorno documentado con
> versiones exactas y preregistro del plan de análisis (diapositivas 19 a 22).

### 3.1 Reproducibilidad no es replicabilidad

Es la distinción que más se confunde, y este proyecto **tiene la primera y no la
segunda**:

| | Definición de la sesión | ¿Se cumple? |
|---|---|---|
| **Reproducibilidad** | Mismos datos y mismo código → mismos resultados | **Sí.** Al reevaluar el modelo congelado salieron **exactamente** las mismas cifras del registro original: 13/276 y 158/179 |
| **Replicabilidad** | **Datos nuevos**, mismo método → hallazgos consistentes | **No.** No existe ninguna captura posterior e independiente |

Decirlo así evita la afirmación más común e injustificada en trabajos de este tipo:
«nuestros resultados son replicables».

### 3.2 Checklist de replicabilidad de la Sesión 02

Los cinco puntos de la diapositiva 22, uno por uno:

| Punto del checklist | Estado | Evidencia |
|---|---|---|
| Datos disponibles públicamente | ✅ | Dataset derivado, manifiesto y 7 modelos publicados, con `docs/dataset/SHA256SUMS` (13 archivos) |
| Código fuente disponible y documentado | ✅ | Repositorio público con historial completo; licencia MIT para código y CC BY 4.0 para datos |
| Entorno y dependencias con versiones exactas | ✅ | `requirements-model.txt`; el manifiesto registra `scikit-learn 1.9.0` |
| Semillas fijadas y reportadas | ✅ | `random_state` explícito; 10 ajustes repetidos dan el mismo hash |
| Instrucciones paso a paso | ✅ | El *datasheet* documenta descarga, verificación de hashes y regeneración |

### No abordado en este eje

- **DOI citable de los datos.** No hay depósito en Zenodo, Figshare ni OSF. El
  repositorio es público pero **no tiene identificador persistente**.
- **Preregistro del plan de análisis.** No se publicaron hipótesis, métricas ni
  umbrales antes de ver los resultados. Esta ausencia está directamente relacionada
  con la selección posterior del modelo que se declara en la sección 5.
- **Replicación con datos nuevos.** Es la carencia principal de este eje.

---

## 4. Eje 3 · Pertinencia

*¿La solución resuelve el problema real, para las personas que la usarán?*

> **Qué pide la Sesión 02.** Validación con usuarios y *stakeholders* reales: pruebas
> de usabilidad, entrevistas, modelos de aceptación tecnológica (**TAM**, TAM2,
> **UTAUT**), métricas como el **System Usability Scale (SUS)** y **trazabilidad de
> requisitos** (diapositivas 23 a 27).

### Estado: sin evidencia

**Es el único eje del informe sin ninguna medición.** Se declara así, sin matizarlo.

| Instrumento que pide la sesión | Estado | Detalle |
|---|---|---|
| Pruebas de usabilidad con usuarios reales | ❌ | Nadie fuera del equipo ha operado el panel |
| **SUS** | ⏳ **Preparado, sin aplicar** | Instrumento de 10 ítems y guion de observación listos en [`08-validacion-usuarios/`](../08-validacion-usuarios/); el archivo de respuestas tiene **0 filas** |
| TAM / TAM2 / UTAUT | ❌ | No se aplicó ningún modelo de aceptación |
| Entrevistas o grupos focales con *stakeholders* | ❌ | No se realizaron |
| **Trazabilidad de requisitos** | ⏳ Parcial | La matriz existe como plan, pero **no está cerrada**: hay filas sin prueba asociada |

> **Por qué importa, con las palabras de la sesión:** «una solución puede ser excelente
> en código y arquitectura, y aun así ser irrelevante si no encaja con la necesidad
> real». Este proyecto ha demostrado lo primero y **no ha medido lo segundo**.

**Coste de cerrarlo: dos horas.** Una sesión con 5–8 evaluadores usando el instrumento
ya preparado. Es la acción de menor coste y mayor efecto de todo el plan, porque cierra
a la vez este eje, el criterio correspondiente de la ficha de auditoría y la debilidad
`D-18` del registro.

---

## 5. Validez interna y externa

Los dos criterios de la **Sesión 01** que sostienen los tres ejes anteriores. El
tratamiento resumido está en el
[informe de evaluación crítica](../01-evaluacion-critica/informe-evaluacion-critica.md);
aquí se detalla la evidencia.

### 5.1 Validez interna

| Aspecto | Evidencia verificable |
|---|---|
| Sin fuga de datos entre particiones | Auditoría automática: `no_episode_split = true`; ningún episodio se reparte entre entrenamiento, validación y prueba |
| Sin información futura en las variables | Prueba unitaria: un evento posterior no altera una ventana ya cerrada |
| Umbral fijado antes de ver los datos de prueba | Cuantil α = 0,05 solo sobre validación (k = 13, n = 273); el escalador se ajusta solo con entrenamiento |
| Evaluación en un solo paso, sin reentrenar | Registro sellado con hash del calibrador y del repositorio |
| **Detección y corrección de una fuga propia** | Un experimento con selección contaminada fue identificado y marcado como *«no debe citarse»* |

**No abordado.** El modelo congelado se eligió **después** de observar su desempeño en
el conjunto de prueba. El 88,3 % es el **máximo entre 7 candidatos evaluados sobre los
mismos datos**, sin ningún conjunto reservado que permita una estimación sin sesgo
optimista. Está declarado en la *model card* antes de cualquier métrica.

### 5.2 Validez externa

Se midió el sistema completo en operación real —2 pases de 29 corridas más 2 pruebas de
aislamiento, con motor y bloqueo activos— y con ataques genuinos desde una máquina
atacante real en 6 familias distintas.

**El resultado refuta la generalización**, y se reporta aunque sea desfavorable:

| Condición de medición | Falsos positivos | IC 95 % |
|---|---|---|
| Laboratorio (conjunto de prueba) | **4,71 %** (13/276) | 2,8 % – 7,9 % |
| Operación real, pase 1 | **25,81 %** (16/62) | 16,6 % – 37,9 % |
| Operación real, pase 2 | **22,97 %** (17/74) | 14,9 % – 33,7 % |

![Falsos positivos: laboratorio frente a operación real](../graficas/C1-fpr-offline-vs-operativo.png)

Los intervalos de Wilson son **descriptivos**: las ventanas comparten episodio e
historia de hasta 60 s, así que su no solapamiento no prueba por sí solo una diferencia
inferencial. Además se reprodujo **en aislamiento**: una transferencia legítima de
200 Mbit/s **bloqueó a un cliente legítimo durante 120 segundos**, y otra ventana de la
misma transferencia se permitió por apenas 0,0014 puntos de score.

**No abordado.** La división se hizo por índice de repetición, así que **los 44 perfiles
de tráfico aparecen en las tres particiones**: se mide repetibilidad del escenario, no
generalización. Faltan además seis escenarios legítimos previstos y no hay captura
multi-sistema-operativo.

---

## 6. Checklist integrador de la Sesión 02

Los seis puntos de la diapositiva 29, que la sesión pide verificar **antes de reportar
resultados**:

| Punto | Estado | Dónde está |
|---|---|---|
| Confiabilidad estadística reportada | ✅ | Sección 2: determinismo, test-retest y estabilidad del umbral |
| Método de validación de resultados declarado | ✅ | Sección 2.4: validación cruzada agrupada y bootstrap |
| Datos y código disponibles | ✅ | Sección 3.2 |
| Entorno, dependencias y semillas documentadas | ✅ | Sección 3.2 |
| **Pertinencia validada con usuarios reales** | ❌ | Sección 4: **el único punto sin evidencia** |
| Trazabilidad de requisitos verificada | ⏳ | Sección 4: matriz abierta |

**Cinco de seis cumplidos.** El que falta es el mismo que la ficha de auditoría penaliza
y el que el plan de validación agenda para el 9 de septiembre.

---

## 7. Qué falta y cómo se abordará

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

## 8. Conclusión

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
- **Davis, F. D. (1989).** Perceived usefulness, perceived ease of use, and user acceptance of information technology. *MIS Quarterly, 13*(3), 319–340. — Modelo TAM, marco del eje de pertinencia (sección 4).
- **Landis, J. R., & Koch, G. G. (1977).** The measurement of observer agreement for categorical data. *Biometrics, 33*(1), 159–174. — Escala de interpretación de Kappa, citada en la sección 2.1 para justificar por qué no aplica.
- **National Academies of Sciences, Engineering, and Medicine (2019).** *Reproducibility and replicability in science.* The National Academies Press. — Distinción entre reproducibilidad y replicabilidad usada en la sección 3.1.
- **ISO/IEC 25010:2011.** *Systems and software engineering — SQuaRE — System and software quality models.* — Marco de calidad de producto; su correspondencia detallada se desarrolla en la ficha de auditoría del producto.
