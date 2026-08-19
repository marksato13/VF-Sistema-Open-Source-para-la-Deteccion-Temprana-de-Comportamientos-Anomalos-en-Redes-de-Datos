# Informe de validación interna, validación externa y confiabilidad de los resultados

**Proyecto:** Detección temprana de comportamientos anómalos en redes de datos mediante modelos predictivos y un mecanismo de control inline
**Integrantes:** Rubén Mark Salazar Tocas · Uziel Elias Sauñe Fernandez
**Curso:** Investigación V · **Docente:** Ing. Nemias Saboya Ríos
**Fecha:** 19 de agosto de 2026

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
- **Pruebas de significancia estadística.** No se realizó ninguna prueba (t, Wilcoxon o equivalente) que compare los modelos.

---

## 3. Validación externa

*¿Los resultados se generalizan a otros contextos, poblaciones o condiciones de uso?*

### Abordado de manera concreta

- **Se midió el sistema completo en operación real**, no solo el modelo en laboratorio: 2 pases de 29 corridas más 2 pruebas de aislamiento, con motor y bloqueo activos.
- **Ataques genuinos** desde una máquina atacante real (Kali) en 6 familias distintas, no simulados por inyección de datos.
- **Se declaró la procedencia heterogénea** de los datos de ataque: 161 ventanas reales y 18 heredadas de otro mecanismo, reportadas por separado (88,8 % frente a 83,3 %).

### Resultado que refuta la generalización

Es el hallazgo más importante y se reporta aunque sea desfavorable:

| Condición de medición | Falsos positivos | IC 95 % |
|---|---|---|
| Laboratorio (conjunto de prueba) | **4,71 %** (13/276) | 2,8 % – 7,9 % |
| Operación real, pase 1 | **25,8 %** (16/62) | 16,6 % – 37,9 % |
| Operación real, pase 2 | **23,0 %** (17/74) | 14,9 % – 33,7 % |

![Falsos positivos: laboratorio frente a operación real](../graficas/C1-fpr-offline-vs-operativo.png)

Los intervalos **no se solapan**, de modo que la diferencia no se explica por azar muestral. Además se reprodujo **en aislamiento**: una transferencia legítima de 200 Mbit/s generó una ventana que cruzó el umbral y **bloqueó a un cliente legítimo durante 120 segundos**. Otra ventana de la misma transferencia se permitió por apenas 0,0014 puntos de score, lo que indica que el tráfico legítimo intenso cae dentro del margen de decisión del modelo.

### No abordado

- **Partición por sesiones independientes.** La división se hizo por índice de repetición (R01–R03 entrenamiento, R04 validación, R05 prueba), por lo que **los 38 perfiles de tráfico aparecen en las tres particiones**. Se mide repetibilidad del escenario, no generalización a tráfico no visto.
- **Jornada de validación temporal externa.** No existe un conjunto capturado en una fecha distinta y reservado sin participar en entrenamiento ni calibración.
- **Diversidad de escenarios.** Faltan seis escenarios legítimos previstos (SSH, SCP/SFTP, SMB, respaldo, streaming y actualizaciones) y no hay captura multi-sistema-operativo.

---

## 4. Confiabilidad

*¿Repetir el procedimiento produce los mismos resultados?*

### Abordado de manera concreta

| Aspecto | Evidencia |
|---|---|
| **Reproducibilidad verificada** | Al reevaluar el modelo congelado se obtuvieron **exactamente** las mismas cifras del registro original (13/276 y 158/179) |
| Integridad de artefactos | SHA-256 de datos, modelo y programa de calibración; repositorio verificado limpio antes y después |
| Trazabilidad | 330 registros de cambios, 181 documentos de campañas, 162 revisiones independientes |
| Estabilidad operativa | 100 % de disponibilidad en 57 corridas, sin pérdida de paquetes en captura |
| Consistencia entre repeticiones | Los dos pases de validación operativa dieron resultados equivalentes (25,8 % y 23,0 %) |

### Abordado parcialmente

- **Cuantificación de la incertidumbre.** El trabajo original no calculó ninguna medida de dispersión. **Se incorporan en este informe** intervalos de confianza de Wilson al 95 %, que revelan un problema que las cifras puntuales ocultaban:

| Cifra reportada | IC 95 % real | Lectura |
|---|---|---|
| 50 % de detección en fuerza bruta (3/6) | **18,8 % – 81,2 %** | Con n = 6 **no sostiene ninguna conclusión** |
| 55,2 % en password-spray (16/29) | 37,5 % – 71,6 % | Intervalo muy amplio, conclusión débil |
| 88,3 % de detección global (158/179) | 82,7 % – 92,2 % | Sólido |

### No abordado

- **Repetición del experimento de modelado.** La calibración se ejecutó una sola vez; no hay repeticiones independientes que permitan estimar la variabilidad del umbral.
- **Confiabilidad inter-evaluador.** No aplica al diseño actual, que no emplea jueces ni instrumentos de percepción.

---

## 5. Qué falta y cómo se abordará con el tiempo disponible

Ordenado por relación entre costo y beneficio. **Ninguna acción del bloque A ni B requiere capturar datos nuevos.**

| Prioridad | Acción | Corrige | Tiempo |
|---|---|---|---|
| **A1** | Declarar explícitamente en la tesis la selección posterior del modelo y que el 88,3 % es una estimación optimista | Validez interna | Horas |
| **A2** | Incorporar los intervalos de confianza a todas las proporciones reportadas | Confiabilidad | Horas |
| **A3** | Sustituir las conclusiones sobre familias con n ≤ 6 por una declaración de muestra insuficiente | Confiabilidad | Horas |
| **A4** | Reportar el error operativo (23–26 %) junto al de laboratorio (4,71 %) | Validez externa | Horas |
| **A5** | Publicar el diccionario de fórmulas de las 14 variables nuevas | Validez de constructo | Horas |
| **B1** | Ejecutar la prueba de ablación por capas (L3/L4/L7) y la comparación 14 frente a 28 variables | Validez de constructo | 1–2 días |
| **B2** | Prueba de estabilidad por remuestreo del modelo elegido | Validez interna | Horas |
| **B3** | Prueba de significancia entre modelos | Validez interna | Horas |
| **C1** | Capturar una jornada nueva y reservarla como validación temporal externa | Validez externa | Días |
| **C2** | Recalibrar el umbral incluyendo tráfico legítimo intenso y repetir la validación operativa | Validez externa | 1–2 semanas |

**Compromiso realista.** Con el tiempo disponible se ejecutarán los bloques **A y B** antes de cerrar la tesis: cubren los dos requisitos formales pendientes y corrigen la principal deficiencia estadística sin requerir experimentación nueva. El bloque **C** se declarará como trabajo futuro, indicando con precisión qué quedaría por demostrar.

---

## 6. Conclusión

Los resultados sostienen una afirmación **acotada y verdadera**: se demostró la viabilidad de detectar comportamientos anómalos y ejercer control en línea en tiempo real sobre una red real, con capacidad discriminante alta (ROC-AUC = 0,974), detección del 88,8 % sobre ataques genuinos y bloqueo en una mediana de 8 segundos.

No sostienen todavía que el sistema sea apto para operación desatendida: sobre tráfico legítimo de alto volumen el error alcanza 23–26 %. Esa limitación **está medida, cuantificada y declarada**, que es la condición que la hace defendible ante una revisión por pares.

La prioridad antes de cerrar no es mejorar el sistema, sino **corregir la inferencia**: declarar la selección posterior del modelo, acompañar cada cifra de su intervalo de confianza y ejecutar la ablación pendiente.
