# Revisión Claude — canario PING-10 F1

Fecha: 27 de julio de 2026. Herramienta: Claude Code 2.1.217. Modelo: Haiku. Alcance: revisión técnica sin operación, herramientas ni edición.

## Dictamen consolidado

Claude emitió **ACEPTAR CON LIMITACIONES** para `F1N-PING-10-R01`. Después de las correcciones, quedaron como aportes válidos:

- diez solicitudes y diez respuestas son veinte paquetes y un intento canónico ICMP;
- `unique_dst_ip_ratio_30s=1` procede de un destino sobre un intento y no clasifica por sí mismo el episodio;
- SID `1000001` es una regla deliberada de telemetría, `allowed` demuestra ausencia de bloqueo y no prueba detección de ataque;
- un episodio, un par, intervalo fijo, tamaño constante y una fila no establecen una distribución;
- el modelo todavía no está entrenado.

## Errores y correcciones

La primera respuesta:

- llamó “serie de diez paquetes” a diez solicitudes más diez respuestas;
- descompuso 84 bytes como 20 IP + 8 ICMP + 48, cuando el payload es 56;
- describió 9.190037 s como primer→último paquete, aunque es primera→última solicitud;
- calificó el RTT sin umbral;
- convirtió un ratio unitario en evidencia de ausencia de escaneo;
- inventó pesos de 5–8 %, 6.9 %, “10 bytes ICMP” e impacto futuro en Isolation Forest;
- usó la partición inexistente `train_benign` y llamó calibración a una campaña `experiment/train`;
- propuso comandos `tcpdump` con opciones y filtros inválidos.

La segunda respuesta confundió los cinco paquetes adicionales de Suricata con eventos `stats`, escribió `unique_dst_ip_ratio_10s` en vez de `_30s`, llamó L3/L4 al intento ICMP y predijo pérdida futura. La tercera contaminó la revisión con `1.260866 s` de la campaña DNS anterior, redujo el episodio a cinco intentos y cambió el SID a `2260049`.

La cuarta respuesta reprodujo los datos vinculantes: un episodio, un par, diez solicitudes dentro de un intento canónico ICMP, cinco paquetes Suricata sin identificar, SID `1000001` no productivo, 28 aceptadas y siguiente `PING-100/R01`.

## Límites del dictamen

- EVE contiene diez alertas y once stats; no veinticinco eventos de paquete.
- La diferencia Suricata 25 frente a PCAP 20 permanece sin clasificar.
- Una alerta de prueba permitida no evalúa un ruleset productivo.
- `unique_dst_port_ratio_30s=0` significa ausencia de denominador TCP/UDP.
- Una fila oficial pequeña sigue siendo `experiment/train`, no calibración.
- No se atribuye peso ni desempeño antes de entrenar el modelo.

Dictamen final: **ACEPTAR CON LIMITACIONES**. Siguiente: `PING-100/R01`, con preflight completo.
