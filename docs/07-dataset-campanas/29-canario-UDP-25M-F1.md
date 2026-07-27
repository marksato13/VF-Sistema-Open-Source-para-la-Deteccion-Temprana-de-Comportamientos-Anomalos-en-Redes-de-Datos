# Vigésimo segundo canario oficial F1 — UDP 25 Mbit/s R01

Fecha: 26 de julio de 2026. Campaña: `F1N-UDP-25M-R01`. Estado: **ACEPTADA CON LIMITACIONES**.

## Objetivo y preflight

Esta celda continúa la progresión UDP de F1 con una transferencia iperf3 legítima desde Cliente `10.20.0.20` hacia Servidor `10.30.0.10:5201`, solicitada a 25 Mbit/s durante 20 s y con bloques de 1,448 bytes. Amplía el rango de carga benigna pesada entre los perfiles de 10 y 50 Mbit/s; no representa un SLA ni una aplicación UDP real.

El preflight confirmó Git limpio y sincronizado en `28dcde1d3c6144f6d3d4f9a355db81c420eda1f0`, ID libre, volumen oficial con 141,402,013,696 bytes disponibles y gate de capacidad en `PASS`. Las cinco máquinas respondieron por SSH y pasaron NTP, con offsets absolutos menores de 0.1 s. Suricata, iperf3, rutas y captura estaban sanos; el generador remoto coincidió con el hash versionado. Las NIC externas permanecieron `DOWN`, el camino Cliente→Sensor→Servidor respondió y el bypass `172.17.25.111-.114` quedó bloqueado por ICMP y TCP/22.

| Campo | Valor |
|---|---|
| Propósito / partición | `experiment` / `train` |
| Argumentos | `25M 20` |
| Quietud / warm-up / settle / cooldown | 70 / 60 / 9 / 30 s |
| SHA matriz | `ad22ce5f8b41110b201f0eeacd2b5f13cc9f945c92cf539e9913e87fefdfa824` |
| SHA argumentos | `13602f7b87f04df16d76256c0103ad6ff1679f754cd54e9c6ed2871df05656d6` |

## Rendimiento UDP

| Métrica | Emisor | Receptor |
|---|---:|---:|
| Bytes | 62,504,368 | 62,504,368 |
| Datagramas de datos | 43,166 | 43,166 |
| Duración | 20.001612 s | 20.002030 s |
| Bitrate | 24.999732 Mbit/s | 24.999210 Mbit/s |
| Jitter | n/a | 0.068925 ms |
| Perdidos / fuera de orden | n/a | 0 / 0 |
| Pérdida | n/a | 0 % |

iperf3 terminó sin error. El receptor informó los mismos bytes y datagramas que el emisor, sin pérdida ni reordenamiento. La calibración histórica comparable registró aproximadamente 24.999 Mbit/s, 0.033 ms de jitter, 0 % de pérdida y cero drops del Sensor. Ambas ejecuciones son coherentes en bitrate, pérdida y captura; sus diferencias puntuales de jitter no establecen mejora, deterioro ni umbral.

Respecto de `UDP-10M/R01`, los datagramas de datos crecieron de 17,267 a 43,166 y el bitrate receptor de 9.997181 a 24.999210 Mbit/s. Esta comparación confirma que se ejecutaron dos niveles distintos de la matriz, pero dos episodios no bastan para inferir una ley de escalamiento.

## Integridad, recursos y paquetes

El PCAP contiene:

- 43,166 datagramas UDP de datos Cliente→Servidor, cada uno con longitud IPv4 de 1,476 bytes;
- dos datagramas iniciales UDP con longitud IPv4 de 32 bytes, uno por sentido;
- 27 paquetes de la conexión TCP de control de iperf3.

| Control | Resultado |
|---|---:|
| Evidencia completa | `true` |
| PCAP capturado / recibido / parseado | 43,195 / 43,195 / 43,195 |
| PCAP | 1 archivo / 65,011,215 bytes |
| Drops `tcpdump` | 0 |
| Delta Suricata | 43,199 |
| Drops / ifdrops / decoder / overflow | 0 / 0 / 0 / 0 |
| EVE esperado / extraído | 12 / 12 |
| Muestras Sensor / stderr | 71 / vacío |
| Transferencia / límite PCAP | verificada / no alcanzado |

De 43,195 paquetes IPv4, 43,166 —**99.9329 %**— midieron entre 500 y 1500 bytes; los 29 restantes fueron los 27 paquetes TCP de control y los dos datagramas UDP iniciales. Ninguno superó 1500 bytes. La longitud media fue 1,475.06 y la máxima 1,476 bytes.

Suricata alcanzó CPU puntual máxima de 3.02 %, RSS de 780,308 KiB, memoria disponible mínima de 14,102,556 KiB y carga máxima de 0.26. EVE contiene únicamente doce eventos `stats`, sin observaciones de aplicación. La etiqueta benigna procede del escenario controlado y del manifiesto, no de la ausencia de alertas.

Cero pérdida reportada por iperf3 y cero drops en tcpdump/Suricata son mediciones diferentes: la primera corresponde a entrega entre extremos; la segunda, a conservación de evidencia en el Sensor.

## Features

El extractor procesó 43,195 observaciones y produjo tres filas elegibles:

| Ventana UTC | Paquetes | Tasa pps | Tasa bytes/s | `large_ip_ratio_10s` |
|---|---:|---:|---:|---:|
| `04:34:00` | 13,410 | 1,341.0 | 1,977,054.0 | 0.99880686 |
| `04:34:10` | 21,582 | 2,158.2 | 3,185,503.2 | 1.00000000 |
| `04:34:20` | 8,203 | 820.3 | 1,208,975.5 | 0.99841521 |

Las tres filas son ventanas autocorrelacionadas de un episodio, no repeticiones independientes. La primera contiene el SYN de control. `flow_attempt_count_30s=2` representa el inicio del control TCP y del flujo UDP según el contrato del extractor. `application_observations=0`: esta celda aporta carga y comportamiento de transporte, no semántica L7.

El 99.9329 % de paquetes dentro de 500–1500 bytes amplía el soporte benigno pedido por el jurado. Demuestra cobertura pesada para este episodio, pero no descarta sesgo del dataset ni prueba qué score asignará el Isolation Forest final, que todavía no está entrenado.

## Integridad raíz

```text
manifest.json          120bb779527e157a7f83f372b0348d6b7452ee005f48a228fe8f0e7e9be0250f
capture.pcap0          2ba38364a337c4bebab78cc10ebad1a948996bb42cfedfa9ff07fa5eec04fa09
eve-slice              d624e05b619fb49d959521cc35951fdc71e9874ae888958ed6522251bcab9e74
campaign SHA256SUMS    7bd132cc3a210e671639cc95cc47643acca2648016b9fd0945b7a1c6bf5f4c45
multilayer-v1.csv      70535db37d67318288234ce296d1d31f372de5af625a84715a1ef47e4d485126
extraction-report      b79aea69a1eae3782e3284a3ee9a84b2241b72360086bd4704c12068d0883c7a
feature SHA256SUMS     6ad2440ec7b34bc2f1740081035c9b2e7f6a937a8dddf4421931c49950347814
ledger                 8ee4e76b9afe6ef132a4544709fee8f5da20bdd235dc998f35957ba6c532b075
```

Todos los hashes pasaron. El ensamblador informó 145 esperadas, 22 aceptadas, 0 inválidas, 0 advertencias, 0 duplicados y 123 faltantes. El dataset completo todavía no puede construirse.

## Decisión

Claude emitió **ACEPTAR CON LIMITACIONES**. Su primera revisión afirmó fragmentación cero sin recibir ese conteo, dijo que la distribución descartaba sesgo y atribuyó causalmente el jitter al laboratorio; esas inferencias se rechazaron. La siguiente consulta perdió el contexto efímero y buscó un archivo inexistente. Una tercera revisión autocontenida corrigió los tres puntos.

**CANARIO UDP-25M ACEPTADO CON LIMITACIONES.** Aporta un segundo nivel de tráfico UDP legítimo pesado, íntegro y sin pérdida observada, sin generalizar a aplicaciones UDP/L7 ni al desempeño futuro del modelo. El siguiente perfil exacto es `UDP-50M/R01`, con preflight nuevo.
