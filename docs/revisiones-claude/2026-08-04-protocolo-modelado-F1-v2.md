# Revisión adversarial del protocolo de modelado F1-v2

Fecha: 4 de agosto de 2026. Revisor: Claude Code/Sonnet, sólo lectura. Implementación y comprobación: Codex.

## Alcance

Claude leyó el protocolo `PM-F1-v1`, la política R04/R05, el diccionario G5, la matriz G6, los requisitos ML, el verificador de pesos y sus pruebas. Se le pidió cuestionar fuga, cuantil, unidad experimental, parámetros, escalado, ponderación, expansión, comparadores y apertura de R05 sin editar archivos.

Una primera consulta sin acceso de lectura produjo la afirmación falsa de que G6 no existía. Esa salida fue descartada íntegramente. Las dos revisiones válidas se hicieron después con permiso local exclusivo `Read`; Claude no tuvo herramientas de edición ni ejecución.

## Primer dictamen válido

Claude encontró dos bloqueos corregibles:

1. `n` en la regla `k=floor(0.05*n)` no decía expresamente si representaba ventanas o campañas, pese a reconocer correlación intraepisodio.
2. La equivalencia entre pesos uniformes y `1/n_filas_campaña` estaba documentada desde una prueba efímera, sin script versionado que permitiera reproducirla.

No encontró fuga temporal o de partición ni uso de R04/R05 para seleccionar features o hiperparámetros. Consideró correctas la separación train/validation/test, la prohibición de búsqueda post hoc, el uso de `score_samples`, la decisión de no usar el `offset_` de contamination y la conservación atómica por campaña.

## Correcciones y evidencia

- `PM-F1-v1` define ahora `n = ventanas elegibles R04`, mantiene alerta estricta `score < threshold` y obliga a reportar cuántas campañas originan la cola y las alertas. La incidencia por campaña se informa separada y no se presenta como controlada al 5 %.
- `scripts/analysis/verify_if_weighting.py` reutiliza primero el auditor oficial, exige exactamente las 87 celdas train y compara scores y estructuras de 500 árboles con/sin pesos en tres seeds.
- `tests/test_if_weighting_verification.py` prueba pesos, expansión MCM, unidad por ventanas y empates conservadores.
- La ejecución real sobre train verificó 87 campañas, 224 ventanas, conteos de 1/2/3/4/6/7 filas, MCM 84 y expansión de 7,308 registros.
- Para seeds `20260804`, `7` y `42`, la diferencia máxima de scores fue cero y las estructuras de árboles fueron idénticas. La cola train con `k=11` abarcó siete u ocho campañas; es diagnóstico previo, no predicción de R04.
- Las 43 pruebas pasaron con Python del sistema y con `.venv`.

## Segundo dictamen válido

Claude declaró resueltos los problemas metodológicos. No agregó otro bloqueo científico. Su condición restante fue procedimental: publicar protocolo, código, pruebas, requisitos y esta revisión en un commit sin secretos; verificar versiones; ejecutar el escaneo; y repetir el preflight justo antes de R04.

Como mejora no bloqueante solicitó registrar hash del verificador y commit. Se incorporaron `verifier_sha256`, `requirements_sha256`, `git_commit` y `git_dirty` a su JSON.

## Limitaciones conservadas

- `alpha=0.05` es un operating point experimental, no un SLA ni una garantía conformal.
- El umbral se calibra por ventana conforme a la unidad primaria congelada; la tasa por campaña puede diferir.
- Con 224 filas, `max_samples=auto` entrega las 224 a cada árbol principal; la diversidad proviene de cortes/features aleatorios.
- El soporte train de errores HTTP y NXDOMAIN es escaso. Las campañas normales R04/R05 medirán falsos positivos, pero no sustituyen F3/F4 para medir detección.
- La expansión por campaña es una sensibilidad secundaria y altera multiplicidades; no reemplaza el resultado principal.
- LOF y OCSVM son comparadores predefinidos, no candidatos elegidos después de observar validation/test.

## Decisión

**APTO METODOLÓGICAMENTE PARA R04, CON GATE OPERATIVO.** La publicación del commit, el escaneo de secretos, las versiones exactas y un preflight fresco son requisitos de ejecución. R04 sólo acumulará evidencia; ningún modelo se puntuará hasta completar sus 29 campañas.
