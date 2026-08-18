# Revisión Claude — TLS-SESSIONS-20 R02

Fecha: 28 de julio de 2026. Claude Code 2.1.217, modelo Haiku.

Claude emitió **ACEPTAR CON LIMITACIONES**. Reconoció veinte resultados HTTP 200, veinte TLS, PCAP íntegro, cero drops, una fila elegible, independencia respecto a R01 y falta de diversidad criptográfica. Autorizó `HTTP-MULTI-1/R02`.

Se conservaron:

- veinte sesiones secuenciales de un Cliente a un Servidor;
- mismo fingerprint por configuración homogénea;
- baja cobertura pesada propia de respuestas pequeñas;
- certificado autofirmado y `--insecure` solo de laboratorio;
- una fila R02 frente a dos R01 por fase UTC.

Se corrigieron o descartaron:

- 430/430 es capturado/parseado, no capturado/esperado;
- `large_ip_ratio_10s` sí es visible en PCAP aunque HTTP esté cifrado;
- los tiempos C2/C4 pertenecen a campañas distintas y no prueban esta;
- no se verificó negociación o ausencia de HTTP/2/pipelining;
- la distribución de tamaños se describe, no se declara “típica” universal;
- las métricas de recursos no se califican contra umbrales inexistentes.

**Dictamen consolidado: ACEPTADA CON LIMITACIONES.** Estado global 45/145; R02 16/29.
