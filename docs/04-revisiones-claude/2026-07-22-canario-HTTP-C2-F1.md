# Revisión Claude — canario HTTP concurrente C2 F1

Fecha: 22 de julio de 2026. Herramienta: Claude Code 2.1.217. Modelo: Haiku. Alcance: revisión adversarial del resumen técnico, sin herramientas, edición ni operación.

## Dictamen

Claude emitió **ACEPTAR**. Consideró demostrados el solapamiento de dos transferencias completas, PCAP íntegro, cero pérdidas, cobertura pesada de 95.7053 %, recursos holgados y admisión del ensamblador.

## Condiciones y límites

- `curl --limit-rate` excedió aproximadamente 5 % el nominal agregado;
- ambos flujos pertenecen a un Cliente y destino;
- las dos filas comparten el mismo episodio y no son repeticiones independientes;
- la segunda fila tiene `syn_completion_ratio_10s=0` porque no contiene SYN nuevos;
- Suricata truncó la inspección de cada archivo a 102,400 bytes, no la transferencia ni el PCAP.

El máximo observado, 176.15 Mbit/s, conserva 23.85 Mbit/s de margen hasta el techo de 200 Mbit/s. C4 mantiene el mismo nominal agregado, pero debe volver a medir la desviación real.

## Correcciones al dictamen

EVE contiene dieciséis registros: doce `stats`, dos `http` y dos `fileinfo`; no catorce.

`syn_completion_ratio_10s` ya es el nombre versionado y su fórmula está documentada como `min(|SYNACK10|, |SYN10|) / |SYN10|`. No se renombra durante una matriz activa. Con cero SYN, `safe_ratio` devuelve cero.

`unique_dst_ip_ratio_30s=0.5` significa una IP destino dividida entre dos intentos. `unique_dst_port_ratio_30s=0.5` significa un puerto destino entre dos intentos. Los puertos origen efímeros no son features.

No se añade `potential_correlation_group`: cambiaría el esquema congelado y es redundante, porque ambas filas comparten `campaign_id`, perfil, repetición y partición.

Los 145 GB libres corresponden al volumen de VM01. El helper remoto del Sensor comprobó su gate mínimo al iniciar la captura, pero esta revisión no recibió una medición exacta del espacio remoto y no la inventa.

Superar 500 MB no sería por sí solo un fallo: el capturador rota a 512 MB y admite hasta cuatro archivos. Los gates reales son integridad, `pcap_limit_reached=false`, cero drops y capacidad.

## Próximo paso

Se autoriza `HTTP-C4/R01` con nuevo preflight:

- cuatro descargas concurrentes de 100 MB;
- `5M` por flujo, 5 MiB/s o 41.94 Mbit/s;
- nominal agregado 20 MiB/s o 167.77 Mbit/s;
- un Cliente y un destino;
- PCAP estimado de 450 MB.

Si C4 registra drops, errores, límite PCAP o throughput por encima del techo operativo, debe rechazarse y detener la progresión hacia C8.
