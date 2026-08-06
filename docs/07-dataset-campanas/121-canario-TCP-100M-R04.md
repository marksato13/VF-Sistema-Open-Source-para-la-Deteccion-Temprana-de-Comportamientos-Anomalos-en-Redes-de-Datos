# Vigesimocuarto canario oficial R04 — TCP 100 Mbit/s

Fecha: 6 de agosto de 2026. Campaña `F1N-TCP-100M-R04`, partición `validation`. Estado: **ACEPTADA CON LIMITACIONES**.

## Objetivo y preflight

Una transferencia TCP legítima de iperf3, limitada a 100 Mbit/s durante 20 s desde Cliente `10.20.0.20` hacia Servidor `10.30.0.10:5201` a través del Sensor. Aporta normalidad L3/L4 pesada sin semántica HTTP. Iperf3 crea una conexión de control y otra de datos; no son dos usuarios ni dos cargas.

Antes del preflight válido se separaron cinco controles no capturantes. Los intentos parciales 01/02 terminaron tras contrato porque `ssh` consumía el stdin del envoltorio; el 03 exigía erróneamente `sudo -n true` en lugar de privilegios mínimos; el 04 confundía `LOWER_UP` con el estado operativo; el 05 esperaba `ens37` en Cliente en vez de `ens38`. Ninguno abrió captura ni creó campaign, features o ledger. Sus logs se preservan fuera de Git y no autorizan evidencia.

El preflight completo corregido pasó entre `14:41:45.971` y `14:42:09.440 -05:00` sobre commit limpio `618d8ebab3a87b90c920f26d38c6254cfeac2a38`. Pasaron contrato, almacenamiento con 122,660,892,672 bytes, NTP 5/5 con máximo absoluto 0.690 ms, SSH, ID libre, NIC externas operacionalmente `DOWN` por MAC, bypass bloqueado, rutas, Suricata y captura. `ppi-iperf3` estaba activo, sin sesiones y ligado sólo a `10.30.0.10:5201`; Cliente y Servidor usaban iperf 3.20 y el probe TCP cerró. DNS, ICMP y generador pasaron. Log SHA-256 `30b5dd1aea390c2d6bb9afc46bf41107a93f4442f633c6a3359718f427630a6e`. Claude autorizó exactamente una ejecución. No hubo reintento ni scoring.

## Resultado iperf3 y conexiones

| Métrica | Emisor | Receptor |
|---|---:|---:|
| Bytes | 250,085,376 | 250,085,376 |
| Duración | 20.001544 s | 20.004063 s |
| Bitrate | 100.026428 Mbit/s | 100.013833 Mbit/s |
| Desviación nominal | +0.026428 % | +0.013833 % |

Iperf3 informó TCP Cubic, RTT medio 877 µs, mínimo 681 y máximo 1,937 µs. Registró dos retransmisiones, ambas en el intervalo 0–1 s. Se conservan como observaciones sin umbral ni causa demostrada.

| Rol | Puerto Cliente | Paquetes | SYN / SYN-ACK / FIN / RST | Span |
|---|---:|---:|---:|---:|
| Control | 50974 | 29 | 1 / 1 / 2 / 0 | 20.010362 s |
| Datos | 50978 | 182,974 | 1 / 1 / 2 / 0 | 20.008131 s |

Los dos handshakes y cierres quedaron completos. `flow_attempt_count_30s=2` representa control más datos con `num_streams=1`, no dos transferencias independientes.

## Integridad, EVE y tráfico pesado

| Control | Resultado |
|---|---:|
| Estado / evidencia | `completed` / completa |
| PCAP capturado / recibido / parseado | 183,003 / 183,003 / 183,003 |
| PCAP | 1 archivo / 265,094,104 bytes |
| Drops / límite / transferencia | 0 / no alcanzado / verificada |
| Suricata / PCAP | 183,005 / 183,003 |
| drops / ifdrops / decoder / overflow | 0 / 0 / 0 / 0 |
| Paquetes de 500–1500 bytes | 173,629 / 183,003 (94.8777 %) |
| Paquetes de 1,500 bytes | 171,721 |
| longitud media / máxima | 1,418.58 / 1,500 bytes |

El delta Suricata +2 queda sin causa atribuida. El PCAP supera los bytes de aplicación en 15,008,728 bytes (6.001442 %); esa diferencia incluye cabeceras, ACK, control, registros y ambos sentidos, y no mide pérdida.

EVE contiene trece stats, una alerta permitida SID 2260003 y una anomalía `APPLAYER_PROTO_DETECTION_SKIPPED` sobre la conexión de datos. Indican clasificación L7 no lograda para iperf3, no ataque ni etiqueta; el extractor registró cero observaciones de aplicación.

Dos flows ICMP/DNS empezaron durante el preflight a `14:42:08/09`, se emitieron por timeout a `14:47:12` y sus paquetes están fuera del PCAP y de las features. Se preservan sin atribuirlos a iperf3. El estado histórico `alerted=true` del flow ICMP tampoco es una alerta nueva de la transferencia.

## Features, recursos e integridad raíz

Las tres filas elegibles contienen 19,263, 91,676 y 72,064 paquetes, que suman exactamente 183,003. Sus ratios pesados son 0.94486840, 0.94597277 y 0.95338865. La finalización vale 1 en la ventana con handshakes y 0 en las siguientes sin SYN nuevo; no implica fallo. Las tres filas son ventanas correlacionadas de un episodio y ninguna coincide exactamente con R01, R02 o R03.

El Sensor produjo 79 muestras: CPU 0–12.10 %, RSS constante 782,504 KiB, memoria disponible 14,063,496–14,189,012 KiB y load1 0–0.32. Ambos bundles pasaron. Hashes: manifest `3a6e21d9…`, PCAP `5932fec8…`, EVE `782ee89d…`, CSV `1d13274b…`, extraction report `a7c1c4fb…` y ledger `917989f2…`.

| Métrica | R01 | R02 | R03 | R04 |
|---|---:|---:|---:|---:|
| Paquetes PCAP | 181,684 | 181,650 | 181,745 | 183,003 |
| Paquetes 500–1500 | 173,632 | 173,626 | 173,634 | 173,629 |
| Proporción 500–1500 | 95.5681 % | 95.5827 % | 95.5372 % | 94.8777 % |
| Longitud media | 1,428.51 | 1,428.75 | 1,428.06 | 1,418.58 |
| Retransmisiones | 4 | 0 | 7 | 2 |

Cuatro episodios permiten una comparación descriptiva, no causal ni inferencial. El auditor limpio aceptó 111/145, R04 24/29, 34 faltantes, 25 coincidencias, ocho cruces y cero inválidas/advertencias.

Claude dictaminó **ACEPTAR CON LÍMITES**: retransmisiones y delta sin causa, filas agrupadas por campaña y preflight fallidos conservados como no capturantes. Autoriza exclusivamente el preflight independiente `F1N-TCP-200M-R04`; no su captura ni scoring.

