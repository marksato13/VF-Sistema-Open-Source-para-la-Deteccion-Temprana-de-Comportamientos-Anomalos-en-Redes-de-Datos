# Vigesimoséptimo canario oficial R03 — UDP 25 Mbit/s

Fecha: 4 de agosto de 2026. Campaña: `F1N-UDP-25M-R03`. Estado: **ACEPTADA CON LIMITACIONES**.

## Objetivo y preflight

Iperf3 genera un stream UDP benigno de 25 Mbit/s durante 20 s, con bloques de 1,448 bytes, desde Cliente hacia Servidor a través del Sensor. Aporta normalidad L3/L4 pesada; no representa un SLA.

El dry-run fijó `experiment/train`, quietud/warm-up/settle/cooldown `70/60/9/30 s`, commit limpio `2362de072df24350d26f5d3873da2f5a1a35749d`, matriz SHA `ad22ce5f8b41110b201f0eeacd2b5f13cc9f945c92cf539e9913e87fefdfa824` y argumentos SHA `13602f7b87f04df16d76256c0103ad6ff1679f754cd54e9c6ed2871df05656d6`.

El almacenamiento pasó con 128,358,612,992 bytes disponibles. NTP pasó en cinco nodos con máximo absoluto 0.718 ms, SSH 4/4, NIC externas `DOWN`, bypass bloqueado y rutas por Sensor. Suricata estaba sano y la captura inactiva. Iperf 3.20 escuchaba solo en `10.30.0.10:5201`, sin sesión tras el sondeo. Claude autorizó una ejecución.

## Resultado UDP

| Métrica | Emisor | Receptor |
|---|---:|---:|
| Bytes | 62,504,368 | 62,504,368 |
| Datagramas | 43,166 | 43,166 |
| Duración | 20.001668 s | 20.002275 s |
| Bitrate | 24.999662 Mbit/s | 24.998904 Mbit/s |
| Jitter | 0 ms | 0.113916 ms |
| Perdidos / fuera de orden | 0 / 0 | 0 / 0 |
| Pérdida | 0 % | 0 % |

El escenario terminó con código cero y stderr vacío. Bytes y datagramas coinciden; pérdida, orden y jitter son mediciones crudas. “Retransmisiones” no es una métrica de este reporte UDP.

## Composición e integridad

Los 43,195 paquetes del PCAP se reconcilian exactamente:

- 43,166 UDP de datos con payload de 1,448 bytes;
- dos UDP de inicialización con payload de cuatro bytes;
- 27 TCP de control, con 1 SYN, 1 SYN/ACK, 2 FIN, 0 RST y span 20.007223 s.

| Control | Resultado |
|---|---:|
| PCAP archivos / bytes | 1 / 65,011,216 |
| Capturados / recibidos / parseados | 43,195 / 43,195 / 43,195 |
| Drops / transferencia / límite | 0 / verificada / no alcanzado |
| Delta Suricata / PCAP | 43,199 / 43,195 |
| Drops / ifdrops / decoder / overflow | 0 / 0 / 0 / 0 |
| EVE esperado / extraído | 12 / 12 `stats` |
| Muestras Sensor / stderr | 70 / vacío |
| Lock / captura residual | ausente / inactiva |

Los cuatro paquetes adicionales del contador Suricata no tienen causa identificada. Pérdida UDP y drops de observación son controles distintos. EVE sin alertas no prueba benignidad; esta procede del escenario controlado.

El PCAP supera el payload UDP en 2,506,848 bytes —4.010677 %— por estructura, cabeceras, inicialización y control; no mide pérdida.

De 43,195 paquetes IPv4, 43,166 —**99.9329 %**— midieron 500–1500 bytes; 29 fueron menores de 500 y ninguno mayor de 1,500. La media fue 1,475.06 y la máxima, 1,476 bytes.

## Features, comparación y recursos

| Fin UTC | Paquetes | Packet rate | Byte rate | Media IP | Ratio grande | SYN / completion |
|---|---:|---:|---:|---:|---:|---:|
| `23:22:20` | 14,286 | 1,428.6 | 2,106,351.6 | 1,474.4166 | 0.99888002 | 1 / 1 |
| `23:22:30` | 21,582 | 2,158.2 | 3,185,503.2 | 1,476.0000 | 1.00000000 | 0 / 0 |
| `23:22:40` | 7,327 | 732.7 | 1,079,678.0 | 1,473.5608 | 0.99822574 | 0 / 0 |

Las tres filas suman 43,195 y están correlacionadas. La fila interior coincide exactamente con R01, no con R02. Los bordes UTC describen el reparto por ventanas, pero no prueban causa para otras variaciones de red.

R01/R02/R03 transfirieron los mismos 62,504,368 bytes y 43,166 datagramas sin pérdida/reordenamiento. Sus jitter fueron 0.068925, 0.040616 y 0.113916 ms; no demuestran tendencia ni degradación.

El Sensor registró CPU máxima 2.97 %, RSS 781,720 KiB, memoria disponible mínima 14,081,792 KiB y carga máxima 0.40. No existe umbral formal.

## Integridad y decisión

```text
manifest              ee37d73063d7df7159e7c18b077842e79f00f89274c76181ce761e07332541a2
pcap                  f7546d5353d465bf10b79f01418ea0f5d76aa8e4529614f5847e7401e0c8a6bb
eve                   91a0360fb58de77557458afdeca1f482470a11bf9cca427ed5834448ab01c8da
campaign SHA256SUMS   0d86f46dbd1044269cd90b3d05d33fccd6eaa302262681032b5980a5357ee952
features CSV          537428cfd66ea7bdb79311145dfd26afa1a786d302c3a1f9866160cf9a36aa7c
extraction report     7072f40184a5db12ace881784edd1b75acd3d3fc1fb80fffae302b179fbb316a
feature SHA256SUMS    55e2b157d40fb595fcb5b13d7c03ba90eae0744f7819e881e60470998ffb030e
ledger                24fa399b72f665e06215011b6361bddcc01eac9560d078340be3826b0063d1dc
```

Todos los hashes pasaron. El ensamblador aceptó 85/145: R03 27/29, 60 faltantes, cero inválidas/advertencias, diecisiete duplicados `train` y cero cruzados. La fila interior añadió una coincidencia.

Claude emitió **ACEPTAR CON LIMITACIONES** y autorizó solo el preflight de `UDP-50M/R03`. Se corrigió su mención previa de retransmisiones UDP y se limitó la interpretación de bordes UTC.

**F1N-UDP-25M-R03 ACEPTADA CON LIMITACIONES.** Siguiente autorizado: solo preflight independiente de `F1N-UDP-50M-R03`; no su ejecución.
