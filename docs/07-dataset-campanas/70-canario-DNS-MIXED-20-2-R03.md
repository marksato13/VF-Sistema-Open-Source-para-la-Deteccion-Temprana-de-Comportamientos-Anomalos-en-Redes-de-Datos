# Tercer canario oficial R03 — DNS-MIXED-20-2

Fecha: 29 de julio de 2026. Campaña: `F1N-DNS-MIXED-20-2-R03`. Estado: **ACEPTADA CON LIMITACIONES**.

## Objetivo y preflight

La campaña genera veinte consultas DNS legítimas a `server.ppi.lab/A`, seguidas de dos nombres controlados que deben responder NXDOMAIN. Es tráfico benigno con error legítimo para ejercitar `dns_nxdomain_ratio_60s`; no representa un ataque.

El preflight confirmó Git limpio y sincronizado en `494fa1e9c2134f13b51e82e6214c9745ae4a5f2e`, ID/feature/ledger/lock libres y almacenamiento oficial `PASS` con 134,505,111,552 bytes disponibles. Las cuatro VM respondieron por SSH y el gate NTP pasó con desfase absoluto máximo observado de 1.461426 ms.

Suricata y dnsmasq estaban activos. Las pruebas de control obtuvieron `10.30.0.10` para el nombre válido y NXDOMAIN para el inexistente. Las rutas Cliente↔Servidor atravesaban el Sensor, las NIC externas estaban `DOWN`, el bypass `172.17.25.111–114` quedó bloqueado por ICMP y TCP/22, y el generador local/remoto coincidió:

```text
d4cd42b65f1b22cea0a3f585c2df760af68a8557799c3859eabc803d4f9b4203
```

| Campo | Valor |
|---|---|
| Propósito / partición | `experiment` / `train` |
| Estrato / escenario | `legitimate-error` / `dns-mixed` |
| Argumentos | `20` válidas / `2` NXDOMAIN |
| Quietud / warm-up / settle / cooldown | 70 / 60 / 9 / 30 s |
| SHA matriz | `ad22ce5f8b41110b201f0eeacd2b5f13cc9f945c92cf539e9913e87fefdfa824` |
| SHA argumentos | `4086992cb07355511e61bfce11d4c2dbf71be23f526d062154f55c2d707ea157` |

## Resultado DNS

El escenario terminó con código cero y stderr vacío. Su salida tiene veinte líneas `10.30.0.10`; esto es correcto porque `dig +short` no imprime una dirección para NXDOMAIN. PCAP y EVE acreditan las dos consultas de error.

| Control | Resultado |
|---|---:|
| Consultas / respuestas PCAP | 22 / 22 |
| Requests / responses EVE | 22 / 22 |
| Responses `NOERROR` / NXDOMAIN | 20 / 2 |
| Respuestas A correctas | 20 × `10.30.0.10` |
| Consultas válidas / de error | 20 / 2 |
| Ratio NXDOMAIN | 2/22 = 0.09090909 |
| Alertas / `stats` | 0 / 9 |

El orden es determinista: primero las veinte consultas válidas y después los dos errores. Esta ejecución no demuestra cómo se comportará el modelo ante otros órdenes, tasas, nombres o proporciones NXDOMAIN.

## PCAP, Suricata y recursos

| Control | Resultado |
|---|---:|
| Estado / código | `completed` / 0 |
| PCAP capturado / recibido / parseado | 44 / 44 / 44 |
| PCAP | 1 archivo / 5,092 bytes |
| Drops tcpdump | 0 |
| Delta Suricata / PCAP | 44 / 44 |
| Drops / ifdrops / decoder / overflow | 0 / 0 / 0 / 0 |
| EVE esperado / extraído | 53 / 53 |
| Transferencia / límite PCAP | verificada / no alcanzado |

Los 44 paquetes son IPv4 menores de 500 bytes, con longitud media 85.18 y máxima 93. El 0 % entre 500–1500 bytes es esperable en este perfil DNS ligero: esta campaña no tiene la función de aportar tráfico pesado, cuya cobertura corresponde a los perfiles HTTP, TCP, UDP y mixtos de F1.

El Sensor produjo 53 muestras: CPU máxima 2.27 %, RSS máximo 781,816 KiB, memoria disponible mínima 14,075,764 KiB y carga máxima 0.18. Son observaciones, no umbrales de aceptación.

## Feature y comparación R01↔R02↔R03

El extractor procesó 44 observaciones de paquete, 24 de aplicación y generó una fila elegible. Las 24 observaciones internas son 22 objetos `dns_query` más dos marcadores `dns_nxdomain`; no representan 24 transacciones.

| Feature | Valor |
|---|---:|
| `packet_count_10s` | 44 |
| `dns_query_count_60s` | 22 |
| `packet_rate_10s` | 4.4/s |
| `byte_rate_10s` | 374.8 B/s |
| `mean_ip_len_10s` | 85.18181818 B |
| `unique_dst_ip_ratio_30s` | 1/22 = 0.04545455 |
| `flow_attempt_count_30s` | 22 |
| `flow_attempt_rate_10s` | 2.2/s |
| `unique_dst_port_ratio_30s` | 1/22 = 0.04545455 |
| `dns_nxdomain_ratio_60s` | 2/22 = 0.09090909 |
| Resto de las 14 features | 0.0 |

R01, R02 y R03 producen exactamente el mismo vector de 14 features. No reutilizan evidencia:

| Repetición | PCAP SHA-256 |
|---|---|
| R01 | `2f72f38e…` |
| R02 | `c9c69a00…` |
| R03 | `970d316c…` |

Los PCAP, EVE, manifiestos, ledgers, timestamps y hashes son distintos. Esto demuestra repetibilidad de un generador determinista, pero no diversidad, independencia estadística ni separabilidad frente a anomalías. Las tres filas están en `train`, de modo que incrementan el peso empírico de esa firma; su efecto deberá comprobarse mediante análisis de sensibilidad por campaña, sin asumir que mejora o perjudica automáticamente al modelo.

## Integridad raíz

Todos los archivos listados en ambos `SHA256SUMS` pasaron:

```text
manifest.json          378d67cc7205d19d0fd6c0023c9729601246544724d07bb69e704b26eaabb46e
capture.pcap0          970d316c0dcc69935d3c54d1df8cc3b9e09137d5dc7abad398779522ab3c4768
eve-slice              bd8d69f6ad50d47fea465afcca82e501aa08df11f28300f0348e3a0cbc18ca1c
campaign SHA256SUMS    27bc615e97ca9b78d8845b8239630359ac77dec6558cf0541be0ca0537478a26
multilayer-v1.csv      b12bdf6831e4a2fb1bfba9790838c370fe75bfc978c9b01a5ce50f4f356aaddd
extraction-report      22572652eb2ebb4d4975fe38fb441d8dcb956d3885bc32687caa9393dd9e0ce7
feature SHA256SUMS     f490986be32351b5b7a07a29844bc69b44a05903ca203ccb7b40fe715724c0a5
ledger                 07a411b725b4d34e174411b3f8bcc9f0189469f81d8cf828b9bc368e703f6c12
```

El ensamblador aceptó 61/145 campañas: R03 3/29, 84 faltantes, cero inválidas/advertencias, nueve coincidencias exactas dentro de `train` y cero cruces observados. Validation/test todavía no existen; por ello, cero cruces no demuestra limpieza futura entre particiones.

Claude aceptó con limitaciones. Se conservaron su evaluación del orden determinista, el peso repetido y la ausencia de prueba de separabilidad. Se descartaron sus porcentajes y totales de filas no derivados del gate, su cuantificación de sobreajuste y la expectativa de que el perfil 50+10 no repita vectores; R01↔R02 de ese perfil ya coincidieron.

**F1N-DNS-MIXED-20-2-R03 ACEPTADA CON LIMITACIONES.** Siguiente autorizado: preflight independiente de `F1N-DNS-MIXED-50-10-R03`.
