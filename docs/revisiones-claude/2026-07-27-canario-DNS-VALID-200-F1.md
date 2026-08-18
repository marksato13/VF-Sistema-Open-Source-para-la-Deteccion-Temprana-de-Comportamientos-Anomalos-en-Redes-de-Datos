# Revisión Claude — canario DNS-VALID-200 F1

Fecha: 27 de julio de 2026. Herramienta: Claude Code 2.1.217. Modelo: Haiku. Alcance: resumen técnico, sin operación, herramientas ni edición.

## Resultado

Claude emitió **ACEPTAR CON LIMITACIONES** para `F1N-DNS-VALID-200-R01`:

- 200 consultas `server.ppi.lab/A` produjeron 200 respuestas `10.30.0.10`, todas `NOERROR`;
- el PCAP conserva 400/400 paquetes, 46,024 bytes y cero drops;
- EVE contiene 400 DNS, diez `stats` y un flow IPv6 fuera de alcance;
- dos filas elegibles pertenecen a una sola ráfaga;
- hashes y ensamblador pasaron con 26 aceptadas, 0 inválidas y 119 faltantes.

## Correcciones de la revisión

La primera respuesta llamó “TCP half-open” al evento adicional. Es un Router Solicitation ICMPv6 tipo 133, iniciado antes del manifiesto y emitido después por timeout de flow. Está fuera del PCAP IPv4 y de las features.

Claude también afirmó 200 intentos L3/L4. Existen 200 transacciones DNS L7, pero solo 199 flow IDs/puertos únicos porque `39878` se reutilizó dos veces. La segunda fila tiene `packet_rate_10s=17.2 paquetes/s` y `flow_attempt_rate_10s=8.5 intentos/s`; la primera respuesta confundió ambas tasas.

La segunda consulta corrigió los tres errores y mantuvo el dictamen.

## Límites del dictamen

- Dos filas son ventanas de un episodio, no dos ráfagas.
- Los cuatro paquetes adicionales del contador Suricata no están tipificados.
- El flow IPv6 se conserva en EVE, pero no afecta la entidad IPv4.
- El 0 % de paquetes grandes corresponde a DNS pequeño.
- Una repetición no establece SLA ni generalización.
- Isolation Forest final aún no está entrenado.

Dictamen final: **ACEPTAR CON LIMITACIONES**. Siguiente: `DNS-MIXED-50-10/R01`, con preflight completo.
