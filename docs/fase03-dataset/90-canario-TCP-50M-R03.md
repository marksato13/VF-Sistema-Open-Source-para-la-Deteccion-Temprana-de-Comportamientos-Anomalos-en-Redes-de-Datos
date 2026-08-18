# Vigesimotercer canario oficial R03 — TCP 50 Mbit/s

Fecha: 1 de agosto de 2026. Campaña: `F1N-TCP-50M-R03`. Estado: **ACEPTADA CON LIMITACIONES**.

## Objetivo y preflight

La campaña reproduce una transferencia TCP legítima de iperf3, limitada a 50 Mbit/s durante 20 s desde Cliente `10.20.0.20` hacia Servidor `10.30.0.10:5201` a través del Sensor. Aporta normalidad L3/L4 de tráfico pesado sin semántica HTTP. Iperf3 crea una conexión de control y otra de datos; no son dos usuarios ni dos streams de carga.

El dry-run fijó `experiment/train`, perfil `TCP-50M`, escenario `iperf-tcp`, argumentos `50M 20` y estrato `throughput`. Git estaba limpio y sincronizado en `491f4572c59ed43439eb399e916c9ba783ae8879`. La reserva de almacenamiento pasó con 129,313,378,304 bytes disponibles en el volumen oficial.

El preflight confirmó NTP en VM01 y las cuatro VM, con desfase absoluto máximo de 0.130 ms; SSH 4/4; rutas Cliente/Kali por el Sensor; NIC externas `DOWN`; bypass `172.17.25.111–114` bloqueado; Suricata sano y captura inactiva. Cliente y Servidor usaron iperf 3.20. `ppi-iperf3` estaba activo, sin sesiones establecidas y escuchaba únicamente en `10.30.0.10:5201`. El sondeo TCP pasó antes de los 70 s de quietud. Claude autorizó una sola ejecución.

| Campo | Valor |
|---|---|
| Quietud / warm-up / settle / cooldown | 70 / 60 / 9 / 30 s |
| SHA matriz | `ad22ce5f8b41110b201f0eeacd2b5f13cc9f945c92cf539e9913e87fefdfa824` |
| SHA argumentos | `7b6496223b57502ffb482ccf32fdc28990b008ba20a1fb176139c9d7790b852f` |
| SHA generador local/remoto | `d4cd42b65f1b22cea0a3f585c2df760af68a8557799c3859eabc803d4f9b4203` |

## Resultado iperf3

El escenario terminó con código cero y stderr vacío:

| Métrica | Emisor | Receptor |
|---|---:|---:|
| Bytes | 125,042,688 | 125,042,688 |
| Duración | 20.001573 s | 20.002092 s |
| Bitrate | 50.013142 Mbit/s | 50.011844 Mbit/s |
| Desviación nominal | +0.026283 % | +0.023688 % |

La sesión usó TCP Cubic. Iperf3 informó RTT medio de 1,242 µs, mínimo de 784 µs y máximo de 2,442 µs, con cuatro retransmisiones: una en el primer segundo, una en el noveno y dos en el undécimo.

Las retransmisiones se conservan como variación observada. No existe un umbral formal para clasificarlas como normales o anómalas ni evidencia para atribuirles una causa. No impidieron completar los mismos bytes en ambos extremos ni sostener el objetivo nominal, y no coincidieron con drops del Sensor.

## Conexiones de control y datos

| Rol | Puerto Cliente | Paquetes | SYN / SYN-ACK / FIN / RST | Span |
|---|---:|---:|---:|---:|
| Control | `59780` | 30 | 1 / 1 / 2 / 0 | 20.006378 s |
| Datos | `59796` | 90,336 | 1 / 1 / 2 / 0 | 20.004789 s |

Los dos handshakes y cierres FIN quedaron completos. Por eso `flow_attempt_count_30s=2`: representa control más datos de una ejecución con `num_streams=1`, no dos usuarios ni dos transferencias independientes.

## Integridad y tráfico pesado

| Control | Resultado |
|---|---:|
| Estado / evidencia completa | `completed` / `true` |
| PCAP archivos / bytes | 1 / 132,456,710 |
| Capturados / recibidos / parseados | 90,366 / 90,366 / 90,366 |
| Drops tcpdump / transferencia / límite | 0 / verificada / no alcanzado |
| Delta Suricata / PCAP | 90,368 / 90,366 |
| Drops / ifdrops / decoder / overflow | 0 / 0 / 0 / 0 |
| EVE esperado / extraído | 15 / 15 |
| Muestras Sensor / stderr | 73 / vacío |
| Lock / captura residual | ausente / inactiva |

Los dos paquetes adicionales del contador Suricata no están identificados; no se les atribuye origen ni significado. PCAP y EVE pasaron sus checkpoints e integridad por separado.

El PCAP supera los bytes de aplicación en 7,414,022 bytes, 5.9292 %. No es una medida de pérdida: el archivo incluye registros PCAP, cabeceras Ethernet/IP/TCP, ACK, control y ambos sentidos, mientras iperf3 informa payload de aplicación.

| Longitud IPv4 | Paquetes | Proporción |
|---|---:|---:|
| Menores de 500 bytes | 3,548 | 3.9263 % |
| De 500 a 1500 bytes | 86,818 | **96.0737 %** |
| Mayores de 1500 bytes | 0 | 0 % |
| Exactamente 1500 bytes | 85,860 | 95.0136 % |

La longitud IPv4 media fue 1,435.78 bytes y la máxima, 1,500. Esta campaña amplía el entrenamiento con tráfico grande legítimo; tamaño alto por sí solo no constituye una etiqueta de ataque.

## Telemetría EVE

EVE contiene trece `stats`, una alerta permitida SID `2260003` —`SURICATA Applayer Protocol detection skipped`— y una anomalía `APPLAYER_PROTO_DETECTION_SKIPPED`, ambas sobre la conexión de datos; `app_proto=failed`.

La telemetría registra que Suricata abandonó la clasificación L7 de iperf3. En esta evidencia no demuestra ataque: el origen está controlado y versionado, la acción fue `allowed`, la transferencia terminó íntegra y no hubo drops ni errores del decoder. El extractor informó `application_observations=0`; alerta y anomalía no son etiqueta ni feature. Su repetición en R01–R03 tampoco permite generalizar que siempre aparecerá.

## Features

El extractor produjo tres filas elegibles de un solo episodio:

| Fin UTC | Paquetes | Byte rate | Media IP | Ratio grande | Attempts | SYN | Completion |
|---|---:|---:|---:|---:|---:|---:|---:|
| `02:39:40` | 21,664 | 3,088,089.5 B/s | 1,425.4475 | 0.95356352 | 2 | 2 | 1 |
| `02:39:50` | 45,328 | 6,488,069.2 B/s | 1,431.3601 | 0.95768620 | 2 | 0 | 0 |
| `02:40:00` | 23,374 | 3,398,411.9 B/s | 1,453.9283 | 0.97330367 | 2 | 0 | 0 |

La completitud SYN vale cero en ventanas sin SYN nuevos según la convención segura del extractor; no representa fallo de la conexión ya establecida. Las tres filas están autocorrelacionadas y deben agruparse por `campaign_id`. No existe vector exacto R03↔R01 ni R03↔R02.

## Comparación R01–R03

Las tres repeticiones transfirieron exactamente 125,042,688 bytes en ambos extremos, aproximadamente a 50 Mbit/s y sin drops de captura. R01 registró una retransmisión, R02 cero y R03 cuatro. Tres observaciones no permiten afirmar tendencia ni causa.

R03 capturó 90,366 paquetes: 466 menos que R01 y 232 más que R02. Conservó 85,860 paquetes exactamente de 1,500 bytes en las tres repeticiones. Frente a R02 tuvo 228 paquetes pequeños y cuatro del rango objetivo adicionales; la proporción de 500–1500 bajó 0.2429 puntos porcentuales. Es variación descriptiva, no degradación ni cambio causal demostrado.

El Sensor produjo 73 muestras: CPU máxima 6.77 %, RSS 781,768 KiB, memoria disponible mínima 14,087,772 KiB y carga máxima 0.42. Se documentan magnitudes, no una clasificación de presión sin umbral formal.

## Integridad raíz

```text
manifest.json          ed515a1d66359729c7be659f1d0a3cd012d0fec14c11ae385aa88697ff62f3bf
capture.pcap0          06d614af76472888f3f04d7e98fe7dacd388346b6053438d973b669838b50edf
eve-slice              ff07be05c811f8066a2b76b497319fba9905c8ee5720759899239d9ac51cd141
campaign SHA256SUMS    c2f0a3f48d96c3dea9b7e53dd4df9e04fcf3e4654247a9baae873958694b7191
multilayer-v1.csv      2d26ace0388568c3fca8a36388814a46d94ea397e2d24dd58507079dc0a601c0
extraction-report      ae367275f9e54681729725d96004c50629e015fc19ebbe905a3ea8ef5b9829dd
feature SHA256SUMS     252b17c0fa87b0a17e4dece9d9601fb18e1665921480f3eb3a923dcef30e767d
ledger                 6084bb6136183da20d524ff6bf1ef7f13eea1ae0a5597846f390f83031f65d66
```

Todos los hashes internos pasaron. El ensamblador, invocado con la raíz explícita `/srv/ppi-evidence/artifacts`, aceptó 81/145 campañas: R03 23/29, 64 faltantes, cero inválidas/advertencias, quince coincidencias dentro de `train` y cero entre particiones. TCP-50M-R03 no añadió coincidencias.

Claude emitió **ACEPTAR CON LIMITACIONES** y autorizó únicamente el preflight independiente de `TCP-100M/R03`. Se descartó su frase “dentro del techo calibrado”: no existe ese gate formal; solo se afirma el resultado medido. También se evita presentar SID 2260003 como universalmente esperado.

**F1N-TCP-50M-R03 ACEPTADA CON LIMITACIONES.** Siguiente autorizado: solo preflight independiente de `F1N-TCP-100M-R03`; no su ejecución.
