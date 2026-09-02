# Handoff de Claude para Codex — PPI-DOCS-001

**Fecha:** 2 de septiembre de 2026
**Sesión de origen:** auditoría de los entregables del curso Investigación V
contra los PDF de las Sesiones 01, 02 y 04.
**Alcance:** solo documentación de producto, resultados, evaluación crítica,
plan de validación y cronograma. **No toca el modelo ni el dataset.**

---

## 1 · Qué se auditó y contra qué

| Documento del repositorio | Se auditó contra |
|---|---|
| `docs/entregables/01-evaluacion-critica/` | Sesión 01, diapositivas 7 y 12–33 |
| `docs/entregables/07-plan-de-validacion/` | Sesión 02, diapositivas 7, 12–29 y 33–35 |
| `docs/entregables/04-ficha-auditoria/` | Sesión 02, diapositiva 32 (ficha de 6 criterios / 20 puntos) |
| `docs/entregables/02-validacion-y-confiabilidad/` | Coherencia interna con los anteriores |

---

## 2 · Hallazgos confirmados

### H-01 · El `.docx` y su `.md` fuente expresan el FPR operativo con precisión distinta · **Media**

**Hecho.** Los cuatro informes en Markdown escriben el rango **«23–26 %»**.
El `.docx` del Doc 1 escribe **«22,97 % [14,9–33,7]»**.

Comprobado con:

```bash
grep -o -E '.{0,45}(22[.,]97|25[.,]81|23[–-]26).{0,40}' \
  docs/entregables/01-evaluacion-critica/informe-evaluacion-critica.md
```

Resultado literal: `23–26 % de FPR operativo y un falso positivo`.

**Fuente primaria** (`docs/fase07-validacion-final/02-resultados-f6.md`):
dos pases, **25.81 %** y **22.97 %**.

**Inferencia (separada del hecho).** Ninguna de las dos formas es incorrecta:
22,97 % es el pase 1 y 23–26 % es el rango de los dos pases. Pero un lector que
compare el Word con su fuente ve dos cifras distintas para lo mismo.

**Corrección autorizada.** Unificar el criterio: usar **«22,97 % (pase 1) y
25,81 % (pase 2)»** cuando se citen ambos, y el rango 23–26 % solo cuando se
hable en términos aproximados, diciendo explícitamente que es un rango de dos
pases. No inventar un promedio.

---

### H-02 · `22,97 %` no aparece en ningún `.md` de entregables · **Baja**

**Hecho.** La cifra exacta del pase 1 solo vive en `docs/fase07-*`,
`docs/requisitos-jurado/` y `docs/revisiones-claude/`. Los entregables usan el
rango redondeado.

**Riesgo.** Si un evaluador pide la cifra exacta, no está en el documento que
tiene delante.

**Corrección autorizada.** Añadir la cifra exacta con su intervalo al menos una
vez en el Doc 1 y en `02-validacion-y-confiabilidad`, citando el documento F6
como fuente.

---

### H-03 · El `.md` del plan de validación no lleva el nombre de su `.docx` · **Baja**

**Hecho.**

```
docs/entregables/07-plan-de-validacion/
├── Plan-de-validacion-de-resultados.docx
├── plan-de-validacion.md          ← nombre distinto
└── README.md
```

**Corrección autorizada.** Renombrar el `.md` a
`plan-de-validacion-de-resultados.md` y actualizar toda referencia. Verificar
que ningún enlace queda roto antes de dar por buena la corrección.

---

### H-04 · `02-validacion-y-confiabilidad` no declara su relación con el Doc 2 del curso · **Media**

**Hecho.** El `README.md` de `docs/entregables/` dice que este informe «no
sustituye al plan de la Sesión 02», pero **el propio documento no lo dice**.

**Riesgo.** Se puede subir el documento equivocado al aula virtual.

**Corrección autorizada.** Añadir un recuadro al inicio del informe indicando
que es un informe **en pasado** sobre validación ya ejecutada, y que el
entregable de la Sesión 02 es `07-plan-de-validacion/`, que es **prospectivo**.

---

## 3 · Lo que ya está correcto y NO debe tocarse

Verificado en esta auditoría; modificarlo sería una regresión:

- **Ficha de auditoría (`04-`)**: usa los **seis criterios exactos** de la
  diapositiva 32 de la Sesión 02, con sus pesos 4-4-3-3-3-3 sobre 20.
- **Plan de validación (`07-`)**: cubre los tres ejes, el cronograma por
  semanas, Cronbach, Kappa, validación cruzada, TAM, SUS, trazabilidad y FAIR.
  **1,9 pp** — dentro del 1–2 exigido.
- **Informe de evaluación (`01-`)**: cubre **15 de 15** criterios de la Sesión
  01, incluidos ISO/IEC 25010 y la sección de amenazas a la validez.
  **3,5 pp** — dentro del 2–4 exigido.
- **Cronograma del Doc 1, sección 10.4**: fechas comprometidas por pendiente y
  responsable. Las dos que dependen de terceros están marcadas como tales.

---

## 4 · Decisiones metodológicas ya tomadas

Se documentan para que no se reabran sin motivo:

1. **α de Cronbach y Kappa de Cohen no aplican al producto.** No hay ítems de
   escala que correlacionar ni jueces clasificando. Aplicarán al instrumento SUS
   cuando se aplique. Está justificado en el informe, no omitido.
2. **CASP y JBI no aplican.** Son instrumentos de evaluación de literatura
   clínica. Se dice explícitamente en vez de forzarlos.
3. **Los intervalos por ventana son descriptivos, no inferenciales.** Las
   ventanas de un episodio comparten historia. La comparación entre modelos usa
   McNemar con corrección de Holm.
4. **La selección posterior del modelo se declara, no se corrige.** Corregirla
   exige evaluación nueva y reservada (`PM-multilayer-v2-v2`), que no está en
   el alcance de esta tarea.

---

## 5 · Comandos ejecutados y resultado literal

```bash
$ .venv/bin/python3 -m pytest tests/ -q
90 passed in 1.56s

$ python3 scripts/entregables/verificar_consistencia.py
RASTROS OBSOLETOS: 0   ·   exit 0

$ git status --short --branch
## main...origin/main
```

Hashes congelados al inicio de la auditoría (`docs/dataset/SHA256SUMS`):

```
3846d44c…28ab  artifacts/dataset/multilayer-v2-normal.csv
d115ef98…78c3  artifacts/dataset/multilayer-v2-anomalies.csv
0a1e8c52…f5b1b  artifacts/model/manifest.json
af9b50c2…7236  artifacts/model/ocsvm_scaled.joblib
```

**Deben ser idénticos al terminar.** Si alguno cambia, detenerse.

---

## 6 · Archivos que pueden modificarse

- `docs/entregables/01-evaluacion-critica/` (`.md` y su generador)
- `docs/entregables/02-validacion-y-confiabilidad/`
- `docs/entregables/07-plan-de-validacion/`
- `scripts/entregables/generar_evaluacion_critica_word.py`
- `scripts/entregables/generar_plan_validacion_word.py`

## 7 · Archivos prohibidos

- `artifacts/dataset/*.csv` · `artifacts/model/*.joblib` · `artifacts/model/manifest.json`
- `results/ablacion/*.json` · `results/f6/*.jsonl`
- `configs/campaigns/multilayer-v2-normal.json`
- `docs/entregables/04-ficha-auditoria/` — **ya coincide con la rúbrica; no tocar**
- `docs/entregables/09-matriz-revistas/` y `10-mapeo-secciones-articulo/` — fuera de alcance
- **`git commit` y `git push`**

---

## 8 · Pendientes que esta tarea NO resuelve

Dependen de personas o de tiempo de laboratorio, no de documentación:

| Pendiente | De quién depende | Fecha comprometida |
|---|---|---|
| Sesión SUS con 5–8 evaluadores (`D-18`) | Conseguir evaluadores | mié 9 sep 2026 |
| Juicio experto con 3 evaluadores | Agenda de los asesores | mié 23 sep 2026 |
| Escenarios legítimos faltantes (`D7`) | Laboratorio | sáb 19 sep 2026 |
| Recalibrar con tráfico pesado y repetir F6 (`D5`) | Laboratorio | sáb 10 oct 2026 |
| *Holdout* temporal externo (`D6`) | Laboratorio | sáb 24 oct 2026 |

---

## 9 · Riesgos de esta tarea

1. **Unificar el FPR puede romper la coherencia con `docs/fase07-*`.** Ese
   documento es la fuente primaria y **no está en el alcance**: si hace falta
   cambiarlo, detenerse y reportarlo.
2. **El verificador de consistencia declara 21 excepciones legítimas.** No son
   errores. Un agente anterior las leyó como fallos. Su salida correcta es
   `RASTROS OBSOLETOS: 0` con `exit 0`.
3. **Los `.docx` se regeneran con marca de tiempo distinta aunque el texto no
   cambie.** Comparar el **texto extraído**, no el binario, antes de afirmar que
   hubo un cambio.
