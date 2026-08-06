# Vigesimoséptimo canario oficial R04 — UDP 25 Mbit/s

Fecha: 6 de agosto de 2026. Campaña `F1N-UDP-25M-R04`, partición `validation`. Estado: **ACEPTADA CON LIMITACIONES**.

## Objetivo y preflight

Un flujo UDP benigno de iperf3 a 25 Mbit/s durante 20 s, desde Cliente `10.20.0.20` hacia Servidor `10.30.0.10:5201` a través del Sensor. Usa bloques de 1,448 bytes y aporta tráfico grande legítimo L3/L4; no representa un SLA ni una aplicación productiva.

El dry-run fijó perfil `UDP-25M`, escenario `iperf-udp`, argumentos `["25M","20"]`, estimación de 70,000,000 bytes, matriz SHA-256 `ad22ce5f8b41110b201f0eeacd2b5f13cc9f945c92cf539e9913e87fefdfa824` y argumentos SHA-256 `13602f7b87f04df16d76256c0103ad6ff1679f754cd54e9c6ed2871df05656d6`.

El preflight continuo pasó entre `17:28:43.384` y `17:29:07.320 -05:00` sobre commit limpio y sincronizado `ad3605461702a0194ffa2101709e0084690e3654`. Pasaron contrato/almacenamiento con 121,838,542,848 bytes libres, NTP 5/5 con máximo absoluto 4.969 ms, SSH e identidades, NIC externas `DOWN`, bypass bloqueado, rutas por Sensor, Suricata/captura, listener iperf exclusivo y ocioso, iperf 3.20, probes DNS/ICMP y generador. Log SHA-256 `6ce95af49c8c222e6a23de99099b4a3190ddb03a5cb29ba73b72eba7aa43c735`. Claude autorizó exactamente una ejecución; no hubo reintento ni scoring.

## Resultado UDP y secuencia

| Métrica | Emisor | Receptor |
|---|---:|---:|
| Bytes | 62,504,368 | 62,504,368 |
| Datagramas | 43,166 | 43,166 |
| Duración | 20.001897 s | 20.003372 s |
| Bitrate | 24.999376 Mbit/s | 24.997533 Mbit/s |
| Desviación nominal | −0.002496 % | −0.009870 % |
| Jitter | 0 ms | 0.084857 ms |
| Perdidos / fuera de orden | 0 / 0 | 0 / 0 |

`43,166 × 1,448 = 62,504,368`. La auditoría binaria de sólo lectura encontró IDs `1..43,166`: todos únicos, consecutivos y ordenados, sin faltantes ni duplicados. Esto prueba continuidad en el punto Sensor; el reporte receptor aporta evidencia distinta sobre recepción de aplicación. No se generaliza la fiabilidad de iperf3 3.20.

El PCAP reconcilia 43,166 datagramas de datos, dos UDP de inicialización de cuatro bytes y 27 paquetes TCP de control: 43,195 paquetes. El control TCP `49156` tuvo 1 SYN, 1 SYN/ACK, 2 FIN, 0 RST y span 20.008736 s.

## Integridad, EVE y features

| Control | Resultado |
|---|---:|
| PCAP capturado / recibido / parseado | 43,195 / 43,195 / 43,195 |
| PCAP | 1 archivo / 65,011,217 bytes |
| Drops / límite / transferencia | 0 / no alcanzado / verificada |
| Suricata / PCAP | 43,199 / 43,195 |
| drops / ifdrops / decoder / overflow | 0 / 0 / 0 / 0 |
| Paquetes de 500–1500 bytes | 43,166 / 43,195 (99.9329 %) |
| longitud media / máxima | 1,475.06 / 1,476 bytes |

El delta Suricata +4 queda sin causa atribuida. El PCAP supera los bytes UDP de datos en 2,506,849 bytes (4.010678 %) por cabeceras, inicialización, control y estructura; no mide pérdida. Pérdida de extremo, continuidad de secuencia y drops de captura son controles diferentes aunque los tres pasaron.

EVE contiene catorce registros: doce `stats` y dos `flow` de probes DNS/ICMP iniciados a las `17:29:06/07`, antes del PCAP oficial de `17:34:05`, y emitidos por timeout durante la campaña. No aparecen en el PCAP ni en las 43,195 observaciones de extracción. El slice no contiene eventos `alert`; el metadato `alerted=true` del flow ICMP pertenece al probe permitido previo y no demuestra una alerta del escenario UDP. La ausencia de alertas tampoco prueba benignidad: ésta procede del escenario versionado.

| Fin UTC | Paquetes | Packet rate | Byte rate | Media IP | Ratio grande | SYN / completion |
|---|---:|---:|---:|---:|---:|---:|
| `22:34:10` | 9,530 | 953.0 | 1,404,366.0 | 1,473.6264 | 0.99832109 | 1 / 1 |
| `22:34:20` | 21,581 | 2,158.1 | 3,185,355.6 | 1,476.0000 | 1.00000000 | 0 / 0 |
| `22:34:30` | 12,084 | 1,208.4 | 1,781,811.3 | 1,474.5211 | 0.99892420 | 0 / 0 |

Las tres ventanas correlacionadas suman 43,195. La fila interior coincide exactamente en las catorce features con la fila interior de R02; ninguna fila coincide con R01 ni R03. Se conserva como vector `seen` train↔validation conforme al protocolo congelado, sin deduplicación post hoc.

R01–R04 transfirieron los mismos 62,504,368 bytes y 43,166 datagramas, sin pérdida/reordenamiento. Sus jitter receptores fueron 0.068925, 0.040616, 0.113916 y 0.084857 ms; cuatro episodios no demuestran tendencia ni rango normal.

El Sensor produjo 70 muestras: CPU 0–3.69 %, RSS estable en 782,504 KiB, memoria disponible 14,080,504–14,145,780 KiB y load1 0.13–0.38. No existe umbral formal de suficiencia de recursos.

## Hashes, auditoría y decisión

```text
manifest              530bf4340e67997ab9e6df3720330d6098e52965060884cf225c2dc85d688474
pcap                  7d3796d0fbfbe1924f67ec36fa3e4a3d97e876ef8f200ccce7d80778fc855479
eve                   5be2a4b9e4973775acac92d515576db5fe1f2f17e0e88be01384d1d86747db76
campaign SHA256SUMS   012210a57e1c0d7f9388204058d0cfc5319a0cb6892a32d254368ef315467e73
features CSV          30438b96417aba6e05c0dad83aef8d0ad3f8931a91973a01551a7d5566dac55e
extraction report     4ac296fe7e0b91a9704bdcec69f7509f118c43911860eca7496fcbde0ec59523
feature SHA256SUMS    4235f23ec0934b4126916aedff72a3197369de0ae6773a4454af3b2297cbd724
ledger                bec1cf03abd8c246aedd62ea4a797fc42938d5304a00c7390b87a43a47319ab2
```

Ambos bundles y el listado remoto del PCAP pasaron. El auditor limpio aceptó 114/145: R04 27/29, 31 faltantes, 26 coincidencias totales, nueve cruces y cero inválidas/advertencias. El contador de cruces es subconjunto del total; por diseño, esta nueva coincidencia incrementa ambos. Claude cuestionó inicialmente esa semántica, leyó `find_cross_campaign_duplicate_vectors` y cerró el hallazgo al confirmar el comportamiento del código.

Claude emitió **ACEPTAR CON LIMITACIONES**. Las limitaciones conservadas son el delta Suricata +4 no atribuido, los dos flows diferidos de preflight y el alcance de un laboratorio virtualizado. **F1N-UDP-25M-R04 queda cerrada.** Siguiente autorizado: sólo preflight independiente de `F1N-UDP-50M-R04`; no su captura ni scoring.
