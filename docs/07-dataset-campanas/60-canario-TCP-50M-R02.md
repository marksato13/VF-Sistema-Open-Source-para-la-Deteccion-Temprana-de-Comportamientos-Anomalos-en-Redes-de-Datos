# Vigesimotercer canario oficial R02 — TCP 50 Mbit/s

Fecha: 28 de julio de 2026. Campaña: `F1N-TCP-50M-R02`. Estado: **ACEPTADA CON LIMITACIONES**.

## Objetivo y preflight

La celda ejecuta iperf3 TCP a 50 Mbit/s durante 20 s desde Cliente `10.20.0.20` hacia Servidor `10.30.0.10:5201`, a través del Sensor. Iperf3 crea una conexión de control y una de datos; no son dos usuarios ni dos streams de carga.

El preflight confirmó Git limpio y sincronizado en `9b051c2bdb84b6b37cfa1d5266ab8ac514470e1c`, ID/captura libres, almacenamiento oficial PASS y 135,833,837,568 bytes disponibles. Las cuatro VM respondieron por SSH y NTP pasó con desfase absoluto máximo de 0.718060 ms.

Cliente y Servidor usaban iperf 3.20. `ppi-iperf3` estaba activo, escuchaba únicamente en `10.30.0.10:5201` y no tenía sesión establecida. El sondeo TCP desde Cliente pasó. Servicios, generador, rutas y aislamiento también pasaron; las cuatro NIC externas estaban `DOWN` y el bypass `172.17.25.111–114` quedó bloqueado. La quietud de 70 s drenó el sondeo previo.

| Campo | Valor |
|---|---|
| Propósito / partición | `experiment` / `train` |
| Escenario / argumentos | `iperf-tcp` / `50M 20` |
| Quietud / warm-up / settle / cooldown | 70 / 60 / 9 / 30 s |
| SHA matriz | `ad22ce5f8b41110b201f0eeacd2b5f13cc9f945c92cf539e9913e87fefdfa824` |
| SHA argumentos | `7b6496223b57502ffb482ccf32fdc28990b008ba20a1fb176139c9d7790b852f` |

## Resultado iperf3

El escenario terminó con código cero y stderr vacío:

| Métrica | Emisor | Receptor |
|---|---:|---:|
| Bytes | 125,042,688 | 125,042,688 |
| Duración | 20.001619 s | 20.004554 s |
| Bitrate | 50.013027 Mbit/s | 50.005689 Mbit/s |
| Desviación nominal | +0.026053 % | +0.011378 % |

La sesión usó TCP Cubic. Iperf3 registró RTT medio 1,168 µs, mínimo 877 µs y máximo 1,883 µs, con cero retransmisiones. Estos valores se conservan como observación, sin umbral de tolerancia.

El PCAP distingue:

| Rol | Puerto Cliente | Paquetes | Span |
|---|---:|---:|---:|
| Control | `41810` | 28 | 20.039616 s |
| Datos | `41812` | 90,106 | 20.012479 s |

En conjunto hubo dos SYN, dos SYN/ACK, cuatro FIN y cero RST. `flow_attempt_count_30s=2` proviene de los dos SYN iniciales de control/datos; los FIN no crean intentos.

## Integridad y tráfico pesado

| Control | Resultado |
|---|---:|
| PCAP archivos / bytes | 1 / 132,434,627 |
| Capturados / recibidos / parseados | 90,134 / 90,134 / 90,134 |
| Drops tcpdump | 0 |
| Transferencia / límite PCAP | verificada / no alcanzado |
| Delta Suricata / PCAP | 90,137 / 90,134 |
| Drops / ifdrops / decoder / overflow | 0 / 0 / 0 / 0 |
| EVE extraído / esperado | 18 / 18 |

Los tres paquetes adicionales del contador Suricata no están identificados y no se interpretan como eventos ni drops.

El PCAP supera los bytes de aplicación en 7,391,939 bytes, 5.9115 %. No es pérdida ni retransmisión: compara un archivo con registros/cabeceras/ACK/control y bytes de payload informados por iperf3. La integridad se prueba por bytes iguales en extremos, parseo, hashes y cero drops.

| Longitud IPv4 | Paquetes | Proporción |
|---|---:|---:|
| Menores de 500 bytes | 3,320 | 3.6834 % |
| De 500 a 1500 bytes | 86,814 | **96.3166 %** |
| Mayores de 1500 bytes | 0 | 0 % |
| Exactamente 1500 bytes | 85,860 | 95.2582 % |

La longitud media fue 1,439.31 bytes y la máxima, 1,500. La proporción pesada es una métrica L3, no L7.

## EVE y clasificación

EVE contiene trece `stats`, tres `flow`, una alerta permitida SID `2260003` —`SURICATA Applayer Protocol detection skipped`— y una anomalía `APPLAYER_PROTO_DETECTION_SKIPPED`. La alerta/anomalía corresponde a la conexión de datos `41812`; `app_proto=failed`.

Iperf3 completó los mismos bytes en ambos extremos y la acción fue `allowed`. La clasificación no lograda se conserva como telemetría/falso positivo de seguridad; no etiqueta ataque ni entra en las 14 features. `application_observations=0`.

Los tres `flow` diferidos no pertenecen a iperf3:

- un IPv6-ICMP iniciado a `19:14:26`;
- dos flujos mDNS iniciados a `19:14:34`;
- todos comenzaron antes del manifiesto `19:14:52` y fueron emitidos después por timeout;
- sus destinos multicast están fuera del filtro PCAP LAN↔DMZ;
- el extractor ignora `event_type=flow`.

Su presencia se documenta; no se exige que se repitan en campañas futuras.

## Features

El extractor produjo tres filas elegibles del mismo episodio:

| Fin UTC | Paquetes | Byte rate | Large ratio | Attempts | SYN | Completion |
|---|---:|---:|---:|---:|---:|---:|
| `00:16:00` | 6,114 | 844,465.1 B/s | 0.92280013 | 2 | 2 | 1 |
| `00:16:10` | 44,958 | 6,485,916.0 B/s | 0.96550113 | 2 | 0 | 0 |
| `00:16:20` | 39,062 | 5,642,677.2 B/s | 0.96679637 | 2 | 0 | 0 |

`syn_completion_ratio_10s=1` solo en la primera fila; las siguientes no contienen SYN nuevos. Todas conservan `unique_dst_ip_ratio_30s=0.5` y `unique_dst_port_ratio_30s=0.5`. Las tres ventanas están correlacionadas y no son repeticiones.

## Comparación R01↔R02

Ambas repeticiones transfirieron 125,042,688 bytes en cada extremo a aproximadamente 50 Mbit/s, sin drops. R01 tuvo una retransmisión; R02, cero. No se interpreta como estabilización ni como tendencia.

R02 contiene 90,134 paquetes frente a 90,832 en R01: −698 (−0.7685 %). Hay 697 paquetes pequeños menos, un paquete objetivo menos y exactamente los mismos 85,860 paquetes de 1,500 bytes. La proporción objetivo pasó de 95.5775 % a 96.3166 %, +0.7391 puntos, y la media de 1,428.66 a 1,439.31 bytes.

La causa no fue medida. La alineación UTC explica el reparto de filas —42,280/45,233/3,319 en R01 frente a 6,114/44,958/39,062 en R02—, pero no se usa para explicar la distribución global de paquetes. Como las features de tamaño y tasa cambian, la variación sí aparece en los vectores.

R01 tuvo EVE 14/14; R02, 18/18 por un `stats` y tres `flow` adicionales. Ambas conservan la misma alerta/anomalía permitida. Sus PCAP, EVE, CSV, ledger, timestamps y puertos son independientes; no existe vector exacto R01↔R02.

El Sensor produjo 73 muestras: CPU máxima 6.77 %, RSS 781,816 KiB, memoria disponible mínima 14,052,384 KiB y carga máxima 0.22. R01 registró CPU 6.78 %, RSS 780,304 KiB y carga 0.29. No existe umbral formal para declarar estos recursos “normales”.

## Integridad raíz

```text
manifest.json          33e91f47fddd769ce8677f6f3e03812a37ba5b5a00f3e3fbce51d1668510712a
capture.pcap0          dd904fc4154764d07c3b5d8ac987b15a5fb1388c80634a6299b0abfdaab01ede
eve-slice              a0ec1186a2dcd8f08cb53dc54995aaa2c2e7e324b72903c28cb8185d15ff1dc7
campaign SHA256SUMS    1d87363556920279148a5b10477840d6380179bb589370d2e16fe256024bdddb
multilayer-v1.csv      6d7deb35095d695dca1131de10f85822024dc05d0dc1ec6a34085c7817b3fe52
extraction-report      8a47d33efc61bb8ca973adffde2c264724c6ab419a89607cf86dbd85877db71d
feature SHA256SUMS     8bea06156c3928a59fab6e8217051fe9704ebc602a57641ced7597fe11533ec2
ledger                 4c1bc102b15b08089f76743e598abd665cf8bad49c2840283e113a32174fd315
```

El ensamblador aceptó 52/145 campañas, R02 23/29, 93 faltantes globales y 6 de R02, cero inválidas/advertencias, una calibración excluida, seis coincidencias dentro de `train` y cero entre particiones. TCP-50M no añadió coincidencias.

Claude aceptó con limitaciones y autorizó el preflight siguiente. Se corrigieron capa de la métrica, causalidad, tolerancias, timestamps, intentos, completitud, recursos y gates/proyecciones inventados.

**F1N-TCP-50M-R02 ACEPTADA CON LIMITACIONES.** Siguiente: preflight nuevo de `F1N-TCP-100M-R02`.
