# Guion de observación

**Participante:** ________________  **Fecha:** ____________
**Observador:** ________________

## Antes de empezar — leer en voz alta

> «Vamos a evaluar un panel de monitoreo, **no a usted**. Si algo no se
> entiende, es un problema del panel. Le voy a pedir cuatro cosas concretas.
> Puede pensar en voz alta si quiere. **No voy a poder ayudarle** durante las
> tareas: si se atasca, lo anoto y pasamos a la siguiente. Eso también es
> información útil.»

**Contexto que sí se da:** el sistema vigila el tráfico de una red, detecta
comportamiento anómalo y bloquea automáticamente la dirección responsable
durante un tiempo.

**Contexto que NO se da:** nada sobre cómo está organizado el panel, dónde
está cada dato ni qué significa cada indicador. Eso es justo lo que se mide.

---

## Registro por tarea

| # | Tarea | ¿Completó sin ayuda? | Tiempo | Intentos fallidos / dónde buscó primero |
|---|---|:---:|---:|---|
| **T1** | ¿Qué IP está bloqueada en este momento? | ☐ Sí ☐ No | ___ s | |
| **T2** | ¿En cuántos segundos expira ese bloqueo? | ☐ Sí ☐ No | ___ s | |
| **T3** | ¿La última alerta la produjo el modelo o el heurístico de autenticación? | ☐ Sí ☐ No | ___ s | |
| **T4** | ¿Están los tres servicios activos? | ☐ Sí ☐ No | ___ s | |

**Criterio de éxito:** la respuesta es correcta **y** el participante llegó a
ella solo. Una respuesta correcta por azar, o alcanzada tras una pista del
observador, se registra como **No**.

**Corte por tarea: 120 segundos.** Al cumplirse, se anota el tiempo, se marca
No y se pasa a la siguiente. Insistir más allá frustra al participante y no
añade información.

---

## Observaciones cualitativas

**Momentos de duda visible** (dónde miró, qué leyó dos veces):

<br><br>

**Vocabulario que no reconoció** (términos del panel que tuvo que interpretar):

<br><br>

**Frase textual más útil que dijo:**

<br><br>

---

## Al terminar

1. Entregar el [cuestionario SUS](instrumento-SUS.md) y dejar que lo complete
   **sin comentarlo**. Comentar los ítems mientras responde contamina la escala.
2. Hacer las dos preguntas abiertas del final.
3. Volcar los datos a `respuestas-sus.csv`.

> **No corrija al participante al final.** Si se le explica cómo debería haber
> encontrado el dato, se sentirá evaluado y, si repite la sesión, ya no será
> un usuario nuevo.
