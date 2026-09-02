# Entregables académicos

Documentos de cara al evaluador, construidos sobre la evidencia registrada fase por fase en el resto de `docs/`. Cada entregable tiene su **carpeta propia** con su fuente en Markdown y, cuando corresponde, su versión en Word.

## Mapa: qué sesión pide qué

El curso Investigación V entrega en cada sesión un **taller en clase** (momento
APLICA) y un **entregable autónomo** (momento CREA). Solo el segundo se sube.

| Sesión | Entregable autónomo | Formato exigido | Carpeta | Estado |
|---|---|---|---|---|
| **01** · Criterios y técnicas para la evaluación de resultados | Informe de evaluación crítica | PDF **2–4 pp** | [`01-evaluacion-critica/`](01-evaluacion-critica/) | ✅ **Listo** (~2,6 pp) — incluye el cronograma fechado |
| **02** · Métodos de validación: confiabilidad, replicabilidad y pertinencia | **Plan de validación de resultados** | PDF **1–2 pp** | [`07-plan-de-validacion/`](07-plan-de-validacion/) | ✅ **Listo** (~2 pp) |
| **03** · Estrategias para identificar y mapear revistas científicas | Mapa de revistas | — | [`09-matriz-revistas/`](09-matriz-revistas/) | ⚠️ Absorbido en la matriz de la Sesión 04 |
| **04** · Selección de la revista objetivo | **Matriz de decisión + justificación** | Matriz completa + justificación **de 1 página, aparte** | [`09-matriz-revistas/`](09-matriz-revistas/) | ✅ **Listo** — matriz de 9 candidatas + `Justificacion-revista-objetivo.docx` (~1 p) |
| **05** · Estructura del artículo científico | **Mapeo de artículos + estructura final** | `.xlsx` | [`10-mapeo-secciones-articulo/`](10-mapeo-secciones-articulo/) | ✅ **Listo** — 21 artículos, 7 semilla, análisis de la guía y estructura final |

Además, el taller en clase de la Sesión 02 usa una **ficha de auditoría de 6
criterios sobre 20 puntos**. La ficha de [`04-ficha-auditoria/`](04-ficha-auditoria/)
es más exhaustiva —3 dimensiones, 51 puntos— pero **no está expresada en el
esquema que el docente califica**; conviene añadir su tabla de 6 criterios al
inicio sin retirar el análisis extenso.

> **Los tres desajustes son de formato, no de contenido.** El material existe y
> está respaldado; lo que falta es presentarlo con la extensión y el esquema
> pedidos. Un entregable sólido pierde puntos por no cumplir el formato.

---

## Índice

| Carpeta | Entregable | Estado | Para qué |
|---|---|---|---|
| [`01-evaluacion-critica/`](01-evaluacion-critica/) | Informe de resultados y evaluación crítica | **Listo** · *entregable del curso* | **Sesión 01.** El `.md` es el análisis completo con las 11 gráficas; el `.docx` es la versión de 3 páginas con la estructura que pide la consigna: qué se abordó, qué falta y cómo se está abordando |
| [`02-validacion-y-confiabilidad/`](02-validacion-y-confiabilidad/) | Informe de validación y confiabilidad | **Listo** | Informe **en pasado** sobre validación interna, externa y confiabilidad. **No sustituye al plan de la Sesión 02**, que es prospectivo y de 1–2 páginas |
| [`03-auditoria-comparativa/`](03-auditoria-comparativa/) | Auditoría comparativa MVP vs versión final | **Listo** | Contrasta repositorios, arquitectura, modelo, dataset y cumplimiento de las observaciones del jurado |
| [`04-ficha-auditoria/`](04-ficha-auditoria/) | Ficha de auditoría del producto | **Listo** · *entregable del curso* | Los 6 criterios sobre 20 puntos del docente (**16/20**) más el análisis extenso en tres dimensiones: **42/51 = 82,4 %** |
| [`05-ppi/`](05-ppi/) | PPI — Proyecto de Investigación | **Pendiente** | Documento del proyecto. Debe subirse actualizado (versión 2) al sistema LAM Research |
| [`diagramas/`](diagramas/) | Diagramas editables (draw.io) | — | Fuentes editables con iconos, para el PPI y los demás entregables |
| [`06-plan-de-mejora/`](06-plan-de-mejora/) | Plan de mejora del producto | **Listo** | Registro único de las debilidades abiertas con evidencia, impacto, esfuerzo y mitigación, más el checklist de ejecución |
| [`10-mapeo-secciones-articulo/`](10-mapeo-secciones-articulo/) | Mapeo de artículos y estructura final del artículo | **Listo** · *entregable del curso* | **Sesión 05.** 21 artículos (7 semilla de IJIES), nombres de sección transcritos del PDF, frecuencias, veredicto **flexible en el cuerpo / rígido en el cierre**, análisis crítico de la guía de autores con citas literales y las **10 secciones definitivas** del artículo |
| [`09-matriz-revistas/`](09-matriz-revistas/) | Matriz de decisión + justificación de la revista | **Listo** · *entregable del curso* | **Sesión 04.** Cinco candidatas con filtro de legitimidad aplicado antes de puntuar, criterios ponderados y Plan A/B/C. Cada celda con su fuente y estado de verificación |
| [`08-validacion-usuarios/`](08-validacion-usuarios/) | Validación con usuarios (SUS) | **Instrumento listo, sin aplicar** | Cuestionario, guion de observación, plantilla de captura y script de cálculo. Cierra a la vez el criterio 6 de la ficha, el eje de pertinencia del plan y `D-18` |
| [`07-plan-de-validacion/`](07-plan-de-validacion/) | Plan de validación de resultados | **Listo** · *entregable del curso* | **Sesión 02.** Plan prospectivo de 1–2 páginas con método y umbral por cada eje —confiabilidad, replicabilidad, pertinencia— y cronograma |
| — | Manual de implementación técnica | Pendiente | |

## Organización

```
docs/entregables/
├── graficas/                        figuras GENERADAS por script (no editar a mano)
├── diagramas/                       diagramas DIBUJADOS en draw.io (editables)
│   ├── topologia-laboratorio.drawio
│   └── exportados/                  PNG 300 dpi para Word y PDF
├── 01-evaluacion-critica/
│   ├── informe-evaluacion-critica.md      ← detallado
│   └── Informe-evaluacion-critica.docx    ← preciso, 3 pp
├── 02-validacion-y-confiabilidad/
│   ├── informe-validacion-confiabilidad.md
│   └── Informe-validacion-confiabilidad.docx
├── 03-auditoria-comparativa/
│   └── auditoria-comparativa-mvp-vs-version-final.md
├── 04-ficha-auditoria/
│   ├── ficha-auditoria.md
│   └── Ficha-auditoria-producto.docx
├── 05-ppi/                          documento del PPI (pendiente de actualizar)
├── 06-plan-de-mejora/               debilidades, mitigaciones y checklist
├── 07-plan-de-validacion/
│   ├── plan-de-validacion.md
│   └── Plan-de-validacion-de-resultados.docx
├── 08-validacion-usuarios/          instrumento SUS, guion y plantilla
└── 09-matriz-revistas/
    ├── matriz-decision-revistas.md   ← detallada, con ficha por candidata
    └── Matriz-decision-revistas.docx ← precisa, ~2,6 pp
```

**Figuras y diagramas son cosas distintas.** `graficas/` contiene lo que se *genera* con matplotlib desde los datos reales; se regenera con un script y no se edita a mano. `diagramas/` contiene lo que se *dibuja*: topologías, arquitecturas y flujos, en draw.io con iconos. Las figuras viven en una sola carpeta y no dentro de cada entregable porque los informes 01 y 02 comparten varias; los documentos las referencian como `../graficas/`.

**Markdown como fuente, Word como presentación.** El `.md` es la versión versionable y revisable en GitHub; el `.docx` se genera por script, de modo que si cambia una cifra el documento presentable se regenera sin editarlo a mano:

```bash
.venv/bin/python3 scripts/entregables/generar_graficas.py       # las 11 figuras + intervalos de confianza
.venv/bin/python3 scripts/entregables/generar_evaluacion_critica_word.py  # Word del entregable 01
.venv/bin/python3 scripts/entregables/generar_informe_word.py   # Word del entregable 02
.venv/bin/python3 scripts/entregables/generar_ficha_word.py     # Word del entregable 04
.venv/bin/python3 scripts/entregables/generar_plan_validacion_word.py  # Word del entregable 07
.venv/bin/python3 scripts/entregables/generar_matriz_revistas.py       # matriz de revistas (.md y Word)
```

## Estructura del entregable 01

Un solo informe con dos partes, porque los dos encargos recibidos son complementarios y no independientes:

- **Parte I — Resultados.** Qué se obtuvo, con gráficas y tablas. Descriptivo.
- **Parte II — Evaluación crítica.** Si esos resultados valen, bajo criterios de validez, confiabilidad y evaluación técnica. Analítico: dictamina, prioriza y propone.

La diferencia entre ambos géneros: los resultados son *el análisis de sangre*; la evaluación crítica es *el diagnóstico*.

## Trazabilidad de las cifras

Ninguna cifra de estos documentos está escrita a mano: todas se leen de artefactos verificables (`artifacts/model/manifest.json`, `results/f6/f6_resultados.jsonl`) o se recalculan re-puntuando el modelo congelado. El script de gráficas **verifica antes de dibujar** que la re-puntuación reproduce exactamente el manifiesto (13/276 y 158/179); si no coincidiera, falla en vez de generar figuras engañosas.

## Aportes propios de los informes

Además de evaluar lo existente, estos documentos **calculan magnitudes que el trabajo original nunca computó**:

- **ROC-AUC = 0,974**, curva completa, recall, especificidad y F1 (antes solo había FPR y detección en un único punto de operación).
- **Intervalos de confianza de Wilson 95 %** sobre todas las proporciones. Revelan, por ejemplo, que el "50 % de detección en fuerza bruta" tiene un intervalo de 18,8 % – 81,2 % con n = 6 y por tanto no sostiene ninguna conclusión.
- **Verificación independiente** de que el modelo congelado reproduce sus propias métricas al re-puntuar.

## Gráficas

| Grupo | Figuras | Qué muestran |
|---|---|---|
| **A · Modelo congelado** | `A1` curva ROC · `A2` distribución de scores · `A3` matriz de confusión · `A4` barrido de umbral | Capacidad discriminante, dónde se solapan las clases y qué se gana o pierde al mover el umbral |
| **B · Comparación de modelos** | `B1` detección frente a FPR · `B2` mapa de calor por familia | Por qué se eligió OCSVM y dónde falla frente a las alternativas |
| **C · Operación real (F6)** | `C1` FPR offline vs operativo · `C2` lead-time · `C3` scores de tráfico pesado | Comportamiento del sistema desplegado, incluidos los resultados negativos |
| **D · Dataset y variables** | `D1` particiones, familias y features por capa | Composición y alcance de los datos |
| **E · Infraestructura** | `E1` topología del laboratorio | Dónde se captura, se decide y se bloquea |

## Capturas pendientes

El informe 01 deja dos espacios señalados para capturas que deben tomarse manualmente del panel en vivo (`http://127.0.0.1:8788/` mediante túnel SSH): el panel operativo y una IP bloqueada durante un ataque.
