# Revisión Claude — DNS-MIXED-20-2/R04

Fecha: 4 de agosto de 2026. Revisor: Claude Code/Sonnet, sólo lectura. Dictamen: **ACEPTAR CON LIMITACIONES**.

## Verificación

Claude contrastó documento, EVE completo, manifiesto/deltas, PCAP, estados/serie del Sensor, extracción, CSV, ledger, esquema y extractor. Confirmó:

- 22 requests y 22 responses en orden: veinte `NOERROR` y dos NXDOMAIN al final;
- PCAP 44/44, 5,092 bytes y cero drops;
- EVE 54 = 44 DNS + 9 stats + 1 flow;
- `dns_nxdomain_ratio_60s=2/22=0.09090909`;
- 24 observaciones internas = 22 queries + 2 marcadores NXDOMAIN, no 24 transacciones;
- delta Suricata 44 igual al PCAP, sin errores ni alertas;
- una fila con 22 intentos, lo que demuestra que el flow diferido no añadió un intento.

## Decisión sobre el flow diferido

El evento registra tráfico real a `20:56:10`, mientras `pcap-start.json` verificó la captura desde `21:00:40`; Suricata lo emitió a `21:01:12` por timeout. Por tanto, quedó dentro del slice EVE por hora de emisión, pero ocurrió antes del PCAP. El escenario empezó a `21:01:40`, y sus 44 paquetes/22 transacciones explican por completo la fila.

Claude concluyó que esto no obliga a rechazar: no hubo exclusión retrospectiva de paquetes ni alteración numérica; el evento ajeno permanece visible como limitación. El slice EVE no puede describirse como exclusivamente causal.

## Corrección a la respuesta del revisor

Claude citó el mismo precedente en `MIXED-LIGHT/R01`, R02 y R03. La búsqueda documental sólo lo demuestra explícitamente para `MIXED-LIGHT/R03` (`96-canario-MIXED-LIGHT-R03.md`). Se corrige el alcance sin afectar el dictamen: esta campaña se sostiene en sus propios timestamps, PCAP y conteos, no en la cantidad de precedentes.

La igualdad exacta R01–R04 tampoco fue recalculada por Claude; Codex sí comparó las catorce columnas con normalización decimal y encontró las tres filas train coincidentes. El auditor limpio registró 19 coincidencias globales y dos cruces.

## Decisión

**ACEPTADA CON LIMITACIONES.** Siguiente autorizado: sólo preflight independiente de `F1N-DNS-MIXED-50-10-R04`. No lote ni scoring durante R04.
