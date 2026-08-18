# Segundo canario oficial R02 — DNS-VALID-200

Fecha: 27 de julio de 2026. Campaña: `F1N-DNS-VALID-200-R02`. Estado: **ACEPTADA CON LIMITACIONES**.

## Objetivo y preflight

Esta campaña repite el perfil legítimo de doscientas consultas DNS secuenciales desde Cliente `10.20.0.20` hacia Servidor `10.30.0.10:53`. Cada consulta solicita `server.ppi.lab/A` y debe recibir `10.30.0.10`. El perfil es `experiment/train`, estrato `burst`; no es calibración ni ataque.

El preflight confirmó Git limpio y sincronizado en `70d62388a2d99e9927a1743250309871910d60b9`, ID libre, volumen oficial válido, unos 141 GB disponibles y gate de capacidad en `PASS`. Las cuatro VMs respondieron por SSH y NTP pasó con un desfase absoluto máximo observado de aproximadamente 0.4 ms.

Suricata, NGINX, dnsmasq, SSH y `ppi-iperf3.service` estaban activos. DNS resolvió por el camino Cliente→Sensor→Servidor, la captura residual estaba inactiva y el generador remoto coincidió por SHA-256. Las NIC externas permanecieron `DOWN` (`ens34`, excepto `eth0` en Kali) y el bypass `172.17.25.111–114` quedó bloqueado por ICMP y TCP/22.

| Campo | Valor |
|---|---|
| Perfil / repetición | `DNS-VALID-200` / R02 |
| Propósito / partición | `experiment` / `train` |
| Argumentos | `200` |
| Quietud / warm-up / settle / cooldown | 70 / 60 / 9 / 30 s |
| SHA matriz | `ad22ce5f8b41110b201f0eeacd2b5f13cc9f945c92cf539e9913e87fefdfa824` |
| SHA argumentos | `4d83a1f3e47b09a57f011d4bd69c80eaaed35d7122fbd598fca53a56f2f82d95` |

## Resultado DNS

La salida contiene exactamente doscientas líneas `10.30.0.10`; stderr está vacío.

| Control | Resultado |
|---|---:|
| Consultas / respuestas PCAP | 200 / 200 |
| Request / response EVE | 200 / 200 |
| RCODE `NOERROR` | 400 eventos |
| Respuestas A `10.30.0.10` | 200 |
| IDs DNS / flow IDs distintos | 200 / 200 |
| Span de requests | 4.110662 s |
| Tasa observada | 48.653964 consultas/s |
| Alertas | 0 |
| Eventos `stats` | 10 |

La tasa es descriptiva: no constituye un umbral de aceptación.

## PCAP, EVE y recursos

| Control | Resultado |
|---|---:|
| Estado / código de escenario | `completed` / 0 |
| Evidencia completa | `true` |
| PCAP archivos / bytes | 1 / 46,024 |
| Capturados / parseados | 400 / 400 |
| Drops tcpdump | 0 |
| Transferencia verificada / límite alcanzado | sí / no |
| EVE extraído / esperado | 410 / 410 |
| Delta `kernel_packets` Suricata | 404 |
| Drops / ifdrops / decoder / overflow | 0 / 0 / 0 / 0 |
| Muestras Sensor / stderr | 56 / vacío |

Los 400 paquetes UDP/IPv4 son menores de 500 bytes, con media 85 y máximo 87. El perfil DNS ligero/burst no pretende aportar payload pesado; los perfiles HTTP, HTTPS e iperf cubren ese rango.

Suricata contó cuatro paquetes más que el PCAP filtrado LAN↔DMZ. No están identificados y no se convierten en un protocolo supuesto. El PCAP capturó y parseó los 400 paquetes esperados con cero drops; EVE contiene exactamente 400 eventos DNS y diez `stats`, sin eventos extra.

El Sensor observó CPU puntual máxima de 2.24 %, RSS máximo de 780,308 KiB, memoria disponible mínima de 14,101,764 KiB y carga máxima de 0.42. Son observaciones de esta ejecución, no límites.

## Dos ventanas y efecto de fase

El extractor procesó 400 paquetes, obtuvo 200 observaciones de aplicación y produjo dos filas elegibles:

| Ventana UTC | Paquetes nuevos | Consultas nuevas | Consultas historia 60 s | Attempts historia 30 s | `packet_rate_10s` | `flow_attempt_rate_10s` |
|---|---:|---:|---:|---:|---:|---:|
| `17:32:30` | 24 | 12 | 12 | 12 | 2.4/s | 1.2/s |
| `17:32:40` | 376 | 188 | 200 | 200 | 37.6/s | 18.8/s |

La ráfaga empezó a las `17:32:29.709857Z`: aunque duró solo 4.110662 s, cruzó el borde UTC de `17:32:30`. La primera fila contiene aproximadamente los 0.29 s iniciales; la segunda contiene los paquetes nuevos restantes y conserva el historial de las 200 consultas.

Ambas filas pertenecen a un solo episodio y están autocorrelacionadas. El ensamblador conserva las dos; no aplica una política de “una fila por campaña”. La independencia experimental se evalúa por episodio/campaña, no contando cada ventana como una repetición.

## Comparación descriptiva R01↔R02

| Repetición | Span requests | Tasa observada | Flow IDs | Reparto paquetes por ventana |
|---|---:|---:|---:|---:|
| R01 | 4.076892 s | 49.056978/s | 199 | 228 / 172 |
| R02 | 4.110662 s | 48.653964/s | 200 | 24 / 376 |

El número de transacciones, resultado DNS, tamaño medio y duración global son próximos. La gran diferencia entre filas proviene principalmente de la fase respecto al borde fijo de diez segundos. R01 inició aproximadamente 2.33 s antes de su borde; R02, 0.29 s antes.

R01 reutilizó una 5-tupla y registró 199 flow IDs para 200 transacciones; R02 registró 200. Es variación legítima del puerto efímero, no pérdida. PCAP y EVE de ambas repeticiones tienen hashes distintos.

Este resultado demuestra por qué las ventanas de una campaña no deben tratarse como observaciones independientes. Antes del entrenamiento se evaluará sensibilidad al peso por ventana y agregación por campaña, sin alterar retroactivamente la matriz ni descartar filas después de observarlas.

## Integridad raíz

Todos los archivos listados en ambos `SHA256SUMS` pasaron:

```text
manifest.json          9abeb1bbce048a677dde0a1852a5c5d0a7db23bd66f364c8e66145e0996b8981
capture.pcap0          83a7e471869db429279f316d8c6197c60ecf88fce0850288345d582ff7492ee1
eve-slice              4a57a2a452571fadcff3e8c693aa14c9aba06fd63d803ffa1162609d42f44d68
campaign SHA256SUMS    867e5d8b5e221fc1bdccff2989d303a273c63747f53c85c436e3175fb37d9955
multilayer-v1.csv      d4e396eca06c88605fd23c14fa1d510b07e488b0a48192d2256823ac1a4f2b37
extraction-report      7743af6250880b3ed4edaab759f4ffa8a0fe8c572c2f91a14abbe9a2cbf98453
feature SHA256SUMS     2d21be76cf296e5cfe231da3fc656c7f82c8a394918f69159ecb3bac49e4c361
ledger                 acb20e8ac9edda7dd2147e596f9214cb940760d7382d0fab5eda3650889a217c
```

## Ensamblador y revisión Claude

El ensamblador aceptó 31/145 campañas, con 114 faltantes, cero inválidas y cero advertencias. R02 queda 2/29. Persiste una sola coincidencia exacta entre campañas —`DNS-VALID-10/R01↔R02`— y ninguna entre particiones; `DNS-VALID-200/R02` no agregó coincidencias.

Claude aceptó la integridad y reconoció el efecto de fase y la autocorrelación. Se descartaron sus afirmaciones de que la ráfaga no cruzó un borde, que el sistema selecciona una sola fila por campaña, que el ledger acredita cruces entre particiones y que el ratio esperado de dos NXDOMAIN entre 22 consultas sería 0.095. El valor aritmético es `2/22 = 0.090909…`, pero la evidencia del próximo perfil se observará antes de afirmar su fila exacta.

**F1N-DNS-VALID-200-R02 ACEPTADA CON LIMITACIONES.** El siguiente paso autorizado es el preflight individual de `F1N-DNS-MIXED-20-2-R02`.
