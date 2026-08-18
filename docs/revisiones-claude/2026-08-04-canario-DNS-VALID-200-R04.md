# Revisión Claude — DNS-VALID-200/R04

Fecha: 4 de agosto de 2026. Revisor: Claude Code/Sonnet, acceso local de sólo lectura. Dictamen: **ACEPTAR CON LIMITACIONES**.

## Alcance y resultado

Claude contrastó `99-canario-DNS-VALID-200-R04.md` con manifiesto, deltas, EVE, PCAP summary/cierre, estados y serie del Sensor, salida, extracción, CSV, ledger, esquema y política R04. Confirmó que no hay bloqueo en conteos, ventanas causales, partición ni prohibición de scoring.

Verificó 410 EVE: diez stats y 400 DNS; 200 requests, 200 responses y 100 % `NOERROR`. El puerto del Servidor fue 53 y no observó reutilización de los puertos efímeros revisados. Aceptó la explicación del borde: 274/126 paquetes equivalen a 137/63 pares; la segunda fila conserva 200 intentos en 30 s y queries en 60 s, mientras `flow_attempt_rate_10s=6.3` usa los 63 intentos recientes.

Claude mantuvo la conclusión de que R04 no reproduce vector exacto de train en estas dos filas y no reporta scores/umbrales. El próximo paso quedó limitado al preflight independiente de `DNS-MIXED-20-2/R04`.

## Límites de la sesión y cobertura de Codex

Claude no tuvo Bash y no pudo ejecutar `sha256sum -c`; además, su lector cubrió aproximadamente 70 % de los puertos antes de inferir que el resto conservaba estructura. No se ocultan esas limitaciones.

Codex verificó ambos bundles completos y la copia PCAP remoto/local. Un parser sobre los 400 paquetes leyó las 200 transacciones y confirmó 200 puertos Cliente distintos; por tanto, la limitación corresponde a la herramienta del revisor y no queda como hueco de evidencia de la campaña.

El auditor oficial reportó 89 candidatos aceptados, R04 2/29, 56 faltantes, cero inválidas/advertencias, 18 coincidencias y un cruce train↔validation. El estado dirty procedía únicamente del borrador documental posterior a una captura con Git limpio.

## Decisión

**ACEPTADA CON LIMITACIONES.** Se conservan Suricata+4 no atribuido, dependencia de fase UTC y dos ventanas correlacionadas. Siguiente: sólo preflight de `F1N-DNS-MIXED-20-2-R04`; no lote ni scoring.
