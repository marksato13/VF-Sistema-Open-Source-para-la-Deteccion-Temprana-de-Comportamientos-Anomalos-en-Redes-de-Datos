# Vigesimoséptimo canario oficial R02 — UDP 25 Mbit/s

Fecha: 28 de julio de 2026. Campaña: `F1N-UDP-25M-R02`. Estado: **ACEPTADA CON LIMITACIONES**.

## Objetivo y preflight

La celda continúa la progresión UDP de R02 con una transferencia iperf3 benigna desde Cliente `10.20.0.20` hacia Servidor `10.30.0.10:5201`, solicitada a 25 Mbit/s durante 20 s y con bloques de 1,448 bytes. Amplía el rango de carga pesada legítima entre 10 y 50 Mbit/s; no representa un SLA ni una aplicación UDP productiva.

El preflight confirmó Git limpio y sincronizado en `28cea6d3fc5a19406d0f7ab7797a40b994cdd39b`, ID y lock libres, almacenamiento oficial `PASS` y 134,879,150,080 bytes disponibles. Las cuatro VM respondieron por SSH. El gate NTP pasó con un desfase absoluto máximo observado de 0.394426 ms.

Suricata estaba activo con cero drops e `ifdrops`. Servidor y Cliente usaban iperf 3.20; el listener TCP de control estaba exclusivamente en `10.30.0.10:5201`, sin sesión establecida, y el sondeo desde Cliente pasó. El generador remoto y local coincidieron:

```text
d4cd42b65f1b22cea0a3f585c2df760af68a8557799c3859eabc803d4f9b4203
```

Las rutas atravesaban el Sensor, las cuatro interfaces externas estaban `DOWN` y el bypass `172.17.25.111–114` quedó bloqueado por ICMP y TCP/22. Los 70 s de quietud drenaron el sondeo.

| Campo | Valor |
|---|---|
| Propósito / partición | `experiment` / `train` |
| Escenario / argumentos | `iperf-udp` / `25M 20` |
| Bloque UDP | 1,448 bytes |
| Quietud / warm-up / settle / cooldown | 70 / 60 / 9 / 30 s |
| SHA matriz | `ad22ce5f8b41110b201f0eeacd2b5f13cc9f945c92cf539e9913e87fefdfa824` |
| SHA argumentos | `13602f7b87f04df16d76256c0103ad6ff1679f754cd54e9c6ed2871df05656d6` |

## Resultado iperf3

El escenario terminó con código cero y stderr vacío:

| Métrica | Emisor | Receptor |
|---|---:|---:|
| Bytes | 62,504,368 | 62,504,368 |
| Datagramas de datos | 43,166 | 43,166 |
| Duración | 20.001671 s | 20.002116 s |
| Bitrate | 24.999658 Mbit/s | 24.999102 Mbit/s |
| Jitter | n/a | 0.040616 ms |
| Perdidos / fuera de orden | n/a | 0 / 0 |
| Pérdida | n/a | 0 % |

El receptor informó los mismos bytes y datagramas. Cero pérdida de extremo y cero drops de captura son controles separados; ninguno se proyecta al perfil de 50 Mbit/s.

## Composición e integridad

El PCAP contiene:

- 43,166 datagramas UDP de datos Cliente→Servidor, con payload de 1,448 bytes y longitud IPv4 de 1,476 bytes;
- dos datagramas UDP iniciales de cuatro bytes, uno por sentido;
- 27 paquetes TCP de control, con span de 20.013879 s;
- un SYN, un SYN/ACK, dos FIN y cero RST en el control.

Por tanto, 43,168 UDP = 43,166 de datos + 2 iniciales; el total con el control es 43,195 paquetes.

| Control | Resultado |
|---|---:|
| PCAP archivos / bytes | 1 / 65,011,215 |
| Capturados / recibidos / parseados | 43,195 / 43,195 / 43,195 |
| Drops tcpdump | 0 |
| Transferencia / límite PCAP | verificada / no alcanzado |
| Delta Suricata / PCAP | 43,199 / 43,195 |
| Drops / ifdrops / decoder / overflow | 0 / 0 / 0 / 0 |
| EVE extraído / esperado | 12 / 12 |

Los cuatro paquetes adicionales del contador Suricata no están identificados; no se atribuyen a una pila local ni se convierten en pérdida. Los 144 bytes de `pcap-validation.stderr` son el banner de lectura de tcpdump y las fallas registradas son cero. Los stderr del escenario y muestreador están vacíos.

El PCAP supera los bytes UDP de datos en 2,506,847 bytes, 4.010675 %, por cabeceras, inicialización, control y estructura de archivo. No mide pérdida.

| Longitud IPv4 | Paquetes | Proporción |
|---|---:|---:|
| Menores de 500 bytes | 29 | 0.0671 % |
| De 500 a 1500 bytes | 43,166 | **99.9329 %** |
| Mayores de 1500 bytes | 0 | 0 % |
| Exactamente 1500 bytes | 0 | 0 % |

La longitud IPv4 media fue 1,475.06 bytes y la máxima, 1,476. No se compara directamente la media L3 con el bloque UDP de 1,448 bytes porque miden capas distintas.

## EVE y features

EVE contiene doce `stats`, sin alertas ni observaciones de aplicación. `application_observations=0`: esta celda aporta comportamiento L3/L4 y carga, no semántica L7. La etiqueta benigna procede del escenario y manifiesto.

El extractor produjo tres filas elegibles correlacionadas:

| Fin UTC | Paquetes | Byte rate | Large ratio | Attempts | SYN | Completion |
|---|---:|---:|---:|---:|---:|---:|
| `03:46:50` | 9,165 | 1,350,492.0 B/s | 0.99825423 | 2 | 1 | 1 |
| `03:47:00` | 21,581 | 3,185,355.6 B/s | 1.00000000 | 2 | 0 | 0 |
| `03:47:10` | 12,449 | 1,835,685.1 B/s | 0.99895574 | 2 | 0 | 0 |

Los dos intentos son un destino único observado a través del control TCP y el inicio UDP; por ello `unique_dst_ip_ratio_30s=1/2=0.5`, igual que el ratio de puerto. No es una métrica sin definición. Las tres filas pertenecen a un episodio, no son repeticiones independientes.

## Comparación R01↔R02

R01 y R02 reproducen exactamente los totales de payload, datagramas, composición UDP/TCP, paquetes y bytes PCAP, longitudes y EVE. Ambas informan cero pérdida, cero reordenamiento y cero drops.

| Métrica | R01 | R02 | R02 − R01 |
|---|---:|---:|---:|
| Bytes / datagramas | 62,504,368 / 43,166 | 62,504,368 / 43,166 | 0 / 0 |
| Paquetes / bytes PCAP | 43,195 / 65,011,215 | 43,195 / 65,011,215 | 0 / 0 |
| Bitrate receptor | 24.999210 Mbit/s | 24.999102 Mbit/s | −0.000108 Mbit/s |
| Jitter receptor | 0.068925 ms | 0.040616 ms | −0.028309 ms |
| Proporción pesada | 99.9329 % | 99.9329 % | 0 |
| EVE | 12 `stats` | 12 `stats` | 0 |

Los bytes son idénticos; la pequeña diferencia de bitrate proviene de la duración reportada y no equivale a bytes perdidos. El cambio de jitter se conserva sin llamarlo mejora, degradación o variación normal.

La fase UTC redistribuye las filas —13,410/21,582/8,203 en R01 frente a 9,165/21,581/12,449 en R02—. No existe vector exacto entre repeticiones. Los artefactos y tiempos son independientes.

El Sensor produjo 71 muestras: CPU máxima 3.04 %, RSS 781,816 KiB, memoria disponible mínima 14,080,672 KiB y carga máxima 0.64. R01 registró 3.02 %, 780,308 KiB, 14,102,556 KiB y 0.26. No se aplican umbrales ni se infiere tendencia.

## Integridad raíz

```text
manifest.json          36eb0a830d51233a1ad45abcb5f8ccdde9c4946056742ae514f19c175fd1312c
capture.pcap0          1e63597c446588713ea1bfe45d17ef19acf8539587b8af1899fb3bd7f69a915f
eve-slice              84c369268c909c101ba83894fef06353a721fb6b517aec5e65fa9c3d7eb4536f
campaign SHA256SUMS    dcbadf5f591a67b6823b9d01c631bd30b6a02de5effc3575f2f86033141620aa
multilayer-v1.csv      a6ff0a237156f8c38b7413ca506aff34903b060177d507629818a20cf8bb1b7d
extraction-report      4e657c529cf45c38132055db7dc954d649dc2ade4bec2029d268a856ab0cf08a
feature SHA256SUMS     5a9927563da0c91f4ed6425133d8519fbaad98dc5a54095eaafb3d63d117238b
ledger                 e50565334bb89fce3c9b4b727c34e2a51f6ca430926553b56f91d7981b3cd0bc
```

El ensamblador aceptó 56/145 campañas, R02 27/29, 89 faltantes globales y 2 de R02, cero inválidas/advertencias, una calibración excluida, siete coincidencias exactas dentro de `train` y cero entre particiones. UDP-25M no añadió coincidencias; el dataset aún no está listo para construir.

Claude aceptó con limitaciones y autorizó únicamente el preflight siguiente. Se corrigieron composición UDP, capas, aritmética de bitrate, normalidad y causas inventadas, definición del ratio, umbrales y preflight futuro declarado prematuramente.

**F1N-UDP-25M-R02 ACEPTADA CON LIMITACIONES.** Siguiente: preflight nuevo de `F1N-UDP-50M-R02`.
