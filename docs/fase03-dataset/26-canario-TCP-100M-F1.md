# Decimonoveno canario oficial F1 — TCP 100 Mbit/s R01

Fecha: 26 de julio de 2026. Campaña: `F1N-TCP-100M-R01`. Estado: **ACEPTADA CON LIMITACIONES**.

## Objetivo y contrato

Un stream iperf3 TCP legítimo transmite de Cliente `10.20.0.20` a Servidor `10.30.0.10:5201`, a través del Sensor, con bitrate objetivo de 100 Mbit/s durante 20 s.

| Campo | Valor |
|---|---|
| Propósito / partición | `experiment` / `train` |
| Commit | `943bbe9b78e7ec5b8b3738aa914080e1d99b1ce1` |
| Quietud / warm-up / settle / cooldown | 70 / 60 / 9 / 30 s |
| SHA matriz | `ad22ce5f8b41110b201f0eeacd2b5f13cc9f945c92cf539e9913e87fefdfa824` |
| SHA argumentos | `253484f3d35c6eb92ae1a4c89c7983db5520cb8c6c9aa12f94730f48fb0908bf` |

El preflight confirmó Git limpio, ID libre, 142,223,826,944 bytes disponibles, volumen oficial, NTP en cinco nodos, rutas, iperf3 3.20, captura y Suricata sanos. Las cuatro NIC externas permanecieron `DOWN` y `172.17.25.111-.114` quedó bloqueado.

## Rendimiento

| Métrica | Emisor | Receptor |
|---|---:|---:|
| Bytes | 250,085,376 | 250,085,376 |
| Duración | 20.001725 s | 20.002298 s |
| Bitrate | 100.025523 Mbit/s | 100.022658 Mbit/s |
| Desviación del objetivo | +0.025523 % | +0.022658 % |

iperf3 terminó sin error, con Cubic y cuatro retransmisiones. Los bytes iguales prueban entrega completa en aplicación; no prueban ausencia de pérdida de red. Las retransmisiones se registran como variación recuperada por TCP, con causa no determinada.

No se calcula una “tasa de retransmisión” dividiendo cuatro entre bytes: son unidades incompatibles. Tampoco se crea un umbral de aceptación a partir de una campaña. La calibración histórica obtuvo cero retransmisiones a 100 Mbit/s, mientras esta ejecución obtuvo cuatro; la diferencia queda disponible para comparación descriptiva.

iperf3 abrió dos conexiones esperadas:

| Rol | Puerto Cliente | Paquetes | SYN / SYN-ACK / FIN / RST | Span |
|---|---:|---:|---:|---:|
| control | `56218` | 27 | 1 / 1 / 2 / 0 | 20.023736 s |
| datos | `56234` | 181,657 | 1 / 1 / 2 / 0 | 20.005952 s |

## Integridad y paquetes grandes

| Control | Resultado |
|---|---:|
| Estado / evidencia completa | `completed` / `true` |
| PCAP capturado / recibido / parseado | 181,684 / 181,684 / 181,684 |
| PCAP | 1 archivo / 264,987,469 bytes |
| Drops `tcpdump` | 0 |
| Delta Suricata | 181,686 |
| Drops / ifdrops / decoder / overflow | 0 / 0 / 0 / 0 |
| EVE esperado / extraído | 15 / 15 |
| Muestras Sensor / stderr | 78 / vacío |
| Transferencia / límite PCAP | verificada / no alcanzado |
| Captura residual | inactiva |

Cero drops prueba que los mecanismos de observación no descartaron paquetes; no equivale a demostrar cero pérdida de red.

De 181,684 paquetes IPv4, 173,632 —**95.5681 %**— midieron entre 500 y 1500 bytes; 171,718 midieron exactamente 1500. La longitud media fue 1,428.51 y la máxima 1,500 bytes. Esta celda amplía el rango legítimo pesado pedido por el jurado.

Suricata alcanzó CPU puntual máxima 11.97 %, RSS de 780,308 KiB, memoria disponible mínima de 14,082,236 KiB y carga máxima 0.35.

## Alerta L7 y features

EVE contiene trece `stats`, una alerta permitida SID `2260003` y una anomalía `APPLAYER_PROTO_DETECTION_SKIPPED` sobre el flujo de datos. Es el mismo límite observado en TCP-50M: Suricata abandonó la clasificación de iperf3. Se conserva como telemetría/falso positivo de seguridad; no etiqueta ataque ni entra en las 14 features.

El extractor produjo tres filas elegibles y cero observaciones L7. Sus ratios de paquetes grandes fueron `0.93430602`, `0.96371124` y `0.95802436`. La primera fila contiene los dos SYN, completitud 1.0 y los dos intentos iperf; las otras no contienen SYN nuevos.

Las tres filas son ventanas autocorrelacionadas de un episodio, no repeticiones independientes.

## Integridad raíz

```text
manifest.json          75d17bdc0091ef1cddb85bab9ed9163a9a8d9eb3e10dcfb066c7459a62d7af27
capture.pcap0          751f5acce6a46865224756bb0b6a926e695426fd969a15296cf8f7203fcc9c38
eve-slice              6773c897d3147e7b50ed5d029416e523dea26eee179d58309ad226607cdb6c72
campaign SHA256SUMS    d34fe21870c034dd1e88fee56a167bb4b519205883839fb242f3a53be4936759
multilayer-v1.csv      51ad81fdb5e47f98e091d03a04c198e1f024c600815db3b3662408c27e858581
extraction-report      787d74060adee28bd59c9c62cb9986bce60e92523be27a97833123cd6f959f80
feature SHA256SUMS     d6a5e9b663c720ff2baa283bd58f0d4cb03dd3af49915efcc9bcb2507de94d1a
ledger                 2dab5224b1fb490bf37532e4abd53fff4511d03d7890ccb0e93f5b64d3f9157d
```

Todos los hashes pasaron. El ensamblador informó 145 esperadas, 19 aceptadas, 0 inválidas, 0 advertencias, 0 duplicados y 126 faltantes.

## Decisión

Claude aceptó después de retirar una tasa y umbrales de retransmisión inventados y de separar drops de captura de pérdida de red. Se descartó también su afirmación no sustentada sobre fragmentación.

**CANARIO TCP-100M ACEPTADO CON LIMITACIONES.** El siguiente perfil exacto es `TCP-200M/R01`, con preflight nuevo.
