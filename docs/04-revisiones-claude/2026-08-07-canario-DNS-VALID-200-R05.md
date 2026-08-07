# Revisión Claude — DNS-VALID-200/R05

Fecha: 7 de agosto de 2026. Dictamen final: **ACEPTAR CON LIMITACIONES**.

## Bloqueo preventivo de almacenamiento

Claude bloqueó el primer comando propuesto porque omitía
`PPI_ARTIFACTS_ROOT`. Aunque no identificó un artefacto persistido como origen
del JSON `storage=false` que citó, sí descubrió una divergencia real: el
preflight y el orquestador no comparten el mismo valor por defecto.

Codex repitió el dry-run con el volumen explícito y confirmó ambos storage
gates en `true`, marker/mountpoint válidos y ausencia del ID. Claude releyó el
log, cerró `R05-01` y autorizó exactamente una captura sin `--pilot`, reintento
ni scoring. La ejecución real conservó esa variable.

## Revisión postcaptura

Claude leyó en modo restringido preflight, manifest, deltas, ledger, CSV,
reporte de extracción, EVE completo, bundles como texto, recursos y controles
PCAP. Corroboró:

- 200 solicitudes y 200 respuestas DNS `NOERROR` en 4.203137 s;
- PCAP 400/400/400 de 46,024 bytes y cero drops;
- EVE 410 = 400 DNS + 10 stats, sin flows de probes;
- una ventana `[05:08:20, 05:08:30)` con los 400 paquetes;
- 198 puertos origen porque `45430` y `48222` se reutilizaron;
- `flow_attempt_count=198` y `dns_query_count=200` como semánticas L4/L7
  distintas, no pérdida;
- delta Suricata 404 frente a PCAP 400, recurrente y no atribuido;
- CPU 0.00–2.98 %, RSS 782,504 KiB y ausencia de presión observada.

El revisor comparó R01–R05 y confirmó que las repeticiones previas suman
también 400 paquetes, pero cruzan bordes UTC y producen dos filas. R05 cayó en
una sola ventana y no introduce un vector exacto repetido.

Claude no pudo abrir el PCAP binario, recalcular SHA-256 ni reproducir el
auditor global; Codex hizo esas verificaciones. Se corrigieron dos excesos del
texto: el resultado correcto es 200 solicitudes + 200 respuestas, y la ausencia
de impacto observado del delta +4 en esta campaña no equivale a riesgo general
nulo.

Claude autorizó únicamente documentar y publicar. El siguiente preflight y
todo scoring quedaron fuera de su autorización y requieren una decisión
separada del flujo de trabajo.
