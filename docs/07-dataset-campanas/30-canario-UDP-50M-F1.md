# Vigésimo tercer canario oficial F1 — UDP 50 Mbit/s R01

Fecha: 27 de julio de 2026. Campaña: `F1N-UDP-50M-R01`. Estado: **ACEPTADA CON LIMITACIONES**.

## Objetivo y preflight

Esta celda ejecuta el techo UDP calibrado de F1: una transferencia iperf3 legítima desde Cliente `10.20.0.20` hacia Servidor `10.30.0.10:5201`, solicitada a 50 Mbit/s durante 20 s y con bloques de 1,448 bytes. Cierra la progresión UDP R01 de 10/25/50 Mbit/s; no representa un SLA ni una aplicación UDP productiva.

El preflight confirmó Git limpio y sincronizado en `f8a67b8b66bd12ce6214b37a63812610c9ae8e7a`, ID libre, volumen oficial con 141,336,776,704 bytes disponibles y gate de capacidad en `PASS`. Las cinco máquinas respondieron por SSH y pasaron NTP, con offsets absolutos menores de 0.1 s. Suricata, iperf3, rutas y captura estaban sanos; el generador remoto coincidió con el hash versionado. Las NIC externas permanecieron `DOWN`, el camino Cliente→Sensor→Servidor respondió y el bypass `172.17.25.111-.114` quedó bloqueado por ICMP y TCP/22.

| Campo | Valor |
|---|---|
| Propósito / partición | `experiment` / `train` |
| Estrato | `throughput-ceiling` |
| Argumentos | `50M 20` |
| Quietud / warm-up / settle / cooldown | 70 / 60 / 9 / 30 s |
| SHA matriz | `ad22ce5f8b41110b201f0eeacd2b5f13cc9f945c92cf539e9913e87fefdfa824` |
| SHA argumentos | `7b6496223b57502ffb482ccf32fdc28990b008ba20a1fb176139c9d7790b852f` |

## Rendimiento UDP

| Métrica | Emisor | Receptor |
|---|---:|---:|
| Bytes | 125,007,288 | 125,007,288 |
| Datagramas de datos | 86,331 | 86,331 |
| Duración | 20.001412 s | 20.007156 s |
| Bitrate | 49.999385 Mbit/s | 49.985031 Mbit/s |
| Jitter | n/a | 0.132158 ms |
| Perdidos / fuera de orden | n/a | 0 / 0 |
| Pérdida | n/a | 0 % |

iperf3 terminó sin error y ambos extremos informaron los mismos bytes y datagramas. Las tres rondas históricas de calibración a 50 Mbit/s registraron aproximadamente 49.998 Mbit/s, 0 % de pérdida, cero drops y jitter de 0.037/0.048/0.040 ms. El jitter oficial de 0.132158 ms es mayor que esas tres observaciones, pero el proyecto no define un umbral de rechazo para jitter. Una ejecución tampoco demuestra causa ni deterioro sistemático; el dato se conserva para compararlo con R02–R05.

Cero pérdida reportada por iperf3 y cero drops en tcpdump/Suricata son controles distintos: el primero mide entrega entre extremos y el segundo conservación de evidencia en el Sensor.

## Progresión UDP R01

| Perfil | Bitrate receptor | Datagramas de datos | Jitter | Pérdida | PCAP | Rango 500–1500 | CPU máx. Sensor |
|---|---:|---:|---:|---:|---:|---:|---:|
| UDP-10M | 9.997181 Mbit/s | 17,267 | 0.027371 ms | 0 % | 17,298 | 99.8208 % | 2.27 % |
| UDP-25M | 24.999210 Mbit/s | 43,166 | 0.068925 ms | 0 % | 43,195 | 99.9329 % | 3.02 % |
| UDP-50M | 49.985031 Mbit/s | 86,331 | 0.132158 ms | 0 % | 86,364 | 99.9618 % | 4.47 % |

La tabla prueba que se ejecutaron tres niveles distintos y que los tres conservaron entrega y captura completas en R01. No establece una ley de escalamiento, una distribución de jitter ni capacidad fuera del techo calibrado.

## Integridad, recursos y paquetes

El PCAP contiene:

- 86,331 datagramas UDP de datos Cliente→Servidor, cada uno con longitud IPv4 de 1,476 bytes;
- dos datagramas iniciales UDP con longitud IPv4 de 32 bytes, uno por sentido;
- 31 paquetes de la conexión TCP de control de iperf3.

| Control | Resultado |
|---|---:|
| Evidencia completa | `true` |
| PCAP capturado / recibido / parseado | 86,364 / 86,364 / 86,364 |
| PCAP | 1 archivo / 130,018,203 bytes |
| Drops `tcpdump` | 0 |
| Delta Suricata | 86,368 |
| Drops / ifdrops / decoder / overflow | 0 / 0 / 0 / 0 |
| EVE esperado / extraído | 13 / 13 |
| Muestras Sensor / stderr | 73 / vacío |
| Transferencia / límite PCAP | verificada / no alcanzado |

De 86,364 paquetes IPv4, 86,331 —**99.9618 %**— midieron entre 500 y 1500 bytes; los 33 restantes fueron los 31 paquetes TCP de control y los dos datagramas UDP iniciales. Ninguno superó 1500 bytes. La longitud media fue 1,475.47 y la máxima 1,476 bytes.

Suricata alcanzó CPU puntual máxima de 4.47 %, RSS de 780,308 KiB, memoria disponible mínima de 14,099,108 KiB y carga máxima de 0.42. EVE contiene únicamente trece eventos `stats`, sin observaciones de aplicación. La etiqueta benigna procede del escenario controlado y del manifiesto, no del ratio de paquetes grandes ni de la ausencia de alertas.

## Features

El extractor procesó 86,364 observaciones y produjo tres filas elegibles:

| Ventana UTC | Paquetes | Tasa pps | Tasa bytes/s | `large_ip_ratio_10s` |
|---|---:|---:|---:|---:|
| `13:08:40` | 2,020 | 202.0 | 295,479.6 | 0.99059406 |
| `13:08:50` | 43,163 | 4,316.3 | 6,370,858.8 | 1.00000000 |
| `13:09:00` | 41,181 | 4,118.1 | 6,076,386.1 | 0.99966004 |

La primera ventana contiene solo el inicio parcial del episodio y el SYN de control; las otras dos concentran la transferencia. `flow_attempt_count_30s=2` representa el inicio del control TCP y del flujo UDP según el contrato del extractor. Las tres filas están autocorrelacionadas y no constituyen repeticiones independientes.

`application_observations=0`: este perfil aporta carga y comportamiento de transporte, no semántica L7. El 99.9618 % de paquetes entre 500 y 1500 bytes refuerza la cobertura benigna pesada solicitada por el jurado en este episodio, pero no elimina sesgos del dataset ni prueba el score del Isolation Forest final, que aún no está entrenado.

## Integridad raíz

```text
manifest.json          c11e70791edecbe730a836dea04321be9ac5d4490cda67bbc8547bb68e8c3a18
capture.pcap0          975edd5e4598a39ce92cc0631f869e02b1313c936dea5387d82637134ea85947
eve-slice              4c3e15b82b7ad0c52fcb2a93ba7736fc09a30559353b85cb165a3482844c48a4
campaign SHA256SUMS    af075b15e4359f8c782a9621affbbab80cc345b945634b0fe188c1333996c7e1
multilayer-v1.csv      ad759081d510ab5a348c495e89bcdfd1d4a4cdb6d461a924ec32ed6142bf3968
extraction-report      5fd3667cf471b875f6aa5df67841a97bfa1e17f1eed22cf6017d80f54a22da3e
feature SHA256SUMS     129c816b704361b2fe8fce1405241777c8ed8af79572fb41187cb4bc6141afe4
ledger                 8d9e212dea799329d5157a38b9bb41051b569d96ba13acd4f0c5f43aebe1c7ad
```

Todos los hashes pasaron. El ensamblador informó 145 esperadas, 23 aceptadas, 0 inválidas, 0 advertencias, 0 duplicados y 122 faltantes. El dataset completo todavía no puede construirse.

## Decisión

Claude emitió **ACEPTAR CON LIMITACIONES**. Su primera revisión llamó “anómalo” y luego “elevado” al jitter sin existir umbral, calificó la carga como “normal” y realizó una afirmación temporal incorrecta sobre las features L7. Esas expresiones se rechazaron. Una segunda revisión autocontenida describió correctamente el jitter como una observación mayor que la calibración, sin atribuir causa ni criterio de rechazo.

**CANARIO UDP-50M ACEPTADO CON LIMITACIONES.** Cierra la progresión UDP R01 de 10/25/50 Mbit/s con entrega y captura completas. No generaliza a aplicaciones UDP/L7 ni al desempeño futuro del modelo. El siguiente perfil exacto es `MIXED-LIGHT/R01`, con preflight nuevo.
