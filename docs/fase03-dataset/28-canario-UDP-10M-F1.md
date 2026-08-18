# Vigésimo primer canario oficial F1 — UDP 10 Mbit/s R01

Fecha: 26 de julio de 2026. Campaña: `F1N-UDP-10M-R01`. Estado: **ACEPTADA CON LIMITACIONES**.

## Objetivo y preflight

Esta celda abre la progresión UDP de F1 con una transferencia iperf3 legítima desde Cliente `10.20.0.20` hacia Servidor `10.30.0.10:5201`, solicitada a 10 Mbit/s durante 20 s y con bloques de 1,448 bytes. Su propósito es incorporar carga benigna de paquetes grandes; no representa un SLA ni una aplicación UDP real.

El preflight confirmó Git limpio en `92a775f8f23171088f78e98fa60680e818c593dc`, ID y rutas de salida libres, almacenamiento oficial con 141,428,244,480 bytes disponibles, NTP dentro del gate en los cinco nodos, iperf3 activo, ruta Cliente→Sensor→Servidor, Suricata/captura sanos y las cuatro NIC externas `DOWN`. El bypass `172.17.25.111-.114` continuó bloqueado.

| Campo | Valor |
|---|---|
| Propósito / partición | `experiment` / `train` |
| Argumentos | `10M 20` |
| Quietud / warm-up / settle / cooldown | 70 / 60 / 9 / 30 s |
| SHA matriz | `ad22ce5f8b41110b201f0eeacd2b5f13cc9f945c92cf539e9913e87fefdfa824` |
| SHA argumentos | `f13202e70b2d4d581dbb998885e48b1de6e7980d54a8aae59e0d57b9c630a1ae` |

## Rendimiento UDP

| Métrica | Emisor | Receptor |
|---|---:|---:|
| Bytes | 25,002,616 | 25,002,616 |
| Datagramas de datos | 17,267 | 17,267 |
| Duración | 20.001519 s | 20.007733 s |
| Bitrate | 10.000287 Mbit/s | 9.997181 Mbit/s |
| Jitter | n/a | 0.027371 ms |
| Perdidos / fuera de orden | n/a | 0 / 0 |
| Pérdida | n/a | 0 % |

iperf3 terminó sin error. El receptor informó los mismos bytes y datagramas que el emisor, sin pérdida ni reordenamiento. La calibración histórica comparable había observado aproximadamente 10.000 Mbit/s, 0.125 ms de jitter, 0 % de pérdida y cero drops del Sensor. La ejecución oficial es coherente con esa referencia, pero una única repetición no permite definir una distribución ni un umbral operativo.

El PCAP distingue:

- 17,267 datagramas UDP de datos Cliente→Servidor, cada uno con longitud IPv4 de 1,476 bytes;
- dos datagramas iniciales UDP de cuatro bytes, uno por sentido;
- 29 paquetes de la conexión TCP de control de iperf3.

Por ello, iperf3 cuenta 17,267 datagramas de datos, mientras que el PCAP contiene 17,269 paquetes UDP y 17,298 paquetes totales. No hay contradicción entre ambas métricas.

## Integridad, recursos y paquetes

| Control | Resultado |
|---|---:|
| Evidencia completa | `true` |
| PCAP capturado / recibido / parseado | 17,298 / 17,298 / 17,298 |
| PCAP | 1 archivo / 26,007,490 bytes |
| Drops `tcpdump` | 0 |
| Delta Suricata | 17,302 |
| Drops / ifdrops / decoder / overflow | 0 / 0 / 0 / 0 |
| EVE esperado / extraído | 12 / 12 |
| Muestras Sensor / stderr | 69 / vacío |
| Transferencia / límite PCAP | verificada / no alcanzado |

De 17,298 paquetes IPv4, 17,267 —**99.8208 %**— midieron entre 500 y 1500 bytes; 31 fueron menores de 500 y ninguno superó 1500. La longitud media fue 1,473.49 y la máxima 1,476 bytes. Los 31 pequeños corresponden exactamente a los 29 TCP de control y los dos datagramas UDP iniciales.

Suricata alcanzó CPU puntual máxima de 2.27 %, RSS de 780,308 KiB, memoria disponible mínima de 14,098,396 KiB y carga máxima de 0.32. EVE contiene únicamente doce eventos `stats`: no hubo alerta ni observación L7. La ausencia de alertas no establece la etiqueta; la benignidad procede del escenario controlado y del manifiesto.

Cero pérdida en iperf3 y cero drops de captura son controles distintos. El primero describe la entrega reportada por los extremos UDP; el segundo evalúa si tcpdump y Suricata perdieron evidencia en el Sensor.

## Features

El extractor procesó 17,298 observaciones y produjo tres filas elegibles para `10.20.0.20`:

| Ventana UTC | Paquetes | Tasa pps | Tasa bytes/s | `large_ip_ratio_10s` |
|---|---:|---:|---:|---:|
| `03:58:00` | 6,630 | 663.0 | 976,183.6 | 0.99743590 |
| `03:58:10` | 8,633 | 863.3 | 1,274,230.8 | 1.00000000 |
| `03:58:20` | 2,035 | 203.5 | 298,436.8 | 0.99312039 |

Las tres filas son ventanas autocorrelacionadas de un solo episodio, no tres repeticiones independientes. En la primera, `syn_count_10s=1` corresponde al control TCP. `flow_attempt_count_30s=2` representa el inicio del control TCP y el primer datagrama del flujo UDP según el contrato del extractor. `application_observations=0`, por lo que esta campaña aporta señales L3/L4 y carga, pero no semántica L7.

La campaña responde directamente a la observación del jurado: incorpora como ground truth benigno un episodio donde casi todos los paquetes están entre 500 y 1500 bytes. Esto amplía la cobertura con la que se entrenará el modelo final; **no** demuestra todavía qué score asignará Isolation Forest, porque el modelo final aún no ha sido entrenado ni evaluado.

## Integridad raíz

```text
manifest.json          85d86f0bf9b0f3ffbd72f06001cd74d9a417057b1dda08c5b26cfd4d3b7a7ea4
capture.pcap0          3c24042817e8121cde8094339eba549bdd12cd6a8f4fe55114a83165ee33167f
eve-slice              bafe6572a4bb28f480bbe097988710bad0f3dc7c4dbe1e4bbcdd1ce82a3418a7
campaign SHA256SUMS    9cdd703a3a442d11fec4696857f00b92cae48210d8bb0fe8b4ae926149ed4725
multilayer-v1.csv      ec4ad779862fb14faa8105072a589430805347b2fe78c4efb450c0fe6ec44ddd
extraction-report      3fb97739ec924aebf32f3721a44802ad219d178ae3b9421246b3f6101bc37904
feature SHA256SUMS     af914ecf68744b3ee0de82dc642bc83ca3ae097c4fb9d5bf2b8b814ce370e7ff
ledger                 4d0161389eb27c43ff31fe9777696b726e18946b10a813224a362bdaa85340fb
```

Todos los hashes pasaron. El ensamblador informó 145 esperadas, 21 aceptadas, 0 inválidas, 0 advertencias, 0 duplicados y 124 faltantes. El dataset completo todavía no puede construirse.

## Decisión

Claude emitió finalmente **ACEPTAR CON LIMITACIONES**. Sus dos primeras respuestas introdujeron tolerancias y gates no definidos, y luego mezclaron el perfil actual con `UDP-25M`; esas afirmaciones se rechazaron. La tercera revisión utilizó los conteos correctos y separó benignidad, telemetría y futuro modelado.

**CANARIO UDP-10M ACEPTADO CON LIMITACIONES.** Aporta tráfico legítimo pesado reproducible y una línea base UDP a 10 Mbit/s, sin afirmar generalización a aplicaciones UDP ni desempeño futuro del modelo. El siguiente perfil exacto es `UDP-25M/R01`, siempre con un preflight nuevo.
