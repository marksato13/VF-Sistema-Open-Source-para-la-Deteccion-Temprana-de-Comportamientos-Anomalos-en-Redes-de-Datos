# Revisión Claude — calibración de búfer HTTP-C8

Fecha: 23 de julio de 2026. Herramienta: Claude Code 2.1.217. Modelo: Haiku. Alcance: revisión adversarial de la calibración y condiciones del retry, sin edición ni operación.

## Dictamen

Claude consideró que la calibración con cero drops justifica preparar un retry, condicionado a documentar la cadena de custodia, archivar el intento fallido sin alterarlo, auditar el ensamblador y repetir el preflight.

Confirmó que una sola calibración no garantiza cero drops futuros y que la rotación 512 MB × 4 solo queda validada para las condiciones observadas de C8.

## Condiciones aceptadas

- publicar hashes y métricas de `CAL-G6-HTTP-C8-R01`;
- preservar propósito `calibration` y partición `excluded_calibration`;
- mantener el intento rechazado como evidencia histórica;
- archivar fuera de las raíces activas antes de liberar el ID canónico;
- exigir cero drops en el retry;
- no cambiar rotación antes del retry;
- repetir NTP, aislamiento, rutas, servicios, almacenamiento y Suricata.

## Correcciones al dictamen

Después de archivar el fallido, el ensamblador debe mostrar **15 aceptadas, 0 inválidas y 130 faltantes**, porque C8 ya estaba incluido entre las 130 celdas faltantes aun cuando su intento aparecía inválido. Tras un retry exitoso debe mostrar 16/0/129.

No se necesita modificar el ensamblador para ignorar el archivo: los artefactos runtime viven en `/srv/ppi-evidence/artifacts`, fuera de Git, y el auditor solo consume las raíces activas `campaigns/`, `features/` y `g6-ledger/`.

El comando propuesto por Claude con `--preflight-only` no existe. El preflight reproducible combina `run_matrix_profile.py --dry-run` con los gates NTP, aislamiento, rutas, servicios, almacenamiento, captura y Suricata ya usados.

La métrica de CPU de 61.71 % no significa que el Sensor haya consumido 61.71 % de sus seis vCPU agregadas. Se conserva como dato del proceso, sin convertirla en gate.

La suite de 29 pruebas sí fue ejecutada y pasó antes de publicar el cambio de búfer.

## Autorización

**RETRY AUTORIZADO CONDICIONALMENTE, NO EJECUTADO.** Falta versionar y probar el procedimiento de archivado, realizar el movimiento recuperable, validar el ensamblador y repetir el preflight.
