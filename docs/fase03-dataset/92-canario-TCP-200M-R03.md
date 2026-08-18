# Vigesimoquinto canario oficial R03 — TCP 200 Mbit/s

Fecha: 1 de agosto de 2026. Campaña: `F1N-TCP-200M-R03`. Estado: **ACEPTADA CON LIMITACIONES**.

## Objetivo y preflight

Un stream iperf3 TCP legítimo transmite durante 20 s desde Cliente `10.20.0.20` hacia Servidor `10.30.0.10:5201`, a través del Sensor, con pacing explícito de 200 Mbit/s. Es el máximo `throughput-ceiling` permitido por la matriz; no autoriza pruebas superiores ni sin límite.

El dry-run fijó `experiment/train`, quietud/warm-up/settle/cooldown `70/60/9/30 s`, commit limpio y sincronizado `abecb27b09a61d90cae654a31f898ff631b23b45`, matriz SHA `ad22ce5f8b41110b201f0eeacd2b5f13cc9f945c92cf539e9913e87fefdfa824` y argumentos SHA `faee06d0a2df5e1d04db840eb446cbee345863478160c705e01d6f39a459bc93`.

Almacenamiento oficial/reserva pasó con 128,915,439,616 bytes disponibles. NTP pasó en cinco nodos con máximo absoluto 0.255 ms; SSH 4/4. Las cuatro NIC externas estaban `DOWN` por MAC, bypass bloqueado, rutas por Sensor, Suricata/captura sanos e ID libre. Iperf 3.20 escuchaba solo en `10.30.0.10:5201`, sin sesiones antes/después del sondeo. El generador local/remoto coincidió en `d4cd42b65f1b22cea0a3f585c2df760af68a8557799c3859eabc803d4f9b4203`. Claude autorizó una ejecución.

## Rendimiento e integridad

El escenario terminó con código cero y stderr vacío:

| Métrica | Emisor | Receptor |
|---|---:|---:|
| Bytes | 500,039,680 | 500,039,680 |
| Duración | 20.001647 s | 20.002136 s |
| Bitrate | 199.999402 Mbit/s | 199.994513 Mbit/s |
| Desviación nominal | −0.000299 % | −0.002744 % |

TCP Cubic registró una retransmisión en el primer intervalo. No existe tolerancia formal ni causa medida; no se clasifica como normal o anómala.

| Control | Resultado |
|---|---:|
| PCAP archivos / bytes | 2 / 530,336,483 |
| Capturados / recibidos / parseados | 369,452 / 369,452 / 369,452 |
| Drops / transferencia / límite | 0 / verificada / no alcanzado |
| Delta Suricata / PCAP | 369,454 / 369,452 |
| Drops / ifdrops / decoder / overflow | 0 / 0 / 0 / 0 |
| EVE esperado / extraído | 17 / 17 |
| Muestras Sensor / stderr | 87 / vacío |
| Lock / captura residual | ausente / inactiva |

Los dos paquetes adicionales del contador Suricata no están identificados. El PCAP supera el payload iperf3 en 30,296,803 bytes —6.058880 %— porque incluye registros, cabeceras, ACK, control y ambos sentidos; no mide pérdida.

La conexión de control `36350` tuvo 27 paquetes y span 20.009373 s; la de datos `36356`, 369,425 y 20.008557 s. Ambas contienen 1 SYN, 1 SYN/ACK, 2 FIN y 0 RST. `flow_attempt_count=2` significa control más datos, no dos usuarios o streams.

## Tráfico pesado, EVE y features

| Longitud IPv4 | Paquetes | Proporción |
|---|---:|---:|
| Menores de 500 | 22,295 | 6.0346 % |
| 500–1500 | 347,157 | **93.9654 %** |
| Mayores de 1500 | 0 | 0 % |
| Exactamente 1500 | 343,359 | 92.9374 % |

La media fue 1,405.47 bytes y la máxima, 1,500. Es otra muestra de tráfico pesado legítimo; tamaño alto no es etiqueta de ataque.

EVE contiene quince `stats`, SID `2260003` permitido y `APPLAYER_PROTO_DETECTION_SKIPPED` sobre datos; `application_observations=0`. En esta ejecución indican clasificación L7 no lograda, no ataque, y no son etiqueta ni feature.

Las tres filas elegibles y correlacionadas fueron:

| Fin UTC | Paquetes | Packet rate | Byte rate | Media IP | Ratio grande | SYN / completion |
|---|---:|---:|---:|---:|---:|---:|
| `03:36:40` | 55,969 | 5,596.9 | 7,736,030.8 | 1,382.1992 | 0.92336829 | 2 / 1 |
| `03:36:50` | 184,015 | 18,401.5 | 25,952,308.4 | 1,410.3366 | 0.94305899 | 0 / 0 |
| `03:37:00` | 129,468 | 12,946.8 | 18,236,948.3 | 1,408.6066 | 0.94185436 | 0 / 0 |

Suman 369,452 paquetes y no coinciden exactamente con R01/R02. Son ventanas de un episodio, no tres repeticiones.

## Comparación y recursos

R01/R02/R03 transfirieron 500,039,680 bytes por extremo aproximadamente a 200 Mbit/s, con una, dos y una retransmisión; capturaron 364,128, 364,201 y 369,452 paquetes, y 94.1131 %, 94.1073 % y 93.9654 % en 500–1500 bytes. No se infiere tendencia, causa ni normalidad con tres episodios.

El Sensor alcanzó CPU puntual 22.21 %, RSS 781,768 KiB, memoria disponible mínima 14,070,104 KiB y carga máxima 0.33. Son observaciones sin umbral de capacidad.

## Integridad raíz y decisión

```text
manifest              ea1a0bcdda82d83f5716c50f0fed8c3e12cd9268aa47fd6fce9f76a0ea73b283
pcap0                 e65041e80ccf4809715ef029fe7f91c427534666c21eceb875890873d295f3ec
pcap1                 e8617ec0e1ac115fa3f0545bcb7e4f2095e214cac1fa3544d89aa4e370e16b98
eve                    226bc45b46ec0e68b8dc9a97a07aed26376f84f756393e57b9d68e7d8b045052
campaign SHA256SUMS   6f1b657e8c33b68410b19abad5c390b2943abf778cde78e3cbab6e4aec9fefe7
features CSV          2f200f7766f17c128bb2cf5d254273d8233afc6e5360f112250d1706b24e3d0c
extraction report     d181bed747158d65cca8a5d94faef6fb3f91154836d465d8b8af051c610aec58
feature SHA256SUMS    c99f3f6b3da64ac177d411dbbd82ce4a60eab75c64f00a07c35adb2947d321eb
ledger                c48e736a8a05521d1ad51a9467e8ad20ca587f18e4ae75b050a436eeb265c746
```

Todos los hashes pasaron. El ensamblador aceptó 83/145: R03 25/29, 62 faltantes, cero inválidas/advertencias, quince duplicados dentro de `train` y cero cruzados. Esta campaña no añadió coincidencias.

Claude emitió **ACEPTAR CON LIMITACIONES** y autorizó solo el preflight de `UDP-10M/R03`. Se corrigió su pre-review: seis duplicados era un conteo antiguo; antes y después de esta campaña son quince. Sus frases “coherente con techo/estrato” se conservan únicamente como descripción del perfil y medición, no como gate estadístico.

**F1N-TCP-200M-R03 ACEPTADA CON LIMITACIONES.** Siguiente autorizado: solo preflight independiente de `F1N-UDP-10M-R03`; no su ejecución.
