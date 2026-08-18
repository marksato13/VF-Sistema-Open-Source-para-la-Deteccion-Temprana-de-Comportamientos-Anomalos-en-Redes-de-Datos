# Vigésimo quinto canario oficial F1 — DNS-VALID-10 R01

Fecha: 27 de julio de 2026. Campaña: `F1N-DNS-VALID-10-R01`. Estado: **ACEPTADA CON LIMITACIONES**.

## Objetivo y preflight

Esta celda genera diez consultas DNS legítimas y secuenciales desde Cliente `10.20.0.20` hacia Servidor `10.30.0.10:53`. Cada consulta solicita `server.ppi.lab/A` y espera `10.30.0.10`. Representa tráfico ligero de control y complementa —no sustituye— los perfiles benignos pesados.

El preflight confirmó Git limpio y sincronizado en `68f4c47c5703d8557a0986ff8218477ac9cd2496`, ID libre, volumen oficial con 141,028,724,736 bytes disponibles y gate de capacidad en `PASS`. Las cinco máquinas respondieron por SSH y pasaron NTP. dnsmasq, Suricata, rutas y captura estaban sanos; la consulta de comprobación resolvió correctamente por el camino Cliente→Sensor→Servidor. El generador remoto coincidió por SHA-256, las NIC externas permanecieron `DOWN` y el bypass `172.17.25.111-.114` quedó bloqueado por ICMP y TCP/22.

| Campo | Valor |
|---|---|
| Propósito / partición | `experiment` / `train` |
| Estrato | `light` |
| Argumentos | `10` |
| Quietud / warm-up / settle / cooldown | 70 / 60 / 9 / 30 s |
| SHA matriz | `ad22ce5f8b41110b201f0eeacd2b5f13cc9f945c92cf539e9913e87fefdfa824` |
| SHA argumentos | `6e32bc5b03ab4d239b1eff1de30de5007f906dda41e8f720240bbf6481496a60` |

## Resultado DNS

La salida contiene exactamente diez líneas `10.30.0.10`. El PCAP contiene diez consultas y diez respuestas:

| Control | Resultado |
|---|---:|
| Consultas / respuestas | 10 / 10 |
| Nombre / tipo | `server.ppi.lab` / `A` |
| RCODE | 20 eventos DNS `NOERROR` |
| Respuesta A | `10.30.0.10` |
| Span del episodio | 0.242729 s |
| Puertos origen | 10 distintos |

EVE confirma diez `request` y diez `response`; no existen NXDOMAIN ni alertas. Los conteos exactos del escenario indican que el tráfico de preflight no apareció en el PCAP/EVE oficial. Es un resultado de esta campaña, no una garantía universal contra contaminación futura.

## PCAP, Suricata y recursos

| Control | Resultado |
|---|---:|
| Evidencia completa | `true` |
| PCAP capturado / recibido / parseado | 20 / 20 / 20 |
| PCAP | 1 archivo / 2,324 bytes |
| Drops `tcpdump` | 0 |
| Delta Suricata | 24 |
| Drops / ifdrops / decoder / overflow | 0 / 0 / 0 / 0 |
| EVE esperado / extraído | 30 / 30 |
| Muestras Sensor / stderr | 53 / vacío |
| Transferencia / límite PCAP | verificada / no alcanzado |

Los veinte paquetes son UDP/IPv4: diez consultas de 83 bytes y diez respuestas de 87 bytes. Todos son menores de 500 bytes; la longitud media es 85 y la máxima 87. El 0 % entre 500 y 1500 bytes es correcto para el estrato DNS ligero. La observación del jurado exige que el dataset incluya tráfico pesado legítimo, no que todos los perfiles sean pesados; conservar ambos extremos evita un rango de entrenamiento artificialmente homogéneo.

EVE contiene veinte eventos DNS y diez `stats`. El delta `kernel_packets=24` de Suricata y los veinte paquetes del PCAP no miden exactamente el mismo alcance: Suricata recibe la interfaz `ens35` completa, mientras tcpdump aplica el filtro fijo LAN↔DMZ. Los cuatro paquetes adicionales no están identificados en este bundle; no se les asigna protocolo o evento ni se interpretan como pérdida. tcpdump recibió y guardó los veinte paquetes del escenario con cero drops.

El Sensor alcanzó CPU puntual máxima de 2.26 %, RSS de 780,308 KiB, memoria disponible mínima de 14,071,756 KiB y carga máxima de 0.18. Son observaciones, no umbrales.

## Features

El extractor procesó veinte paquetes, obtuvo diez observaciones de aplicación y produjo una fila elegible:

| Feature | Valor |
|---|---:|
| `packet_rate_10s` | 2.0 paquetes/s |
| `byte_rate_10s` | 170.0 B/s |
| `mean_ip_len_10s` | 85.0 bytes |
| `large_ip_ratio_10s` | 0.0 |
| `flow_attempt_count_30s` | 10 |
| `flow_attempt_rate_10s` | 1.0/s |
| `unique_dst_ip_ratio_30s` | 1/10 = 0.1 |
| `unique_dst_port_ratio_30s` | 1/10 = 0.1 |
| `dns_query_count_60s` | 10 |
| `dns_nxdomain_ratio_60s` | 0/10 = 0.0 |

La fila ejercita una señal L3 de concentración en un único destino y semántica L7 DNS válida. Al no existir TCP, SYN, HTTP o TLS, sus features correspondientes permanecen en cero. Una fila representa un episodio, no una repetición independiente ni un SLA.

La etiqueta benigna procede del escenario controlado, manifiesto y respuestas esperadas; no de la ausencia de alertas. Isolation Forest final todavía no está entrenado, por lo que esta campaña no prueba score ni falsos positivos.

## Integridad raíz

```text
manifest.json          1dec95fdec19b4a9d8331db9cacfc502572aa6d1747cc9498d255a9d988f62f4
capture.pcap0          631db5e4bbc8edde41c032e0c49b85ce7e1a227a3f866b47a289af078b1efbe5
eve-slice              ab815cd5fb9cc96c3db04e3b0baffdf560d4da84ead61d94aa68ea4110d189de
campaign SHA256SUMS    69dd942ee6aa31f0755beee0f1a8e4ba74759bb845df6fe7022a4ea99b73411b
multilayer-v1.csv      047fa004b9acd37783c095abc1b95a659e132f9df21d18657ace4e565270f9db
extraction-report      172dcbdd2a3ca0ed371a72e2b9e427fb44f5f3369d441a63567a38b4ba64e6a9
feature SHA256SUMS     482b7939c206471b24e0bdee9d13dd599c84ddfe02309ae8e721400c3994caa4
ledger                 3cf3eee78b804165030e206b37ac0d290ec7cd1ad001aa4952cd889e1beda401
```

Todos los hashes pasaron y la captura residual quedó inactiva. El ensamblador informó 145 esperadas, 25 aceptadas, 0 inválidas, 0 advertencias, 0 duplicados y 120 faltantes. El dataset completo todavía no puede construirse.

## Decisión

Claude emitió **ACEPTAR CON LIMITACIONES**. Su primera respuesta confundió los cuatro paquetes adicionales del contador Suricata con cuatro eventos `stats`; se corrigió que EVE contiene diez `stats` y que ambos conteos pertenecen a métricas diferentes. También se corrigió que esta fila sí ejercita señales L3 y L7.

**CANARIO DNS-VALID-10 ACEPTADO CON LIMITACIONES.** Aporta una línea base DNS legítima, pequeña y concentrada, con conteos exactos y captura íntegra. Quedan cuatro gaps R01: `DNS-VALID-200`, `DNS-MIXED-50-10`, `PING-10` y `PING-100`. El siguiente exacto por orden de matriz es `DNS-VALID-200/R01`, con preflight nuevo.
