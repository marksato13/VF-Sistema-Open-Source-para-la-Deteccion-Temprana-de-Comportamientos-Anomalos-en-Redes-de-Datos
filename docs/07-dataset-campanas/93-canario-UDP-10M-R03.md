# Vigesimosexto canario oficial R03 — UDP 10 Mbit/s

Fecha: 4 de agosto de 2026. Campaña: `F1N-UDP-10M-R03`. Estado: **ACEPTADA CON LIMITACIONES**.

## Objetivo y preflight

La campaña reproduce un flujo UDP benigno de iperf3 a 10 Mbit/s durante 20 s, desde Cliente `10.20.0.20` hacia Servidor `10.30.0.10:5201` a través del Sensor. Usa bloques de 1,448 bytes y aporta tráfico grande legítimo L3/L4; no representa un SLA ni una aplicación productiva.

El dry-run fijó `experiment/train`, estrato `throughput`, quietud/warm-up/settle/cooldown `70/60/9/30 s`, commit limpio y sincronizado `515fda4449fcd42f862f9ff3a7720a07064babae`, matriz SHA `ad22ce5f8b41110b201f0eeacd2b5f13cc9f945c92cf539e9913e87fefdfa824` y argumentos SHA `f13202e70b2d4d581dbb998885e48b1de6e7980d54a8aae59e0d57b9c630a1ae`.

Almacenamiento oficial/reserva pasó con 128,384,843,776 bytes disponibles. NTP pasó en cinco nodos con máximo absoluto 0.718 ms y SSH respondió 4/4. Las NIC externas estaban `DOWN` por MAC, el bypass bloqueado y las rutas atravesaban el Sensor. Suricata/captura estaban sanos e inactivos. Iperf 3.20 escuchaba solo en `10.30.0.10:5201`; el sondeo cerró antes de la quietud. El generador local/remoto coincidió en `d4cd42b65f1b22cea0a3f585c2df760af68a8557799c3859eabc803d4f9b4203`. Claude autorizó una ejecución.

## Resultado UDP

El escenario terminó con código cero y stderr vacío:

| Métrica | Emisor | Receptor |
|---|---:|---:|
| Bytes | 25,002,616 | 25,002,616 |
| Datagramas | 17,267 | 17,267 |
| Duración | 20.001569 s | 20.004262 s |
| Bitrate | 10.000262 Mbit/s | 9.998916 Mbit/s |
| Desviación nominal | +0.002619 % | −0.010844 % |
| Jitter | 0 ms | 0.042085 ms |
| Perdidos / fuera de orden | 0 / 0 | 0 / 0 |
| Pérdida | 0 % | 0 % |

`17,267 × 1,448 = 25,002,616`: bytes y datagramas coinciden en ambos extremos. Jitter, pérdida y reordenamiento son valores crudos de esta ejecución; tres repeticiones no definen umbrales ni distribución.

## Composición e integridad

El PCAP reconcilia exactamente 17,296 paquetes:

- 17,267 UDP de datos con payload de 1,448 bytes;
- dos UDP de inicialización con payload de cuatro bytes;
- 27 TCP de control.

El control TCP `56368` tuvo 1 SYN, 1 SYN/ACK, 2 FIN, 0 RST y span 20.008564 s. `flow_attempt_count_30s=2` representa inicio UDP más control TCP según el extractor, no dos usuarios.

| Control | Resultado |
|---|---:|
| PCAP archivos / bytes | 1 / 26,007,325 |
| Capturados / recibidos / parseados | 17,296 / 17,296 / 17,296 |
| Drops / transferencia / límite | 0 / verificada / no alcanzado |
| Delta Suricata / PCAP | 17,300 / 17,296 |
| Drops / ifdrops / decoder / overflow | 0 / 0 / 0 / 0 |
| EVE esperado / extraído | 12 / 12 |
| Muestras Sensor / stderr | 68 / vacío |
| Lock / captura residual | ausente / inactiva |

Los cuatro paquetes adicionales del contador Suricata no están identificados. Pérdida UDP de extremo y drops de captura son controles diferentes aunque ambos resultaron cero.

El PCAP supera los bytes UDP de datos en 1,004,709 bytes —4.018416 %— por cabeceras, inicialización, control TCP y estructura del archivo; no mide pérdida.

| Longitud IPv4 | Paquetes | Proporción |
|---|---:|---:|
| Menores de 500 | 29 | 0.1677 % |
| 500–1500 | 17,267 | **99.8323 %** |
| Mayores de 1500 | 0 | 0 % |

La media fue 1,473.66 bytes y la máxima, 1,476. EVE contiene doce `stats`, sin alertas ni observaciones L7. La benignidad procede del escenario controlado, no de la ausencia de alertas.

## Features y repetibilidad

Las tres filas elegibles pertenecen a un episodio:

| Fin UTC | Paquetes | Packet rate | Byte rate | Media IP | Ratio grande | Attempts | SYN / completion |
|---|---:|---:|---:|---:|---:|---:|---:|
| `23:07:10` | 6,915 | 691.5 | 1,018,392.0 | 1,472.7289 | 0.99768619 | 2 | 1 / 1 |
| `23:07:20` | 8,633 | 863.3 | 1,274,230.8 | 1,476.0000 | 1.00000000 | 2 | 0 / 0 |
| `23:07:30` | 1,748 | 174.8 | 256,217.9 | 1,465.7775 | 0.99256293 | 2 | 0 / 0 |

Suman 17,296 paquetes. La fila interior coincide exactamente con R01 y R02. Es equivalencia observacional entre evidencias independientes, no prueba por sí sola de `seed`, independencia estadística ni realismo de una población. Las tres ventanas están correlacionadas y deben agruparse por `campaign_id`.

R01/R02/R03 transfirieron los mismos 25,002,616 bytes y 17,267 datagramas por extremo, sin pérdida/reordenamiento ni drops. Sus jitter fueron 0.027371, 0.049850 y 0.042085 ms. No se infiere tendencia ni rango normal.

El Sensor alcanzó CPU puntual 2.96 %, RSS 781,720 KiB, memoria disponible mínima 14,091,848 KiB y carga máxima 0.43. Son observaciones sin umbral de capacidad.

## Integridad raíz y decisión

```text
manifest              a4b1461ec1dfe0edfcf3406da6e08527c41dc226ef9fcd03737fa5c60207b0ce
pcap                  11aaf3fb9ffbefc7a354a509865b44d007c727c1a429b500bf8b92e37c85d88a
eve                   a3a5bc2842046a01303c0d8765a759512c8904438decd8a21c5321afbc072d6d
campaign SHA256SUMS   d84879855c4d4b4d1de258b5f61b7c72ca9ea45bcfca6a8a5534f0406a0ad85f
features CSV          538f659b35a0fbca568aa80e692ca1c2f1c7952271609c4bea5a9d77672702c6
extraction report     d3c0c023c85a80daeb181d808e42b7dc9bbfc8f07a64bcf7f607993099235487
feature SHA256SUMS    b55177db3809ef1b42a8bb869e17431a7fc6fdf962c08a1c1b2c0653833e6b5e
ledger                a30251a4e0eb464b42d147a45219a31773cfc278912b994db4febd3f01d5717e
```

Todos los hashes pasaron. El ensamblador aceptó 84/145: R03 26/29, 61 faltantes, cero inválidas/advertencias, dieciséis duplicados dentro de `train` y cero cruzados. La fila interior añadió una coincidencia.

Claude emitió **ACEPTAR CON LIMITACIONES** y autorizó solo el preflight de `UDP-25M/R03`. Se corrigieron tres afirmaciones: el contador 16 proviene directamente del ensamblador; pérdida de extremo y drops del Sensor no son la misma medida; la fila repetida no prueba determinismo.

**F1N-UDP-10M-R03 ACEPTADA CON LIMITACIONES.** Siguiente autorizado: solo preflight independiente de `F1N-UDP-25M-R03`; no su ejecución.
