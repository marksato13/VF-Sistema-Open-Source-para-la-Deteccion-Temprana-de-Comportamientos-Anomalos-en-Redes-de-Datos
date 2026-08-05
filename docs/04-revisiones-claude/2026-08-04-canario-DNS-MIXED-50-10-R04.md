# Revisión Claude — DNS-MIXED-50-10/R04

Fecha: 4 de agosto de 2026. Revisor: Claude Code/Sonnet, sólo lectura. Dictamen: **ACEPTAR CON LIMITACIONES**.

## Autorización previa

Claude leyó el protocolo congelado, el contexto del proyecto y el cierre anterior. Con almacenamiento, NTP, aislamiento, servicios, rutas, DNS, generadores, identificadores, captura y contadores en `PASS`, autorizó exactamente una ejecución de `F1N-DNS-MIXED-50-10-R04`. Confirmó que pertenece a `validation`, no modifica `train`, no abre R05 y no permite scoring durante R04.

## Verificación posterior

Claude leyó el EVE completo por rangos, manifiesto, deltas, estados antes/después, cierre y resumen PCAP, transferencia, serie de recursos, extracción y los CSV R01–R04. Confirmó directamente:

- 50 líneas de salida válida y stderr vacío;
- 120 eventos DNS consecutivos como sesenta pares request/response, con cincuenta `NOERROR` seguidos de diez NXDOMAIN;
- EVE 130 = 120 DNS + 10 stats, sin `flow`, alerta ni anomalía;
- PCAP 120 capturados/recibidos, 120 parseados, 13,866 bytes y cero drops;
- 120 IPv4 menores de 500 bytes, media 85.35 y máximo 94;
- delta crudo Suricata `20165469-20165345=124`, cuatro más que PCAP, con drops/ifdrops en cero;
- 54 muestras y los rangos de CPU, RSS, memoria y carga publicados;
- `application_observations=70`, `packet_observations=120` y una fila elegible;
- igualdad decimal de las catorce features R01–R04, con diferencias sólo de campaña y timestamp;
- transferencia y hashes coherentes entre entradas, salida y bundles.

## Alcance de la revisión

Claude no encontró errores concretos ni pidió correcciones al cierre. No pudo reejecutar el auditor global porque la sesión tenía sólo la herramienta `Read`; registró esa cifra como limitación de su revisión, no como discrepancia. Codex sí ejecutó `build_f1_dataset.py --audit-only` desde el árbol limpio y confirmó 91/145, R04 4/29, 54 faltantes, veinte coincidencias, tres cruces, cero inválidas/advertencias y `current_git_dirty=false`.

Claude consideró legítimo el tercer vector `seen`: repite una firma determinista, pero los artefactos, hashes y timestamps R04 son independientes de R01–R03. El delta Suricata +4 permanece sin causa atribuida y evita afirmar identidad total entre todo el tráfico visto por Suricata y el PCAP causal; no invalida los 120 paquetes DNS íntegros.

## Decisión

**ACEPTADA CON LIMITACIONES.** Se autoriza únicamente el preflight —no la ejecución— de `F1N-PING-10-R04`. Continúan prohibidos scoring, calibración y acceso a R05 mientras R04 no alcance 29/29.
