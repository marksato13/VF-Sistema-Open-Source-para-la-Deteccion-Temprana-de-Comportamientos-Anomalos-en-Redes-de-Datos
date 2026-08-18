# Cuarto canario oficial R02 — DNS-MIXED-50-10

Fecha: 27 de julio de 2026. Campaña: `F1N-DNS-MIXED-50-10-R02`. Estado: **ACEPTADA CON LIMITACIONES**.

## Objetivo y preflight

Esta campaña genera cincuenta consultas legítimas `server.ppi.lab/A` seguidas de diez nombres controlados que deben devolver NXDOMAIN. Es un perfil `experiment/train` de error operativo legítimo y mide `dns_nxdomain_ratio_60s`; no etiqueta NXDOMAIN como ataque.

El preflight confirmó Git limpio y sincronizado en `10f1f4cf13ac8ca97888545e9b747ae47daa8666`, ID libre, almacenamiento oficial válido y gate de capacidad en `PASS`. Las cuatro VMs respondieron por SSH y NTP pasó con desfase absoluto máximo aproximado de 0.34 ms.

Suricata, NGINX, dnsmasq, SSH y `ppi-iperf3.service` estaban activos. Se comprobaron respuestas válida y NXDOMAIN, captura residual inactiva, SHA idéntico del generador, NIC externas `DOWN` y bypass `172.17.25.111–114` bloqueado por ICMP y TCP/22.

| Campo | Valor |
|---|---|
| Perfil / repetición | `DNS-MIXED-50-10` / R02 |
| Propósito / partición | `experiment` / `train` |
| Argumentos | 50 válidas / 10 NXDOMAIN |
| Quietud / warm-up / settle / cooldown | 70 / 60 / 9 / 30 s |
| SHA matriz | `ad22ce5f8b41110b201f0eeacd2b5f13cc9f945c92cf539e9913e87fefdfa824` |
| SHA argumentos | `3e1d6b27aac4e5297c7bddae4dbf13d0c28ef3ae116ffc99e8162b8486aab317` |

## Resultado causal

La salida contiene cincuenta líneas `10.30.0.10`; stderr está vacío. Las diez respuestas sin dirección se demuestran en PCAP/EVE:

| Control | Resultado |
|---|---:|
| Consultas / respuestas PCAP | 60 / 60 |
| Request / response EVE | 60 / 60 |
| Responses `NOERROR` / NXDOMAIN | 50 / 10 |
| Respuestas A correctas | 50 |
| Nombres NXDOMAIN distintos | 10 |
| Flow IDs / IDs DNS distintos | 60 / 60 |
| Span de requests | 1.220735 s |
| Tasa observada | 49.150717 consultas/s |
| Alertas / `stats` | 0 / 9 |

La benignidad procede del escenario controlado, origen autorizado, nombres conocidos y respuestas esperadas. El ratio por sí solo no diferencia error legítimo de DNS anómalo.

## Integridad y recursos

| Control | Resultado |
|---|---:|
| Estado / código | `completed` / 0 |
| Evidencia completa | `true` |
| PCAP archivos / bytes | 1 / 13,866 |
| Capturados / parseados | 120 / 120 |
| Drops tcpdump | 0 |
| Transferencia verificada / límite alcanzado | sí / no |
| EVE extraído / esperado | 129 / 129 |
| Delta `kernel_packets` Suricata | 124 |
| Drops / ifdrops / decoder / overflow | 0 / 0 / 0 / 0 |
| Muestras Sensor / stderr | 54 / vacío |

Los 120 paquetes son IPv4 menores de 500 bytes, con media 85.35 y máximo 94. Los cuatro paquetes adicionales del contador Suricata no están identificados. PCAP preserva exactamente los 120 paquetes del escenario con cero drops.

R01 produjo 130 eventos EVE —120 DNS y diez `stats`— y R02 produjo 129 —120 DNS y nueve `stats`. Cada bundle coincide con su checkpoint y conteo esperado; el número de `stats` depende del intervalo temporal de emisión y no altera las features DNS.

El Sensor observó CPU puntual máxima de 2.22 %, RSS máximo de 780,308 KiB, memoria disponible mínima de 14,110,304 KiB y carga máxima de 0.12. Son observaciones, no umbrales.

## Feature y reproducibilidad R01↔R02

El extractor procesó 120 paquetes y creó una fila elegible:

| Feature | Valor |
|---|---:|
| `packet_rate_10s` | 12.0/s |
| `byte_rate_10s` | 1,024.2 B/s |
| `mean_ip_len_10s` | 85.35 B |
| `unique_dst_ip_ratio_30s` | 1/60 = 0.01666667 |
| `flow_attempt_rate_10s` | 6.0/s |
| `unique_dst_port_ratio_30s` | 1/60 = 0.01666667 |
| `dns_nxdomain_ratio_60s` | 10/60 = 0.16666667 |
| Resto de las 14 features | 0.0 |

Las 70 observaciones internas de aplicación son 60 `dns_query` más diez marcadores `dns_nxdomain`; la red contiene 60 transacciones, no 70.

El vector coincide exactamente con R01, pero la evidencia es independiente:

| Repetición | Span requests | PCAP SHA-256 |
|---|---:|---|
| R01 | 1.260866 s | `7befb436…` |
| R02 | 1.220735 s | `bce4e488…` |

También difieren EVE, manifiesto, ledger, timestamps y hashes de bundle. Ambas repeticiones son `train`; no existe cruce de partición. La coincidencia se conserva como evidencia de reproducibilidad y se tratará como posible peso repetido en el análisis de sensibilidad.

## Integridad raíz

Todos los archivos de ambos `SHA256SUMS` pasaron:

```text
manifest.json          5760c290e6bee504552adbef152930f67ac35bd56e1e0c52422209cad4ba08d9
capture.pcap0          bce4e488b0f2be26d826e03daea659928e9c3b749a3677790c3c7e8df7583df4
eve-slice              ca8e59e007caa3e34f5c9d7cce027da9f08e6325b58cf645bd56c97fe13df515
campaign SHA256SUMS    802aacff4d711c91808e2787ce5d251d108692ed62bc28bcb7c4f144909abe5f
multilayer-v1.csv      070e3f1c99d64c748aba322253eee51fbff714abcac4799328894c016af7b941
extraction-report      c6344c1b262acffc39d889a294cf54fe22695efa24a75a06d72cebf7f96fb562
feature SHA256SUMS     e56aef3735cb17c02ba128f2d2bd36a5175c9ff8d08dae3bdc6fe3bd01aec903
ledger                 fa91a11bce420a7dcda23af676788ba33b98ab26aabaa457ff28af7e4baa4526
```

## Ensamblador y revisión Claude

El ensamblador aceptó 33/145 campañas, con 112 faltantes, cero inválidas y cero advertencias. R02 queda 4/29. Existen tres coincidencias exactas:

1. `DNS-VALID-10/R01↔R02`;
2. `DNS-MIXED-20-2/R01↔R02`;
3. `DNS-MIXED-50-10/R01↔R02`.

Ninguna cruza particiones. `DNS-VALID-200/R02` no coincide con R01 debido a la fase respecto al borde UTC.

La primera revisión de Claude analizó por completo el perfil equivocado `DNS-MIXED-20-2`; se descartó. La corrección aceptó esta campaña, pero volvió a confundir `DNS-VALID-200` como coincidencia, llamó validation a R02 y citó el estado anterior del ensamblador. También especuló sobre los cuatro paquetes adicionales y porcentajes del dataset. Solo se conserva su aceptación condicionada y la necesidad de evaluar peso repetido.

**F1N-DNS-MIXED-50-10-R02 ACEPTADA CON LIMITACIONES.** El siguiente paso autorizado es el preflight individual de `F1N-PING-10-R02`.
