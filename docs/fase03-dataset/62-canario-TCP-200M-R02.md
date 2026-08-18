# Vigesimoquinto canario oficial R02 — TCP 200 Mbit/s

Fecha: 28 de julio de 2026. Campaña: `F1N-TCP-200M-R02`. Estado: **ACEPTADA CON LIMITACIONES**.

## Objetivo y preflight

La celda ejecuta el techo TCP calibrado de F1: un stream iperf3 limitado a 200 Mbit/s durante 20 s desde Cliente `10.20.0.20` hacia Servidor `10.30.0.10:5201`, a través del Sensor. Es una frontera experimental, no un SLA. Iperf3 abre una conexión de control y otra de datos; no son dos cargas.

El preflight confirmó Git limpio y sincronizado en `fced3b998c43962c553de65e95f7e2773286ae5c`, ID y lock libres, volumen oficial montado, gate de capacidad `PASS` y 135,435,935,744 bytes disponibles. Las cuatro VM respondieron por SSH. El gate NTP pasó con un desfase absoluto máximo observado de 0.398070 ms.

Suricata estaba activo con cero drops e `ifdrops`. Servidor y Cliente usaban iperf 3.20; `ppi-iperf3` escuchaba exclusivamente en `10.30.0.10:5201`, sin una sesión establecida, y el sondeo desde Cliente pasó. El generador remoto coincidió con el local:

```text
d4cd42b65f1b22cea0a3f585c2df760af68a8557799c3859eabc803d4f9b4203
```

Las rutas Cliente↔Servidor atravesaban el Sensor. Las interfaces externas estaban `DOWN`: `ens34` en Sensor, Servidor y Cliente, y `eth0` en Kali. Las direcciones de bypass `172.17.25.111–114` quedaron bloqueadas por ICMP y TCP/22. Los 70 s de quietud drenaron el sondeo previo.

| Campo | Valor |
|---|---|
| Propósito / partición | `experiment` / `train` |
| Estrato / escenario | `throughput-ceiling` / `iperf-tcp` |
| Argumentos | `200M 20` |
| Quietud / warm-up / settle / cooldown | 70 / 60 / 9 / 30 s |
| SHA matriz | `ad22ce5f8b41110b201f0eeacd2b5f13cc9f945c92cf539e9913e87fefdfa824` |
| SHA argumentos | `faee06d0a2df5e1d04db840eb446cbee345863478160c705e01d6f39a459bc93` |

## Resultado iperf3

El escenario terminó con código cero y stderr vacío:

| Métrica | Emisor | Receptor |
|---|---:|---:|
| Bytes | 500,039,680 | 500,039,680 |
| Duración | 20.001657 s | 20.002704 s |
| Bitrate | 199.999302 Mbit/s | 199.988834 Mbit/s |
| Desviación nominal | −0.000349 % | −0.005583 % |

La sesión usó TCP Cubic y registró dos retransmisiones. El RTT medio fue 1,026 µs, con mínimo de 563 µs y máximo de 1,943 µs. Estas cifras describen la ejecución; no crean tolerancias ni umbrales universales.

Sobre los dos PCAP aparecen las conexiones completas:

| Rol | Puerto Cliente | Paquetes | Span |
|---|---:|---:|---:|
| Control | `55682` | 29 | 20.011350 s |
| Datos | `55694` | 368,867 | 20.007358 s |

En conjunto hubo dos SYN iniciales, dos SYN/ACK, cuatro FIN y cero RST. `flow_attempt_count_30s=2` procede de los dos SYN; los FIN no crean intentos.

## Integridad y tráfico pesado

| Control | Resultado |
|---|---:|
| PCAP archivos / bytes | 2 / 530,292,350 |
| `capture.pcap0` | 512,001,160 bytes / 356,270 paquetes |
| `capture.pcap1` | 18,291,190 bytes / 12,626 paquetes |
| Capturados / recibidos / parseados | 368,896 / 368,896 / 368,896 |
| Drops tcpdump | 0 |
| Transferencia / límite PCAP | verificada / no alcanzado |
| Delta Suricata / PCAP | 368,898 / 368,896 |
| Drops / ifdrops / decoder / overflow | 0 / 0 / 0 / 0 |
| EVE extraído / esperado | 17 / 17 |

Los dos paquetes adicionales del contador Suricata no están identificados y no se interpretan como eventos, pérdida ni ataque. Los 290 bytes de `pcap-validation.stderr` son los dos banners de lectura de tcpdump; el manifiesto registra cero fallas. Los stderr del escenario y muestreador están vacíos.

El PCAP supera los bytes de aplicación en 30,252,670 bytes, 6.050054 %. Incluye cabeceras, ACK, control y estructura de archivo; no mide pérdida. La integridad se sostiene en bytes iguales en ambos extremos, parseo completo, transferencia verificada, hashes y cero drops.

| Longitud IPv4 | Paquetes | Proporción |
|---|---:|---:|
| Menores de 500 bytes | 21,738 | 5.8927 % |
| De 500 a 1500 bytes | 347,158 | **94.1073 %** |
| Mayores de 1500 bytes | 0 | 0 % |
| Exactamente 1500 bytes | 343,360 | 93.0777 % |

La longitud media fue 1,407.51 bytes y la máxima, 1,500. Esta cobertura L3 demuestra tráfico pesado legítimo al techo TCP; un paquete grande no es ataque por sí solo.

## EVE y features

EVE contiene quince `stats`, una alerta permitida SID `2260003` —`SURICATA Applayer Protocol detection skipped`— y una anomalía `APPLAYER_PROTO_DETECTION_SKIPPED`. Ambas corresponden a la conexión de datos `55694`; `app_proto=failed`.

Iperf3 completó los mismos bytes y la acción fue `allowed`. El evento sigue siendo una alerta diagnóstica de Suricata, pero se conserva como telemetría/falso positivo permitido: no etiqueta ataque ni entra en las 14 features. El extractor registró `application_observations=0`.

Las tres filas elegibles pertenecen al mismo episodio:

| Fin UTC | Paquetes | Byte rate | Large ratio | Attempts | SYN | Completion |
|---|---:|---:|---:|---:|---:|---:|
| `03:08:10` | 103,816 | 14,512,290.4 B/s | 0.93432612 | 2 | 2 | 1 |
| `03:08:20` | 183,796 | 25,951,169.6 B/s | 0.94418268 | 2 | 0 | 0 |
| `03:08:30` | 81,284 | 11,459,082.2 B/s | 0.94265784 | 2 | 0 | 0 |

Todas conservan `unique_dst_ip_ratio_30s=0.5` y `unique_dst_port_ratio_30s=0.5`. Son registros distintos, pero ventanas correlacionadas de una ejecución, no tres repeticiones independientes.

## Comparación R01↔R02

Ambas repeticiones transfirieron exactamente 500,039,680 bytes por extremo a aproximadamente 200 Mbit/s, rotaron a dos PCAP y tuvieron cero drops. R01 registró cinco retransmisiones y R02 dos; sin causa medida y con solo dos ejecuciones, la diferencia no demuestra mejora ni tendencia.

| Métrica | R01 | R02 | R02 − R01 |
|---|---:|---:|---:|
| Paquetes PCAP | 366,334 | 368,896 | +2,562 (+0.699362 %) |
| Bytes PCAP | 530,083,849 | 530,292,350 | +208,501 (+0.039334 %) |
| Paquetes <500 | 19,181 | 21,738 | +2,557 |
| Paquetes 500–1500 | 347,153 | 347,158 | +5 |
| Paquetes =1500 | 343,368 | 343,360 | −8 |
| Proporción 500–1500 | 94.7641 % | 94.1073 % | −0.6568 puntos |
| Longitud media | 1,417.00 | 1,407.51 | −9.49 bytes |
| Retransmisiones | 5 | 2 | −3 |
| EVE | 18 | 17 | −1 `stats` |

El bitrate recibido aumentó 0.027011 Mbit/s. La conexión de control suma un paquete y la de datos 2,561; casi todo el aumento global corresponde a paquetes pequeños. La causa no fue medida.

La fase UTC explica el reparto por filas —45,510/183,312/137,512 en R01 frente a 103,816/183,796/81,284 en R02—, pero no se usa para explicar la distribución global. Los artefactos, puertos, timestamps y hashes son independientes; no existe un vector exacto R01↔R02, lo cual por sí solo no prueba ni refuta reproducibilidad.

El Sensor produjo 87 muestras: CPU máxima 21.23 %, RSS 781,816 KiB, memoria disponible mínima 14,016,148 KiB y carga máxima 0.49. R01 produjo 88: 22.86 %, 780,308 KiB, 13,939,788 KiB y 0.28. Sin un umbral formal, no se califican estos recursos como normales ni se proyecta UDP.

## Integridad raíz

```text
manifest.json          66e77f9f1def04bc2cae411f170c50eae75e9dd3d7138ae225d7d208d97858d3
capture.pcap0          00d76622b5ddf949b1976c716beca3aa240febd861cf967a3ab0ce25877d53a9
capture.pcap1          e0e8d3d533776edf6098bc48e4c9d6c3e65e920b1102af96cf45f16af6863ea9
eve-slice              d48cc0abb60d263f51f654d52d737565b432de02cfa65f41955fbfac54f8a651
campaign SHA256SUMS    dbf1f459b73fe8e3a5f1de8e5fce4ff5f8004f168696603e7f9a23ef0283a28d
multilayer-v1.csv      1daaee527629161242c9e53a0859417d1cbc1beebadf204e130cac5df8bf307c
extraction-report      91d0811820836a0dc8ab77272f923d6008826ec64d54b2119296d6ba893b450d
feature SHA256SUMS     ecff0d4551cba70469d9e78c0f1af4a91eb4979d988ae0b839d2f458da760b90
ledger                 2c594cfeedfdcaa9a9eb53df04052387d062e3a4ea9a3ac38a7f30f5cedfe918
```

El ensamblador aceptó 54/145 campañas, R02 25/29, 91 faltantes globales y 4 de R02, cero inválidas/advertencias, una calibración excluida, seis coincidencias exactas dentro de `train` y cero entre particiones. TCP-200M no añadió coincidencias; el dataset aún no está listo para construir.

Claude aceptó con limitaciones y autorizó únicamente el preflight siguiente. Se corrigieron su inversión PCAP/payload, unidad RSS, causas y normalidad TCP inventadas, tolerancias, clasificación del evento, juicio sobre vectores y proyección de gates.

**F1N-TCP-200M-R02 ACEPTADA CON LIMITACIONES.** Cierra la progresión TCP 50/100/200 Mbit/s de R02. Siguiente: preflight nuevo de `F1N-UDP-10M-R02`.
