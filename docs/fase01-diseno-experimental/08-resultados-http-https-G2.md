# Resultados HTTP/HTTPS de calibración G2

Fecha: 20 de julio de 2026, `America/Lima`. Estas pruebas verifican servicios, límites y captura; no forman parte del dataset final.

## Condiciones

- Cliente `10.20.0.20` hacia Servidor `10.30.0.10` a través del Sensor.
- NGINX HTTP/HTTPS con archivos generados de 10 MB, 100 MB, 500 MB y 1 GB.
- Límite de curl: 20 MiB/s en pruebas individuales.
- Contadores iniciales: `kernel_packets=1448149`, `kernel_drops=0`, `decoder.invalid=0`, `alert_queue_overflow=0`.

`--limit-rate` permite una ráfaga inicial, por lo que los archivos pequeños superan el promedio objetivo. En archivos de 500 MB y 1 GB la tasa se estabilizó cerca de 20 MiB/s.

## Descargas individuales

| Protocolo | Archivo | Código | Tiempo | Velocidad media observada |
|---|---:|---:|---:|---:|
| HTTP | 10 MB | 200 | 0.139 s | 75.55 MB/s, afectada por ráfaga inicial |
| HTTP | 100 MB | 200 | 4.508 s | 23.26 MB/s |
| HTTP | 500 MB | 200 | 24.507 s | 21.39 MB/s |
| HTTP | 1 GB | 200 | 49.784 s | aproximadamente 21.57 MB/s |
| HTTPS | 10 MB | 200 | 0.134 s | 78.47 MB/s, afectada por ráfaga inicial |
| HTTPS | 100 MB | 200 | 4.526 s | 23.17 MB/s |
| HTTPS | 500 MB | 200 | 24.529 s | 21.37 MB/s |
| HTTPS | 1 GB | 200 | 51.018 s | 21.05 MB/s |

La descarga HTTP de 1 GB se repitió al perderse la salida del primer proceso de control; el log NGINX confirmó ambas transferencias completas, con tiempos 49.784 y 49.709 s. Las dos son calibración y quedan excluidas del dataset.

## Concurrencia HTTP

| Flujos | Archivo por flujo | Límite por flujo | Resultado | Tiempo observado |
|---:|---:|---:|---|---:|
| 2 | 100 MB | 10 MiB/s | 2/2 con estado 200 | 9.506–9.508 s |
| 4 | 100 MB | 5 MiB/s | 4/4 con estado 200 | 19.506–19.521 s |
| 8 | 100 MB | 2 MiB/s | 8/8 con estado 200 | 42.545–47.544 s según NGINX |

En la prueba de ocho flujos la herramienta de orquestación dejó de retener el stdout antes de que terminaran los procesos remotos. No se infirió el resultado: se verificaron los ocho registros NGINX, cada uno con estado 200 y `bytes_sent=104857872`. No hubo respuestas 429 durante la calibración.

## Evidencia de tamaño de paquetes

Durante una descarga HTTP de 100 MB se capturaron 5,000 cabeceras con tcpdump en `ens35`:

```text
packets=5000
payload_500_1500=4542
pct=90.84
small=458
large=0
avg_payload=1315.38
max_payload=1448
tcpdump_kernel_drops=0
```

La medición corresponde al payload TCP reportado por tcpdump; los payloads máximos de 1448 bytes más cabeceras Ethernet/IP/TCP corresponden a tramas próximas al MTU de 1500 bytes. Esto aporta evidencia directa de tráfico legítimo pesado dentro del rango solicitado por el jurado.

## Telemetría y salud

Al consultar EVE desde las 23:05 se observaron 20 eventos HTTP, 20 `fileinfo`, 4 TLS y 16 flow; algunos flujos pueden cerrarse y emitirse después de la consulta. HTTPS produjo metadatos TLS, mientras los métodos y estados HTTP cifrados permanecieron en los logs NGINX.

Contadores finales:

```text
kernel_packets=5755854
kernel_drops=0
decoder.invalid=0
alert_queue_overflow=0
```

El proceso Suricata conservó aproximadamente 4.8 % de RAM y 776104 KiB RSS al cierre. El 3.1 % de CPU observado por `ps` es promedio acumulado, no pico instantáneo.

## Decisión

Estado: **calibración HTTP/HTTPS y concurrencia aprobada**. El laboratorio queda habilitado para diseñar y ejecutar sesiones F1 reproducibles. Las campañas finales deberán usar IDs, manifests, CPU muestreada en el tiempo, hashes y separación por sesión; no reutilizarán estas capturas de calibración.

## Revisión de Claude

Claude confirmó que la conclusión es defendible únicamente como calibración. Señaló tres límites que se mantienen abiertos:

1. La muestra de 5,000 paquetes es puntual y no representa por sí sola toda la distribución futura.
2. Cero drops aplica a estas condiciones, no demuestra capacidad durante escenarios mixtos F4.
3. Las combinaciones HTTP/HTTPS concurrentes aún deben repetirse para estimar variación causada por ESXi.

Estas limitaciones impiden presentar G2 como validación final o garantía de capacidad.
