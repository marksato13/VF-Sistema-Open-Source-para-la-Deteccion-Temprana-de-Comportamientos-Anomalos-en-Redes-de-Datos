# Primer canario oficial R02 — DNS-VALID-10

Fecha: 27 de julio de 2026. Campaña: `F1N-DNS-VALID-10-R02`. Estado: **ACEPTADA**.

## Objetivo

Iniciar la segunda repetición de F1 con el mismo contrato congelado de R01. El perfil genera diez consultas DNS legítimas y secuenciales desde Cliente `10.20.0.20` hacia Servidor `10.30.0.10:53`; cada consulta solicita `server.ppi.lab/A` y debe resolver `10.30.0.10`.

Esta ejecución no es calibración. Su propósito es `experiment`, pertenece a `train` y permite observar reproducibilidad entre episodios independientes antes de completar R02.

## Preflight

El árbol Git estaba limpio y sincronizado en `02957dca8da5781bca968cceac0cdd0f4ba6dd2c`. El ID estaba libre en las rutas oficiales de campañas, features y ledger. El volumen identificado tenía 141,027,254,272 bytes disponibles y el gate de almacenamiento pasó.

Las cuatro VMs remotas respondieron por SSH. El gate NTP pasó con un desfase absoluto máximo observado de aproximadamente 0.4 ms. Suricata, NGINX, dnsmasq, SSH y `ppi-iperf3.service` estaban activos; `iperf3.service` inactivo no es una falla porque no es la unidad usada por el laboratorio. La consulta de control resolvió correctamente por Cliente→Sensor→Servidor.

El generador remoto coincidió con el SHA-256 local:

```text
d4cd42b65f1b22cea0a3f585c2df760af68a8557799c3859eabc803d4f9b4203
```

La captura residual para este ID estaba inactiva. Las NIC externas permanecieron `DOWN`: `ens34` en Sensor, Servidor y Cliente, y `eth0` en Kali. El bypass `172.17.25.111–114` quedó bloqueado por ICMP y TCP/22.

| Campo | Valor |
|---|---|
| Perfil / repetición | `DNS-VALID-10` / R02 |
| Propósito / partición | `experiment` / `train` |
| Quietud / warm-up / settle / cooldown | 70 / 60 / 9 / 30 s |
| SHA matriz | `ad22ce5f8b41110b201f0eeacd2b5f13cc9f945c92cf539e9913e87fefdfa824` |
| SHA argumentos | `6e32bc5b03ab4d239b1eff1de30de5007f906dda41e8f720240bbf6481496a60` |

## Resultado observado

La salida contiene exactamente diez líneas `10.30.0.10` y stderr está vacío. PCAP y EVE acreditan diez consultas y diez respuestas:

| Control | Resultado |
|---|---:|
| Consultas / respuestas PCAP | 10 / 10 |
| Request / response EVE | 10 / 10 |
| RCODE `NOERROR` | 20 eventos |
| Respuestas A `10.30.0.10` | 10 |
| IDs DNS distintos | 10 |
| Span DNS | 0.246351 s |
| Alertas | 0 |
| Eventos `stats` | 9 |

Los diez pares son UDP/IPv4. Los 20 paquetes son menores de 500 bytes, con longitud media 85 y máxima 87 bytes. Esto es correcto para la línea base DNS ligera; el rango legítimo pesado se aporta mediante otros perfiles de F1.

## Integridad, captura y recursos

| Control | Resultado |
|---|---:|
| Estado / código de escenario | `completed` / 0 |
| Evidencia completa | `true` |
| PCAP archivos / bytes | 1 / 2,324 |
| Capturados / parseados | 20 / 20 |
| Drops tcpdump | 0 |
| Transferencia verificada / límite alcanzado | sí / no |
| EVE extraído / esperado | 29 / 29 |
| Delta `kernel_packets` Suricata | 24 |
| Drops / ifdrops / decoder / overflow | 0 / 0 / 0 / 0 |
| Muestras Sensor / stderr | 53 / vacío |

Suricata contó 24 paquetes en `ens35` y el PCAP filtrado contiene 20. Los cuatro adicionales no se identifican ni se interpretan como pérdida. PCAP recibió y guardó todos los paquetes del escenario con cero drops.

El Sensor observó CPU puntual máxima de 1.52 %, RSS máximo de 780,308 KiB, memoria disponible mínima de 14,106,804 KiB y carga máxima de 0.56. Son mediciones de esta campaña, no umbrales.

Todos los archivos listados en ambos `SHA256SUMS` pasaron. Hashes raíz:

```text
manifest.json          747af1b474d046779d15657eb972628c3cd9506b451881a6130f04d9ee531c51
capture.pcap0          1525e6dbd936d8b57ac1179281e7f96adb581716891539b1c1ee61581664430d
eve-slice              27baecdfd112907a0496e05a327d6aa21c60df4cb41036f0eb6f8e5604405500
campaign SHA256SUMS    edde58ccc1d656cee40bc21d7ddf9bd5091f5bc3622aff224b7825e802e4c235
multilayer-v1.csv      9e711356e08ad50779d4bf95d391896695c2ee7fa12f50d381904c9e5cea1791
extraction-report      9aac4dea246e7f303a2146ed1cad0d3362e70a6225ada9783816aba742a38b13
feature SHA256SUMS     c43d0545cfa56b8ae9de7a89dad91a23618af17c88b6b30b8fee2a78fbd803dc
ledger                 eaa032b1c4e30a1f0c501d5f471ee8bc4b097d264f30bb071683296a0921354f
```

## Feature y comparación R01↔R02

El extractor procesó 20 paquetes, obtuvo 10 observaciones de aplicación y produjo una fila elegible:

| Feature | R02 |
|---|---:|
| `packet_rate_10s` | 2.0/s |
| `byte_rate_10s` | 170.0 B/s |
| `mean_ip_len_10s` | 85.0 B |
| `large_ip_ratio_10s` | 0.0 |
| `unique_dst_ip_ratio_30s` | 0.1 |
| `flow_attempt_rate_10s` | 1.0/s |
| `unique_dst_port_ratio_30s` | 0.1 |
| `dns_nxdomain_ratio_60s` | 0.0 |
| Resto de las 14 features | 0.0 |

El vector numérico coincide exactamente con `DNS-VALID-10/R01`. Esto es un hallazgo reproducible de dos episodios deterministas, no evidencia reutilizada:

- R01 y R02 tienen PCAP, EVE, manifiesto, ledger y tiempos distintos;
- el PCAP R01 tiene SHA `631db5…` y R02 `1525e6…`;
- R01 abarcó 0.242729 s y R02 0.246351 s;
- ambas campañas pertenecen a `train`, por lo que no existe cruce de partición.

La coincidencia sí puede aumentar el peso de este patrón si se conserva como otra fila de entrenamiento. Por ello se reporta y no se elimina automáticamente. Antes de entrenar se realizará análisis de sensibilidad conservando episodios y colapsando vectores exactos, sin permitir que un episodio cruce particiones.

## Gates y decisión

El ensamblador global informa:

| Métrica | Resultado |
|---|---:|
| Campañas aceptadas | 30 / 145 |
| Inválidas / advertencias | 0 / 0 |
| Faltantes globales | 115 |
| R02 aceptadas / esperadas | 1 / 29 |
| Coincidencias exactas entre campañas | 1 |
| Coincidencias exactas entre particiones | 0 |

El gate de esta campaña pasa. El gate agregado de R02 permanece en `false` porque faltan 28 perfiles; eso es estado de progreso, no invalidación del canario.

Claude primero afirmó incorrectamente que la campaña no existía al no acceder a la ruta externa. Tras recibir la evidencia verificada, corrigió el dictamen y la aceptó. Se descartan sus afirmaciones posteriores de que el gate de repetición ya pasa, la referencia a una feature inexistente `request_rate` y expectativas numéricas no derivadas del contrato.

**F1N-DNS-VALID-10-R02 ACEPTADA.** El siguiente paso autorizado es el preflight individual de `F1N-DNS-VALID-200-R02`; no se autoriza ejecución ciega del resto de la matriz.
