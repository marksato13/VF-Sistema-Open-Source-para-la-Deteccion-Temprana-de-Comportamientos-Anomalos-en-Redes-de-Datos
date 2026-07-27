# Vigésimo sexto canario oficial F1 — DNS-VALID-200 R01

Fecha: 27 de julio de 2026. Campaña: `F1N-DNS-VALID-200-R01`. Estado: **ACEPTADA CON LIMITACIONES**.

## Objetivo y preflight

Esta celda incrementa la línea base DNS legítima a doscientas consultas secuenciales desde Cliente `10.20.0.20` hacia Servidor `10.30.0.10:53`. Cada consulta solicita `server.ppi.lab/A` y espera `10.30.0.10`. El perfil pertenece al estrato `burst`, pero su intensidad se determina con timestamps observados, no únicamente con el número del perfil.

El preflight confirmó Git limpio y sincronizado en `e182a03e80a543b5940dc8884691b7b12141a1f3`, ID libre, volumen oficial con 141,028,515,840 bytes disponibles y gate de capacidad en `PASS`. Las cinco máquinas respondieron por SSH y pasaron NTP. dnsmasq, Suricata, rutas y captura estaban sanos; DNS resolvió correctamente por el Sensor. El generador remoto coincidió por SHA-256, las NIC externas permanecieron `DOWN` y el bypass `172.17.25.111-.114` quedó bloqueado por ICMP y TCP/22.

| Campo | Valor |
|---|---|
| Propósito / partición | `experiment` / `train` |
| Estrato | `burst` |
| Argumentos | `200` |
| Quietud / warm-up / settle / cooldown | 70 / 60 / 9 / 30 s |
| SHA matriz | `ad22ce5f8b41110b201f0eeacd2b5f13cc9f945c92cf539e9913e87fefdfa824` |
| SHA argumentos | `4d83a1f3e47b09a57f011d4bd69c80eaaed35d7122fbd598fca53a56f2f82d95` |

## Resultado DNS

La salida contiene exactamente doscientas líneas `10.30.0.10`. PCAP y EVE confirman:

| Control | Resultado |
|---|---:|
| Consultas / respuestas | 200 / 200 |
| Nombre / tipo | `server.ppi.lab` / `A` |
| RCODE | 400 eventos DNS `NOERROR` |
| Respuesta A | `10.30.0.10` |
| Span de consultas | 4.076892 s |
| Tasa observada | 49.056978 consultas/s |
| Puertos origen / flow IDs únicos | 199 |

Las 200 transacciones L7 no equivalen a 200 flujos L3/L4 únicos. El puerto origen `39878` se reutilizó dos veces con IDs DNS distintos, separados por 0.353 s. El contrato del extractor cuenta 200 consultas DNS y 199 intentos de flujo; ambos valores son correctos y no indican pérdida.

Comparación R01:

| Perfil | Consultas | Span | Tasa observada |
|---|---:|---:|---:|
| DNS-VALID-10 | 10 | 0.242729 s | 41.198209 consultas/s |
| DNS-VALID-200 | 200 | 4.076892 s | 49.056978 consultas/s |

El segundo perfil multiplica el número de consultas por veinte y el span por 16.796. Dos episodios no bastan para establecer una distribución o ley de rendimiento.

## PCAP, EVE y recursos

| Control | Resultado |
|---|---:|
| Evidencia completa | `true` |
| PCAP capturado / recibido / parseado | 400 / 400 / 400 |
| PCAP | 1 archivo / 46,024 bytes |
| Drops `tcpdump` | 0 |
| Delta Suricata | 404 |
| Drops / ifdrops / decoder / overflow | 0 / 0 / 0 / 0 |
| EVE esperado / extraído | 411 / 411 |
| Muestras Sensor / stderr | 56 / vacío |
| Transferencia / límite PCAP | verificada / no alcanzado |

Los 400 paquetes son UDP/IPv4: 200 consultas de 83 bytes y 200 respuestas de 87 bytes. Todos son menores de 500 bytes, con media 85 y máximo 87. El 0 % de tráfico pesado es correcto para esta ráfaga DNS pequeña y complementa los estratos de volumen.

El delta `kernel_packets=404` de Suricata supera en cuatro al PCAP filtrado LAN↔DMZ. Suricata recibe `ens35` completa; los cuatro paquetes adicionales no están identificados en el bundle y no se les asigna protocolo. tcpdump recibió y guardó los 400 paquetes del escenario con cero drops.

EVE contiene 400 DNS, diez `stats` y un `flow` ICMPv6 Router Solicitation tipo 133. El flow empezó a las `09:51:28`, antes del manifiesto de `09:51:51`, y fue emitido a las `09:52:04` por timeout de flow. Nació durante la quietud previa, quedó fuera del PCAP IPv4 y del extractor, pero se preserva en EVE. No modifica las features de `10.20.0.20`.

El Sensor alcanzó CPU puntual máxima de 3.01 %, RSS de 780,308 KiB, memoria disponible mínima de 14,084,272 KiB y carga máxima de 0.11. Son observaciones sin umbral.

## Features

El extractor procesó 400 paquetes, obtuvo 200 observaciones de aplicación y produjo dos filas elegibles del mismo episodio:

| Ventana UTC | Paquetes nuevos | Consultas en historia 60 s | Attempts en historia 30 s | Tasa paquetes 10 s | Tasa attempts 10 s |
|---|---:|---:|---:|---:|---:|
| `14:53:00` | 228 | 114 | 114 | 22.8/s | 11.4/s |
| `14:53:10` | 172 | 200 | 199 | 17.2/s | 8.5/s |

La campaña cruzó una frontera UTC de diez segundos: 114 consultas quedaron en la primera ventana y 86 en la segunda. En la segunda hubo 85 intentos nuevos porque una consulta reutilizó la 5-tupla del puerto `39878`. `dns_query_count_60s=200` conserva todas las transacciones L7, mientras `flow_attempt_count_30s=199` conserva los flujos únicos.

La fila final obtiene `unique_dst_ip_ratio_30s=1/199`, `unique_dst_port_ratio_30s=1/199` y `dns_nxdomain_ratio_60s=0/200`. Ambas filas son ventanas autocorrelacionadas de una sola ráfaga, no repeticiones independientes.

La benignidad procede del escenario y de las respuestas esperadas. Isolation Forest final todavía no está entrenado; esta campaña no determina score, falsos positivos ni generalización.

## Integridad raíz

```text
manifest.json          0f70f2d96651711565e9a00bc462a77c6dd0cd0feed5655a5b0a53a8132ceead
capture.pcap0          6fe38ea73521282e33c9341f86dcc46adbc52ade85f51471f25044c9a1017825
eve-slice              d7dc4fd3ead75950da5e0a97b03b648d663ad55e2be083a00c6120a9ed7c3320
campaign SHA256SUMS    35eceee2fe063b717de220ded3da7cd103a5466b93e5844565a83238142eecc3
multilayer-v1.csv      ed6ffaaf2982fcb73b4787cd633d723115b3ea4285c82409e73b8fdd206da9ed
extraction-report      8812727a36596d61d2b92b3b9d16a00d9cc60acb86bb785cdb39fb052e8d8a87
feature SHA256SUMS     9786f2483da8125b99d4f528b00665ae8fdfce96797cb91c43fac95e78f7ee6c
ledger                 6ada679fac06b34c55fca3ea73249c8279ffc969c1e850e57d326fd8c8619461
```

Todos los hashes pasaron y la captura residual quedó inactiva. El ensamblador informó 145 esperadas, 26 aceptadas, 0 inválidas, 0 advertencias, 0 duplicados y 119 faltantes. El dataset completo todavía no puede construirse.

## Decisión

Claude emitió **ACEPTAR CON LIMITACIONES**. Su primera respuesta convirtió incorrectamente el Router Solicitation ICMPv6 en un “TCP half-open”, contó 200 intentos en lugar de 199 y confundió `flow_attempt_rate=8.5/s` con paquetes por segundo. La segunda revisión corrigió los tres puntos.

**CANARIO DNS-VALID-200 ACEPTADO CON LIMITACIONES.** Aporta una ráfaga legítima de 200 transacciones DNS, evidencia la diferencia entre transacción y flujo y conserva un evento IPv6 fuera de alcance sin contaminar features. Quedan tres gaps R01: `DNS-MIXED-50-10`, `PING-10` y `PING-100`. El siguiente exacto es `DNS-MIXED-50-10/R01`, con preflight nuevo.
