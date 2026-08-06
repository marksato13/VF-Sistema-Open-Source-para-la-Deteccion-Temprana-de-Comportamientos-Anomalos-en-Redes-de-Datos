# Vigesimoquinto canario oficial R04 — TCP 200 Mbit/s

Fecha: 6 de agosto de 2026. Campaña `F1N-TCP-200M-R04`, partición `validation`. Estado: **ACEPTADA CON LIMITACIONES**.

## Objetivo y preflight

Una transferencia TCP legítima de iperf3 desde Cliente `10.20.0.20` hacia Servidor `10.30.0.10:5201`, limitada a 200 Mbit/s durante 20 s y atravesando el Sensor. Es el máximo `throughput-ceiling` calibrado y permitido por la matriz; no autoriza tasas superiores ni tráfico sin pacing.

El preflight contiguo pasó entre `15:05:47.958` y `15:06:11.623 -05:00` sobre commit limpio y sincronizado `05a94578b9541edb239cf42e2f8c38698dab9f02`. Pasaron contrato, almacenamiento con 122,395,553,792 bytes, NTP 5/5 con máximo absoluto 0.679 ms, SSH, ID libre, NIC externas `DOWN` por MAC, bypass bloqueado, rutas, Suricata/captura, listener iperf3 exclusivo y ocioso, versiones 3.20, probe cerrado, DNS, ICMP y generador. Log SHA-256 `9e08f4c9346cbfdb13d57b2b8cabe11a1a24c7730f2a1095bdc10b5589d735e9`. Claude autorizó una única ejecución. No hubo reintento ni scoring.

## Resultado iperf3 y conexiones

| Métrica | Emisor | Receptor |
|---|---:|---:|
| Bytes | 500,039,680 | 500,039,680 |
| Duración | 20.001455 s | 20.001920 s |
| Bitrate | 200.001322 Mbit/s | 199.996672 Mbit/s |
| Desviación nominal | +0.000661 % | −0.001664 % |

TCP Cubic registró RTT medio 839 µs, mínimo 482 y máximo 1,321 µs. Iperf3 informó una retransmisión durante 7–8 s; no se le atribuye causa ni categoría.

| Rol | Puerto Cliente | Paquetes | SYN / SYN-ACK / FIN / RST | Span |
|---|---:|---:|---:|---:|
| Control | 54552 | 27 | 1 / 1 / 2 / 0 | 20.006236 s |
| Datos | 54560 | 371,535 | 1 / 1 / 2 / 0 | 20.006107 s |

Los dos handshakes y cierres quedaron completos. `flow_attempt_count_30s=2` representa control más datos de `num_streams=1`, no dos usuarios ni dos cargas.

## Integridad, tráfico pesado y EVE

| Control | Resultado |
|---|---:|
| PCAP capturado / recibido / parseado | 371,562 / 371,562 / 371,562 |
| PCAP | 2 archivos / 530,509,500 bytes |
| Drops / límite / transferencia | 0 / no alcanzado / verificada |
| Suricata / PCAP | 371,564 / 371,562 |
| drops / ifdrops / decoder / overflow | 0 / 0 / 0 / 0 |
| Paquetes de 500–1500 bytes | 347,166 / 371,562 (93.4342 %) |
| Paquetes de 1,500 bytes | 343,350 |
| longitud media / máxima | 1,397.78 / 1,500 bytes |

El delta Suricata +2 queda sin causa atribuida. El PCAP supera el payload iperf3 en 30,469,820 bytes (6.093480 %) porque incluye cabeceras, ACK, control, registros y ambos sentidos; no mide pérdida.

EVE contiene quince stats, una alerta permitida SID 2260003 y una anomalía `APPLAYER_PROTO_DETECTION_SKIPPED` sobre datos. No contiene flows autónomos. Los eventos indican clasificación L7 no lograda para iperf3, no ataque ni etiqueta; el extractor registró `application_observations=0`.

## Features, recursos y comparación

Las tres filas elegibles contienen 18,265, 185,264 y 168,033 paquetes, que suman exactamente 371,562. Sus ratios pesados son 0.91305776, 0.93706818 y 0.93364994. La finalización vale 1 sólo en la ventana con SYN nuevos. Son ventanas correlacionadas del mismo episodio y ninguna coincide exactamente con R01–R03.

| Métrica | R01 | R02 | R03 | R04 |
|---|---:|---:|---:|---:|
| Paquetes PCAP | 364,128 | 364,201 | 369,452 | 371,562 |
| Proporción 500–1500 | 94.1131 % | 94.1073 % | 93.9654 % | 93.4342 % |
| Retransmisiones | 1 | 2 | 1 | 1 |

Cuatro episodios no sustentan tendencia, causa ni rango normal. El Sensor produjo 88 muestras: CPU 0–21.54 %, RSS 782,504 KiB, memoria disponible 14,080,316–14,163,920 KiB y load1 0.11–0.27. Son magnitudes descriptivas, no un SLA.

Ambos bundles pasaron. Hashes: manifest `22f9cc65…`, PCAP0 `71e952bb…`, PCAP1 `b1cb3d9b…`, EVE `649c50c5…`, CSV `5fac29cd…`, extraction report `02ab483b…` y ledger `845c70e5…`.

El auditor limpio aceptó 112/145, R04 25/29, 33 faltantes, 25 coincidencias, ocho cruces y cero inválidas/advertencias. Claude leyó diez artefactos por rutas exactas y confirmó todas las cifras; el auditor global fue verificado aparte por Codex. Dictamen: **ACEPTAR CON LIMITACIONES**. Siguiente autorizado: únicamente preflight independiente de `F1N-UDP-10M-R04`; no su captura ni scoring.
