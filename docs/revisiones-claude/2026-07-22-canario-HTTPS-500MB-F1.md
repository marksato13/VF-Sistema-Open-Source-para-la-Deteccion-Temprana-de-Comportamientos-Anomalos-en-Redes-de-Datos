# Revisión Claude — canario HTTPS 500 MB F1

Fecha: 22 de julio de 2026. Herramienta: Claude Code 2.1.217. Modelo: Haiku. Alcance: revisión del resumen técnico, sin edición ni operación.

## Dictamen

Claude emitió **ACEPTAR CONDICIONADO**. Validó transferencia, dos PCAP íntegros, 371,438 paquetes, cero pérdidas, 97.7033 % en el rango objetivo, una sesión TLS 1.3, tres filas elegibles y recursos holgados.

Identificó como límites el certificado autofirmado, una sola negociación TLS y la baja diversidad de huellas criptográficas.

## Condición y decisión técnica

Claude propuso forzar dos o tres sesiones concurrentes en `HTTPS-1GB/R01`. No se aplica dentro de esa celda porque cambiaría su lista de argumentos y rompería el contrato congelado de matriz, hash y comparación por volumen.

La intención se satisface sin mezclar variables mediante el perfil oficial `TLS-SESSIONS-20/R01`, que se ejecutará por separado. `HTTPS-1GB` seguirá midiendo una transferencia persistente. Concurrencia y churn no deben incorporarse silenciosamente a una campaña de tamaño.

## Límite

El bundle demuestra normalidad HTTPS pesada en una sesión TLS 1.3, captura completa y operación sin drops. No demuestra diversidad de certificados, clientes, JA3/JA4 o múltiples sesiones. Esa limitación no se oculta ni se etiqueta como ataque.
