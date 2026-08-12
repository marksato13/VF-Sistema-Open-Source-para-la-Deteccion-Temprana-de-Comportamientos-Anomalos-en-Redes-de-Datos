# Escenario DNS multi-destino para la expansión multicapa v2

Fecha de diseño: 2026-08-12. Estado: **propuesto, no ejecutado**.

## Propósito

`dns-multi` genera tráfico DNS legítimo hacia varios nombres del laboratorio
para aumentar la diversidad de comportamiento de capa 7 sin depender de
Internet. El cliente consulta exclusivamente el resolvedor interno `10.30.0.10`
(dnsmasq) y sólo acepta respuestas IPv4 válidas.

Parámetros permitidos: `4`, `10`, `50` o `200` consultas. Las consultas
recorren cíclicamente `server.ppi.lab`, `web.ppi.lab`, `web-a.ppi.lab`,
`web-b.ppi.lab` e `iperf.ppi.lab`, todos definidos en `configs/server/dnsmasq-ppi.conf`.
El escenario está implementado en `scripts/f1/run-benign.sh` y autorizado por
`scripts/campaign/run-f1.sh`.

## Capas y observables

- L3: origen del cliente, destino `10.30.0.10`, tamaño y diversidad de los
  datagramas IP.
- L4: consultas UDP/53, número de transacciones y frecuencia temporal.
- L7: nombres consultados, respuestas A válidas y relación entre consultas y
  respuestas; Suricata EVE `dns` y el log de dnsmasq permiten reconciliación.

La salida del escenario es JSONL en `scenario-output.txt`; la evidencia
defendible también requiere PCAP del sensor, EVE DNS, log de dnsmasq y el
manifiesto de campaña con `episode_id` y argumentos exactos.

## Criterios de aceptación

Una ejecución sólo podrá incorporarse al dataset v2 si todas las consultas
reciben una respuesta A válida, no hay pérdidas de captura (`kernel_drops=0`),
los relojes están sincronizados y los conteos de PCAP, EVE, dnsmasq y JSONL
son reconciliables. Se conservarán ejecuciones separadas por episodio; no se
mezclarán sus filas durante el particionado.

Este escenario aún no se ha ejecutado, no modifica el contrato de 14 features
ni altera el dataset F1-R05 ya cerrado. Antes de incluirlo se debe añadir una
celda versionada a la matriz v2, ejecutar preflight y realizar una campaña
piloto; después se decidirá si aporta nuevas variables DNS (por ejemplo,
diversidad de nombres y ratio consulta/respuesta) sin duplicar las 14 actuales.
