# Resultados de calibración G2

Fecha: 20 de julio de 2026, `America/Lima`. Estas pruebas calibran los límites de F1 y quedan excluidas del dataset final de entrenamiento.

## Condiciones

- Cliente: `10.20.0.20`.
- Servidor: `10.30.0.10`.
- Sensor: Suricata AF_PACKET con 4 threads, ring 32768, bloque/buffer de 1 MiB y RX 4096.
- Duración por intento: 10 segundos.
- Contadores iniciales: `kernel_packets=100615`, `kernel_drops=0`, `decoder.invalid=0`, `alert_queue_overflow=0`.

## TCP

| Bitrate solicitado | Recepción aproximada | Retransmisiones | Drops Sensor | Resultado |
|---:|---:|---:|---:|---|
| 50 Mbit/s | 50.006 Mbit/s | 0 | 0 | Apto |
| 100 Mbit/s | 100.014 Mbit/s | 0 | 0 | Apto |
| 200 Mbit/s, ronda 1 | 200.008 Mbit/s | 0 | 0 | Apto |
| 200 Mbit/s, ronda 2 | 200.020 Mbit/s | 2 | 0 | Apto con retransmisión mínima |
| 200 Mbit/s, ronda 3 | 200.020 Mbit/s | 1 | 0 | Apto con retransmisión mínima |
| 250 Mbit/s | 250.020 Mbit/s | 2 | 0 | Frontera; no se adopta para F1 |
| 300 Mbit/s | no completó | n/d | 0 | Abortado por guardia del Servidor |

La prueba de 300 Mbit/s terminó con `control socket has closed unexpectedly` aproximadamente al intervalo de control de la guardia. No se interpreta como capacidad de 300 Mbit/s ni se usa para entrenamiento.

## UDP

| Bitrate solicitado | Recepción aproximada | Jitter | Pérdida | Drops Sensor | Resultado |
|---:|---:|---:|---:|---:|---|
| 10 Mbit/s | 10.000 Mbit/s | 0.125 ms | 0 % | 0 | Apto |
| 25 Mbit/s | 24.999 Mbit/s | 0.033 ms | 0 % | 0 | Apto |
| 50 Mbit/s, ronda 1 | 49.998 Mbit/s | 0.037 ms | 0 % | 0 | Apto |
| 50 Mbit/s, ronda 2 | 49.998 Mbit/s | 0.048 ms | 0 % | 0 | Apto |
| 50 Mbit/s, ronda 3 | 49.998 Mbit/s | 0.040 ms | 0 % | 0 | Apto |
| 75 Mbit/s | 74.998 Mbit/s | 0.060 ms | 10 paquetes, 0.0154 % | 0 | Frontera; no se adopta |
| 100 Mbit/s | 99.993 Mbit/s | 0.019 ms | 73 paquetes, 0.0846 % | 0 | No apto para baseline sin pérdida |

## Salud del Sensor

Al cierre se observaron:

```text
kernel_packets=1448147
kernel_drops=0
decoder.invalid=0
alert_queue_overflow=0
```

El RSS de Suricata permaneció aproximadamente entre 764824 y 765616 KiB. La RAM total usada del Sensor se mantuvo entre 1421 y 1445 MiB, con más de 13 GiB disponibles. El `%CPU` mostrado por `ps` aumentó de 2.2 a 2.5 %, pero es un promedio acumulado desde el inicio del proceso y no representa el pico instantáneo; para la campaña final se incorporará muestreo temporal de CPU.

## Umbrales adoptados

- TCP F1: máximo 200 Mbit/s, duración máxima 30 s.
- UDP F1: máximo 50 Mbit/s, duración máxima 30 s.
- No ejecutar TCP sin `-b`.
- No usar 250/300 Mbit/s TCP ni 75/100 Mbit/s UDP como baseline normal hasta una nueva calibración justificada.

Estado: **calibración de throughput aprobada**. G2 completo sigue pendiente de descargas HTTP/HTTPS individuales y concurrentes bajo estos límites.

## Revisión de Claude

Claude consideró defendibles los umbrales como techos operativos exploratorios porque las tres rondas seleccionadas no produjeron drops y quedaron por debajo de las fronteras con degradación. Señaló correctamente que tres rondas no permiten estimar varianza, ráfagas o capacidad sostenida ni constituyen un SLA. Por ello, los valores se usan para limitar F1, se excluyen del dataset final y deberán volver a comprobarse en campañas más largas.
