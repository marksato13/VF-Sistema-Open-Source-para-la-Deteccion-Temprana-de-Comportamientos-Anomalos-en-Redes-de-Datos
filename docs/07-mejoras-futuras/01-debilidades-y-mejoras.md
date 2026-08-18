# Debilidades y mejoras — análisis punto por punto

- **Fecha:** 2026-08-18
- **Estado:** análisis, ninguna mejora implementada todavía salvo lo ya desplegado.

## Propósito

Este documento recolecta, en un solo lugar, las debilidades **medidas** del sistema completo (dataset, modelo, motor, enforcement, dashboard) y qué se podría hacer con cada una — separando claramente evidencia de recomendación, y costo/riesgo de cada mejora, siguiendo el mismo criterio de rigor que el resto del proyecto: nada se afirma sin la evidencia real que lo respalda.

No es una lista de "cosas por hacer" genérica: cada fila cita el documento donde la debilidad fue medida.

## Tabla completa

| # | Debilidad medida | Evidencia | Mejora posible | Costo/riesgo |
|---|---|---|---|---|
| 1 | Detección débil en fuerza bruta / password-spray | `ANOM-AUTH-FAIL-50` 50% (3/6), `ANOM-KALI-PASSWORD-SPRAY-50` 55% (16/29) — el peor punto de los 7 modelos comparados. `docs/fase04-modelado/06-modelo-final-congelado-ocsvm.md` | Heurístico complementario (no reemplaza al modelo): contar intentos de login fallidos por IP en una ventana de 60s, mismo patrón que el heurístico de ventana vacía ya implementado en `scripts/engine/motor_decision.py` | **Bajo** — mismo patrón ya validado en producción, solo una regla nueva |
| 2 | Un solo umbral (ALERT/PERMIT), sin nivel intermedio | Decisión de diseño documentada explícitamente, no una limitación técnica del modelo. `docs/fase05-motor-tiempo-real/01-diseno-motor-tiempo-real.md` | Calibrar un segundo umbral (tipo `LIMIT`) con el mismo método de cuantil ya usado (`alpha` distinto, sobre los mismos scores de `validation`) | **Medio** — exige repetir el proceso riguroso de calibración ya usado, nunca inventar el número directamente |
| 3 | `tls_handshake_failure_ratio_60s` constante en todo el dataset | `docs/fase03-dataset/175-limite-tls-handshake-failure-ratio.md` | Diseñar un escenario que induzca fallos reales de handshake TLS (certificado inválido a propósito, truncar la conexión) | **Medio-alto** — requiere nueva campaña de calibración y una posible ampliación v2.1 del dataset |
| 4 | Buffer en anillo del motor (~120s) más corto que una campaña offline completa | `docs/fase05-motor-tiempo-real/01-diseno-motor-tiempo-real.md` | Ampliar `-W` (más archivos en el anillo) en `ppi-motor-capture.service`, si el disco de VM02 lo permite | **Bajo** — cambio de un parámetro, mismo trade-off ya conocido (más historia a cambio de más disco/memoria) |
| 5 | FPR y desempeño reales del sistema completo (motor + enforcement) todavía no medidos en producción — solo el modelo offline | Es exactamente la validación final (equivalente F6) ya pendiente en la hoja de ruta. `docs/fase04-modelado/04-protocolo-modelado-multilayer-v2-y-hoja-de-ruta.md` | Ejecutar la validación final ya diseñada | Ya planificado — siguiente paso natural |
| 6 | Enforcement es solo por IP — vulnerable a rotación de IP del atacante | Limitación estructural conocida de cualquier bloqueo por IP; no medida específicamente en este proyecto | No hay mitigación de bajo costo real dentro del alcance de esta tesis | **N/A** — se declara como límite del diseño, no se intenta resolver |
| 7 | Sin monitoreo de deriva del modelo (¿sigue siendo válido el umbral con el tiempo?) | No hay proceso definido todavía en ningún documento | Documentar (no implementar) un procedimiento de re-evaluación periódica como trabajo futuro explícito | **Bajo** costo de documentar; implementarlo queda fuera de alcance |
| 8 | Dashboard sin tendencia histórica más allá de la última hora visible | Resuelto parcialmente: `docs/fase06-dashboard/01-diseno-dashboard-motor.md` documenta el rediseño con sparkline de actividad de 60 minutos | Ampliar la ventana del sparkline o persistir agregados diarios si se necesita historial más largo que lo que retiene `motor_decision.log` | **Bajo-medio** — depende de cuánto historial se quiera conservar más allá del log actual |

## Qué NO se va a hacer sin evidencia nueva

- No se calibra un segundo umbral (`LIMIT`) inventando el número — requiere repetir el proceso de calibración con datos de `validation`, igual que el umbral actual.
- No se afirma que el enforcement por IP sea "suficiente" ni se intenta parchear con una solución improvisada (fingerprinting, MAC, etc.) sin evaluarla con el mismo rigor que el resto del sistema.
- No se reentrenan modelo ni umbral fuera de una versión nueva formal (`PM-multilayer-v2-v2`), consistente con la regla ya establecida en `docs/fase04-modelado/06-modelo-final-congelado-ocsvm.md`.

## Priorización recomendada

Las filas #1 y #4 son las de menor costo/riesgo y reutilizan patrones ya implementados y validados en producción — candidatas naturales si se decide implementar algo de esta lista antes de la validación final. Las filas #2, #3 y #7 son trabajo futuro legítimo pero exigen su propio proceso de calibración/evaluación, no deben apurarse. La fila #5 (validación final) ya está planificada y es el siguiente paso natural independientemente de esta lista. La fila #6 es una limitación a declarar en el informe final, no una tarea pendiente.
