# Revisión adversarial de PPI-DOCS-001

**Fecha:** 2 de septiembre de 2026
**Revisa:** Claude · **Implementó:** Codex
**Entrada:** [`.agent/RESULTADO-ULTIMA-EJECUCION.md`](../../.agent/RESULTADO-ULTIMA-EJECUCION.md)
**Estado declarado por Codex:** `CONDICIONADO`

---

## Veredicto

**Trabajo correcto.** Los cuatro hallazgos del handoff quedaron implementados,
las cifras coinciden con la fuente primaria y **Codex corrigió un error mío**.
Se confirman **dos defectos** en su implementación, ambos corregidos en esta
revisión.

**Estado final: `COMPLETO`**, con las correcciones de R-05 y R-08 aplicadas.

---

## R-00 · Codex corrigió un error de Claude · **confirmado a favor de Codex**

**Hecho.** El handoff enumeraba los dos pases de F6 como «25.81 % y 22.97 %»
sin decir cuál era cuál, y las respuestas previas de Claude venían citando
**22,97 %** como *el* falso positivo operativo. Codex fue a la fuente primaria
y etiquetó los pases al revés de como Claude los venía usando.

**Verificación** (`docs/fase07-validacion-final/02-resultados-f6.md`, líneas 35-38):

```
| Pase | Ventanas benignas | ALERT | FPR |
| Pase 1 | 62 | 16 | 25.81 % |
| Pase 2 (lag-aware) | 74 | 17 | 22.97 % |
```

**Codex tiene razón.** El pase 1 es 25,81 % y el pase 2 es 22,97 %. La cifra que
Claude venía repitiendo era la del segundo pase, presentada como si fuera la
principal.

**Estado:** corregido por Codex. Es el hallazgo más valioso de esta ejecución.

---

## R-01 · Cifras e intervalos · **confirmado correcto**

Se recalcularon los intervalos de Wilson de forma independiente:

| Dato | Calculado en esta revisión | Escrito por Codex |
|---|---|---|
| 16/62 = 25,81 % | IC 95 % **[16,6 – 37,9]** | [16,6–37,9] ✔ |
| 17/74 = 22,97 % | IC 95 % **[14,9 – 33,7]** | [14,9–33,7] ✔ |

Numeradores, denominadores e intervalos **coinciden exactamente**. No hay cifra
inventada.

---

## R-05 · El enlace simbólico de compatibilidad · **confirmado · alta**

**Hecho.** Para resolver H-03, Codex renombró el `.md` y dejó
`plan-de-validacion.md` como **enlace simbólico** al nuevo nombre.

```
$ ls -la docs/entregables/07-plan-de-validacion/plan-de-validacion.md
lrwxrwxrwx … plan-de-validacion.md -> plan-de-validacion-de-resultados.md
```

**Tres problemas, en orden de gravedad:**

1. **GitHub no resuelve enlaces simbólicos en la vista de archivo.** Quien haga
   clic en `plan-de-validacion.md` en el navegador ve el texto literal
   `plan-de-validacion-de-resultados.md`, no el plan. Es **peor que un enlace
   roto**, porque parece un archivo válido.
2. **No cumplió su propósito.** El handoff pedía «renombrar y actualizar **toda
   referencia**». El enlace se creó para evitar ese trabajo, pero **dos
   referencias seguían apuntando al nombre viejo**:
   - `docs/entregables/08-validacion-usuarios/README.md:12`
   - `docs/entregables/README.md:69`
3. **No sobrevive en Windows** sin modo desarrollador, y el equipo tiene dos
   integrantes.

**Inferencia, separada del hecho.** No fue un descuido sino una decisión: Codex
lo declara explícitamente como «enlace simbólico de compatibilidad». Pero era
una solución que el encargo no pedía y que introduce un fallo nuevo.

**Corrección aplicada.** Enlace eliminado; las dos referencias apuntan al nombre
real. Verificado: `grep -rn "plan-de-validacion\.md"` no devuelve ninguna
referencia viva.

---

## R-08 · El rango 23–26 % sin contexto en el plan · **confirmado · baja**

**Hecho.** Codex contextualizó el rango en los informes 01 y 02 —«resume ambos
pases y no es un promedio»— pero en el plan de validación quedó como
**«El falso positivo operativo de 23–26 %»**, en negrita y sin el matiz.

**Riesgo.** Es el único documento donde el rango aparece como si fuera una
medición y no un resumen.

**Corrección aplicada.** Ahora dice: «El falso positivo operativo —25,81 % en el
pase 1 y 22,97 % en el pase 2, unos 23–26 %—».

---

## R-09 · El plan superó el límite de páginas · **confirmado · media**

**Hecho.** La diapositiva 33 de la Sesión 02 exige **1 a 2 páginas**. Tras las
adiciones de Codex el documento medía **~2,1 pp**.

**Inferencia.** Las adiciones eran correctas en contenido; el problema es que
nadie volvió a medir la extensión después de añadirlas. La tarea sí lo exigía
como criterio de aceptación.

**Corrección aplicada.** Se acortaron dos párrafos sin perder ninguna cifra ni
declaración. Queda en **~2,0 pp**, dentro del límite, conservando 25,81 %,
22,97 %, la columna `PLANIFICADA` y el recuadro de la Sesión 02.

---

## R-10 · Tres enlaces rotos preexistentes · **confirmado · baja · ajeno a Codex**

**Hecho.** `03-auditoria-comparativa/` apuntaba a `01-informe-evaluacion-critica.md`
y `02-informe-validacion-confiabilidad.md`, nombres que no existen desde una
reorganización anterior.

**No es responsabilidad de Codex** —son previos a esta tarea y estaban fuera de
su alcance— pero se corrigieron aquí por estar a un carácter de distancia.

---

## Lo que Codex hizo bien y conviene registrar

1. **Fue a la fuente primaria** en vez de fiarse del handoff, y por eso encontró
   el error de etiquetado de los pases.
2. **Calculó los intervalos de Wilson correctamente**, verificado de forma
   independiente.
3. **No tocó la fuente primaria F6**, como exigía el alcance.
4. **No commiteó ni pusheó.**
5. **Declaró el estado como `CONDICIONADO`, no como `COMPLETO`**, reconociendo
   que faltaba la revisión. Es la conducta correcta: no se autoaprobó.
6. **Reportó un bloqueo real sin disfrazarlo**: intentó lanzar la revisión de
   Claude con `claude -p`, no obtuvo salida en 1:43 min y lo dijo.

---

## Verificación tras las correcciones

```bash
$ .venv/bin/python3 -m pytest tests/ -q
90 passed in 1.65s

$ python3 scripts/entregables/verificar_consistencia.py
exit 0

$ sha256sum -c docs/dataset/SHA256SUMS
13/13 OK

$ git diff --check
(sin salida)
```

Extensión de los dos entregables:

| Documento | Extensión | Exigido |
|---|---|---|
| `Informe-evaluacion-critica.docx` | ~3,6 pp | 2–4 pp ✔ |
| `Plan-de-validacion-de-resultados.docx` | ~2,0 pp | 1–2 pp ✔ |

**Hashes congelados: sin cambios.** Ningún enlace interno roto en
`docs/entregables/`.
