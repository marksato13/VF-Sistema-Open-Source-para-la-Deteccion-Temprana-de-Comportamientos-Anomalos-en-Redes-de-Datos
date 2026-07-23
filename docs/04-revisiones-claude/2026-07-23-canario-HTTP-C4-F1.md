# Revisión Claude — canario HTTP concurrente C4 F1

Fecha: 23 de julio de 2026. Herramienta: Claude Code 2.1.217. Modelo: Haiku. Alcance: revisión adversarial del resumen técnico, sin edición ni operación del laboratorio.

## Dictamen

Claude emitió **ACEPTAR CONDICIONADO**. Consideró demostrados cuatro flujos HTTP realmente concurrentes, cuatro transferencias completas, PCAP íntegro, cero pérdidas, cobertura pesada de 96.1803 %, recursos disponibles y admisión del ensamblador.

También autorizó avanzar a `HTTP-C8/R01`, siempre mediante un nuevo preflight y manteniendo los gates de throughput, drops, integridad y capacidad.

## Condiciones cerradas

1. **Correlación:** las tres filas comparten `campaign_id` y un solo episodio. No se cuentan como tres repeticiones independientes.
2. **mDNS:** dos eventos del Cliente quedaron en EVE crudo, fuera del filtro PCAP LAN↔DMZ. El extractor no consume `mdns`; no contaminaron las features.
3. **Cola temporal:** la tercera fila contiene trece paquetes de cierre —ocho FIN y cinco ACK—, sin payload ni RST. Es normalidad legítima y permanece en el dataset.
4. **CPU:** 43.41 % es una medición descriptiva; no existe un límite formal de CPU que por sí solo apruebe o rechace F1.
5. **Inspección de archivo:** `fileinfo.state=TRUNCATED` y 102,400 bytes reflejan el límite de inspección de Suricata. Cliente, PCAP y hashes prueban la transferencia íntegra de 419,430,400 bytes.

## Correcciones y límites del dictamen

La progresión experimental comprobada es de dos flujos en C2 a cuatro en C4; no se ejecutó una celda oficial de tres flujos.

La estimación de CPU para C8 formulada durante la revisión es una hipótesis, no un resultado y no se presenta como criterio de aceptación. C8 deberá medir sus propios recursos.

Que C8 rote aproximadamente dos archivos PCAP no implica truncamiento. La rotación es parte del contrato; se evaluarán hashes, continuidad, paquetes capturados/parseados, `pcap_limit_reached=false`, cero drops y capacidad.

Los cuatro flujos de C4 usan el mismo Cliente, servidor, archivo y protocolo. El resultado amplía concurrencia y carga pesada legítima, pero no diversidad de usuarios, hosts o contenidos.

## Próximo paso autorizado

`HTTP-C8/R01` tiene contrato congelado:

- ocho descargas concurrentes de 100 MB;
- `2M` por flujo;
- nominal agregado 16 MiB/s o 134.217728 Mbit/s;
- PCAP estimado de 920,000,000 bytes, probablemente rotado;
- un Cliente y un destino;
- rechazo ante drops, errores, límite PCAP, evidencia incompleta o violación del techo operativo.

La autorización no sustituye el preflight ni permite lanzar el resto de la matriz en lote.
