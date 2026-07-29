# Cuarto canario oficial R03 — DNS-MIXED-50-10

Fecha: 29 de julio de 2026. Campaña: `F1N-DNS-MIXED-50-10-R03`. Estado: **ACEPTADA CON LIMITACIONES**.

## Objetivo y preflight

La campaña genera cincuenta consultas legítimas `server.ppi.lab/A`, seguidas de diez nombres controlados que deben responder NXDOMAIN. Es un perfil `experiment/train` de error operativo legítimo para ejercitar `dns_nxdomain_ratio_60s`; no etiqueta NXDOMAIN como ataque.

El preflight confirmó Git limpio y sincronizado en `758eb8e9bb1b44a97476f62291be4f3f93c47add`, ID/feature/ledger/lock libres y almacenamiento oficial `PASS` con 134,504,894,464 bytes disponibles. Las cuatro VM respondieron por SSH y el gate NTP pasó con desfase absoluto máximo observado de 0.601766 ms.

Suricata, dnsmasq, NGINX y `ppi-iperf3.service` estaban activos. Una consulta válida obtuvo `10.30.0.10` y el control negativo devolvió NXDOMAIN. Las rutas Cliente↔Servidor atravesaban el Sensor, las cuatro NIC externas estaban `DOWN`, el bypass `172.17.25.111–114` quedó bloqueado por ICMP y TCP/22, y el generador local/remoto coincidió:

```text
d4cd42b65f1b22cea0a3f585c2df760af68a8557799c3859eabc803d4f9b4203
```

| Campo | Valor |
|---|---|
| Propósito / partición | `experiment` / `train` |
| Estrato / escenario | `legitimate-error` / `dns-mixed` |
| Argumentos | `50` válidas / `10` NXDOMAIN |
| Quietud / warm-up / settle / cooldown | 70 / 60 / 9 / 30 s |
| SHA matriz | `ad22ce5f8b41110b201f0eeacd2b5f13cc9f945c92cf539e9913e87fefdfa824` |
| SHA argumentos | `3e1d6b27aac4e5297c7bddae4dbf13d0c28ef3ae116ffc99e8162b8486aab317` |

## Resultado DNS

El escenario terminó con código cero y stderr vacío. La salida contiene cincuenta líneas `10.30.0.10`; `dig +short` no imprime dirección para NXDOMAIN. PCAP y EVE prueban las diez respuestas de error.

| Control | Resultado |
|---|---:|
| Consultas / respuestas PCAP | 60 / 60 |
| Requests / responses EVE | 60 / 60 |
| Responses `NOERROR` / NXDOMAIN | 50 / 10 |
| Respuestas A correctas | 50 × `10.30.0.10` |
| Nombres NXDOMAIN distintos | 10 |
| Puertos origen / IDs / flow IDs distintos | 60 / 60 / 60 |
| Span requests / tasa descriptiva | 1.222226 s / 49.090757 consultas/s |
| Alertas / `stats` | 0 / 10 |

Las cincuenta consultas válidas preceden a los diez errores. Este orden determinista no representa variantes intercaladas, invertidas ni de otra tasa o proporción; esas condiciones no se infieren de esta campaña.

## PCAP, Suricata y recursos

| Control | Resultado |
|---|---:|
| Estado / código | `completed` / 0 |
| PCAP capturado / recibido / parseado | 120 / 120 / 120 |
| PCAP | 1 archivo / 13,866 bytes |
| Drops tcpdump | 0 |
| Delta Suricata / PCAP | 124 / 120 |
| Drops / ifdrops / decoder / overflow | 0 / 0 / 0 / 0 |
| EVE esperado / extraído | 130 / 130 |
| Transferencia / límite PCAP | verificada / no alcanzado |

Los 120 paquetes son IPv4 menores de 500 bytes, con longitud media 85.35 y máxima 94. El perfil DNS ligero no tiene la función de ampliar el rango 500–1500 bytes; esa cobertura procede de HTTP, TCP, UDP y tráfico mixto.

Suricata contabilizó cuatro paquetes adicionales que no están identificados. El valor es un delta del contador de captura, no 124 eventos EVE. No se le atribuye causa ni invalida por sí mismo el PCAP causal: este contiene los 120 paquetes del escenario, fue recibido y parseado por completo y tiene cero drops.

El Sensor produjo 54 muestras: CPU máxima 2.29 %, RSS máximo 781,816 KiB, memoria disponible mínima 14,089,568 KiB y carga máxima 0.35. Son observaciones, no umbrales.

## Feature y comparación R01↔R02↔R03

El extractor procesó 120 observaciones de paquete y 70 de aplicación, y produjo una fila elegible. Las 70 observaciones internas son 60 objetos `dns_query` más diez marcadores `dns_nxdomain`; no representan 70 transacciones.

| Feature | Valor |
|---|---:|
| `packet_count_10s` | 120 |
| `dns_query_count_60s` | 60 |
| `packet_rate_10s` | 12.0/s |
| `byte_rate_10s` | 1,024.2 B/s |
| `mean_ip_len_10s` | 85.35 B |
| `unique_dst_ip_ratio_30s` | 1/60 = 0.01666667 |
| `flow_attempt_count_30s` | 60 |
| `flow_attempt_rate_10s` | 6.0/s |
| `unique_dst_port_ratio_30s` | 1/60 = 0.01666667 |
| `dns_nxdomain_ratio_60s` | 10/60 = 0.16666667 |
| Resto de las 14 features | 0.0 |

| Repetición | PCAP / bytes | EVE DNS / `stats` | Delta Suricata | PCAP SHA-256 |
|---|---:|---:|---:|---|
| R01 | 120 / 13,866 | 120 / 10 | 124 | `7befb436…` |
| R02 | 120 / 13,866 | 120 / 9 | 124 | `bce4e488…` |
| R03 | 120 / 13,866 | 120 / 10 | 124 | `c137184f…` |

Las tres repeticiones producen exactamente el mismo vector de 14 features, pero sus PCAP, EVE, manifiestos, ledgers, timestamps y hashes son distintos. Esto acredita repetibilidad técnica del perfil determinista, no diversidad ni independencia estadística. Las tres filas están en `train` y aumentan el peso empírico de la firma; el efecto sobre Isolation Forest deberá medirse mediante sensibilidad por campaña, no anticiparse como robustez o sobreajuste demostrado.

## Integridad raíz

Todos los archivos de ambos `SHA256SUMS` pasaron:

```text
manifest.json          dc36c972d2d0e865223761a65e2ed61e3283afe9e0d41a125a6388faef09c2e7
capture.pcap0          c137184fb736ee853201473402ec927486054a21eff33be92256be0789a33d58
eve-slice              ead2c69c7ce9f30a0c85becac8a8f706df25707457cbd9f99525f6dcc59151b6
campaign SHA256SUMS    76147f681c3a5f62a2d3a71716c17973d93f500e511bee8b1a998461c36ca151
multilayer-v1.csv      f259d4504c65709be3a4482dd195227637f2a1a6687099b2141f9b9e8a29371b
extraction-report      6cfeb0c4026f22824b2e41c79ba021992257dfbc583b41c7217b4e2e6a52dd0a
feature SHA256SUMS     5cc8e2b8462bfc3319dfa2459b3592f7f0c043c4f6420cebd5f56fbfc1d6ed31
ledger                 7995c3ab9ea552fdb33babc62cdf366faf0b55271af7caa65bada56310fab460
```

El ensamblador aceptó 62/145 campañas: R03 4/29, 83 faltantes, cero inválidas/advertencias, diez coincidencias exactas dentro de `train` y cero cruces observados. Validation/test todavía no existen, de modo que cero cruces no demuestra limpieza futura.

Claude aceptó con limitaciones. Se conservaron sus observaciones sobre repetibilidad, peso, orden y separabilidad pendiente. Se corrigieron la confusión entre paquetes y eventos EVE, la dependencia de integridad respecto de cuatro paquetes no identificados, la atribución del orden al ledger, el efecto asegurado en Isolation Forest y la generalización indebida de que todas las repeticiones de `train` serían exactas.

**F1N-DNS-MIXED-50-10-R03 ACEPTADA CON LIMITACIONES.** Siguiente autorizado: preflight independiente de `F1N-PING-10-R03`.
