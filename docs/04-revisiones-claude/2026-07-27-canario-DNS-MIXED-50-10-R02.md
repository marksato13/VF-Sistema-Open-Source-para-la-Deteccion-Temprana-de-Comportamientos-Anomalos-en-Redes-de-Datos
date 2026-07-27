# Revisión Claude — DNS-MIXED-50-10 R02

Fecha: 27 de julio de 2026. Herramienta: Claude Code 2.1.217. Modelo: Haiku. Alcance: revisión crítica sin operación ni edición.

## Respuesta contaminada

La primera respuesta revisó `DNS-MIXED-20-2/R02`, pese a que el prompt proporcionaba explícitamente los datos de `DNS-MIXED-50-10/R02`. Citó 44 paquetes, 22 transacciones y ratio 2/22. Se descartó íntegramente.

## Corrección y aportes

En una segunda petición, Claude identificó correctamente:

- ID `F1N-DNS-MIXED-50-10-R02`;
- 120 paquetes y 60 transacciones;
- 50 `NOERROR`, diez NXDOMAIN y ratio 10/60;
- 70 observaciones internas que no equivalen a 70 transacciones;
- independencia de PCAP/EVE/ledger frente a R01;
- vector exacto reproducido por un episodio determinista;
- necesidad de evaluar el posible peso repetido;
- autorización de preflight para `PING-10/R02`.

## Errores de la corrección

Claude enumeró `DNS-VALID-200/R01↔R02` como coincidencia y omitió `DNS-MIXED-20-2`; el ensamblador demuestra lo contrario. También afirmó que R02 era validation, pero R01–R03 pertenecen a `train`.

Citó 32 campañas aceptadas antes de ejecutar el ensamblador posterior; el resultado real es 33/145 y R02 4/29. Introdujo además porcentajes de dataset no válidos porque campañas y filas no son equivalentes, y especuló una causa broadcast/multicast para cuatro paquetes que no están identificados.

No se adopta su razonamiento sobre comportamiento interno de Isolation Forest, AUC futuro ni diversidad todavía no recolectada.

## Dictamen consolidado

**ACEPTADA CON LIMITACIONES.** La campaña es íntegra, reproduce exactamente su vector R01 y crea la tercera coincidencia entre campañas dentro de `train`. No existe coincidencia entre particiones.

Siguiente: preflight individual de `F1N-PING-10-R02`.
