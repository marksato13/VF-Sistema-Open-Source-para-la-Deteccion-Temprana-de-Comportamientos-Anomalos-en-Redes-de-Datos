# Plan de mejora del producto — debilidades, mitigaciones y prioridades

Registro único de **todo lo que falta** en el producto del PPI, con su evidencia, impacto, esfuerzo y mitigación. Consolida los hallazgos de la validación operativa (F6), la evaluación crítica, la ficha de auditoría y la revisión de los propios entregables.

| | |
|---|---|
| **Producto** | Sistema de detección de anomalías de red con control inline (VM02) |
| **Fecha de corte** | 19 de agosto de 2026 |
| **Puntos abiertos en este registro** | **28** |
| **Ya corregidos durante esta fase** | **5** (fuera del registro, listados como resueltos en cada sección) |
| **Corregidos en el registro técnico previo** | **7 de 12** |

## Documentos de esta carpeta

| Archivo | Para qué |
|---|---|
| [`01-registro-debilidades.md`](01-registro-debilidades.md) | El registro maestro: cada debilidad con evidencia, impacto, esfuerzo y mitigación |
| [`02-checklist.md`](02-checklist.md) | Checklist marcable para ejecutar, ordenado por bloques de tiempo |

> **Relación con el registro técnico existente.** `docs/07-mejoras-futuras/01-debilidades-y-mejoras.md` sigue siendo el registro **técnico del sistema** (12 filas, 7 ya corregidas) y no se duplica aquí: este plan lo referencia y añade lo que aquel no cubre —requisitos académicos, replicabilidad, validación con personas y estado de los entregables—.

---

## Cómo se priorizó

Cada punto se clasifica por dos ejes independientes:

**Impacto** — qué se pierde si no se hace:

| Nivel | Significado |
|---|---|
| 🔴 **Crítico** | Compromete una afirmación central de la tesis o incumple un requisito explícito |
| 🟠 **Alto** | Debilita la defensa ante el jurado o la revisión por pares |
| 🟡 **Medio** | Mejora la calidad pero no invalida nada |
| ⚪ **Bajo** | Cosmético o estructural declarable |

**Esfuerzo** — cuánto cuesta: **Minutos · Horas · Días · Semanas**.

La prioridad sale del cruce: **alto impacto con bajo esfuerzo va primero**, siempre.

---

## Matriz de priorización

|  | **Minutos–Horas** | **Días** | **Semanas** |
|---|---|---|---|
| 🔴 **Crítico** | **P1 · Hacer ya**<br>D-01 declarar selección post hoc<br>D-08 publicar dataset y modelo<br>D-14 diccionario de fórmulas<br>D-20 actualizar el PPI | **P2 · Planificar**<br>D-02 ablación por capas | **P3 · Trabajo futuro**<br>D-11 recalibrar con tráfico pesado |
| 🟠 **Alto** | **P1 · Hacer ya**<br>D-03 validación cruzada<br>D-05 estabilidad por remuestreo<br>D-15 cerrar matriz de requisitos | **P2 · Planificar**<br>D-17 manual técnico<br>D-18 validación con usuarios | **P3 · Trabajo futuro**<br>D-09 holdout temporal externo |
| 🟡 **Medio** | **P2**<br>D-04 pruebas de significancia<br>D-06 documentar determinismo<br>D-12 declarar feature no observable<br>D-22 revertir acceso root | **P3**<br>D-10 escenarios faltantes<br>D-19 pruebas de evasión | **P4 · Declarar**<br>D-13 segundo umbral (LIMIT) |
| ⚪ **Bajo** | **P3**<br>D-07 Youden<br>D-23 gráficos de la ficha<br>D-24 ajustar extensión | **P4 · Declarar**<br>D-16 monitoreo de deriva | **P4 · Declarar**<br>D-21 control por identidad |

---

## El hallazgo más rentable

**Cuatro acciones de minutos u horas** (D-01, D-08, D-14, D-15) cierran **dos requisitos explícitos del jurado** y la principal objeción metodológica, sin experimentación nueva. Elevan además el puntaje de la ficha de auditoría de **62,7 % a 76,5 %**.

Ninguna de ellas exige capturar datos, reentrenar el modelo ni repetir campañas: el material ya existe y solo hay que publicarlo, ejecutarlo o declararlo.

---

## Qué NO se hará y por qué

Declarar un límite con evidencia es una posición defendible; fingir que no existe, no. Estos puntos se documentan como límite del alcance en lugar de resolverse:

| Punto | Razón |
|---|---|
| **D-21** Control por identidad más robusta que la IP | Limitación estructural de cualquier bloqueo por dirección; fuera del alcance de la tesis |
| **D-13** Segundo umbral intermedio (`LIMIT`) | Exigiría un proceso de calibración completo; inventar el número contradiría el criterio del proyecto |
| **D-16** Monitoreo de deriva del modelo | Se documenta como procedimiento futuro, no se implementa |

---

## Reglas del registro

Heredadas del propio proyecto, para que este plan no se degrade:

- Un punto solo pasa a **corregido** cuando existe una prueba reproducible, no cuando está descrito.
- Ninguna cifra se transcribe a mano: se lee del artefacto que la respalda.
- Si una mitigación cambia el modelo o el umbral, exige una versión formal nueva (`PM-multilayer-v2-v2`), no un ajuste directo.
