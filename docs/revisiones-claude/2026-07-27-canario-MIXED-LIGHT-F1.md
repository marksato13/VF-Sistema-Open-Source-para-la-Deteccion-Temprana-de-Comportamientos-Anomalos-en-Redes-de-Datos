# Revisión Claude — canario MIXED-LIGHT F1

Fecha: 27 de julio de 2026. Herramienta: Claude Code 2.1.217. Modelo: Haiku. Alcance: resumen técnico, sin operación, herramientas ni edición.

## Resultado

Claude emitió **ACEPTAR CON LIMITACIONES** para `F1N-MIXED-LIGHT-R01` al revisar:

- HTTP 200 con 104,857,600 bytes completos;
- iperf3 con 62,521,344 bytes en ambos extremos, aproximadamente 50 Mbit/s y dos retransmisiones;
- veinte solicitudes y veinte respuestas DNS `NOERROR`;
- solapamiento triple de 0.518239 s y HTTP+iperf3 de aproximadamente 10 s;
- PCAP de 122,802 paquetes y 177,537,599 bytes, sin drops;
- 94.3731 % de paquetes entre 500 y 1500 bytes;
- señales L3/L4/L7 en tres filas autocorrelacionadas;
- ensamblador con 24 aceptadas, 0 inválidas y 121 faltantes.

## Hallazgos sobre la revisión

La primera respuesta confundió los 122,802 paquetes con un PCAP de “122 MB”; el tamaño real es 177,537,599 bytes. También llamó “MSS completo” a todos los IPv4 de 1500 bytes sin demostrarlo, extendió el episodio a 20.5 s, trató `fileinfo TRUNCATED` como límite de toda la inspección HTTP y relacionó indebidamente retransmisiones con drops.

La segunda respuesta corrigió esos puntos, pero describió “único puerto destino = 3” en lugar de tres puertos distintos, declaró CPU “dentro de límites” sin umbral y afirmó cero pérdida TCP/red cuando la evidencia acredita entrega de bytes y cero drops de captura, no ausencia universal de pérdida.

La tercera consulta incluyó nuevamente todos los datos, pero Claude respondió que no podía revisar sin acceder a archivos. El fallo de contexto quedó registrado y esa respuesta se descartó.

## Límites del dictamen

- Las dos retransmisiones tienen causa no determinada y no son drops de captura.
- `fileinfo=102400/TRUNCATED` limita seguimiento del archivo; curl y PCAP acreditan la descarga.
- Existe un solo destino IP; la diversidad L3 de este episodio es limitada.
- Las tres filas comparten un episodio y no forman SLA ni repeticiones.
- La campaña ejercita L3/L4/L7, pero no valida por sí sola todo el modelo.
- Isolation Forest final aún no está entrenado.

Dictamen depurado por Codex: **ACEPTAR CON LIMITACIONES**. Siguiente: `DNS-VALID-10/R01`, tras auditar gaps y ejecutar preflight.
