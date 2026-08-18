# Decimoctavo canario oficial F1 — TCP 50 Mbit/s R01

Fecha: 24 de julio de 2026. Campaña: `F1N-TCP-50M-R01`. Estado: **ACEPTADA CON LIMITACIONES**.

## Objetivo

La celda incorpora una transferencia TCP legítima sostenida con iperf3, limitada explícitamente a 50 Mbit/s durante 20 segundos. Complementa las descargas HTTP/HTTPS: aporta carga L3/L4 pesada sin semántica HTTP y permite observar cómo Suricata trata un protocolo de aplicación no clasificado.

La prueba usa una sola pareja de hosts:

```text
Cliente 10.20.0.20 → Sensor → Servidor 10.30.0.10:5201
```

## Contrato y preflight

| Campo | Valor |
|---|---|
| Perfil / repetición | `TCP-50M` / `R01` |
| Escenario / argumentos | `iperf-tcp` / `50M 20` |
| Estrato | `throughput` |
| Propósito / partición | `experiment` / `train` |
| Quietud / warm-up / settle / cooldown | 70 / 60 / 9 / 30 s |
| Commit | `fa148c0a86773b4866931e895d7e989f440565d8` |
| SHA-256 matriz | `ad22ce5f8b41110b201f0eeacd2b5f13cc9f945c92cf539e9913e87fefdfa824` |
| SHA-256 argumentos | `7b6496223b57502ffb482ccf32fdc28990b008ba20a1fb176139c9d7790b852f` |

El preflight confirmó Git limpio/sincronizado, ID libre, volumen oficial montado, 142,356,549,632 bytes disponibles, NTP en los cinco nodos y Suricata/captura en estado sano. Las NIC externas continuaron `DOWN`; las cuatro IP `172.17.25.111-.114` quedaron bloqueadas por ICMP y TCP/22.

Servidor y Cliente ejecutaron iperf 3.20. `ppi-iperf3.service` estaba activo y escuchaba únicamente en `10.30.0.10:5201`. Un sondeo TCP previo pasó; los 70 s de quietud impidieron que formara parte del PCAP oficial.

## Resultado iperf3

| Métrica | Emisor | Receptor |
|---|---:|---:|
| Bytes | 125,042,688 | 125,042,688 |
| Duración | 20.001700 s | 20.003748 s |
| Bitrate | 50.012824 Mbit/s | 50.007704 Mbit/s |
| Desviación frente a 50 Mbit/s | +0.025648 % | +0.015408 % |

La sesión usó TCP Cubic. iperf3 registró RTT medio de 1,202 µs, mínimo de 824 µs y máximo de 2,804 µs. Hubo una retransmisión en el primer intervalo y cero en los diecinueve restantes.

Una retransmisión no es un gate de rechazo aislado: no hubo pérdida de bytes, interrupción, drops del Sensor ni degradación del bitrate. Se conserva como variación real de normalidad. La calibración histórica obtuvo cero retransmisiones a 50 Mbit/s, pero ya consideró aptas ejecuciones TCP controladas con una o dos retransmisiones a 200 Mbit/s.

## Dos conexiones esperadas de iperf3

El PCAP distingue:

| Rol | Puerto Cliente | Paquetes | SYN / SYN-ACK / FIN / RST | Span |
|---|---:|---:|---:|---:|
| control | `35532` | 27 | 1 / 1 / 2 / 0 | 20.021890 s |
| datos | `35540` | 90,805 | 1 / 1 / 2 / 0 | 20.014017 s |

Por eso `flow_attempt_count_30s=2`: no son dos usuarios ni dos streams de datos; son la conexión de control y la conexión de datos creadas por una ejecución iperf3 con `num_streams=1`.

## Integridad y tráfico pesado

| Control | Resultado |
|---|---:|
| Estado / evidencia completa | `completed` / `true` |
| PCAP capturado / recibido / parseado | 90,832 / 90,832 / 90,832 |
| PCAP | 1 archivo / 132,492,618 bytes |
| Drops `tcpdump` | 0 |
| Delta Suricata | 90,834 paquetes |
| Drops / `ifdrops` Suricata | 0 / 0 |
| Decoder invalid / overflow | 0 / 0 |
| EVE esperado / extraído | 14 / 14 |
| Muestras Sensor / stderr | 73 / vacío |
| Transferencia PCAP / límite | verificada / no alcanzado |
| Lock / captura residual | ausente / inactiva |

La diferencia de 7,449,930 bytes —5.9579 %— entre el tamaño del PCAP y los bytes de aplicación iperf3 no indica datos perdidos. El archivo PCAP incluye registros de captura, cabeceras de enlace/IP/TCP, ACK, control y ambos sentidos. La integridad se prueba mediante bytes emisor/receptor iguales, parseo completo, hashes, transferencia verificada y cero drops; no mediante igualdad entre magnitudes de capas distintas.

| Rango IPv4 | Paquetes | Proporción |
|---|---:|---:|
| Menores de 500 bytes | 4,017 | 4.4225 % |
| De 500 a 1500 bytes | 86,815 | **95.5775 %** |
| Mayores de 1500 bytes | 0 | 0 % |
| Exactamente 1500 bytes | 85,860 | 94.5262 % |

La longitud media fue 1,428.66 bytes y la máxima 1,500. Esta es otra muestra de tráfico grande legítimo que evita asociar tamaño de paquete con ataque.

Suricata alcanzó CPU puntual máxima de 6.78 %, RSS de 780,304 KiB, memoria disponible mínima de 14,080,216 KiB y carga máxima 0.29.

## Alerta y anomalía de clasificación L7

EVE contiene doce `stats`, una alerta permitida SID `2260003` —`SURICATA Applayer Protocol detection skipped`— y una anomalía `APPLAYER_PROTO_DETECTION_SKIPPED`, ambas sobre la conexión de datos. El flujo quedó `app_proto=failed`.

La [documentación oficial de Suricata 8.0.3](https://docs.suricata.io/en/suricata-8.0.3/rules/app-layer.html#bail-out-conditions) explica que la detección puede abandonar la clasificación cuando no reconoce el protocolo o se cumplen condiciones de salida; `applayer_proto_detection_skipped` identifica ese caso.

El evento describe correctamente una clasificación no lograda, pero no es evidencia de ataque:

- la acción fue `allowed`;
- no hubo regla maliciosa, drop ni error del decoder;
- iperf3 completó los mismos bytes en ambos extremos;
- el tráfico fue generado por el perfil benigno versionado;
- el extractor registró `application_observations=0` y no usa `alert/anomaly` como etiqueta ni feature.

Se conserva como falso positivo desde la perspectiva de seguridad y como telemetría válida de Suricata. Demuestra por qué una alerta IDS no debe convertirse automáticamente en ground truth de anomalía.

## Features

El extractor produjo tres filas elegibles:

| Ventana UTC | Paquetes 10 s | `byte_rate_10s` | Ratio grande | Intentos 30 s | SYN 10 s | Completitud SYN |
|---|---:|---:|---:|---:|---:|---:|
| `05:47:30` | 42,280 | 6,013,340.7 | 0.95134816 | 2 | 2 | 1.0 |
| `05:47:40` | 45,233 | 6,487,346.0 | 0.95963124 | 2 | 0 | 0.0 |
| `05:47:50` | 3,319 | 476,076.7 | 0.95962639 | 2 | 0 | 0.0 |

`syn_completion_ratio_10s=0` en las filas sin SYN nuevos es el valor seguro definido por el extractor; no significa conexiones fallidas. Las tres filas comparten una ejecución y son autocorrelacionadas. Deben agruparse por `campaign_id`, no contarse como tres repeticiones independientes.

## Integridad raíz

```text
manifest.json          ff1247af05c6546add4fec919fbc3f1d687ea8de836e1d6dfd95e90dfa744534
capture.pcap0          71549ad112ad0093451c36d99111118538e2000cede576ec7de6ffda94d22717
eve-slice              80e2c22a78d8422cbdfae7b4ab53f144830b8ad29e9e6a135d4d050c8d729be7
campaign SHA256SUMS    111f0707cc3fa0249eaf1151383573e1584cc8f210b58cad8e4abb82551b8dd1
multilayer-v1.csv      0c98c8da58cdcafa2e9a9fb1f27c502a10d70b87b30220c4ccf6c2dc93fd3514
extraction-report      427bd78b33287aa781c801580d860c9160dc47e9d2989255589fb00c57cc4dbf
feature SHA256SUMS     2479c222b43f6e892b06830164c95b9b5dce19bf45cb6822dc3f6b04904272f9
ledger                 94d0aba23e611373deb1d902015a68dd401cf34fe97b6960b65040cccb34f9dd
```

Todos los hashes internos pasaron.

## Decisión

Claude emitió primero **ACEPTAR CONDICIONADO** y luego **ACEPTAR** después de cerrar autocorrelación, integridad y ensamblador. Se corrigieron sus porcentajes, atribución del delta Suricata, comparación PCAP/payload y orden de matriz.

El ensamblador informó 145 esperadas, 18 aceptadas, 0 inválidas, 0 advertencias, 0 duplicados y 127 faltantes.

**CANARIO TCP-50M ACEPTADO CON LIMITACIONES.** El siguiente perfil exacto es `TCP-100M/R01`, siempre con preflight nuevo.
