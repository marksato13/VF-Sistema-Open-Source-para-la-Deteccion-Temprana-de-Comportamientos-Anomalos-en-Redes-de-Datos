# Revisión técnica — MIXED-LIGHT/R05

Dictamen provisional: **ACEPTAR CON LIMITACIONES**.

La campaña confirma HTTP 200/104.857.600 bytes, iperf3 a 50 Mbit/s, 20
respuestas DNS, PCAP íntegro 123.386/123.386/123.386 y cero drops. EVE conserva
DNS, HTTP, fileinfo, alert, anomaly y stats; el registro de alerta se mantiene
para trazabilidad. Las tres filas combinan señales L3, L4 y L7 en un episodio
concurrente, por lo que deben tratarse como observaciones autocorrelacionadas.

Auditoría: 137/145 campañas aceptadas, R05 23/29, 8 faltantes, 36 duplicados,
19 cruces y cero inválidas/advertencias. Los bundles verificaron sus SHA-256.
Se autoriza documentar y publicar; scoring y reentrenamiento siguen bloqueados
hasta completar R05 y revisar la duplicación entre particiones.

Claude Code no pudo autenticarse (`Not logged in`); esta nota representa la
revisión técnica reproducible de Codex y queda pendiente de confirmación.
