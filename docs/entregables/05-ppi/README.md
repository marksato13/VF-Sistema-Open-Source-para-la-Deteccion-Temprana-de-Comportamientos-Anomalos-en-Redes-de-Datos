# PPI — Proyecto de Investigación

Carpeta del documento del PPI y de su versión actualizada.

## Estado

| | |
|---|---|
| **Situación** | **Actualizado y revisado.** Codex aplicó 18 cambios (`0245c61`); revisión adversarial en [`2026-08-26-revision-ppi-v2-codex.md`](../../revisiones-claude/2026-08-26-revision-ppi-v2-codex.md), con dos correcciones aplicadas |
| **Destino** | Sistema **LAM Research** (versión 2, para asignación de dictaminadores) |
| **Plazo** | Miércoles siguiente a la sesión del 12 de agosto de 2026 |
| **Motivo** | El coordinador rechazó todos los proyectos para que cada equipo suba la versión corregida y pueda pasar al proceso formal de titulación |

## Qué debe reflejar la actualización

El PPI se escribió antes de que existieran los resultados. La versión 2 debe incorporar lo que el proyecto **realmente** produjo y midió, no lo que se planificó:

| Aspecto | Estado actual del proyecto | Dónde está la evidencia |
|---|---|---|
| Modelo | OCSVM congelado (`nu=0.05`), umbral 1,8126; se descartó Isolation Forest por puntos ciegos medidos | [`docs/fase04-modelado/`](../../fase04-modelado/) |
| Variables | 28 features multicapa (L3 = 9, L4 = 8, L7 = 11) | [`configs/features/multilayer-v2.json`](../../../configs/features/multilayer-v2.json) |
| Dataset | 1 373 ventanas normales / 220 episodios · 179 de ataque / 132 episodios | [`docs/fase03-dataset/`](../../fase03-dataset/) |
| Resultados del modelo | ROC-AUC 0,974 · detección 88,8 % (Kali real) · FPR 4,71 % | [`../01-evaluacion-critica/`](../01-evaluacion-critica/informe-evaluacion-critica.md) |
| Validación en operación | Sistema desplegado y medido: lead-time 8 s, disponibilidad 100 % | [`docs/fase07-validacion-final/`](../../fase07-validacion-final/) |
| Limitación principal | FPR operativo 23–26 % sobre tráfico legítimo pesado | [`../02-validacion-y-confiabilidad/`](../02-validacion-y-confiabilidad/informe-validacion-confiabilidad.md) |
| Auditoría del producto | 32/51 = 62,7 % (confiabilidad, replicabilidad, pertinencia) | [`../04-ficha-auditoria/`](../04-ficha-auditoria/ficha-auditoria.md) |

## Estado de la revisión

| | |
|---|---|
| Correcciones obligatorias incorporadas | 4 de 4 |
| Cifras verificadas contra los artefactos | Sin discrepancias |
| Errores encontrados y corregidos | 2 — «38 perfiles» → 44 · «57 corridas» → 55 de 58 verificadas |
| Artefactos congelados | Intactos |
| Pendiente | Figura del flujo extremo a extremo, que ninguno de los 11 PNG representa |

Las tres figuras que Codex sustituyó coinciden **byte a byte** con sus fuentes
del repositorio, y las originales del autor se conservan en el respaldo
`PPI Editar_actual.backup-20260822-before-v2.docx`.

## Recomendación

Antes de subir la versión 2, conviene resolver las acciones de **coste en horas** identificadas en la ficha de auditoría, porque cambian cifras que el propio PPI declara:

1. Declarar explícitamente la selección posterior del modelo y que la detección reportada es una estimación optimista.
2. Acompañar cada proporción de su intervalo de confianza.
3. Reportar el FPR operativo junto al de laboratorio.
4. Cerrar la matriz de trazabilidad de requisitos del jurado.

## Diagramas

Los diagramas del PPI se dibujan en [`../diagramas/`](../diagramas/) y se exportan a PNG 300 dpi para insertarlos en el documento. Ya está disponible la topología del laboratorio.
