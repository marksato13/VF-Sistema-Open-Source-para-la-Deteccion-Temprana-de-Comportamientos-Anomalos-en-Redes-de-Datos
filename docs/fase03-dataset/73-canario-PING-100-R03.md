# Sexto canario oficial R03 — PING-100

Fecha: 29 de julio de 2026. Campaña: `F1N-PING-100-R03`. Estado: **ACEPTADA CON LIMITACIONES**.

## Objetivo y preflight

El perfil genera cien echo request ICMP a intervalo nominal de 0.2 s y sus cien replies desde Cliente `10.20.0.20` hacia Servidor `10.30.0.10`. Amplía la línea base ICMP legítima y ejercita `icmp_ratio_10s` y `packet_rate_10s`.

El preflight confirmó Git limpio y sincronizado en `dcda9a7582df7cb2662d20998349cc3e1da386ef`, ID/feature/ledger/lock libres y almacenamiento oficial `PASS` con 134,504,411,136 bytes disponibles. Las cuatro VM respondieron por SSH; NTP pasó con desfase absoluto máximo observado de 1.115102 ms.

El eco de control tuvo 0 % de pérdida. Suricata y los servicios internos estaban activos, la captura residual inactiva, las rutas atravesaban el Sensor, las NIC externas estaban `DOWN` y el bypass `172.17.25.111–114` bloqueado por ICMP y TCP/22. El generador local/remoto coincidió:

```text
d4cd42b65f1b22cea0a3f585c2df760af68a8557799c3859eabc803d4f9b4203
```

| Campo | Valor |
|---|---|
| Propósito / partición | `experiment` / `train` |
| Estrato / escenario | `burst` / `ping` |
| Argumentos | `100` ecos / intervalo `0.2` s |
| Quietud / warm-up / settle / cooldown | 70 / 60 / 9 / 30 s |
| SHA matriz | `ad22ce5f8b41110b201f0eeacd2b5f13cc9f945c92cf539e9913e87fefdfa824` |
| SHA argumentos | `412ee9eb50fba97316261a06e934257bc6a9467e24d73f56a2530aa368886fe0` |

## Resultado ICMP

| Control | Resultado |
|---|---:|
| Echo request / reply PCAP | 100 / 100 |
| Secuencias distintas | 1–100 |
| Transmitidos / recibidos | 100 / 100 |
| Pérdida | 0 % |
| Duración informada | 20.569 s |
| Span de requests EVE | 20.569361 s |
| RTT mín./prom./máx./mdev | 0.308/0.429/1.541/0.151 ms |
| Stderr | vacío |

EVE contiene cien alertas permitidas SID `1000001`, firma `PPI LAB ICMP TEST`, una por echo request, y doce `stats`. Es telemetría controlada del laboratorio, no una etiqueta de ataque.

## Integridad y recursos

| Control | Resultado |
|---|---:|
| Estado / código | `completed` / 0 |
| PCAP capturado / recibido / parseado | 200 / 200 / 200 |
| PCAP | 1 archivo / 22,824 bytes |
| Drops tcpdump | 0 |
| Delta Suricata / PCAP | 204 / 200 |
| Drops / ifdrops / decoder / overflow | 0 / 0 / 0 / 0 |
| EVE esperado / extraído | 112 / 112 |
| Transferencia / límite PCAP | verificada / no alcanzado |

Los doscientos paquetes IPv4 miden 84 bytes y son menores de 500 bytes. Los cuatro paquetes adicionales del contador Suricata permanecen sin identificar; no se convierten en eventos hipotéticos ni se les atribuye causa.

El Sensor produjo 68 muestras: CPU máxima 1.52 %, RSS máximo 781,816 KiB, memoria disponible mínima 14,093,732 KiB y carga máxima 0.33. Son observaciones, no umbrales.

## Ventanas y comparación R01↔R02↔R03

El extractor procesó doscientas observaciones de paquete, cero de aplicación y produjo tres filas elegibles:

| Fin UTC | Paquetes | Packet rate | Byte rate | Attempts historia | Attempt rate | Ratio IP / ICMP |
|---|---:|---:|---:|---:|---:|---:|
| `23:29:30` | 62 | 6.2/s | 520.8 B/s | 1 | 0.1/s | 1 / 1 |
| `23:29:40` | 98 | 9.8/s | 823.2 B/s | 1 | 0.0/s | 1 / 1 |
| `23:29:50` | 40 | 4.0/s | 336.0 B/s | 1 | 0.0/s | 1 / 1 |

Las tres filas conservan `mean_ip_len_10s=84`, ratio pesado cero y ratio de puertos cero. Son ventanas autocorrelacionadas del mismo episodio, no tres repeticiones.

| Repetición | Span requests | Reparto de paquetes | Filas |
|---|---:|---:|---:|
| R01 | 20.553039 s | 6 / 96 / 96 / 2 | 4 |
| R02 | 20.541 s | 48 / 96 / 56 | 3 |
| R03 | 20.569361 s | 62 / 98 / 40 | 3 |

R01 y R02 comparten una fila estable de 96 paquetes. R03 no coincide exactamente con ningún vector previo de `PING-100` ni añade un duplicado global. Los distintos repartos son observaciones de alineación de ventanas y timing; no se atribuye el valor 98 exclusivamente a fase, pacing, jitter o carga sin una prueba causal.

Este perfil ICMP de capa 3 no pretende aportar señales L7 ni paquetes de 500–1500 bytes. Su valor está en representar normalidad ICMP ligera y burst; la cobertura multicapa y pesada se evalúa de forma agregada con los otros perfiles.

## Integridad raíz

Todos los archivos de ambos `SHA256SUMS` pasaron:

```text
manifest.json          d56e4584b81ce177fab85ce8e44d37230347f9fb494b7f201dff9c00f4a4a379
capture.pcap0          2a82ca0d70ba25785c9c3c147a0890986641ebb42b59945ba3dac3b1ebcfddf0
eve-slice              7eb8c7c7b1078380509aa66fc6e1ab6c35a68f961b532c3e3904c4e98a61ca4e
campaign SHA256SUMS    35598ecf0917b87f4528a49408b88e3df3ade40ef6ebd7216e4336e83bcd9065
multilayer-v1.csv      9198465c048707d0f9442ce2647d65cb834630133100b6296c386ea25c67c65a
extraction-report      12e4f6b95558b2e7275cd0cf2c36f9f4903ed567c2334e97efcee35b427ea8c8
feature SHA256SUMS     e89ebd3a3460b03806cf21ea0a58b82bc793aeb5256eafd8438281c7a567c825
ledger                 d7e0bf576efcf509733827d2a7a930267fd22e6d0de3c6d73d657df250d5ba30
```

El ensamblador aceptó 64/145 campañas: R03 6/29, 81 faltantes, cero inválidas/advertencias, once coincidencias exactas dentro de `train` —sin aumento por esta campaña— y cero cruces observados. Validation/test todavía no existen.

Claude aceptó de forma condicionada; el dictamen consolidado usa **ACEPTADA CON LIMITACIONES**. Se corrigieron paquetes frente a eventos, capa 3 frente a L7, soporte efectivo de features, severidad/sobreajuste inventados, causa del reparto, condiciones nuevas y una secuencia de campañas desactualizada.

**F1N-PING-100-R03 ACEPTADA CON LIMITACIONES.** Siguiente autorizado: preflight independiente de `F1N-HTTP-10MB-R03`.
