# Tarea activa

```
ID:     PPI-DOCS-001
Estado: READY
Fecha:  2026-09-02
Autor:  Claude (auditoría) → Codex (implementación)
```

---

## TAREA: Cerrar las inconsistencias de los informes de evaluación y validación

## OBJETIVO

Unificar cómo los informes del producto expresan el **falso positivo
operativo**, declarar en el propio documento cuál es el entregable de cada
sesión del curso, y dejar el cronograma con estados explícitos.

**No se recalcula nada.** Todas las cifras existen ya y tienen fuente primaria;
lo que falta es que los cuatro documentos las digan igual.

---

## ALCANCE

- **Producto:** sistema de detección y bloqueo en tiempo real (PPI, UPeU).
- **Resultados:** los ya congelados. **No se generan resultados nuevos.**
- **Informes permitidos:**
  - `docs/entregables/01-evaluacion-critica/`
  - `docs/entregables/02-validacion-y-confiabilidad/`
  - `docs/entregables/07-plan-de-validacion/`
- **Scripts permitidos:**
  - `scripts/entregables/generar_evaluacion_critica_word.py`
  - `scripts/entregables/generar_plan_validacion_word.py`
- **Archivos que NO deben tocarse:**
  - `artifacts/dataset/*.csv` · `artifacts/model/*.joblib` · `artifacts/model/manifest.json`
  - `results/ablacion/*.json` · `results/f6/*.jsonl`
  - `configs/campaigns/multilayer-v2-normal.json`
  - `docs/entregables/04-ficha-auditoria/` — ya coincide con la rúbrica
  - `docs/fase07-validacion-final/02-resultados-f6.md` — es la fuente primaria
  - `docs/entregables/09-matriz-revistas/` · `10-mapeo-secciones-articulo/`

---

## FUENTES AUTORIZADAS

- `docs/agent-context/ppi-data-science-context.md`
- `CLAUDE.md`
- `docs/revisiones-claude/HANDOFF-CLAUDE.md` ← **leer primero**
- `docs/fase07-validacion-final/02-resultados-f6.md` (solo lectura)
- `artifacts/model/manifest.json` (solo lectura)
- `docs/dataset/SHA256SUMS` (solo lectura)

---

## FLUJO OBLIGATORIO

1. **Claude** audita el estado actual y señala inconsistencias. → **HECHO**,
   en `docs/revisiones-claude/HANDOFF-CLAUDE.md` (hallazgos H-01 a H-04).
2. **Codex** implementa únicamente las correcciones autorizadas en ese handoff.
3. Ejecutar pruebas y verificaciones (comandos en ACEPTACIÓN).
4. **Claude** revisa adversarialmente el diff.
5. **Codex** corrige únicamente los hallazgos confirmados.
6. Actualizar informes, resultados y cronograma.
7. Entregar reporte final en `.agent/RESULTADO-ULTIMA-EJECUCION.md`,
   **sin commit ni push**.

---

## RESTRICCIONES

- No modificar artefactos congelados.
- **No inventar cifras.** Toda cifra nueva debe existir ya en una fuente
  primaria citable; si no existe, reportarlo como pendiente.
- Separar **obtenido**, **validado** y **planificado** en todo texto nuevo.
- No cambiar el dataset salvo autorización explícita.
- **Detenerse ante cualquier hash alterado o prueba fallida.**
- Máximo **2 ciclos** de revisión.

---

## ACEPTACIÓN

**Tests:**

```bash
.venv/bin/python3 -m pytest tests/ -q          # esperado: 90 passed
python3 scripts/entregables/verificar_consistencia.py   # esperado: exit 0, RASTROS OBSOLETOS: 0
sha256sum -c docs/dataset/SHA256SUMS           # esperado: todos OK
git diff --check                               # esperado: sin salida
```

**Hashes esperados** — idénticos antes y después:

```
3846d44c0fe32ac4b4c98f022adac7c459c6add2c6b95062e6bb3237fe9b28ab  artifacts/dataset/multilayer-v2-normal.csv
d115ef987cbd845118038314b7c55a7ad4e359ff4ebfd486c0e664ed3d8078c3  artifacts/dataset/multilayer-v2-anomalies.csv
0a1e8c52dc3282029d9aa1c9a0adbe7cc03c28bbce48bd5b76959e46bdbf5b1b  artifacts/model/manifest.json
af9b50c29f839037b2bda380fc197e017dea482d403c61fa7ae3df79cbff7236  artifacts/model/ocsvm_scaled.joblib
```

**Archivos que deben actualizarse:**

| Archivo | Qué debe cambiar | Hallazgo |
|---|---|---|
| `01-evaluacion-critica/informe-evaluacion-critica.md` | Añadir la cifra exacta 22,97 % y 25,81 % con su fuente | H-01, H-02 |
| `01-evaluacion-critica/…_word.py` | Unificar cómo expresa el FPR operativo | H-01 |
| `02-validacion-y-confiabilidad/informe-…md` | Recuadro que declare que **no** es el entregable de la Sesión 02 | H-04 |
| `07-plan-de-validacion/plan-de-validacion.md` | Renombrar a `plan-de-validacion-de-resultados.md` y arreglar enlaces | H-03 |

**Evidencia requerida:**

- Salida literal de los cuatro comandos de ACEPTACIÓN.
- `git status --short` mostrando **solo** archivos del alcance.
- Para cada `.docx` regenerado: comparación del **texto extraído**, no del
  binario (ver riesgo 3 del handoff).

**Estado final:** `COMPLETO` / `CONDICIONADO` / `BLOQUEADO`

---

## SALIDA

Escribir `.agent/RESULTADO-ULTIMA-EJECUCION.md` con:

1. Cambios realizados.
2. Evidencia y comandos, con salida literal.
3. Resultados exactos.
4. Limitaciones.
5. Archivos modificados.
6. Pendientes y cronograma actualizado.

**No hacer `git commit` ni `git push`.** El usuario revisa y autoriza.
