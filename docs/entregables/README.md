# Entregables académicos

Documentos de cara al evaluador, construidos sobre la evidencia registrada fase por fase en el resto de `docs/`. Cada entregable tiene su **carpeta propia** con su fuente en Markdown y, cuando corresponde, su versión en Word.

## Índice

| Carpeta | Entregable | Estado | Para qué |
|---|---|---|---|
| [`01-evaluacion-critica/`](01-evaluacion-critica/) | Informe de resultados y evaluación crítica | **Listo** | Documento extenso con las 11 gráficas y el detalle completo de cada hallazgo. Funciona como **anexo técnico** de los demás |
| [`02-validacion-y-confiabilidad/`](02-validacion-y-confiabilidad/) | Informe de validación y confiabilidad | **Listo** · *entregable del curso* | Versión breve (4 páginas) con la estructura exacta pedida en clase: validación interna, externa y confiabilidad |
| [`03-auditoria-comparativa/`](03-auditoria-comparativa/) | Auditoría comparativa MVP vs versión final | **Listo** | Contrasta repositorios, arquitectura, modelo, dataset y cumplimiento de las observaciones del jurado |
| [`04-ficha-auditoria/`](04-ficha-auditoria/) | Ficha de auditoría del producto | **Listo** · *entregable del curso* | Auditoría en tres dimensiones (confiabilidad, replicabilidad, pertinencia). Puntaje: **32/51 = 62,7 %** |
| — | Manual de implementación técnica | Pendiente | |
| — | Actualización del PPI | Pendiente | |

## Organización

```
docs/entregables/
├── graficas/                        11 figuras, compartidas por los informes
├── 01-evaluacion-critica/
│   └── informe-evaluacion-critica.md
├── 02-validacion-y-confiabilidad/
│   ├── informe-validacion-confiabilidad.md
│   └── Informe-validacion-confiabilidad.docx
├── 03-auditoria-comparativa/
│   └── auditoria-comparativa-mvp-vs-version-final.md
└── 04-ficha-auditoria/
    ├── ficha-auditoria.md
    └── Ficha-auditoria-producto.docx
```

Las figuras viven en `graficas/` y no dentro de cada carpeta, porque los informes 01 y 02 comparten varias. Los documentos las referencian como `../graficas/`.

**Markdown como fuente, Word como presentación.** El `.md` es la versión versionable y revisable en GitHub; el `.docx` se genera por script, de modo que si cambia una cifra el documento presentable se regenera sin editarlo a mano:

```bash
.venv/bin/python3 scripts/entregables/generar_graficas.py       # las 11 figuras + intervalos de confianza
.venv/bin/python3 scripts/entregables/generar_informe_word.py   # Word del entregable 02
.venv/bin/python3 scripts/entregables/generar_ficha_word.py     # Word del entregable 04
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
