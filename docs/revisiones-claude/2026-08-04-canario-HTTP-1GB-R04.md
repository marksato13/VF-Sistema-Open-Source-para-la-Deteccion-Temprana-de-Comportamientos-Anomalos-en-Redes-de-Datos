# Revisión Claude — HTTP-1GB/R04

Fecha: 4 de agosto de 2026. Dictamen: **ACEPTAR CON LIMITACIONES**.

Claude rechazó el primer cierre de preflight fragmentado, exigió una pasada única con timestamps y autorizó una captura después de que Codex repitiera todos los gates en un proceso continuo de 38.4 s.

En la revisión posterior contrastó manifest, parada PCAP, deltas, resumen de tamaños, EVE, salida del escenario, telemetría, CSV, reporte de extracción, ledger y sumas publicadas. Confirmó 1 GiB con HTTP 200, 751,698 paquetes, tres PCAP, cero drops, delta +6, 98.7115 % de cobertura pesada, flow real coincidente con el total PCAP, seis filas y los rangos de recursos. No encontró discrepancias numéricas.

Su sesión Read no pudo reejecutar el auditor ni revisar individualmente todos los registros EVE. Codex sí confirmó los 28 eventos —incluidos los dos flows previos y el flow real—, ambos bundles y el auditor limpio 97/145, R04 10/29, 48 faltantes, 21 coincidencias, cuatro cruces y cero inválidas/advertencias.

**ACEPTADA CON LIMITACIONES.** Se conservan los flows diferidos fuera de frontera, fileinfo truncado por inspección, ventanas correlacionadas y delta +6 sin causa atribuida. Sólo se autoriza preflight independiente de `F1N-HTTPS-10MB-R04`; no captura ni scoring.
