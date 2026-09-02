# Resultado de ejecución — PPI-DOCS-001

**Fecha:** 2026-09-02  
**Estado:** CONDICIONADO

## 1. Cambios realizados

- Unificado el FPR operativo: pase 1 **25,81 % (16/62)** y pase 2 **22,97 % (17/74)**; el rango 23–26 % se identifica como resumen, no promedio.
- Añadidos numeradores, denominadores, intervalos y referencia a `docs/fase07-validacion-final/02-resultados-f6.md` en los informes 01 y 02.
- Añadidos recuadros que identifican los entregables de las Sesiones 01 y 02.
- Renombrado el plan Markdown a `plan-de-validacion-de-resultados.md`.
- Conservado `plan-de-validacion.md` como enlace simbólico de compatibilidad.
- Añadida columna de estado explícito `PLANIFICADA` al cronograma.
- Regenerados los `.docx` autorizados.

## 2. Evidencia y comandos

```text
$ .venv/bin/python3 -m pytest tests/ -q
90 passed in 1.62s

$ python3 scripts/entregables/verificar_consistencia.py
RASTROS OBSOLETOS: 0
exit 0

$ sha256sum -c docs/dataset/SHA256SUMS
todos los artefactos: OK

$ git diff --check
(sin salida)
```

Texto extraído de los `.docx` regenerados:

```text
Informe-evaluacion-critica.docx: 25,81 % (pase 1, 16/62)=True; 22,97 % (pase 2, 17/74)=True; Entregable de la Sesión 01=True
Plan-de-validacion-de-resultados.docx: 25,81 % (16/62) en el pase 1=True; 22,97 % (17/74) en el pase 2=True; PLANIFICADAS=True; Entregable de la Sesión 02=True
```

## 3. Resultados exactos

Los cuatro hallazgos H-01 a H-04 quedaron implementados dentro del alcance permitido. La revisión local del diff no encontró regresiones.

## 4. Limitaciones

- La revisión adversarial no interactiva de Claude fue intentada con `claude -p`, pero no devolvió salida tras 1:43 min; el proceso fue detenido.
- No se afirma que Claude haya aprobado el diff. El estado queda **CONDICIONADO** hasta revisión de Claude o humana.
- No se modificó la fuente primaria F6.

## 5. Archivos modificados

```text
docs/entregables/01-evaluacion-critica/Informe-evaluacion-critica.docx
docs/entregables/01-evaluacion-critica/informe-evaluacion-critica.md
docs/entregables/02-validacion-y-confiabilidad/informe-validacion-confiabilidad.md
docs/entregables/07-plan-de-validacion/Plan-de-validacion-de-resultados.docx
docs/entregables/07-plan-de-validacion/README.md
docs/entregables/07-plan-de-validacion/plan-de-validacion.md (enlace simbólico)
docs/entregables/07-plan-de-validacion/plan-de-validacion-de-resultados.md
scripts/entregables/generar_evaluacion_critica_word.py
scripts/entregables/generar_plan_validacion_word.py
```

No hubo commit ni push.

## 6. Pendientes y cronograma actualizado

- Completar la revisión adversarial de Claude.
- Revisar y autorizar manualmente los cambios antes de commit.
- Pendientes científicos: sesión SUS, juicio experto, escenarios legítimos faltantes, recalibración con tráfico pesado y holdout temporal externo.

## 7. Integridad de artefactos congelados

Hashes antes y después, idénticos:

```text
3846d44c0fe32ac4b4c98f022adac7c459c6add2c6b95062e6bb3237fe9b28ab  artifacts/dataset/multilayer-v2-normal.csv
d115ef987cbd845118038314b7c55a7ad4e359ff4ebfd486c0e664ed3d8078c3  artifacts/dataset/multilayer-v2-anomalies.csv
0a1e8c52dc3282029d9aa1c9a0adbe7cc03c28bbce48bd5b76959e46bdbf5b1b  artifacts/model/manifest.json
af9b50c29f839037b2bda380fc197e017dea482d403c61fa7ae3df79cbff7236  artifacts/model/ocsvm_scaled.joblib
```

Todos los hashes siguen coincidiendo con `docs/dataset/SHA256SUMS`.
