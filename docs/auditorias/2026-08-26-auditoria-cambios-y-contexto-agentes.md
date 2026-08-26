# Auditoría de cambios nuevos e integración de contexto de agentes

Fecha: **26 de agosto de 2026**

Rango revisado: `7508efb..da96b7f`

Rama auditada: `main`

## Dictamen

Los nueve commits nuevos fortalecen de forma material el proyecto: corrigen el
catálogo, publican artefactos verificables, añaden datasheet/diccionario/cards y
ejecutan ablación y comparación estadística. No obstante, el conjunto todavía
no es internamente consistente: documentos generados quedaron desactualizados
respecto a commits posteriores y la inferencia por ventanas ignora la
correlación conocida dentro de episodios.

**Puntaje técnico del repositorio: 83/100.** Es un juicio de auditoría, no una
métrica del modelo.

| Criterio | Puntaje | Evidencia |
|---|---:|---|
| Integridad y trazabilidad de artefactos | 20/20 | Los 13 archivos de `docs/dataset/SHA256SUMS` verifican |
| Dataset y documentación científica | 18/20 | Datasheet, diccionario, 44/9 perfiles y gates; resta inconsistencia de ablación |
| Evaluación del modelo | 15/20 | Siete candidatos, ablación y Holm; resta selección posterior y dependencia por episodio |
| Evidencia operacional | 18/20 | FPR operativo, aislamiento, lead-time y disponibilidad corregida en la fuente F6 |
| Gobierno y automatización del repositorio | 12/20 | Licencias y generadores presentes; sin CI, tag/release ni dependencia de test declarada |

**Puntaje del datasheet: 88/100**, frente al diagnóstico anterior de 61/100.
La mejora proviene de identidad, responsables, licencia, contacto, catálogo,
diccionario, calidad, privacidad, publicación y mantenimiento. Pierde puntos por
el texto obsoleto sobre ablación, la ausencia de un protocolo canónico para
etiquetas ambiguas y los límites no resueltos de generalización.

## Alcance comprobado

- 57 archivos cambiados: 8 183 inserciones y 66 eliminaciones.
- Nueve commits, todos presentes en `origin/main` al iniciar la auditoría.
- Rama local y remota sincronizadas; árbol limpio antes de integrar habilidades.
- Repositorio público, rama predeterminada `main`, sin incidencias abiertas en
  la consulta pública del repositorio.
- No existe `.github/workflows/`; no hay CI versionado.
- No hay tags Git publicados.
- Suite local: **88 pruebas aprobadas** con `.venv/bin/python -m pytest -q`.
- Integridad: **13/13 hashes aprobados** con
  `sha256sum -c docs/dataset/SHA256SUMS`.

## Hallazgos ordenados por gravedad

### A-01 · Inferencia por ventanas correlacionadas — alto

`scripts/modeling/experiments/significancia_modelos.py` y la ablación aplican
McNemar a ventanas. El propio datasheet y múltiples bitácoras declaran que las
ventanas de un episodio son correlacionadas. McNemar exacto resuelve recuentos
pequeños, pero no elimina el supuesto de independencia entre pares.

**Riesgo:** los valores p pueden ser demasiado optimistas por pseudorreplicación.

**Mejora:** repetir el contraste con el episodio como unidad primaria o usar un
procedimiento pareado que preserve clusters. Una comprobación exploratoria por
episodio conservó la dirección favorable a OCSVM, pero no debe publicarse como
evidencia hasta versionar el script, el resultado y su protocolo.

### A-02 · Datasheet generado contradice la ablación ejecutada — alto

`docs/dataset/DATASHEET_MULTILAYER_V2.md` y
`scripts/entregables/generar_datasheet.py` afirman dos veces que la ablación no
se ejecutó. El commit `4d68c75` la ejecutó y publicó después en
`docs/fase04-modelado/07-ablacion-multicapa.md`.

**Riesgo:** el jurado puede concluir que el datasheet no se regenera desde el
estado vigente o que la mejora D-02 no está cerrada.

**Mejora:** cambiar primero el generador para consumir
`results/ablacion/ablacion-multicapa.json` y después regenerar el datasheet.

### A-03 · Disponibilidad antigua permanece en entregables — alto

La fuente vigente, `docs/fase07-validacion-final/02-resultados-f6.md`, corrige
el resultado a **58 corridas, 55 verificadas y cero caídas registradas**. Aún
aparece “100 % en 57 corridas” en:

- `docs/entregables/01-evaluacion-critica/informe-evaluacion-critica.md`;
- `docs/entregables/02-validacion-y-confiabilidad/informe-validacion-confiabilidad.md`;
- `docs/entregables/04-ficha-auditoria/ficha-auditoria.md`.

**Riesgo:** contradicción directa entre entregables sometidos al jurado.

### A-04 · Publicación de artefactos descrita de dos formas — medio

Los CSV, el manifiesto y siete `.joblib` ya están en Git y verifican sus hashes.
Sin embargo, el contexto anterior de agentes decía que “modelos y datasets”
permanecían fuera. También el comentario de `.gitignore` cifra el conjunto en
824 KB, aunque después se publicaron aproximadamente 5,7 MB con candidatos.

**Riesgo:** un agente puede omitir evidencia publicada o volver a afirmar que
los comparadores no existen.

### A-05 · Siete candidatos no equivalen a siete modelos únicos — medio

`if_uniform` e `if_exact_collapsed` comparten SHA-256 y predicciones. Los
documentos principales ya lo reconocen, pero cualquier resumen debe decir
“siete candidatos, seis objetos únicos”.

### A-06 · Sin CI ni entorno de pruebas plenamente declarado — medio

Las 88 pruebas pasan en `.venv`, pero no hay workflow y
`requirements-model.txt` no incluye `pytest`. Un clon limpio puede verificar
hashes, pero no reproducir la suite siguiendo una única instrucción publicada.

### A-07 · Metadato de licencia en GitHub — bajo

La API pública respondió `NOASSERTION` pese a existir `LICENSE` MIT y
`LICENSE-DATA` CC BY 4.0. El contenido legal está versionado; falta comprobar
por qué GitHub no reconoce la licencia principal.

## Cambios revisados que sí quedan respaldados

- Corrección 38→44 perfiles normales y catálogo 3→9 familias.
- Auditoría vigente 1 373/179 y cuatro gates adicionales.
- Diccionario de 28 variables con 27 efectivas.
- Publicación verificable de dataset, manifiesto y candidatos.
- Model card y system card separadas del datasheet.
- Ablación 14/20/28 sin promover post hoc la variante de 20.
- Comparación relativa favorable a OCSVM y ausencia de diferencia demostrada en
  FPR entre candidatos sobre el conjunto usado.
- Mapeo formal de entregables y preparación del artículo.

## Limitaciones de esta auditoría

La herramienta `gh` no está instalada. La API pública permitió comprobar el
repositorio y que no había incidencias abiertas, pero las consultas posteriores
de PR, Actions y protección de rama sufrieron timeouts de DNS. El historial Git
remoto, el contenido de `origin/main` y la ausencia de workflows locales sí se
verificaron. No se afirma que exista o no protección de rama.
