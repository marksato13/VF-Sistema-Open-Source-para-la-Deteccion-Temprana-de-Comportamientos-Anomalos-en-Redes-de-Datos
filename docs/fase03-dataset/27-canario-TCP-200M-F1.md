# Vigésimo canario oficial F1 — TCP 200 Mbit/s R01

Fecha: 26 de julio de 2026. Campaña: `F1N-TCP-200M-R01`. Estado: **ACEPTADA CON LIMITACIONES**.

## Objetivo y preflight

Esta celda ejecuta el techo TCP permitido de F1: un stream iperf3 de Cliente `10.20.0.20` a Servidor `10.30.0.10:5201`, limitado a 200 Mbit/s durante 20 s. Es una frontera experimental, no un SLA.

El preflight confirmó Git limpio en `8d67af066741325737a4f2c0548d53a61f8541c0`, ID libre, almacenamiento oficial con 141,958,598,656 bytes disponibles, NTP en cinco nodos, iperf3 activo, rutas correctas, Suricata/captura sanos y las cuatro NIC externas `DOWN`. El bypass `172.17.25.111-.114` permaneció bloqueado.

| Campo | Valor |
|---|---|
| Propósito / partición | `experiment` / `train` |
| Argumentos | `200M 20` |
| Quietud / warm-up / settle / cooldown | 70 / 60 / 9 / 30 s |
| SHA matriz | `ad22ce5f8b41110b201f0eeacd2b5f13cc9f945c92cf539e9913e87fefdfa824` |
| SHA argumentos | `faee06d0a2df5e1d04db840eb446cbee345863478160c705e01d6f39a459bc93` |

## Rendimiento

| Métrica | Emisor | Receptor |
|---|---:|---:|
| Bytes | 500,039,680 | 500,039,680 |
| Duración | 20.001780 s | 20.005406 s |
| Bitrate | 199.998072 Mbit/s | 199.961822 Mbit/s |
| Retransmisiones | 5 | n/a |

iperf3 terminó sin error y entregó los mismos bytes en ambos extremos. Las cinco retransmisiones describen recuperación TCP o eventos espurios de causa no determinada. No se convierten en porcentaje usando bytes ni establecen un umbral universal. Cero drops de captura tampoco prueba cero pérdida de red.

Las dos conexiones esperadas fueron:

| Rol | Puerto Cliente | Paquetes | SYN / SYN-ACK / FIN / RST | Span |
|---|---:|---:|---:|---:|
| control | `39248` | 28 | 1 / 1 / 2 / 0 | 20.024347 s |
| datos | `39256` | 366,306 | 1 / 1 / 2 / 0 | 20.014309 s |

## Integridad, recursos y paquetes

| Control | Resultado |
|---|---:|
| Evidencia completa | `true` |
| PCAP capturado / recibido / parseado | 366,334 / 366,334 / 366,334 |
| PCAP | 2 archivos / 530,083,849 bytes |
| Drops `tcpdump` | 0 |
| Delta Suricata | 366,336 |
| Drops / ifdrops / decoder / overflow | 0 / 0 / 0 / 0 |
| EVE esperado / extraído | 18 / 18 |
| Muestras Sensor / stderr | 88 / vacío |
| Transferencia / límite PCAP | verificada / no alcanzado |
| Captura residual | inactiva |

De 366,334 paquetes IPv4, 347,153 —**94.7641 %**— midieron entre 500 y 1500 bytes; 343,368 midieron exactamente 1500. La longitud media fue 1,417.00 y la máxima 1,500 bytes.

Suricata alcanzó CPU puntual máxima 22.86 %, RSS de 780,308 KiB, memoria disponible mínima de 13,939,788 KiB y carga máxima 0.28. No hubo presión observable.

EVE contiene 16 `stats`, una alerta permitida SID `2260003` y una anomalía `APPLAYER_PROTO_DETECTION_SKIPPED`, el mismo límite de clasificación iperf3 documentado en TCP-50M/100M. Se conserva como telemetría y no entra en las 14 features ni etiqueta ataque.

## Features

El extractor produjo tres filas elegibles, autocorrelacionadas dentro de un episodio. Sus ratios de paquetes grandes fueron `0.94161723`, `0.94714476` y `0.95029525`. La primera contiene los dos SYN con completitud 1.0; las demás no contienen SYN nuevos. `flow_attempt_count_30s=2` representa las conexiones de control y datos.

## Integridad raíz

```text
manifest.json          3c6024058873a70d2f68d8b5e658f92d6bf5b736c09077ff400ff4a904807c5a
capture.pcap0          dfec95e2f2d44e0b45a4b4e7d0df94353de8b043469a887809443169e62d2724
capture.pcap1          c3cc5b477ac5ab397b013e1e6c7050a5a4f692c28359109a54a65b53ad338b32
eve-slice              0ccc28f15c7eb74445e9c8291f2080f5af5a726f812e7660065a933741337bb0
campaign SHA256SUMS    168bde87a5986bbd426586b13a1ae7286ea80d21aa76932ee6f6cfe595bd835f
multilayer-v1.csv      8a48d81ac04a279b26769d0032a9a0770c404e6667ce296e342c39ce3292c1ac
extraction-report      3d8021b791718e3c48dfd835ad682e1d05fab60e2d58f4b8bf287b153cbabe41
feature SHA256SUMS     e3edfd08fdee49a8dee3dd77c0b336a7857d2feed271d7c14cb3d7426a19ff13
ledger                 f5b19844e1e2b103afa085a43fa175709a5b0d141d201dbfb7c465ee45422174
```

Todos los hashes pasaron. El ensamblador informó 145 esperadas, 20 aceptadas, 0 inválidas, 0 advertencias, 0 duplicados y 125 faltantes.

## Decisión

Claude emitió **ACEPTAR**, pero describió inicialmente las cinco retransmisiones como “normales”. Se limita esa afirmación: son aceptables en esta campaña porque la entrega, bitrate, captura, recursos y evidencia pasaron; su causa no fue determinada y no crean un umbral.

**CANARIO TCP-200M ACEPTADO CON LIMITACIONES.** Cierra la progresión TCP R01 de 50/100/200 Mbit/s. El siguiente perfil exacto es `UDP-10M/R01`, con preflight nuevo.
