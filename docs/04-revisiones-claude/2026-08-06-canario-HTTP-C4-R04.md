# Revisión Claude — HTTP-C4/R04

Fecha: 6 de agosto de 2026. Dictamen final: **ACEPTAR CON LIMITACIONES**.

Claude autorizó una captura sólo después de corregir tres condiciones: `fileinfo TRUNCATED` es esperado, no existen archivos cliente para hashear y la tasa agregada es descriptiva. Codex verificó directamente transferencias, solapamiento, PCAP, EVE, features, recursos, hashes y auditor.

La revisión posterior confirmó suma de ventanas, cobertura pesada, tasa agregada, delta, `fileinfo`, separación de preflights y progresión del auditor. No encontró discrepancias y mantuvo como límites un solo Cliente, tres ventanas correlacionadas y delta +5 sin causa. Su sesión fue documental y sólo lectura; Codex verificó la evidencia primaria.

Claude autoriza exclusivamente el preflight independiente `F1N-HTTP-C8-R04`; no su captura ni scoring.
