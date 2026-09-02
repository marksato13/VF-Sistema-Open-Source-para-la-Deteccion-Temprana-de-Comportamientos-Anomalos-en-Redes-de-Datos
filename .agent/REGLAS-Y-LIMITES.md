# Reglas y límites para agentes en este repositorio

Estas reglas son **estables**: no cambian entre tareas. La tarea concreta vive
en `TASK-ACTUAL.md`.

## Reparto de responsabilidades

| Agente | Función |
|---|---|
| **Claude** | Revisor adversarial. Audita, señala inconsistencias, revisa diffs. |
| **Codex** | Implementador y operador del laboratorio. |

El objetivo no es que ambos produzcan respuestas parecidas, sino **encontrar
errores antes de la defensa** mediante revisión cruzada.

## Prohibiciones absolutas

1. **Nunca `git commit` ni `git push`** sin autorización explícita del usuario
   en esa misma conversación.
2. **Nunca `push --force`, `reset --hard` ni reescritura de historial publicado.**
3. **Nunca modificar artefactos congelados**: `artifacts/`, `results/ablacion/`,
   `results/f6/`.
4. **Nunca inventar una cifra.** Si un dato no tiene fuente primaria, se reporta
   como pendiente. **Un bloqueo reportado es un resultado válido; un dato
   inventado no lo es.**
5. **Nunca `git add -A`** sin revisar antes `git status`: otro agente puede
   tener trabajo sin commitear.

## Cómo se reporta un hallazgo

Formato obligatorio, sin excepciones:

1. Identificador y título.
2. Severidad: crítica · alta · media · baja.
3. **Hecho observado**, con evidencia concreta y reproducible.
4. **Inferencias, separadas de los hechos.**
5. Riesgo para seguridad, funcionamiento o validez científica.
6. Prueba reproducible para confirmarlo o refutarlo.
7. Corrección propuesta y posibles efectos secundarios.
8. Estado: pendiente · confirmada · rechazada · corregida.

No presentar preferencias de estilo como fallos técnicos. **No aceptar
afirmaciones de otro agente sin comprobarlas.**

## Separación obligatoria de afirmaciones

Todo texto debe distinguir:

- **Obtenido** — medido, con artefacto verificable.
- **Validado** — comprobado con prueba positiva y negativa.
- **Planificado** — no ejecutado todavía. Nunca se escribe en pasado.

## Trampas conocidas de este repositorio

1. El verificador de consistencia declara **21 excepciones legítimas**. No son
   errores. Su salida correcta es `RASTROS OBSOLETOS: 0` con `exit 0`.
2. Los `.docx` y `.xlsx` **se regeneran con marca de tiempo distinta aunque el
   texto sea idéntico**. Comparar el texto extraído, no el binario.
3. `python-docx` y `openpyxl` viven **solo en `.venv/bin/python3`**, no en el
   `python3` del sistema.
4. Cuatro sitios externos **bloquean el acceso automatizado**: Scopus, SCImago,
   DOAJ y Springer. Declarar el bloqueo, no rellenar con agregadores.
5. **`openpyxl` no interpreta Markdown.** Escribir `**texto**` en una celda
   muestra los asteriscos. Usar `CellRichText`.

## Criterio de finalización

Una fase solo está terminada cuando existen: configuración persistente, prueba
funcional positiva, prueba negativa, evidencia fechada, evaluación de riesgos,
documentación reproducible y commit identificable sin secretos.
