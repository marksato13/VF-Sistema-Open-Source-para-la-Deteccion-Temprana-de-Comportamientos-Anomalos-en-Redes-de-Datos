# Quinto canario oficial R02 — PING-10

Fecha: 27 de julio de 2026. Campaña: `F1N-PING-10-R02`. Estado: **ACEPTADA CON LIMITACIONES**.

## Objetivo y preflight

El perfil genera diez echo request ICMP a intervalo de un segundo desde Cliente `10.20.0.20` hacia Servidor `10.30.0.10`, con sus diez replies. Es tráfico benigno ligero para ejercitar `icmp_ratio_10s`.

El preflight confirmó Git limpio y sincronizado en `576badcc042b5d513bf571a93ecfc58a0656670d`, ID libre, volumen oficial válido y gate de capacidad en `PASS`. Las cuatro VMs respondieron por SSH y NTP pasó con desfase absoluto máximo aproximado de 0.28 ms. Un eco de control recorrió Cliente→Sensor→Servidor sin pérdida.

Suricata y los servicios internos estaban activos; la captura residual estaba inactiva, el generador remoto coincidió por SHA-256, las NIC externas permanecieron `DOWN` y el bypass `172.17.25.111–114` quedó bloqueado por ICMP y TCP/22.

| Campo | Valor |
|---|---|
| Perfil / repetición | `PING-10` / R02 |
| Propósito / partición | `experiment` / `train` |
| Argumentos | 10 ecos / intervalo 1 s |
| Quietud / warm-up / settle / cooldown | 70 / 60 / 9 / 30 s |
| SHA matriz | `ad22ce5f8b41110b201f0eeacd2b5f13cc9f945c92cf539e9913e87fefdfa824` |
| SHA argumentos | `4027af88974510696bfebde488ece5ffaa0fdaace6f2d504d035a226e095db67` |

## Resultado ICMP

| Control | Resultado |
|---|---:|
| Echo request / reply | 10 / 10 |
| Secuencias request distintas | 1–10 |
| Transmitidos / recibidos | 10 / 10 |
| Pérdida | 0 % |
| Duración informada por ping | 9.199 s |
| Span de requests EVE | 9.198712 s |
| RTT mín./prom./máx./mdev | 0.381/0.472/0.593/0.064 ms |
| Stderr | vacío |

EVE contiene diez alertas SID `1000001`, firma `PPI LAB ICMP TEST`, y once eventos `stats`. La regla es telemetría controlada del laboratorio; su aparición confirma los requests y no etiqueta el episodio como ataque.

## Integridad, captura y recursos

| Control | Resultado |
|---|---:|
| Estado / código | `completed` / 0 |
| Evidencia completa | `true` |
| PCAP archivos / bytes | 1 / 2,304 |
| Capturados / parseados | 20 / 20 |
| Drops tcpdump | 0 |
| Transferencia verificada / límite alcanzado | sí / no |
| EVE extraído / esperado | 21 / 21 |
| Delta `kernel_packets` Suricata | 24 |
| Drops / ifdrops / decoder / overflow | 0 / 0 / 0 / 0 |
| Muestras Sensor / stderr | 59 / vacío |

Los veinte paquetes IPv4 miden 84 bytes. Los cuatro paquetes adicionales del contador Suricata no están identificados; el PCAP contiene exactamente los diez pares esperados con cero drops.

El Sensor observó CPU puntual máxima de 2.26 %, RSS máximo de 780,308 KiB, memoria disponible mínima de 14,107,484 KiB y carga máxima de 0.63. Son observaciones, no límites.

## Efecto de fase y features

El extractor produjo dos filas elegibles:

| Ventana UTC | Paquetes nuevos | `packet_rate_10s` | `byte_rate_10s` | Attempts historia | `flow_attempt_rate_10s` | `icmp_ratio_10s` |
|---|---:|---:|---:|---:|---:|---:|
| `18:19:10` | 18 | 1.8/s | 151.2 B/s | 1 | 0.1/s | 1.0 |
| `18:19:20` | 2 | 0.2/s | 16.8 B/s | 1 | 0.0/s | 1.0 |

Ambas registran `mean_ip_len_10s=84`, `unique_dst_ip_ratio_30s=1` y ratio de puertos cero porque ICMP no tiene transporte L4. El intento canónico se cuenta una vez en la historia; su tasa solo aparece en la ventana donde empieza.

R02 comenzó a `18:19:01.086734Z`. Los primeros nueve pares cayeron antes del borde fijo `18:19:10Z`; el décimo, después. Las dos filas son ventanas autocorrelacionadas del mismo episodio y no deben contarse como dos repeticiones.

## Comparación R01↔R02

| Repetición | Span requests | Distribución de paquetes | Filas |
|---|---:|---:|---:|
| R01 | 9.190037 s | 20 | 1 |
| R02 | 9.198712 s | 18 / 2 | 2 |

R01 empezó a `15:24:10.279483Z`, justo después de un borde, y sus diez pares quedaron en una sola ventana. R02 comenzó unos 1.09 s después de su ventana y cruzó el borde antes del último eco.

Por eso R02 no repite exactamente el vector de R01: las tasas son 1.8/0.2 frente a 2.0 paquetes/s. No cambió el contrato ni existió pérdida; cambió la fase de un episodio de duración cercana a diez segundos.

## Integridad raíz

Todos los archivos de ambos `SHA256SUMS` pasaron:

```text
manifest.json          c7631e1d5a0718c8ba73e8def3aa1c51da93276f57f4be2427893973dc02070e
capture.pcap0          d47dad7f08e163b8dc992ca73568a9edd6f672b702ab4300a6b96e52f55c680a
eve-slice              fd52578caebfe23c97cec599efd8840987c90a7550947906c14a2c576e91774a
campaign SHA256SUMS    7a1b6ba09bccd3cfe89f49844b5815b44d3d23d3507ea1fd47c638d988a39301
multilayer-v1.csv      a4d9f0c9bbf62d8902e2faa96d9c22bc8bfac53c526137247bf4752aa8133fd1
extraction-report      4875856ca5816db245401d7b97e776cca6152b8b8e8d83f359d09075fe9ed18f
feature SHA256SUMS     9624de7c68a830f10b9f3e02201cb34ebe28c03a7275aa90199b6d9e9194fae4
ledger                 770368491f496debea5043f7ff8be4e0a4a0dee0f9e9ced9b8263942799c661a
```

## Ensamblador y decisión

El ensamblador aceptó 34/145 campañas, con 111 faltantes, cero inválidas y cero advertencias. R02 queda 5/29. Persisten tres coincidencias exactas DNS dentro de `train`; PING-10 no agregó ninguna y no existen coincidencias entre particiones.

Claude aceptó con limitaciones y explicó correctamente el borde UTC, la autocorrelación, la telemetría SID `1000001` y la ausencia de coincidencia R01↔R02. No se adopta su afirmación absoluta de que la fase “no introduce sesgo”: la alineación sí cambia número y peso de filas, por lo que se evaluará antes del entrenamiento.

**F1N-PING-10-R02 ACEPTADA CON LIMITACIONES.** El siguiente paso autorizado es el preflight individual de `F1N-PING-100-R02`.
