# Vigesimosexto canario oficial R02 — UDP 10 Mbit/s

Fecha: 28 de julio de 2026. Campaña: `F1N-UDP-10M-R02`. Estado: **ACEPTADA CON LIMITACIONES**.

## Objetivo y preflight

La celda abre la progresión UDP de R02 con una transferencia iperf3 benigna desde Cliente `10.20.0.20` hacia Servidor `10.30.0.10:5201`, solicitada a 10 Mbit/s durante 20 s y con bloques de 1,448 bytes. Incorpora carga legítima de paquetes grandes; no representa un SLA ni una aplicación UDP productiva.

El preflight confirmó Git limpio y sincronizado en `f3f3ece7058609872d58764a338a0763bddcabb6`, ID y lock libres, volumen oficial montado, gate de capacidad `PASS` y 134,905,380,864 bytes disponibles. Las cuatro VM respondieron por SSH. El gate NTP pasó con un desfase absoluto máximo observado de 0.413403 ms.

Suricata estaba activo con cero drops e `ifdrops`. Servidor y Cliente usaban iperf 3.20; el listener TCP de control estaba exclusivamente en `10.30.0.10:5201`, sin sesión establecida, y el sondeo desde Cliente pasó. El generador remoto coincidió con el local:

```text
d4cd42b65f1b22cea0a3f585c2df760af68a8557799c3859eabc803d4f9b4203
```

Las rutas atravesaban el Sensor, las cuatro interfaces externas permanecían `DOWN` y `172.17.25.111–114` quedó bloqueado por ICMP y TCP/22. Los 70 s de quietud drenaron el sondeo previo.

| Campo | Valor |
|---|---|
| Propósito / partición | `experiment` / `train` |
| Escenario / argumentos | `iperf-udp` / `10M 20` |
| Bloque UDP | 1,448 bytes |
| Quietud / warm-up / settle / cooldown | 70 / 60 / 9 / 30 s |
| SHA matriz | `ad22ce5f8b41110b201f0eeacd2b5f13cc9f945c92cf539e9913e87fefdfa824` |
| SHA argumentos | `f13202e70b2d4d581dbb998885e48b1de6e7980d54a8aae59e0d57b9c630a1ae` |

## Resultado iperf3

El escenario terminó con código cero y stderr vacío:

| Métrica | Emisor | Receptor |
|---|---:|---:|
| Bytes | 25,002,616 | 25,002,616 |
| Datagramas de datos | 17,267 | 17,267 |
| Duración | 20.001627 s | 20.002071 s |
| Bitrate | 10.000233 Mbit/s | 10.000011 Mbit/s |
| Jitter | n/a | 0.049850 ms |
| Perdidos / fuera de orden | n/a | 0 / 0 |
| Pérdida | n/a | 0 % |

El receptor informó exactamente los mismos bytes y datagramas. `17,267 × 1,448 = 25,002,616`: no existe el déficit de payload sugerido durante la revisión. Cero pérdida de extremo y cero drops de captura son controles diferentes.

## Composición e integridad del PCAP

El PCAP distingue:

- 17,267 datagramas UDP de datos Cliente→Servidor, con payload de 1,448 bytes y longitud IPv4 de 1,476 bytes;
- dos datagramas UDP iniciales de cuatro bytes, uno por sentido;
- 27 paquetes de la conexión TCP de control, con span de 20.013206 s;
- un SYN, un SYN/ACK, dos FIN y cero RST en el control TCP.

Iperf3 cuenta solo los 17,267 datagramas de datos. El PCAP contiene 17,269 UDP y 17,296 paquetes totales; ambas métricas son compatibles.

| Control | Resultado |
|---|---:|
| PCAP archivos / bytes | 1 / 26,007,323 |
| Capturados / recibidos / parseados | 17,296 / 17,296 / 17,296 |
| Drops tcpdump | 0 |
| Transferencia / límite PCAP | verificada / no alcanzado |
| Delta Suricata / PCAP | 17,300 / 17,296 |
| Drops / ifdrops / decoder / overflow | 0 / 0 / 0 / 0 |
| EVE extraído / esperado | 12 / 12 |

Los cuatro paquetes adicionales del contador Suricata no están identificados y no se convierten en pérdida ni eventos. Los 144 bytes de `pcap-validation.stderr` son el banner de lectura de tcpdump; el manifiesto registra cero fallas. Los stderr del escenario y muestreador están vacíos.

El PCAP supera los bytes UDP de datos en 1,004,707 bytes, 4.018408 %, por cabeceras, inicialización, control TCP y estructura de archivo. No mide pérdida.

| Longitud IPv4 | Paquetes | Proporción |
|---|---:|---:|
| Menores de 500 bytes | 29 | 0.1677 % |
| De 500 a 1500 bytes | 17,267 | **99.8323 %** |
| Mayores de 1500 bytes | 0 | 0 % |
| Exactamente 1500 bytes | 0 | 0 % |

La longitud media fue 1,473.66 bytes y la máxima, 1,476. Los 29 paquetes pequeños son exactamente los 27 TCP de control y los dos UDP iniciales. La cobertura pesada es ground truth benigno L3, no señal de ataque.

## EVE y features

EVE contiene doce `stats`, sin alertas ni eventos de aplicación. `application_observations=0`: este episodio aporta carga y comportamiento L3/L4, no semántica L7. La benignidad procede del escenario controlado y del manifiesto, no de la ausencia de alertas.

El extractor produjo tres filas elegibles del mismo episodio:

| Fin UTC | Paquetes | Byte rate | Large ratio | Attempts | SYN | Completion |
|---|---:|---:|---:|---:|---:|---:|
| `03:35:40` | 4,469 | 657,362.4 B/s | 0.99641978 | 2 | 1 | 1 |
| `03:35:50` | 8,633 | 1,274,230.8 B/s | 1.00000000 | 2 | 0 | 0 |
| `03:36:00` | 4,194 | 617,247.3 B/s | 0.99690033 | 2 | 0 | 0 |

`flow_attempt_count_30s=2` representa el control TCP y el inicio UDP según el contrato del extractor. Las filas son ventanas correlacionadas, no tres repeticiones independientes.

## Comparación R01↔R02

Ambas repeticiones transfirieron exactamente 25,002,616 bytes y 17,267 datagramas por extremo, con cero pérdida, cero reordenamiento y cero drops. R02 registró jitter de 0.049850 ms frente a 0.027371 ms en R01; dos ejecuciones no forman una distribución ni definen tendencia.

| Métrica | R01 | R02 | R02 − R01 |
|---|---:|---:|---:|
| UDP totales | 17,269 | 17,269 | 0 |
| TCP de control | 29 | 27 | −2 |
| Paquetes PCAP | 17,298 | 17,296 | −2 (−0.011562 %) |
| Bytes PCAP | 26,007,490 | 26,007,323 | −167 (−0.000642 %) |
| Paquetes <500 | 31 | 29 | −2 |
| Paquetes 500–1500 | 17,267 | 17,267 | 0 |
| Proporción 500–1500 | 99.8208 % | 99.8323 % | +0.0115 puntos |
| Longitud media | 1,473.49 | 1,473.66 | +0.17 bytes |
| EVE | 12 `stats` | 12 `stats` | 0 |

Los dos paquetes menos pertenecen exclusivamente al control TCP; el flujo UDP de datos e inicialización es idéntico en conteo. La causa del cambio de control no fue medida.

La fase UTC redistribuye las filas —6,630/8,633/2,035 en R01 frente a 4,469/8,633/4,194 en R02—. La ventana interior de 8,633 paquetes reproduce exactamente el vector R01. PCAP, EVE, ledger, timestamps y hashes son independientes: es una coincidencia dentro de `train`, no cruce de partición ni copia de evidencia. La coincidencia por sí sola no prueba un `seed` ni una distribución realista.

El Sensor produjo 69 muestras: CPU máxima 3.01 %, RSS 781,816 KiB, memoria disponible mínima 13,909,232 KiB y carga máxima 0.23. R01 registró 2.27 %, 780,308 KiB, 14,098,396 KiB y 0.32. No existe umbral formal ni tendencia de recursos con solo dos puntos.

## Integridad raíz

```text
manifest.json          c9bd035da5346e52a846339ab517a8951a0a76d22327647d7a15df87e7435e79
capture.pcap0          06fe384b6e20271635933f955cb8e99e2fabdd8684fdbe3e5e141d63f7c83335
eve-slice              a1bd74e21f7178e811df8082cc9c9de674ca7423d66a74a43ecd54a160e143a8
campaign SHA256SUMS    c7a42831aa65a1d986ac70eae0daf98e38874d77a105e64677ed6954d51af8e6
multilayer-v1.csv      6454dab424ab6ea25334e987a1d4cfd8db424ead304cddfaa693c5cdfbbfb2f1
extraction-report      df25c3367ed7c93a1b534bac0961dec251fa65e348446c9772b960867d61c346
feature SHA256SUMS     c258caee7870b257453994d85635610b05dacd6e78a13144ea5546eff2c65c85
ledger                 ec1762708e13a41cd3be8ef6b52d40c78adce18989c9729f8601a6051b19f2f5
```

El ensamblador aceptó 55/145 campañas, R02 26/29, 90 faltantes globales y 3 de R02, cero inválidas/advertencias, una calibración excluida, siete coincidencias exactas dentro de `train` y cero entre particiones. UDP-10M añadió la séptima coincidencia; el dataset aún no está listo para construir.

Claude aceptó con limitaciones y autorizó únicamente el preflight siguiente. Se corrigieron tolerancias, aritmética de payload, `seed`, regresión, causas, umbrales de recursos/jitter/drops y expectativas incorrectas para UDP-25M.

**F1N-UDP-10M-R02 ACEPTADA CON LIMITACIONES.** Siguiente: preflight nuevo de `F1N-UDP-25M-R02`.
