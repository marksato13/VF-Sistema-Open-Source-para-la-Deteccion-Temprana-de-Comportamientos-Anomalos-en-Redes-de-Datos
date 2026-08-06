# Vigesimotercer canario oficial R04 — TCP 50 Mbit/s

Fecha: 6 de agosto de 2026. Campaña `F1N-TCP-50M-R04`, partición `validation`. Estado: **ACEPTADA CON LIMITACIONES**.

## Objetivo y preflight

Transferencia TCP legítima iperf3, limitada a 50 Mbit/s durante 20 s desde Cliente hacia Servidor a través del Sensor. Aporta normalidad L3/L4 pesada sin semántica HTTP. Iperf3 crea control y datos; no son dos usuarios ni dos cargas.

El preflight completo pasó entre `13:57:43.270` y `13:58:15.063 -05:00` sobre commit limpio `3ecd5aafde5e53b01a46842fe89a10a4f189a520`. Pasaron contrato, almacenamiento con 122,793,611,264 bytes, NTP 5/5 (máximo 0.710 ms), IDs, SSH, NIC externas `DOWN`, bypass, rutas, Suricata y captura. `ppi-iperf3` estaba activo, sin sesiones y escuchando sólo en `10.30.0.10:5201`; Cliente y Servidor usaron iperf 3.20 y el probe TCP previo pasó. DNS, ICMP y generador pasaron. Log SHA-256 `97c176241d712c40c45433544cddc19ce25d818967432817a32c9a9c1289f531`. Claude autorizó una captura. No hubo reintento ni scoring.

## Resultado iperf3 y conexiones

| Métrica | Emisor | Receptor |
|---|---:|---:|
| Bytes | 125,042,688 | 125,042,688 |
| Duración | 20.001612 s | 20.002253 s |
| Bitrate | 50.013044 Mbit/s | 50.011441 Mbit/s |

Iperf3 informó TCP Cubic, RTT medio 1,146 µs, mínimo 768 y máximo 1,612 µs. Registró dos retransmisiones: una en 0–1 s y otra en 5–6 s. Se conservan como variación sin umbral formal ni causa atribuida.

| Rol | Puerto Cliente | Paquetes | SYN / SYN-ACK / FIN / RST | Span |
|---|---:|---:|---:|---:|
| Control | 59080 | 27 | 1 / 1 / 2 / 0 | 20.011234 s |
| Datos | 59090 | 90,413 | 1 / 1 / 2 / 0 | 20.007205 s |

Ambos handshakes y cierres quedaron completos. `flow_attempt_count=2` representa control más datos de `num_streams=1`, no dos transferencias independientes.

## Integridad, EVE y features

| Control | Resultado |
|---|---:|
| PCAP capturado / recibido / parseado | 90,440 / 90,440 / 90,440 |
| PCAP | 1 archivo / 132,461,248 bytes |
| Drops / límite / transferencia | 0 / no alcanzado / verificada |
| Suricata / PCAP | 90,442 / 90,440 |
| drops / ifdrops / decoder / overflow | 0 / 0 / 0 / 0 |
| Paquetes de 500–1500 bytes | 86,816 / 90,440 (95.9929 %) |
| Paquetes de 1,500 bytes | 85,860 |
| longitud media / máxima | 1,434.63 / 1,500 bytes |

El delta Suricata +2 queda sin causa atribuida. EVE contiene doce stats, una alerta permitida SID 2260003, una anomalía `APPLAYER_PROTO_DETECTION_SKIPPED` sobre datos y dos flows diferidos. La alerta/anomalía indica que Suricata abandonó clasificación L7 de iperf3; no es etiqueta de ataque ni feature.

Los flows ICMP y DNS empezaron durante el preflight a `13:58:14`, se emitieron cinco minutos después por timeout y sus paquetes están fuera del PCAP. El extractor informó cero observaciones de aplicación. Se conservan sin atribuirlos a iperf3; el ICMP mantiene `alerted=true` como estado histórico del flow, no un evento de alerta nuevo en el segmento.

Las tres filas contienen 39,401; 45,111 y 5,928 paquetes, que suman 90,440. Sus ratios pesados son 0.95852897, 0.96222651 y 0.95175439. La finalización vale 1 en la ventana con handshakes y 0 en las siguientes sin SYN nuevo; no implica caída de la conexión. Las filas pertenecen al mismo episodio y ninguna coincide exactamente con R01–R03 u otro vector global.

El Sensor produjo 73 muestras: CPU 0–6.78 %, RSS 782,504 KiB, memoria disponible 14,047,308–14,151,792 KiB y load1 0.12–0.33. Ambos bundles pasaron. Hashes: manifest `a99c6d55…`, PCAP `9c170241…`, EVE `89d3a9f2…`, CSV `3f73b076…`, extraction report `89f26e69…` y ledger `8332ff53…`.

El auditor limpio aceptó 110/145, R04 23/29, 35 faltantes, 25 coincidencias, ocho cruces y cero inválidas/advertencias.

**ACEPTADA CON LIMITACIONES.** Es una única transferencia iperf3 con control/datos, dos retransmisiones y telemetría L7 fallida permitida. Conserva flows diferidos y delta +2. No hubo scoring. Claude autorizó únicamente el preflight independiente `F1N-TCP-100M-R04`; no su captura.
