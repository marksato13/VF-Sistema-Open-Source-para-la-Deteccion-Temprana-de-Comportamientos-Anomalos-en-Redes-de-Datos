# Tercer canario oficial R02 — DNS-MIXED-20-2

Fecha: 27 de julio de 2026. Campaña: `F1N-DNS-MIXED-20-2-R02`. Estado: **ACEPTADA CON LIMITACIONES**.

## Objetivo y preflight

El perfil produce veinte consultas DNS legítimas que deben resolver `server.ppi.lab/A` como `10.30.0.10`, seguidas de dos nombres controlados que deben devolver NXDOMAIN. Es tráfico benigno con error legítimo y ejercita `dns_nxdomain_ratio_60s`; no introduce un ataque en F1.

El preflight confirmó Git limpio y sincronizado en `fb84f1a6c27c4f4ae0af325736d0aa65705b7b29`, ID libre, almacenamiento oficial válido y gate de capacidad en `PASS`. Las cuatro VMs respondieron por SSH y NTP pasó con desfase absoluto menor de 0.4 ms.

Suricata, NGINX, dnsmasq, SSH y `ppi-iperf3.service` estaban activos. Se probaron una respuesta A válida y un NXDOMAIN por Cliente→Sensor→Servidor. La captura residual estaba inactiva, el generador remoto coincidió por SHA-256, las NIC externas permanecieron `DOWN` y el bypass `172.17.25.111–114` quedó bloqueado por ICMP y TCP/22.

| Campo | Valor |
|---|---|
| Propósito / partición | `experiment` / `train` |
| Estrato | `legitimate-error` |
| Argumentos | 20 válidas / 2 NXDOMAIN |
| Quietud / warm-up / settle / cooldown | 70 / 60 / 9 / 30 s |
| SHA matriz | `ad22ce5f8b41110b201f0eeacd2b5f13cc9f945c92cf539e9913e87fefdfa824` |
| SHA argumentos | `4086992cb07355511e61bfce11d4c2dbf71be23f526d062154f55c2d707ea157` |

## Resultado causal

La salida contiene veinte líneas `10.30.0.10`; `dig +short` no imprime una dirección para NXDOMAIN. El stderr está vacío. PCAP y EVE acreditan el escenario completo:

| Control | Resultado |
|---|---:|
| Consultas / respuestas PCAP | 22 / 22 |
| Request / response EVE | 22 / 22 |
| Responses `NOERROR` / NXDOMAIN | 20 / 2 |
| Respuestas A `10.30.0.10` | 20 |
| Nombres NXDOMAIN | `error-legitimo-1.ppi.lab`, `error-legitimo-2.ppi.lab` |
| Flow IDs / IDs DNS distintos | 22 / 22 |
| Span de requests | 0.481996 s |
| Alertas / `stats` | 0 / 9 |

## Integridad y recursos

| Control | Resultado |
|---|---:|
| Estado / código | `completed` / 0 |
| Evidencia completa | `true` |
| PCAP archivos / bytes | 1 / 5,092 |
| Capturados / parseados | 44 / 44 |
| Drops tcpdump | 0 |
| Transferencia verificada / límite alcanzado | sí / no |
| EVE extraído / esperado | 53 / 53 |
| Delta `kernel_packets` Suricata | 48 |
| Drops / ifdrops / decoder / overflow | 0 / 0 / 0 / 0 |
| Muestras Sensor / stderr | 53 / vacío |

Los 44 paquetes son IPv4 menores de 500 bytes, con longitud media 85.18 y máxima 93. Los cuatro paquetes adicionales del contador Suricata no están identificados; no se interpretan como pérdida ni se les inventa protocolo.

El Sensor observó CPU puntual máxima de 2.24 %, RSS máximo de 780,308 KiB, memoria disponible mínima de 14,089,252 KiB y carga máxima de 0.24. Son observaciones, no umbrales.

## Feature y comparación R01↔R02

El extractor produjo una fila elegible:

| Feature | Valor |
|---|---:|
| `packet_rate_10s` | 4.4/s |
| `byte_rate_10s` | 374.8 B/s |
| `mean_ip_len_10s` | 85.18181818 B |
| `unique_dst_ip_ratio_30s` | 1/22 = 0.04545455 |
| `flow_attempt_rate_10s` | 2.2/s |
| `unique_dst_port_ratio_30s` | 1/22 = 0.04545455 |
| `dns_nxdomain_ratio_60s` | 2/22 = 0.09090909 |
| Resto de las 14 features | 0.0 |

El reporte cuenta 24 observaciones internas de aplicación: 22 objetos `dns_query` y dos marcadores adicionales `dns_nxdomain`. No son 24 transacciones de red; EVE y PCAP prueban 22 pares.

El vector coincide exactamente con R01. Los episodios siguen siendo independientes:

| Repetición | Span requests | PCAP SHA-256 |
|---|---:|---|
| R01 | 0.471976 s | `2f72f38e…` |
| R02 | 0.481996 s | `c9c69a00…` |

También difieren EVE, manifiesto, ledger, timestamps y hashes de bundle. Ambas campañas están en `train`; no hay cruce de partición. La coincidencia es reproducibilidad de un episodio determinista y, al mismo tiempo, posible peso repetido para el futuro entrenamiento. Se conserva y se incluirá en el análisis de sensibilidad por campaña.

## Integridad raíz

Todos los archivos listados en ambos `SHA256SUMS` pasaron:

```text
manifest.json          173e350c8dcd332cb3a2bd89f6d2ce4f36198dccbe681f5c5cf8b61e75cee5d3
capture.pcap0          c9c69a007fc52684ae4d3d6917cec8b26b60c2731fc9b8617bdb12a304b3ef60
eve-slice              393e324f6dc9e14d0d5e160be7a3e00228bcca375e460ae858123e04bdf927f7
campaign SHA256SUMS    c728083ffe894d2ed6d61aafbe4bd2d214116aa0bcc4696b895e5cc69b000677
multilayer-v1.csv      3009285b848f1a6f8e6ae306770dd1da7178b78a7216d7bf310e0abf97585e94
extraction-report      fe170378e27050ce619a7f876df5873ec8129ff1c82e37f6d4c6da2c9398d85e
feature SHA256SUMS     c00ae2c667b15c7fc1da6420df6b243f14eabe9eb76e6c9065e7d3c5233aa123
ledger                 96745804ca085c6a9fbeae96bb2533eb885fa1a261e583300391116ca98bedc2
```

## Ensamblador y decisión

El ensamblador aceptó 32/145 campañas, con 113 faltantes, cero inválidas y cero advertencias. R02 queda 3/29. Existen dos coincidencias exactas entre campañas: `DNS-VALID-10/R01↔R02` y `DNS-MIXED-20-2/R01↔R02`; ninguna cruza particiones.

Claude aceptó la campaña y autorizó el siguiente preflight. Se descartaron sus proyecciones de que las 145 campañas producirán unas 145 filas, que todas las repeticiones serán idénticas, que Isolation Forest pesa automáticamente una coincidencia una sola vez, su fase F5 inexistente y sus nuevos umbrales/controles no contenidos en el contrato.

**F1N-DNS-MIXED-20-2-R02 ACEPTADA CON LIMITACIONES.** El siguiente paso autorizado es el preflight individual de `F1N-DNS-MIXED-50-10-R02`.
