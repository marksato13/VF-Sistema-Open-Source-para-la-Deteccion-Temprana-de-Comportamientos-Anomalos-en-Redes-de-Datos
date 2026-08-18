# Revisión Claude — canario HTTPS 100 MB F1

Fecha: 22 de julio de 2026. Herramienta: Claude Code 2.1.217. Modelo: Haiku. Alcance: resumen técnico del bundle, sin edición ni operación del laboratorio.

## Dictamen

El primer intento agotó su turno sin contenido y no cuenta como revisión. El segundo emitió **ACEPTAR CONDICIONADO** y autorizó avanzar a HTTPS 500 MB si se mantienen cero drops, PCAP íntegro, filas elegibles, cobertura de paquetes grandes y hashes remotos/locales.

Claude consideró validado el escalamiento 10× respecto de HTTPS 10 MB: 74,858 paquetes, 96.9502 % en 500–1500 bytes, dos filas elegibles, TLS 1.3 y recursos holgados.

## Riesgos aceptados

1. El certificado autofirmado y `--insecure` no representan validación PKI productiva.
2. Una sola sesión por campaña ofrece diversidad TLS limitada.
3. HTTPS cifra la semántica HTTP; la completitud se confirma en el Cliente y PCAP.

## Correcciones

Claude mencionó un `fileinfo` truncado, pero esta campaña no produjo `fileinfo`: Suricata no inspecciona el cuerpo HTTPS. También afirmó que solo estaban disponibles L3/L4; el evento TLS sí produce una señal L7 pasiva, `tls_session_rate_60s=1/60`. No existe, en cambio, visibilidad del método, estado o contenido HTTP.

Los dos flows mDNS de la evidencia cruda nacieron durante la quietud, quedaron fuera del filtro PCAP y no son consumidos por el extractor. No alteran el dictamen.

## Límite

Se demuestra volumen HTTPS legítimo, sesión TLS observable, captura íntegra y ausencia de pérdida. No se demuestra confianza de certificado, diversidad de PKI, contenido HTTP ni comportamiento de múltiples sesiones.
