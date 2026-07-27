# Vigésimo cuarto canario oficial F1 — MIXED-LIGHT R01

Fecha: 27 de julio de 2026. Campaña: `F1N-MIXED-LIGHT-R01`. Estado: **ACEPTADA CON LIMITACIONES**.

## Objetivo y preflight

Esta celda combina de forma concurrente tres cargas legítimas desde Cliente `10.20.0.20` hacia Servidor `10.30.0.10`: HTTP 100 MB limitado a 5 MB/s, iperf3 TCP a 50 Mbit/s durante 10 s y veinte consultas DNS válidas. Su objetivo es ejercitar conjuntamente señales de volumen y comportamiento L3/L4/L7, no simular toda la diversidad de una red productiva.

El preflight confirmó Git limpio y sincronizado en `3df337b8c2b73b809b3e2654ce387b9c4eac75b9`, ID libre, volumen oficial con 141,206,523,904 bytes disponibles y gate de capacidad en `PASS`. Las cinco máquinas respondieron por SSH y pasaron NTP. NGINX, dnsmasq, iperf3, Suricata, rutas y captura estaban sanos; HTTP devolvió 200, DNS resolvió `server.ppi.lab` como `10.30.0.10` y el control iperf3 respondió. El generador remoto coincidió por SHA-256, las NIC externas permanecieron `DOWN` y el bypass `172.17.25.111-.114` quedó bloqueado por ICMP y TCP/22.

| Campo | Valor |
|---|---|
| Propósito / partición | `experiment` / `train` |
| Estrato | `mixed-legitimate` |
| Argumentos | ninguno |
| Quietud / warm-up / settle / cooldown | 70 / 60 / 9 / 30 s |
| SHA matriz | `ad22ce5f8b41110b201f0eeacd2b5f13cc9f945c92cf539e9913e87fefdfa824` |
| SHA argumentos | `4f53cda18c2baa0c0354bb5f9a3ecbe5ed12ab4d8e11ba873c2f11161202b945` |

## Resultado por componente

| Componente | Resultado |
|---|---|
| HTTP | 200; 104,857,600 bytes; 19.517769 s; 5,372,417 B/s |
| iperf3 TCP emisor | 62,521,344 bytes; 50.009599 Mbit/s; 10.001495 s; 2 retransmisiones |
| iperf3 TCP receptor | 62,521,344 bytes; 50.000775 Mbit/s; 10.003260 s |
| DNS | 20 respuestas en la salida; EVE: 20 solicitudes + 20 respuestas `NOERROR` |

Los bytes iperf3 coinciden en ambos extremos y no hubo error de escenario. Las dos retransmisiones tienen causa no determinada y no existe un umbral contractual para convertirlas en aceptación o rechazo. Tampoco se equiparan con drops de captura: son métricas distintas.

## Concurrencia demostrada

El PCAP permite reconstruir el inicio de cada componente:

| Flujo | Inicio epoch | Diferencia frente a HTTP | Span observado |
|---|---:|---:|---:|
| HTTP `35692→80` | 1785160577.870680 | 0 ms | 19.519484 s |
| iperf control `35306→5201` | 1785160577.871351 | 0.671 ms | 10.012489 s |
| iperf datos `35312→5201` | 1785160577.874424 | 3.744 ms | 10.009182 s |
| primer DNS `→53` | 1785160577.890705 | 20.025 ms | 0.518239 s para los 20 pares |

Los tres componentes se solaparon durante aproximadamente 0.518 s; HTTP e iperf3 coexistieron durante unos 10 s. Esto prueba concurrencia temporal real, no solo presencia en la misma campaña.

## PCAP, EVE y recursos

| Control | Resultado |
|---|---:|
| Evidencia completa | `true` |
| PCAP capturado / recibido / parseado | 122,802 / 122,802 / 122,802 |
| PCAP | 1 archivo / 177,537,599 bytes |
| TCP / UDP | 122,762 / 40 paquetes |
| Drops `tcpdump` | 0 |
| Delta Suricata | 122,804 |
| Drops / ifdrops / decoder / overflow | 0 / 0 / 0 / 0 |
| EVE esperado / extraído | 57 / 57 |
| Muestras Sensor / stderr | 75 / vacío |
| Transferencia / límite PCAP | verificada / no alcanzado |

De 122,802 paquetes IPv4, 115,892 —**94.3731 %**— midieron entre 500 y 1500 bytes; 115,381 midieron exactamente 1500, 6,910 fueron menores de 500 y ninguno superó 1500. La longitud media fue 1,415.72 bytes.

EVE contiene 13 `stats`, 40 DNS, un HTTP, un `fileinfo`, una alerta permitida SID `2260003` y una anomalía `APPLAYER_PROTO_DETECTION_SKIPPED`. La alerta/anomalía corresponde al límite de clasificación de iperf3 ya observado en los perfiles TCP; se conserva como telemetría, no etiqueta ataque ni entra en las features.

Los veinte pares DNS consultaron `server.ppi.lab/A`, recibieron `NOERROR` y resolvieron `10.30.0.10`. HTTP observó `GET /files/100MB.bin` y estado 200. `fileinfo` quedó en 102,400 bytes con estado `TRUNCATED`: limita el seguimiento/extracción del archivo por Suricata, no la descarga acreditada por curl ni la integridad del PCAP.

El Sensor alcanzó CPU puntual máxima de 20.69 %, RSS de 780,308 KiB, memoria disponible mínima de 13,908,744 KiB y carga máxima de 0.37. No se inventa un umbral de recursos; se conservan estos valores para compararlos con R02–R05.

## Features

El extractor procesó 122,802 paquetes, obtuvo 21 observaciones de aplicación —20 consultas DNS y una solicitud HTTP— y produjo tres filas elegibles:

| Ventana UTC | Paquetes | Tasa bytes/s | Attempts 30 s | SYN 10 s | HTTP 60 s | DNS 60 s | Ratio grande |
|---|---:|---:|---:|---:|---:|---:|---:|
| `13:56:20` | 36,027 | 4,660,617.6 | 23 | 3 | 1 | 20 | 0.85885586 |
| `13:56:30` | 72,091 | 10,532,835.5 | 23 | 0 | 1 | 20 | 0.97566964 |
| `13:56:40` | 14,684 | 2,191,898.4 | 23 | 0 | 1 | 20 | 0.99516481 |

Los 23 intentos representan veinte flujos UDP DNS, una conexión HTTP y las conexiones de control/datos iperf3. La primera fila contiene tres SYN con `syn_completion_ratio_10s=1`. Existe un único destino IP y tres puertos destino distintos —53, 80 y 5201—, por lo que `unique_dst_ip_ratio_30s=1/23` y `unique_dst_port_ratio_30s=3/23`. `dns_nxdomain_ratio_60s=0/20` y `http_error_ratio_60s=0`.

Las filas segunda y tercera conservan historia causal de 30/60 s, aunque ya no contienen SYN nuevos. Las tres pertenecen al mismo episodio y no son repeticiones independientes.

Esta campaña ejercita conjuntamente señales L3, L4 y L7 y contiene tráfico pesado benigno. Responde a ambas observaciones del jurado dentro de este episodio, pero no elimina sesgo del dataset ni prueba desempeño del Isolation Forest final, todavía no entrenado.

## Integridad raíz

```text
manifest.json          c92ceaaba748b0bbd7f023146e9a339ff9f935efd9453549f9759796410383b6
capture.pcap0          b493b572f4b5cbcd407694d99c30fad3bd0843de3e0404da842159cc417cac9d
eve-slice              7fd792deccdfea1a76264c8aea4ef0795a6a1e1fd4de5331c2fadb80aab4fd19
campaign SHA256SUMS    b942926ecae2013632e9611edc700f34cd8495b7e5a8133f6864159450800282
multilayer-v1.csv      fa1d21583ab78fa562bf20228e397283e5cc43f02686293e9c81e3247f9366a5
extraction-report      3daace3a403633834e2194acb49eb55afa2af393a083188f9a6b22695df892fd
feature SHA256SUMS     f9b0d4006681ac5588f7d3855721086aa2b892a1ee4fcf6db9cb047674990fee
ledger                 1a53f1823b7a775c078f6bffc968f0c5295a799db947dae67720e6f78c1348d3
```

Todos los hashes pasaron y la captura residual quedó inactiva. El ensamblador informó 145 esperadas, 24 aceptadas, 0 inválidas, 0 advertencias, 0 duplicados y 121 faltantes. El dataset completo todavía no puede construirse.

## Decisión

Claude emitió **ACEPTAR CON LIMITACIONES**, pero sus dos primeras respuestas mezclaron unidades, límites de inspección y métricas; la tercera pidió datos que ya estaban incluidos en el prompt. Solo se conserva el dictamen coincidente y se corrigen sus afirmaciones contra la evidencia.

**CANARIO MIXED-LIGHT ACEPTADO CON LIMITACIONES.** Demuestra solapamiento reproducible de HTTP, TCP pesado y DNS válido, con captura completa y señales L3/L4/L7. Permanecen cinco gaps R01: `DNS-VALID-10`, `DNS-VALID-200`, `DNS-MIXED-50-10`, `PING-10` y `PING-100`. El siguiente exacto por orden de matriz es `DNS-VALID-10/R01`, con preflight nuevo.
