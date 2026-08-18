# Revisión Claude — canario DNS-VALID-10 F1

Fecha: 27 de julio de 2026. Herramienta: Claude Code 2.1.217. Modelo: Haiku. Alcance: resumen técnico, sin operación, herramientas ni edición.

## Resultado

Claude emitió **ACEPTAR CON LIMITACIONES** para `F1N-DNS-VALID-10-R01`:

- diez consultas `server.ppi.lab/A` produjeron diez respuestas `10.30.0.10`;
- EVE contiene diez solicitudes y diez respuestas, todas `NOERROR`;
- el PCAP conserva 20/20 paquetes, 2,324 bytes y cero drops;
- una fila elegible representa diez flujos DNS, un destino, un puerto y NXDOMAIN 0/10;
- hashes y ensamblador pasaron con 25 aceptadas, 0 inválidas y 120 faltantes.

## Corrección de la revisión

La primera respuesta dijo que EVE contenía “20 más 4 stats”. El dato correcto es 20 eventos DNS más 10 `stats`, para 30/30. Los cuatro adicionales pertenecen al delta `kernel_packets=24` de Suricata frente a los veinte paquetes del PCAP; son contadores con alcances distintos y su protocolo no está identificado en el bundle.

También se corrigió la afirmación de que la diversidad L3/L7 correspondía a otros perfiles. Esta fila mide concentración L3 —`unique_dst_ip_ratio=1/10`— y semántica L7 DNS —diez consultas, NXDOMAIN 0/10—. Lo que aportan otros perfiles es cobertura legítima pesada.

## Límites del dictamen

- El 0 % de paquetes grandes es propio del estrato DNS ligero.
- Una fila no establece independencia estadística ni SLA.
- El resultado exacto indica que no se observó tráfico de preflight en esta campaña, no garantiza campañas futuras.
- La benignidad procede del escenario y respuestas, no de ausencia de alertas.
- Isolation Forest final aún no está entrenado.

Dictamen final: **ACEPTAR CON LIMITACIONES**. Siguiente: `DNS-VALID-200/R01`, con preflight completo.
