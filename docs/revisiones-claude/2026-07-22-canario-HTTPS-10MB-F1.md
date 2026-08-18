# Revisión Claude — canario HTTPS 10 MB F1

Fecha: 22 de julio de 2026. Herramienta: Claude Code 2.1.217. Modelo: Haiku. Alcance: revisión adversarial del resumen del bundle; sin edición ni operación del laboratorio.

## Dictamen

Claude emitió **ACEPTAR CONDICIONADO**. Reconoció integridad del PCAP, cero pérdidas, 95.4127 % de paquetes en el rango objetivo, evento TLS 1.3, dos filas elegibles y aceptación del ensamblador.

Las condiciones fueron:

1. declarar que el certificado es autofirmado y el Cliente usa `--insecure`;
2. no equiparar HTTPS de laboratorio con diversidad TLS de producción;
3. no afirmar inspección HTTP/fileinfo dentro del cifrado;
4. ampliar sesiones, servidores o certificación en fases futuras si se requiere diversidad L7 criptográfica.

Todas quedan incorporadas en la documentación de campaña. La matriz F1 vigente conserva este escenario como normalidad HTTPS mínima; cualquier ampliación de certificados o SNI será un perfil suplementario versionado, no una mutación retroactiva de las campañas ya capturadas.

## Correcciones al texto del revisor

- El flow IPv6 link-local se emitió a las `21:55:57`, durante la campaña que terminó a las `21:57:17`; no después.
- El extractor no “descarta L7 cifrada”: consume el evento TLS y produce `tls_session_rate_60s=1/60`. Lo que descarta es `event_type=flow` y lo que no puede observar es HTTP dentro de TLS.

Estas correcciones no cambian el dictamen.

## Límite aceptado

Puede afirmarse transferencia de 10 MiB confirmada por el Cliente, PCAP íntegro, sesión TLS 1.3 observable, comportamiento L3/L4 y tasa de sesión TLS. No puede afirmarse validación de cadena confiable, contenido HTTP inspeccionado ni representatividad completa del ecosistema TLS.
