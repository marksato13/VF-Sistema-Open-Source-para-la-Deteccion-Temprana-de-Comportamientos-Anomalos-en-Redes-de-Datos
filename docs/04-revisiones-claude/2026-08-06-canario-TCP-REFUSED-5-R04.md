# Revisión Claude — TCP-REFUSED-5/R04

Fecha: 6 de agosto de 2026. Dictamen final: **ACEPTAR CON LIMITACIONES**.

Claude autorizó una captura con cinco pares SYN–RST/ACK, medición temporal, cero drops, EVE sin L7 y auditoría sin scoring. Codex verificó directamente PCAP paquete a paquete, latencias, EVE, features, recursos, hashes y auditor.

La revisión posterior confirmó pares, tiempos, flags, features, recursos, hashes y progresión del auditor sin discrepancias. Mantuvo como límites la firma determinista `seen`, alcance específico del rechazo activo y delta +4 sin causa. Su sesión fue documental; Codex verificó la evidencia primaria.

Claude autoriza exclusivamente el preflight independiente `F1N-TCP-50M-R04`; no su captura ni scoring.
