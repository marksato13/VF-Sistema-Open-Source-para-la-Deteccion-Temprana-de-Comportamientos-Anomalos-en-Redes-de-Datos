# Vigesimocuarto canario oficial R03 — TCP 100 Mbit/s

Fecha: 1 de agosto de 2026. Campaña: `F1N-TCP-100M-R03`. Estado: **ACEPTADA CON LIMITACIONES**.

## Objetivo y preflight

La campaña reproduce una transferencia TCP legítima de iperf3 limitada a 100 Mbit/s durante 20 s desde Cliente `10.20.0.20` hacia Servidor `10.30.0.10:5201`, a través del Sensor. Aporta normalidad L3/L4 de tráfico pesado sin semántica HTTP. Iperf3 abre una conexión de control y otra de datos; no representan dos usuarios ni dos streams de carga.

El dry-run fijó `experiment/train`, perfil `TCP-100M`, escenario `iperf-tcp`, argumentos `100M 20` y estrato `throughput`. Git estaba limpio y sincronizado en `453a618bcf36d0e3d9e7b2d3b66824559e1206f2`. El volumen oficial y la reserva pasaron con 129,180,680,192 bytes disponibles; campaña, features, ledger y lock estaban libres.

NTP pasó en VM01 y las cuatro VM con desfase absoluto máximo observado de 0.174 ms. SSH respondió 4/4. Las NIC externas se verificaron por MAC y estaban `DOWN`; el bypass `172.17.25.111–114` quedó bloqueado por ICMP y TCP/22. Cliente y Kali enrutarían al Servidor por `10.20.0.1`, y el retorno del Servidor al Cliente por `10.30.0.1`.

Suricata estaba activo con drops, `ifdrops`, decoder invalid y overflow en cero; la captura estaba inactiva. Servidor y Cliente usaban iperf 3.20. `ppi-iperf3` escuchaba exclusivamente en `10.30.0.10:5201`, sin sesiones establecidas. El sondeo TCP pasó, cerró y ocurrió antes de los 70 s de quietud. Claude autorizó una sola ejecución.

| Campo | Valor |
|---|---|
| Quietud / warm-up / settle / cooldown | 70 / 60 / 9 / 30 s |
| SHA matriz | `ad22ce5f8b41110b201f0eeacd2b5f13cc9f945c92cf539e9913e87fefdfa824` |
| SHA argumentos | `253484f3d35c6eb92ae1a4c89c7983db5520cb8c6c9aa12f94730f48fb0908bf` |
| SHA generador local/remoto | `d4cd42b65f1b22cea0a3f585c2df760af68a8557799c3859eabc803d4f9b4203` |

## Resultado iperf3

El escenario terminó con un único `scenario_exit_code=0` y stderr vacío:

| Métrica | Emisor | Receptor |
|---|---:|---:|
| Bytes | 250,085,376 | 250,085,376 |
| Duración | 20.001570 s | 20.002898 s |
| Bitrate | 100.026298 Mbit/s | 100.019658 Mbit/s |
| Desviación nominal | +0.026298 % | +0.019658 % |

La sesión usó TCP Cubic. Iperf3 informó RTT medio de 1,224 µs, mínimo de 799 µs y máximo de 2,232 µs. Registró siete retransmisiones distribuidas en cinco intervalos: `2, 1, 1, 2, 1`.

Las retransmisiones se conservan como variación real recuperada por TCP. No existe un umbral formal para declararlas normales o anómalas ni evidencia para atribuirles una causa. Los mismos bytes llegaron a ambos extremos, el bitrate medido permaneció próximo al objetivo nominal y el Sensor no reportó drops; estas observaciones no eliminan ni explican las retransmisiones.

## Conexiones de control y datos

| Rol | Puerto Cliente | Paquetes | SYN / SYN-ACK / FIN / RST | Span |
|---|---:|---:|---:|---:|
| Control | `50078` | 29 | 1 / 1 / 2 / 0 | 20.019527 s |
| Datos | `50088` | 181,716 | 1 / 1 / 2 / 0 | 20.014577 s |

Los dos handshakes y cierres FIN quedaron completos. `flow_attempt_count_30s=2` procede de control más datos de una ejecución con `num_streams=1`; no representa dos usuarios ni dos transferencias independientes.

## Integridad y tráfico pesado

| Control | Resultado |
|---|---:|
| Estado / evidencia completa | `completed` / `true` |
| PCAP archivos / bytes | 1 / 264,994,753 |
| Capturados / recibidos / parseados | 181,745 / 181,745 / 181,745 |
| Drops tcpdump / transferencia / límite | 0 / verificada / no alcanzado |
| Delta Suricata / PCAP | 181,747 / 181,745 |
| Drops / ifdrops / decoder / overflow | 0 / 0 / 0 / 0 |
| EVE esperado / extraído | 16 / 16 |
| Muestras Sensor / stderr | 78 / vacío |
| Lock / captura residual | ausente / inactiva |

Los dos paquetes adicionales del contador Suricata no están identificados y no reciben una atribución. EVE y PCAP pasaron sus checkpoints e integridad por separado.

El PCAP supera los bytes de aplicación en 14,909,377 bytes, 5.961715 %. No mide pérdida: compara un archivo con registros, cabeceras, ACK, control y ambos sentidos contra payload informado por iperf3.

| Longitud IPv4 | Paquetes | Proporción |
|---|---:|---:|
| Menores de 500 bytes | 8,111 | 4.4628 % |
| De 500 a 1500 bytes | 173,634 | **95.5372 %** |
| Mayores de 1500 bytes | 0 | 0 % |
| Exactamente 1500 bytes | 171,721 | 94.4846 % |

La longitud IPv4 media fue 1,428.06 bytes y la máxima, 1,500. Es tráfico grande legítimo útil para que el modelo no convierta tamaño alto en sinónimo de ataque.

## EVE y clasificación L7

EVE contiene catorce `stats` con cadencia aproximada de ocho segundos, una alerta permitida SID `2260003` —`SURICATA Applayer Protocol detection skipped`— y una anomalía `APPLAYER_PROTO_DETECTION_SKIPPED`, ambas sobre la conexión de datos; `app_proto=failed`.

En esta evidencia controlada los eventos describen una clasificación L7 no lograda, no un ataque: la acción fue `allowed`, el generador es benigno y versionado, la transferencia terminó y no hubo drops ni errores del decoder. El extractor registró `application_observations=0`; alerta y anomalía no son etiqueta ni feature. Que aparezcan en R01–R03 no garantiza que sean universales para iperf3.

## Features

El CSV contiene 24 columnas sin vacíos: metadatos, campos de soporte y las 14 features. Sus tres filas elegibles suman exactamente los 181,745 paquetes observados:

| Fin UTC | Paquetes | Packet rate | Byte rate | Media IP | Ratio grande | Attempts | SYN | Completion |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| `03:06:40` | 90,702 | 9,070.2 p/s | 12,923,820.8 B/s | 1,424.8661 | 0.95315429 | 2 | 2 | 1 |
| `03:06:50` | 90,560 | 9,056.0 p/s | 12,962,302.8 B/s | 1,431.3497 | 0.95766343 | 2 | 0 | 0 |
| `03:07:00` | 483 | 48.3 p/s | 68,114.3 B/s | 1,410.2340 | 0.94202899 | 2 | 0 | 0 |

La tercera fila corta es efecto de la alineación del episodio con bordes UTC. La completitud SYN en cero de las ventanas sin SYN nuevos sigue la convención segura del extractor y no significa que la conexión establecida fallara. Las filas son autocorrelacionadas y deben agruparse por `campaign_id`; no son tres repeticiones. No existe vector exacto R03↔R01 ni R03↔R02.

## Comparación R01–R03

Las tres repeticiones transfirieron 250,085,376 bytes en cada extremo, aproximadamente a 100 Mbit/s y sin drops de captura. R01 registró cuatro retransmisiones, R02 cero y R03 siete. Tres episodios no sustentan tendencia, causalidad ni rango normal.

| Métrica | R01 | R02 | R03 |
|---|---:|---:|---:|
| Paquetes PCAP | 181,684 | 181,650 | 181,745 |
| Paquetes <500 | 8,052 | 8,024 | 8,111 |
| Paquetes 500–1500 | 173,632 | 173,626 | 173,634 |
| Paquetes =1500 | 171,718 | 171,722 | 171,721 |
| Proporción 500–1500 | 95.5681 % | 95.5827 % | 95.5372 % |
| Longitud media | 1,428.51 | 1,428.75 | 1,428.06 |
| Retransmisiones | 4 | 0 | 7 |

R03 tuvo 61 paquetes más que R01 y 95 más que R02. La proporción objetivo bajó 0.0309 y 0.0455 puntos porcentuales, respectivamente. Son diferencias descriptivas muy pequeñas; no se les asigna causa ni significancia estadística.

El Sensor produjo 78 muestras: CPU máxima 11.92 %, RSS 781,768 KiB, memoria disponible mínima 14,059,272 KiB y carga máxima 0.52. Sin umbral formal, solo se documentan magnitudes.

## Integridad raíz

```text
manifest.json          e66ed0b825e9af80e7352167fbad17488886ecaa46ed97800853ea2d5e822b90
capture.pcap0          ae205e427484c6c466854be5ce655c4e9419c2d83fbb6d4cf2ad6d8fde98e657
eve-slice              b59d6841b9dfa3d925200809e0ed47fd5a0e35c52f1bd52cfeeac46f5f8cfe10
campaign SHA256SUMS    f8bdb4a9c246f184935872ebdd39b81fccc9774b4cbafdb97f6c8d83a0e5902d
multilayer-v1.csv      0b073960a2831fcbb4421ad876a045aaa5ff2950699179aa850281181de7cae9
extraction-report      e84aaeff39027e71fc46aa0d8141e37e4c2ccc00d6f7be9f12e3f4497d6f916c
feature SHA256SUMS     0cdbc7e19458ddbeaff4f0d48bf162a6988fcb87e32c0a413d551cf3a830ae11
ledger                 d03028927ac8367ef53e909db408d5adfb445eb1f82b940a3546d7d1cd414c18
```

Todos los hashes internos pasaron. El ensamblador, invocado con la raíz explícita `/srv/ppi-evidence/artifacts`, aceptó 82/145 campañas: R03 24/29, 63 faltantes, cero inválidas/advertencias, quince coincidencias dentro de `train` y cero entre particiones. TCP-100M-R03 no añadió coincidencias.

Claude emitió **ACEPTAR CON LIMITACIONES** y autorizó únicamente el preflight independiente de `TCP-200M/R03`. Se corrigió su doble conteo: su propuesta 83/145 y R03 25/29 sumaba otra vez una campaña que la auditoría ya incluía; los valores válidos son 82/145 y 24/29.

**F1N-TCP-100M-R03 ACEPTADA CON LIMITACIONES.** Siguiente autorizado: solo preflight independiente de `F1N-TCP-200M-R03`; no su ejecución.
