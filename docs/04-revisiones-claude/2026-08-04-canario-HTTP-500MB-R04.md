# Revisión Claude — HTTP-500MB/R04

Fecha: 4 de agosto de 2026. Dictamen: **ACEPTAR CON LIMITACIONES**.

Claude autorizó previamente una captura `validation` después de que Codex descartara un gate de bypass defectuoso y repitiera correctamente todos los controles vivos. En la revisión posterior contrastó manifest, ledger, CSV, contrato y filas R01–R03. Confirmó el estado `completed/validation`, hashes contractuales, 371,072 paquetes, dos PCAP, 554,952,099 bytes, cero drops, 18 eventos EVE, tres filas y ausencia de vector exacto contra `train`. No encontró discrepancias.

Su sesión de sólo lectura no pudo recalcular hashes, reejecutar el auditor ni resumir la telemetría cruda. Codex completó esos controles: ambos `SHA256SUMS` pasaron, el ledger dio `4fa6bb8d…`, las 92 muestras reprodujeron CPU 0–20.41 %, RSS 781,720 KiB, memoria 14,067,932–14,171,120 KiB y load1 0.04–0.46. El auditor confirmó 96/145, R04 9/29, 21 coincidencias, cuatro cruces y cero inválidas/advertencias; el estado limpio corresponde a la ejecución previa a redactar estos archivos y la repetición durante la edición marcó suciedad documental esperada.

Las limitaciones conservadas son el gate defectuoso respaldado por trazabilidad operativa pero sin artefacto propio, el fileinfo truncado por inspección, tres ventanas correlacionadas y el delta Suricata +4 sin causa atribuida. **ACEPTADA CON LIMITACIONES.** Sólo se autoriza preflight independiente de `F1N-HTTP-1GB-R04`; no captura ni scoring.
