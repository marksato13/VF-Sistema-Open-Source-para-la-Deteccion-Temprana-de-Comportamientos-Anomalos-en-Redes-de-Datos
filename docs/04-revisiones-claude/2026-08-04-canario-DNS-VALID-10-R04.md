# Revisión Claude — DNS-VALID-10/R04

Fecha: 4 de agosto de 2026. Revisor: Claude Code/Sonnet con acceso local de sólo lectura. Estado: **ACEPTADA CON LIMITACIONES CONFIRMADA**.

## Alcance

Claude contrastó `98-canario-DNS-VALID-10-R04.md` con manifiesto, deltas, EVE completo, PCAP summary, inicio/cierre de captura, estados Suricata, serie de recursos, salida del escenario, extracción, CSV, ledger y bundles SHA declarados. También leyó la política R04/R05 y `PM-F1-v1`. No editó ni ejecutó comandos.

## Verificaciones

- Confirmó 29 EVE: veinte DNS y nueve stats; diez pares request/response `NOERROR`, todos `server.ppi.lab→10.30.0.10`.
- Confirmó PCAP 20/20/20, 2,324 bytes, cero drops, media IPv4 85 y máximo 87.
- Recalculó Suricata 20,164,870 − 20,164,846 = 24; la diferencia +4 frente al PCAP queda sin causa atribuida y los contadores de error permanecen en cero.
- Confirmó 53 filas de recursos, CPU 0–1.51 %, RSS 781,720 KiB, memoria y load1 citados.
- Confirmó propósito `experiment`, partición `validation`, repetición 4 y tiempos 60/70/9/30 s.
- Confirmó 20 observaciones de paquete, diez de aplicación, una fila elegible y los valores decimales citados.
- Verificó que el cierre no contiene score, threshold ni selección de modelo; la coincidencia train↔validation se preserva y reporta sin tratarla como fuga operacional.

## Observación aplicada

Claude señaló que el bloque mostraba ocho de catorce features y podía parecer un vector completo. Se cambió la introducción para declararlo expresamente como selección; el CSV sigue siendo la fuente contractual de las catorce.

## Límites de la revisión

La sesión de Claude no ejecutó Bash, por lo que no recomputó hashes ni el auditor agregado y no observó directamente el preflight. Codex sí ejecutó ambos bundles `sha256sum -c`, el auditor oficial y los gates NTP/SSH/NIC/bypass antes de solicitar la revisión. El auditor produjo 88/145, R04 1/29, cero inválidas/advertencias, 18 coincidencias entre campañas y un cruce train↔validation.

## Decisión

**ACEPTADA CON LIMITACIONES.** Siguiente autorizado: sólo preflight independiente de `F1N-DNS-VALID-200-R04`. No se autoriza lote ni scoring antes de R04 29/29.
