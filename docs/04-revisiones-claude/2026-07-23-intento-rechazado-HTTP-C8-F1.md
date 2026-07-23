# Revisión Claude — intento rechazado HTTP-C8 F1

Fecha: 23 de julio de 2026. Herramienta: Claude Code 2.1.217. Modelo: Haiku. Alcance: revisión adversarial del fallo y la corrección propuesta, sin edición ni operación.

## Dictamen

Claude confirmó que `F1N-HTTP-C8-R01` debe rechazarse y que la causa exacta de los 476 drops no está demostrada. Recomendó cambiar y calibrar primero únicamente el búfer de captura, sin modificar simultáneamente la rotación.

## Aportes aceptados

- separar hechos de la hipótesis de rotación;
- mantener fuera del dataset cualquier PCAP con drops;
- aumentar `net.core.rmem_max` y `tcpdump -B` como primera variable;
- ejecutar una calibración excluida antes del reintento;
- preservar el intento fallido y establecer una política explícita de retry;
- no cambiar a la vez búfer, rotación y throughput.

## Correcciones al dictamen

La transición entre PCAP fue de dos microsegundos, no veinte nanosegundos.

El Sensor tiene seis vCPU. El 44.41 % observado no se interpreta contra un supuesto techo de 200 % ni existe un gate formal de CPU para F1.

La calibración no se aceptará con “menos de 100 drops”. Ese rango puede ayudar al diagnóstico, pero el reintento oficial solo se autoriza con **cero** drops.

`F1N-HTTP-C8-R01-RETRY-001` no es un ID válido para el ensamblador, que exige una correspondencia canónica por celda. El intento rechazado deberá archivarse íntegramente fuera de las raíces activas y el futuro reintento conservará `F1N-HTTP-C8-R01`.

No está demostrado que cambiar la rotación sea necesario. Si el aumento del búfer produce cero drops con la rotación actual, esta permanecerá en 512 MB × 4.

## Decisión

**AUTORIZADO SOLO PARA CALIBRACIÓN DE BÚFER.** Se versionará y desplegará 64 MiB de búfer con `rmem_max` coherente; después se ejecutará el perfil C8 con propósito `calibration`. El intento oficial rechazado no se borra, no se edita y no produce features.
