# Vigesimoctavo canario oficial R02 — UDP 50 Mbit/s

Fecha: 28 de julio de 2026. Campaña: `F1N-UDP-50M-R02`. Estado: **ACEPTADA CON LIMITACIONES**.

## Objetivo y preflight

La celda ejecuta el techo UDP calibrado de F1: una transferencia iperf3 benigna desde Cliente `10.20.0.20` hacia Servidor `10.30.0.10:5201`, solicitada a 50 Mbit/s durante 20 s y con bloques de 1,448 bytes. Cierra la progresión UDP 10/25/50 Mbit/s de R02; no representa un SLA ni una aplicación UDP productiva.

El preflight confirmó Git limpio y sincronizado en `12d2212d26903734e048d42884b064c8d32bf4c4`, ID y lock libres, almacenamiento oficial `PASS` y 134,813,913,088 bytes disponibles. Las cuatro VM respondieron por SSH. El gate NTP pasó con un desfase absoluto máximo observado de 0.552 ms.

Suricata estaba activo con cero drops e `ifdrops`. Servidor y Cliente usaban iperf 3.20; el listener TCP de control estaba exclusivamente en `10.30.0.10:5201`, sin sesión establecida, y el sondeo desde Cliente pasó. El generador remoto coincidió con el local:

```text
d4cd42b65f1b22cea0a3f585c2df760af68a8557799c3859eabc803d4f9b4203
```

Las rutas atravesaban el Sensor, las cuatro interfaces externas estaban `DOWN` y el bypass `172.17.25.111–114` quedó bloqueado por ICMP y TCP/22. Los 70 s de quietud drenaron el sondeo.

| Campo | Valor |
|---|---|
| Propósito / partición | `experiment` / `train` |
| Estrato / escenario | `throughput-ceiling` / `iperf-udp` |
| Argumentos / bloque UDP | `50M 20` / 1,448 bytes |
| Quietud / warm-up / settle / cooldown | 70 / 60 / 9 / 30 s |
| SHA matriz | `ad22ce5f8b41110b201f0eeacd2b5f13cc9f945c92cf539e9913e87fefdfa824` |
| SHA argumentos | `7b6496223b57502ffb482ccf32fdc28990b008ba20a1fb176139c9d7790b852f` |

## Resultado iperf3 y discrepancia

El escenario terminó con código cero y stderr vacío, pero el resumen de extremos no es idéntico:

| Métrica | Emisor | Receptor | Diferencia |
|---|---:|---:|---:|
| Bytes | 125,007,288 | 125,005,840 | −1,448 |
| Datagramas | 86,331 | 86,330 | −1 |
| Duración | 20.001426 s | 20.001992 s | +0.000566 s |
| Bitrate | 49.999350 Mbit/s | 49.997356 Mbit/s | −0.001994 Mbit/s |
| Jitter | n/a | 0.099880 ms | n/a |
| Fuera de orden | n/a | 0 | n/a |

El déficit receptor es un datagrama, 0.001158332 % de los enviados. El JSON de iperf3 3.20 declara simultáneamente `lost_packets=0` y `lost_percent=0`; esos campos contradicen los bytes/datagramas de `sum_received` y no se usan para afirmar pérdida cero.

## Investigación de la discrepancia

El análisis binario del PCAP en `ens35` encontró:

```text
count=86331 unique=86331 min=1 max=86331
missing_count=0 duplicates=0
first_seq=1 last_seq=86331
span=20.001049 s
```

El punto de captura Sensor observó todos los datagramas de datos enviados, en secuencia completa y sin duplicados. Esto prueba conservación de evidencia en ese punto; no demuestra que el proceso iperf3 del Servidor contabilizara el último datagrama.

La [FAQ oficial de iperf3](https://software.es.net/iperf/faq.html) explica que la conexión de control puede finalizar antes de que todos los datos sean procesados, dejando datos en vuelo. Además, las [notas oficiales de iperf3 3.21](https://github.com/esnet/iperf/releases/tag/3.21) indican la corrección de un caso donde se informaba erróneamente pérdida UDP cero en una prueba con pérdida. La campaña usó 3.20.

Estas fuentes hacen compatible la observación con cierre/procesamiento tardío o un defecto de reporte, pero no prueban cuál ocurrió. Tampoco permiten afirmar que el datagrama se perdió en tránsito, en el kernel o en el proceso. Para preservar comparabilidad, R02 no cambia versión a mitad de fase; la actualización sincronizada de Cliente y Servidor a 3.21 debe evaluarse después del cierre R02 y antes de R03.

## Composición e integridad

El PCAP contiene 86,333 UDP —86,331 datos + dos iniciales de cuatro bytes— y 27 TCP de control. El control tuvo un SYN, un SYN/ACK, dos FIN, cero RST y span de 20.006374 s.

| Control | Resultado |
|---|---:|
| PCAP archivos / bytes | 1 / 130,017,703 |
| Capturados / recibidos / parseados | 86,360 / 86,360 / 86,360 |
| Drops tcpdump | 0 |
| Transferencia / límite PCAP | verificada / no alcanzado |
| Delta Suricata / PCAP | 86,364 / 86,360 |
| Drops / ifdrops / decoder / overflow | 0 / 0 / 0 / 0 |
| EVE extraído / esperado | 13 / 13 |

Los cuatro paquetes adicionales del contador Suricata no están identificados. Los 144 bytes de `pcap-validation.stderr` son el banner de lectura de tcpdump y las fallas registradas son cero. Los stderr del escenario y muestreador están vacíos.

El PCAP supera los bytes UDP enviados en 5,010,415 bytes, 4.008098 %, por cabeceras, inicialización, control y estructura de archivo. No mide pérdida.

| Longitud IPv4 | Paquetes | Proporción |
|---|---:|---:|
| Menores de 500 bytes | 29 | 0.0336 % |
| De 500 a 1500 bytes | 86,331 | **99.9664 %** |
| Mayores de 1500 bytes | 0 | 0 % |
| Exactamente 1500 bytes | 0 | 0 % |

La longitud media fue 1,475.53 bytes y la máxima, 1,476. Esta cobertura es ground truth benigno pesado observado en el Sensor; no convierte tamaño en etiqueta de ataque ni demuestra representatividad poblacional.

## EVE y features

EVE contiene trece `stats`, sin alertas ni observaciones de aplicación. `application_observations=0`: la celda aporta carga y comportamiento L3/L4, no semántica L7. Esto no prueba que iperf3 sea universalmente inclasificable.

El extractor produjo tres filas elegibles correlacionadas:

| Fin UTC | Paquetes | Byte rate | Large ratio | Attempts | SYN | Completion |
|---|---:|---:|---:|---:|---:|---:|
| `03:58:00` | 35,199 | 5,193,110.4 B/s | 0.99954544 | 2 | 1 | 1 |
| `03:58:10` | 43,169 | 6,371,744.4 B/s | 1.00000000 | 2 | 0 | 0 |
| `03:58:20` | 7,992 | 1,177,831.7 B/s | 0.99837337 | 2 | 0 | 0 |

Los intentos representan control TCP e inicio UDP. Las tres filas proceden de un episodio; la validez del PCAP para features no vuelve irrelevante la discrepancia del extremo.

## Comparación R01↔R02

R01 y R02 contienen exactamente los mismos 86,331 datagramas UDP de datos y dos de inicialización en el Sensor. R01 informó igualdad completa entre extremos; R02 no.

| Métrica | R01 | R02 | R02 − R01 |
|---|---:|---:|---:|
| Emisor / receptor | 86,331 / 86,331 | 86,331 / 86,330 | 0 / −1 |
| UDP en PCAP | 86,333 | 86,333 | 0 |
| TCP de control | 31 | 27 | −4 |
| Paquetes PCAP | 86,364 | 86,360 | −4 (−0.004632 %) |
| Bytes PCAP | 130,018,203 | 130,017,703 | −500 (−0.000385 %) |
| Proporción 500–1500 | 99.9618 % | 99.9664 % | +0.0046 puntos |
| Longitud media | 1,475.47 | 1,475.53 | +0.06 bytes |
| Jitter receptor | 0.132158 ms | 0.099880 ms | −0.032278 ms |
| EVE | 13 `stats` | 13 `stats` | 0 |

Los cuatro paquetes totales menos pertenecen al control TCP. La fase UTC redistribuye las filas —2,020/43,163/41,181 en R01 frente a 35,199/43,169/7,992 en R02—; no existe vector exacto entre repeticiones. No se atribuye causa a jitter, control ni déficit receptor.

El Sensor produjo 73 muestras: CPU máxima 4.48 %, RSS 781,816 KiB, memoria disponible mínima 14,067,624 KiB y carga máxima 0.22. R01 registró 4.47 %, 780,308 KiB, 14,099,108 KiB y 0.42. No se aplican umbrales ni tendencia.

## Integridad raíz

```text
manifest.json          3ac91f28f25aa6f816d250e83e60bc86a2ec3d0cd5c221d6d8d8e7dea0d7251d
capture.pcap0          a79a7411592d89ec98eb74574552333934a315c07e9d4e1af21d1d5425b15851
eve-slice              887d40d10881984204239964f87f30d4b6644da48cbf7cd5da83aa0191567160
campaign SHA256SUMS    d1f7290084de5342bb8dc4ffff6526c9ba9fda48d7c5b5dbf5897f6d937ca1af
multilayer-v1.csv      cef108b8788948f066a4187e362130793a34e9f2f286010494b2353746e9f495
extraction-report      653640d0f366e2d271674fcc8632155b82238141f372ffa42b7253e17f63fa0f
feature SHA256SUMS     d5c38eea1d9a680b5ea4825d3c3ce4e7b7251cac1b8ae71c010fab5bd7dc7dda
ledger                 4eaad4482de46f75e560731be8e808f389d557868a6186462dfbb031dee78768
```

El ensamblador aceptó la evidencia de captura/features: 57/145 campañas, R02 28/29, 88 faltantes globales y una de R02, cero inválidas/advertencias, una calibración excluida, siete coincidencias exactas dentro de `train` y cero entre particiones. UDP-50M no añadió coincidencias. Este gate no comprueba igualdad UDP entre extremos.

Claude aceptó con limitaciones y autorizó únicamente el preflight siguiente. Se corrigieron causalidad del déficit, alcance de la captura, vínculo exacto con el bug oficial, representatividad, clasificación L7 y la afirmación de que la entrega del extremo sería irrelevante.

**F1N-UDP-50M-R02 ACEPTADA CON LIMITACIONES.** Válida para features observadas en el Sensor, con déficit receptor no resuelto y campos de pérdida 3.20 no confiables en esta ejecución. Siguiente: preflight nuevo de `F1N-MIXED-LIGHT-R02`.
