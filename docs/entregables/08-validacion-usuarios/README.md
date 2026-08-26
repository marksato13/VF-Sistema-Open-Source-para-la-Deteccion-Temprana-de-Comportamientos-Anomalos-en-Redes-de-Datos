# Validación con usuarios — protocolo

> **Estado: instrumento listo, sin aplicar.** Esta carpeta contiene todo lo
> necesario para ejecutar la sesión; falta convocar a los evaluadores.

Cierra la **única ausencia total** del producto. Hoy vale cero en tres sitios a
la vez, y una sola sesión de dos horas los cierra los tres:

| Dónde puntúa cero | Qué pasa a valer |
|---|---|
| Ficha del docente, criterio 6 | 0 / 3 → **2 o 3** |
| Eje de pertinencia del [plan de validación](../07-plan-de-validacion/plan-de-validacion.md) | sin evidencia → **medido** |
| `D-18` del [plan de mejora](../06-plan-de-mejora/01-registro-debilidades.md) | abierto → **cerrado** |

## Por qué SUS y no una encuesta propia

Es un instrumento **validado**, con **baremo publicado**, **aplicable con
muestras pequeñas** y **comparable** con otros estudios. Una encuesta ad hoc no
permitiría ninguna de las cuatro cosas, y un jurado lo señalaría.

Alfa de Cronbach **no se calcula** aquí: la fiabilidad del SUS ya está
establecida en la literatura, y estimarla con 5–8 respondientes no aportaría
evidencia. Eso se declara, no se disimula.

## Participantes

**5 a 8 evaluadores.** No hacen falta más: en pruebas de usabilidad, cinco
participantes detectan la mayoría de los problemas de una interfaz, y el
objetivo aquí es medir usabilidad, no estimar una media poblacional.

| Perfil buscado | Cuántos |
|---|---|
| Personas con experiencia en administración de redes o seguridad | 3–5 |
| Personas del área de sistemas sin experiencia específica en seguridad | 2–3 |

Incluir a los dos grupos importa: el panel debe ser legible para un analista
**y** para alguien que releva un turno.

## Procedimiento — 20 minutos por participante

1. **Contexto (2 min).** Explicar qué hace el sistema. **No** explicar el panel.
2. **Tareas (10 min).** Las cuatro del guion, en orden, sin ayuda. El
   observador **solo** registra: si la completó, cuánto tardó y qué intentó
   antes de acertar.
3. **Cuestionario (5 min).** Los 10 ítems del SUS, sin comentarlos.
4. **Cierre (3 min).** Dos preguntas abiertas: qué le sobró y qué le faltó.

> **Regla del observador: no ayudar.** Si el participante se atasca, se anota
> el tiempo y se pasa a la siguiente tarea. Una tarea rescatada con ayuda es
> una tarea fallida, y registrarla como éxito falsearía la medición.

## Las cuatro tareas

Cada una corresponde a algo que el panel **debe** comunicar sin explicación.

| # | Tarea | Qué pone a prueba |
|---|---|---|
| **T1** | Decir qué IP está bloqueada en este momento | Que el estado operativo se lea de un vistazo |
| **T2** | Decir en cuántos segundos expira ese bloqueo | Que la expiración sea visible, y no haya que calcularla |
| **T3** | Decir si la última alerta la produjo el modelo o el heurístico de autenticación | Que el panel distinga los dos caminos de detección |
| **T4** | Verificar que los tres servicios están activos | Que la salud del sistema no exija leer registros |

**Umbral declarado: tasa de éxito ≥ 80 % sin ayuda.** Por debajo, el elemento
correspondiente del panel se rediseña antes de la defensa.

## Umbral del SUS

| Puntaje | Lectura |
|---|---|
| **≥ 80** | Excelente |
| **68 – 79** | Por encima de la media de referencia |
| **< 68** | Por debajo de la media: **el panel se rediseña** |

**68 es la media de referencia** establecida en la literatura sobre cientos de
estudios. Se declara **antes** de aplicar el instrumento, no después: fijar el
umbral al ver el resultado sería exactamente el sesgo que este proyecto
critica en su propia evaluación crítica.

## Cómo se procesa

Registrar las respuestas en `respuestas-sus.csv` y ejecutar:

```bash
python3 scripts/entregables/calcular_sus.py
```

El script calcula el puntaje SUS por participante y la media con su intervalo
de confianza, la tasa de éxito por tarea y el tiempo mediano. **No interpreta
el resultado**: solo lo calcula.

## Qué NO demuestra esta prueba

- **No mide si el sistema detecta bien.** Eso lo miden la evaluación bloqueada
  y la validación operativa.
- **No sustituye al juicio experto.** Un SUS alto con 6 personas no equivale a
  una evaluación por jueces (`D-28`, que sigue abierta).
- **Con 5–8 participantes, el intervalo de confianza de la media será ancho.**
  Se reporta igual, porque ocultarlo sería el mismo error que este proyecto ya
  corrigió en sus métricas de detección.

## Archivos

| Archivo | Para qué |
|---|---|
| [`instrumento-SUS.md`](instrumento-SUS.md) | El cuestionario, listo para imprimir o pasar a formulario |
| [`guion-observacion.md`](guion-observacion.md) | Guion del observador y hoja de registro por participante |
| `respuestas-sus.csv` | Plantilla de captura |

---

## Nota sobre `resultados-sus.md`

Ese archivo **no existe todavía y no debe existir hasta que haya respuestas
reales**. Lo genera el script a partir del CSV; si aparece sin que se haya
aplicado el instrumento, contiene datos inventados y hay que borrarlo.

El script se probó con un CSV sintético fuera del repositorio, precisamente
para no dejar resultados falsos versionados.
