# Vigesimocuarto canario oficial R02 — TCP 100 Mbit/s

Fecha: 28 de julio de 2026. Campaña: `F1N-TCP-100M-R02`. Estado: **ACEPTADA CON LIMITACIONES**.

## Objetivo y preflight

La celda ejecuta iperf3 TCP a 100 Mbit/s durante 20 s desde Cliente `10.20.0.20` hacia Servidor `10.30.0.10:5201`, a través del Sensor. Iperf3 abre una conexión de control y una de datos; no representan dos cargas ni dos usuarios.

El preflight confirmó Git limpio y sincronizado en `2630288762d0f60b5fd50b3e4b2a123f9f498a08`, ID y lock libres, volumen oficial montado, gate de capacidad `PASS` y 135,701,164,032 bytes disponibles. Las cuatro VM respondieron por SSH. El gate NTP pasó con un desfase absoluto máximo observado de 1.745 ms.

Suricata estaba activo y reportaba cero drops e `ifdrops`. Servidor y Cliente usaban iperf 3.20; `ppi-iperf3` escuchaba exclusivamente en `10.30.0.10:5201`, sin una sesión establecida, y el sondeo desde Cliente pasó. El generador remoto coincidió con el local:

```text
d4cd42b65f1b22cea0a3f585c2df760af68a8557799c3859eabc803d4f9b4203
```

Las rutas Cliente↔Servidor atravesaban el Sensor. Las interfaces externas estaban `DOWN`: `ens34` en Sensor, Servidor y Cliente, y `eth0` en Kali. Las direcciones de bypass `172.17.25.111–114` quedaron bloqueadas por ICMP y TCP/22. El sondeo previo ocurrió antes de los 70 s de quietud y no contaminó el PCAP.

| Campo | Valor |
|---|---|
| Propósito / partición | `experiment` / `train` |
| Escenario / argumentos | `iperf-tcp` / `100M 20` |
| Quietud / warm-up / settle / cooldown | 70 / 60 / 9 / 30 s |
| SHA matriz | `ad22ce5f8b41110b201f0eeacd2b5f13cc9f945c92cf539e9913e87fefdfa824` |
| SHA argumentos | `253484f3d35c6eb92ae1a4c89c7983db5520cb8c6c9aa12f94730f48fb0908bf` |

## Resultado iperf3

El escenario terminó con código cero y stderr vacío:

| Métrica | Emisor | Receptor |
|---|---:|---:|
| Bytes | 250,085,376 | 250,085,376 |
| Duración | 20.001472 s | 20.001920 s |
| Bitrate | 100.026788 Mbit/s | 100.024548 Mbit/s |
| Desviación nominal | +0.026788 % | +0.024548 % |

La sesión usó TCP Cubic y registró cero retransmisiones. El RTT medio fue 1,116 µs, con mínimo de 762 µs y máximo de 1,944 µs. Son observaciones de esta ejecución; no se convierten en umbrales de aceptación.

El PCAP separa las dos conexiones:

| Rol | Puerto Cliente | Paquetes | Span |
|---|---:|---:|---:|
| Control | `45874` | 27 | 20.035471 s |
| Datos | `45884` | 181,623 | 20.013124 s |

En conjunto hubo dos SYN iniciales, dos SYN/ACK, cuatro FIN y cero RST. `flow_attempt_count_30s=2` procede de los dos SYN de control y datos; los FIN no crean intentos.

## Integridad y tráfico pesado

| Control | Resultado |
|---|---:|
| PCAP archivos / bytes | 1 / 264,981,625 |
| Capturados / recibidos / parseados | 181,650 / 181,650 / 181,650 |
| Drops tcpdump | 0 |
| Transferencia / límite PCAP | verificada / no alcanzado |
| Delta Suricata / PCAP | 181,652 / 181,650 |
| Drops / ifdrops / decoder / overflow | 0 / 0 / 0 / 0 |
| EVE extraído / esperado | 16 / 16 |

Los dos paquetes adicionales del contador Suricata no están identificados y no se interpretan como eventos, pérdida ni ataque. `pcap-validation.stderr` tiene 145 bytes correspondientes al banner de lectura de tcpdump; el manifiesto registra cero fallas de validación. Los stderr del escenario y del muestreador están vacíos.

El PCAP supera los bytes de aplicación en 14,896,249 bytes, 5.956465 %. Esta comparación incluye cabeceras, ACK, control y estructura del archivo; no mide pérdida. La integridad se sostiene en bytes iguales en ambos extremos, parseo completo, transferencia verificada, hashes y cero drops.

| Longitud IPv4 | Paquetes | Proporción |
|---|---:|---:|
| Menores de 500 bytes | 8,024 | 4.4173 % |
| De 500 a 1500 bytes | 173,626 | **95.5827 %** |
| Mayores de 1500 bytes | 0 | 0 % |
| Exactamente 1500 bytes | 171,722 | 94.5345 % |

La longitud media fue 1,428.75 bytes y la máxima, 1,500. Esta proporción pesada es una observación L3 de tráfico legítimo, no una señal de ataque por sí sola.

## EVE y clasificación

EVE contiene catorce `stats`, una alerta permitida SID `2260003` —`SURICATA Applayer Protocol detection skipped`— y una anomalía `APPLAYER_PROTO_DETECTION_SKIPPED`. Ambas corresponden a la conexión de datos `45884`; `app_proto=failed`.

Iperf3 completó los mismos bytes en ambos extremos y la acción fue `allowed`. La clasificación fallida se conserva como telemetría/falso positivo de seguridad, no como etiqueta de ataque ni como una observación de aplicación. El extractor registró `application_observations=0`.

## Features

El extractor produjo tres filas elegibles del mismo episodio:

| Fin UTC | Paquetes | Byte rate | Large ratio | Attempts | SYN | Completion |
|---|---:|---:|---:|---:|---:|---:|
| `00:54:30` | 68,320 | 9,687,616.4 B/s | 0.94833138 | 2 | 2 | 1 |
| `00:54:40` | 90,365 | 12,974,166.8 B/s | 0.96070381 | 2 | 0 | 0 |
| `00:54:50` | 22,965 | 3,291,426.9 B/s | 0.95893751 | 2 | 0 | 0 |

`syn_completion_ratio_10s=1` solo en la primera fila; las siguientes no contienen SYN nuevos. Todas conservan `unique_dst_ip_ratio_30s=0.5` y `unique_dst_port_ratio_30s=0.5`. Las filas son ventanas correlacionadas de una ejecución y no tres repeticiones independientes.

## Comparación R01↔R02

Ambas repeticiones transfirieron 250,085,376 bytes por extremo a aproximadamente 100 Mbit/s y sin drops. R01 registró cuatro retransmisiones y R02 ninguna; con dos ejecuciones y sin causa medida, esto no demuestra mejora ni tendencia.

| Métrica | R01 | R02 | R02 − R01 |
|---|---:|---:|---:|
| Paquetes PCAP | 181,684 | 181,650 | −34 (−0.018714 %) |
| Bytes PCAP | 264,987,469 | 264,981,625 | −5,844 (−0.002205 %) |
| Paquetes <500 | 8,052 | 8,024 | −28 |
| Paquetes 500–1500 | 173,632 | 173,626 | −6 |
| Paquetes =1500 | 171,718 | 171,722 | +4 |
| Proporción 500–1500 | 95.5681 % | 95.5827 % | +0.0146 puntos |
| Longitud media | 1,428.51 | 1,428.75 | +0.24 bytes |
| EVE | 15 | 16 | +1 `stats` |

El bitrate recibido cambió solo +0.001890 Mbit/s. La causa de las pequeñas diferencias de paquetes no fue medida. La alineación con bordes UTC explica el reparto por filas —39,547/90,083/52,054 en R01 frente a 68,320/90,365/22,965 en R02—, pero no se usa como causa de la distribución global.

R01 y R02 conservan la misma alerta/anomalía permitida. Sus artefactos, puertos, timestamps, hashes y filas son independientes; no existe vector exacto R01↔R02.

El Sensor produjo 78 muestras: CPU máxima 12.62 %, RSS 781,816 KiB, memoria disponible mínima 14,046,464 KiB y carga máxima 0.34. R01 registró 11.97 %, 780,308 KiB, 14,082,236 KiB y 0.35. No existe un umbral formal para calificar estos recursos como normales o aceptables.

## Integridad raíz

```text
manifest.json          9af5091530850b7adffb9f2f2159e5967c07e108c293ae85a4c4ad77dd203062
capture.pcap0          269716cf7aa222fb347b54ef6a89bd376b1ba9fbf9467edfcf07da123aad50ef
eve-slice              abc6f53ea4d2dbe1e2fa41b6a8dac210d1d49198d4cc8015335283e35c9f25e6
campaign SHA256SUMS    80a52d7a318439d9781e8e408d0492f2c7f1a26cd895b807ea97c6e60cc3a843
multilayer-v1.csv      0bbaa29f7ca750177ca6dfc3461d124fe7c2778198fd84a8a7108b30ae30125b
extraction-report      5ce76523ad90da7b035c66d68ac6b61456694d578f5a7ef1a3d2fa6da853c230
feature SHA256SUMS     9ef76b7dc09daedc1976df812c82bcb49d3875210dba97dd006e4145a18ab5f5
ledger                 8f32bcda8cac030c73afbb6115577370015e8276c1fd42beb5aeda7ddbe372dd
```

El ensamblador aceptó 53/145 campañas, R02 24/29, 92 faltantes globales y 5 de R02, cero inválidas/advertencias, una calibración excluida, seis coincidencias exactas dentro de `train` y cero entre particiones. TCP-100M no añadió coincidencias; el dataset aún no está listo para construir.

Claude aceptó con limitaciones y autorizó únicamente el preflight siguiente. Se descartaron sus tolerancias NTP/bitrate, normalidad de retransmisiones, conversión de memoria, conteo de perfiles y condiciones futuras no sustentadas.

**F1N-TCP-100M-R02 ACEPTADA CON LIMITACIONES.** Siguiente: preflight nuevo de `F1N-TCP-200M-R02`.
