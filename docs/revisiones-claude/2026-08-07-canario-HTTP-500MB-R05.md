# Revisión técnica — HTTP-500MB/R05

Dictamen provisional: **ACEPTAR CON LIMITACIONES**.

La evidencia confirma HTTP 200/524.288.000 bytes, PCAP íntegro de 367.817
paquetes, cero drops y 98.5205 % de paquetes IPv4 entre 500–1500 bytes. EVE
contiene HTTP, fileinfo y stats; `TRUNCATED` a 102.400 bytes es el límite de
inspección de Suricata. Las cuatro ventanas de features son elegibles, pero
pertenecen al mismo episodio HTTP y no deben tratarse como muestras
independientes.

El auditor registra 125/145 campañas aceptadas, R05 9/29, 20 faltantes, 33
duplicados, 16 cruces y cero inválidas/advertencias. Se autoriza documentar y
publicar. Scoring, reentrenamiento y capturas en lote continúan bloqueados.

Claude Code no pudo emitir un dictamen autenticado en esta sesión (`Not
logged in`); esta nota deja explícita la revisión técnica reproducible de
Codex y queda pendiente de confirmación Claude.
