# Revisión Claude — canario HTTPS 1 GB F1

Fecha: 22 de julio de 2026. Herramienta: Claude Code 2.1.217. Modelo: Haiku. Alcance: revisión adversarial del resumen técnico, sin editar ni operar.

## Dictamen

Claude emitió **ACEPTAR**. Validó los tres PCAP, 757,999 paquetes, cero pérdidas, 98.0435 % en el rango objetivo, TLS 1.3, siete filas elegibles, ausencia de ruido EVE y margen de recursos.

## Ventana de cierre

Claude consideró defendible la séptima fila de cuatro paquetes. Es la cola ACK/FIN posterior a la transferencia; `large_ip_ratio_10s=0` y `tls_session_rate_60s=0` son coherentes con una ventana de baja actividad cuyo handshake ya expiró del horizonte. Conservarla evita seleccionar solo ventanas de alta carga.

## Sesión y certificado

Una sesión TLS única cumple el contrato del perfil de volumen. La matriz separa la diversidad temporal en `TLS-SESSIONS-20`. El certificado autofirmado sigue siendo una limitación conocida y no se presenta como PKI productiva.

## Corrección numérica

Claude estimó aproximadamente 157 Mbit/s. El cálculo reproducible `1,073,741,824 × 8 / 51.021313 / 1,000,000` produce 168.36 Mbit/s. Ambos quedan debajo de 200 Mbit/s, pero se conserva el valor exacto para la defensa.

## Próximo paso

Claude confirmó el orden: `HTTP-404-5/R01` para normalidad de errores HTTP y, posteriormente, `TLS-SESSIONS-20/R01` para churn TLS.
