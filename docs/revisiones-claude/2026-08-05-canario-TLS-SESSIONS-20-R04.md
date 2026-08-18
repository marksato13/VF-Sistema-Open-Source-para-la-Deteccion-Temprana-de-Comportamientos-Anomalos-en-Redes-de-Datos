# Revisión Claude — TLS-SESSIONS-20/R04

Fecha: 5 de agosto de 2026. Dictamen final: **ACEPTAR CON LIMITACIONES**.

Claude autorizó una única captura después del preflight continuo y exigió veinte sesiones secuenciales, veinte respuestas HTTP activas, veinte eventos TLS pasivos, puertos/fingerprints verificables, PCAP íntegro y ausencia de scoring. Codex comprobó directamente manifest, escenario, PCAP, EVE completo, CSV, recursos, bundles y auditor global.

La revisión posterior no encontró discrepancias numéricas ni aritméticas. La evidencia satisface esos controles: veinte HTTP 200, veinte puertos origen, veinte TLS 1.3, PCAP 433/433/433, cero drops y dos filas nuevas correlacionadas por episodio. Se conservan como limitaciones la homogeneidad de los fingerprints, la ausencia de concurrencia o diversidad PKI, el delta Suricata +2 sin causa y el alcance documental de cualquier comprobación que Claude no pueda realizar sobre `/srv/ppi-evidence`.

Claude observó que el resumen no conserva un timestamp individual por cada gate del preflight de 21 segundos. Codex verificó la salida continua y el resultado de todos los gates antes de la captura, pero no se sustituye esa observación por una inferencia: queda como mejora obligatoria persistir el log crudo desglosado en las campañas siguientes.

Claude autoriza exclusivamente el preflight independiente `F1N-HTTP-MULTI-1-R04`; no otra captura TLS ni scoring.
