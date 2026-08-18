# Quinto canario oficial R03 — PING-10

Fecha: 29 de julio de 2026. Campaña: `F1N-PING-10-R03`. Estado: **ACEPTADA CON LIMITACIONES**.

## Objetivo y preflight

El perfil genera diez echo request ICMP a intervalo nominal de un segundo desde Cliente `10.20.0.20` hacia Servidor `10.30.0.10`, con sus diez replies. Es tráfico benigno ligero para ejercitar `icmp_ratio_10s`.

El preflight confirmó Git limpio y sincronizado en `caccafe8f32c7ec9f10caf7726c49751f11cbaea`, ID/feature/ledger/lock libres y almacenamiento oficial `PASS` con 134,504,615,936 bytes disponibles. Las cuatro VM respondieron por SSH; NTP pasó con desfase absoluto máximo observado de 0.676318 ms.

Un eco de control recorrió Cliente→Sensor→Servidor con 0 % de pérdida. Suricata y los servicios internos estaban activos, la captura residual inactiva, las NIC externas `DOWN` y el bypass `172.17.25.111–114` bloqueado por ICMP y TCP/22. El generador local/remoto coincidió:

```text
d4cd42b65f1b22cea0a3f585c2df760af68a8557799c3859eabc803d4f9b4203
```

| Campo | Valor |
|---|---|
| Propósito / partición | `experiment` / `train` |
| Estrato / escenario | `light` / `ping` |
| Argumentos | `10` ecos / intervalo `1` s |
| Quietud / warm-up / settle / cooldown | 70 / 60 / 9 / 30 s |
| SHA matriz | `ad22ce5f8b41110b201f0eeacd2b5f13cc9f945c92cf539e9913e87fefdfa824` |
| SHA argumentos | `4027af88974510696bfebde488ece5ffaa0fdaace6f2d504d035a226e095db67` |

## Resultado ICMP

| Control | Resultado |
|---|---:|
| Echo request / reply PCAP | 10 / 10 |
| Secuencias distintas | 1–10 |
| Transmitidos / recibidos | 10 / 10 |
| Pérdida | 0 % |
| Duración informada | 9.187 s |
| Span de requests EVE | 9.181516 s |
| RTT mín./prom./máx./mdev informado | 0.374/1.013/6.374/1.787 ms |
| Stderr | vacío |

El máximo RTT de 6.374 ms se conserva como observación puntual. No es una feature, un umbral ni evidencia de anomalía, y no se le atribuye causa.

EVE contiene diez alertas SID `1000001`, firma `PPI LAB ICMP TEST`, sobre los echo request, además de diez `stats`. La regla es telemetría permitida del laboratorio; confirma la semántica del episodio, pero no etiqueta ataque.

## Integridad y recursos

| Control | Resultado |
|---|---:|
| Estado / código | `completed` / 0 |
| PCAP capturado / recibido / parseado | 20 / 20 / 20 |
| PCAP | 1 archivo / 2,304 bytes |
| Drops tcpdump | 0 |
| Delta Suricata / PCAP | 24 / 20 |
| Drops / ifdrops / decoder / overflow | 0 / 0 / 0 / 0 |
| EVE esperado / extraído | 20 / 20 |
| Transferencia / límite PCAP | verificada / no alcanzado |

Los veinte paquetes IPv4 miden 84 bytes y son menores de 500 bytes. Los cuatro paquetes adicionales del contador Suricata no están identificados. El valor 24 representa paquetes procesados, no eventos EVE; no se inventa una causa ni una categoría de ruido.

El Sensor produjo 60 muestras: CPU máxima 1.53 %, RSS máximo 781,816 KiB, memoria disponible mínima 14,086,852 KiB y carga máxima 0.16. Son observaciones, no límites.

## Fase UTC y dos ventanas

El extractor procesó veinte observaciones de paquete, cero de aplicación y produjo dos filas elegibles:

| Fin UTC | Paquetes nuevos | Packet rate | Byte rate | Attempts historia | Attempt rate | Ratio IP / ICMP |
|---|---:|---:|---:|---:|---:|---:|
| `13:55:40` | 6 | 0.6/s | 50.4 B/s | 1 | 0.1/s | 1 / 1 |
| `13:55:50` | 14 | 1.4/s | 117.6 B/s | 1 | 0.0/s | 1 / 1 |

Ambas filas tienen `mean_ip_len_10s=84`, ratio pesado cero y ratio de puertos cero porque ICMP no posee transporte L4. Son ventanas autocorrelacionadas de un episodio y no constituyen dos repeticiones independientes.

| Repetición | Span requests | Reparto de paquetes | Filas |
|---|---:|---:|---:|
| R01 | 9.190037 s | 20 | 1 |
| R02 | 9.198712 s | 18 / 2 | 2 |
| R03 | 9.181516 s | 6 / 14 | 2 |

La fase respecto de bordes UTC fijos cambia el reparto y el peso de filas sin cambiar los diez pares causales. R03 no coincide con vectores de `PING-10/R01` o R02.

## Coincidencia entre perfiles

La primera fila R03 —seis paquetes, 0.6/s, 50.4 B/s, un intento y ratios IP/ICMP iguales a uno— coincide exactamente con la primera ventana de `PING-100/R01`.

Esto no es reutilización de evidencia ni cruce de partición: son campañas y PCAP independientes dentro de `train`. También es coherente con inferencia online: durante ese prefijo observado, las 14 features no conocen si el generador terminará en diez o cien solicitudes. La coincidencia aumenta el peso de esa firma y demuestra equivalencia observacional de esas ventanas; no demuestra contaminación, error del extractor, separabilidad ni rendimiento futuro del modelo.

## Integridad raíz

Todos los archivos de ambos `SHA256SUMS` pasaron:

```text
manifest.json          a4663ffca28a64a31208d4d0e0556570f57c0d4857ff1ec9297861332049ea29
capture.pcap0          5130068aa9b8f50b3c756a3fb72e8811aad9d06bacc9eb41ecff0d45380d7ef0
eve-slice              6ecc586866ff913408ce872179be558f0633d5c87db6a106d0141d484b611a3a
campaign SHA256SUMS    5068280444a8194f69ade9bf81ac6e0585e5c95eae52a4b526384e73a57c95b8
multilayer-v1.csv      d1ea234ac2dcaa24243f536516531e8100655ca4b27e385e69fa5b041ca1b8cc
extraction-report      2b2ef0c55212a76f21d1c8289cd9ac6ffebb81631405748c5955f938b8e6d004
feature SHA256SUMS     85b73c953878eb3f144de5357dae42b3a55281b7407a7eb914f19f13cddf96bf
ledger                 7cc804cc5b1f7ea420ec28855a16fbe99c88b0a5c59e1dfc0bd37fea4a695b8e
```

El ensamblador aceptó 63/145 campañas: R03 5/29, 82 faltantes, cero inválidas/advertencias, once coincidencias exactas dentro de `train` y cero cruces observados. Validation/test aún no existen.

Claude aceptó con limitaciones. Se conservaron la equivalencia del prefijo, la autocorrelación, la telemetría y la separabilidad pendiente. Se corrigieron paquetes frente a eventos, causalidad de los cuatro adicionales, rangos ICMP inventados, contaminación inexistente, soporte 14/14 atribuido a una sola campaña y efectos ML anticipados.

**F1N-PING-10-R03 ACEPTADA CON LIMITACIONES.** Siguiente autorizado: preflight independiente de `F1N-PING-100-R03`.
