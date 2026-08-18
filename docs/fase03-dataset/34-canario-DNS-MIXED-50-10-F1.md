# Vigésimo séptimo canario oficial F1 — DNS-MIXED-50-10 R01

Fecha: 27 de julio de 2026. Campaña: `F1N-DNS-MIXED-50-10-R01`. Estado: **ACEPTADA CON LIMITACIONES**.

## Objetivo y preflight

Esta celda representa errores DNS legítimos dentro de tráfico benigno controlado. Cliente `10.20.0.20` consultó al DNS interno del Servidor `10.30.0.10:53`: primero cincuenta veces `server.ppi.lab/A` y después una vez cada nombre `error-legitimo-1.ppi.lab` a `error-legitimo-10.ppi.lab`. Los primeros nombres debían devolver `10.30.0.10`; los diez últimos, `NXDOMAIN`.

El preflight confirmó Git limpio y sincronizado en `2c8542c8c5571ba6e67efc3df5e16e7c9199f73c`, ID libre, 141,028,044,800 bytes disponibles en el volumen oficial y gate de capacidad en `PASS`. Las cinco máquinas respondieron por SSH y pasaron NTP. dnsmasq, Suricata, rutas y captura estaban sanos; se probaron tanto la resolución válida como un NXDOMAIN controlado. El generador local y remoto coincidió por SHA-256. Las NIC externas permanecieron `DOWN` y el bypass `172.17.25.111-.114` quedó bloqueado por ICMP y TCP/22.

| Campo | Valor |
|---|---|
| Propósito / partición | `experiment` / `train` |
| Estrato | `legitimate-error` |
| Argumentos | `50`, `10` |
| Quietud / warm-up / settle / cooldown | 70 / 60 / 9 / 30 s |
| SHA matriz | `ad22ce5f8b41110b201f0eeacd2b5f13cc9f945c92cf539e9913e87fefdfa824` |
| SHA argumentos | `3e1d6b27aac4e5297c7bddae4dbf13d0c28ef3ae116ffc99e8162b8486aab317` |

## Resultado DNS

PCAP y EVE confirman sesenta transacciones:

| Control | Resultado |
|---|---:|
| Consultas / respuestas | 60 / 60 |
| Respuestas válidas | 50 `NOERROR`, A=`10.30.0.10` |
| Errores controlados | 10 `NXDOMAIN` |
| Span de consultas | 1.260866 s |
| Tasa observada | 47.586341 consultas/s |
| Puertos origen / flow IDs únicos | 60 / 60 |
| Ratio NXDOMAIN | 10/60 = 1/6 = 0.16666667 |

La salida del escenario contiene cincuenta líneas `10.30.0.10` y stderr vacío. Esto es correcto: `dig +short` imprime el registro A de las consultas válidas y no imprime una línea de respuesta para NXDOMAIN. Los diez errores se demuestran con las respuestas conservadas en PCAP y EVE, no contando líneas vacías de stdout.

EVE contiene 120 eventos DNS y diez `stats`. El campo `rcode=NOERROR` de los sesenta eventos `request` no expresa el resultado final de la transacción; las respuestas contienen cincuenta `NOERROR` y diez `NXDOMAIN`. Por ello no existe contradicción entre solicitudes y respuestas.

La benignidad no se infiere de NXDOMAIN por sí solo. Procede de la intención del escenario, sus nombres sintéticos conocidos, el origen autorizado y las respuestas esperadas. Un ratio NXDOMAIN alto también puede aparecer en DGA, enumeración o errores operativos; esta celda demuestra medición, no separabilidad frente a una anomalía.

## Orden y comparación

El generador ejecutó las cincuenta consultas válidas antes de las diez inválidas. La última consulta válida ocurrió 19.024 ms antes de la primera NXDOMAIN. No hubo alternancia ni aleatorización, de modo que la celda conserva un sesgo temporal de orden que deberá considerarse al diseñar variaciones posteriores.

| Perfil R01 | Válidas | NXDOMAIN | Ratio NXDOMAIN | Paquetes |
|---|---:|---:|---:|---:|
| DNS-MIXED-20-2 | 20 | 2 | 2/22 = 0.09090909 | 44 |
| DNS-MIXED-50-10 | 50 | 10 | 10/60 = 0.16666667 | 120 |

La comparación aporta dos niveles legítimos de error, pero son solo dos episodios deterministas. No establece una distribución poblacional ni demuestra por sí misma que el futuro modelo distinga error benigno de DNS anómalo.

## PCAP, EVE y recursos

| Control | Resultado |
|---|---:|
| Evidencia completa | `true` |
| PCAP capturado / recibido / parseado | 120 / 120 / 120 |
| PCAP | 1 archivo / 13,866 bytes |
| Drops `tcpdump` | 0 |
| Delta Suricata | 124 |
| Drops / ifdrops / decoder / overflow | 0 / 0 / 0 / 0 |
| EVE esperado / extraído | 130 / 130 |
| Muestras Sensor / stderr | 54 / vacío |
| Transferencia / límite PCAP | verificada / no alcanzado |

Los 120 paquetes son UDP/IPv4. Las consultas válidas miden 83 bytes y sus respuestas 87; nueve consultas NXDOMAIN miden 81 y una 82, mientras nueve respuestas miden 93 y una 94. La media IPv4 es 85.35 bytes, el máximo 94 y el 0 % cae entre 500 y 1500 bytes. Esto es correcto para DNS pequeño: la cobertura legítima pesada procede de los perfiles HTTP/HTTPS e iperf3, no se fuerza artificialmente en esta celda.

El delta `kernel_packets=124` de Suricata supera en cuatro al PCAP filtrado LAN↔DMZ. Suricata observa la interfaz `ens35` completa; los cuatro paquetes adicionales no se identifican en el bundle y no se les asigna protocolo ni causa. tcpdump recibió y guardó los 120 paquetes del escenario con cero drops.

El Sensor alcanzó CPU puntual máxima de 2.21 %, RSS de 780,308 KiB, memoria disponible mínima de 14,079,576 KiB y carga máxima de 0.39. Son observaciones de esta campaña, no SLA ni umbrales.

## Features

El extractor procesó 120 observaciones de paquete y 70 de aplicación. Estas últimas son sesenta consultas DNS más diez resultados NXDOMAIN contabilizados separadamente; no equivalen a setenta consultas. Produjo una fila elegible:

| Ventana UTC | Paquetes | Attempts | Consultas DNS | Tasa paquetes | Tasa attempts | Ratio NXDOMAIN |
|---|---:|---:|---:|---:|---:|---:|
| `2026-07-27T15:06:00+00:00` | 120 | 60 | 60 | 12/s | 6/s | 0.16666667 |

La misma fila registra `byte_rate_10s=1024.2 B/s`, `mean_ip_len_10s=85.35`, `large_ip_ratio_10s=0`, `unique_dst_ip_ratio_30s=1/60` y `unique_dst_port_ratio_30s=1/60`. SYN, ICMP, HTTP, RST y TLS quedan en cero, coherentes con UDP/DNS. La fila es una ventana de un episodio, no una repetición independiente.

Isolation Forest final todavía no está entrenado. Esta campaña no produce score, no mide falsos positivos y no demuestra detección ni generalización.

## Integridad raíz

```text
manifest.json          a1da9a6e8c92caaa0365df1a8c2ab1d01728c053fda2539336d66ec6aa12229d
capture.pcap0          7befb436346b7581aac3e9a149a8fc1cdbaea59cd51ac09324a0378d322c8109
eve-slice              892f7655c93ec80f4a10251b5ff63e603ab96beade5f3dbdaa2098ea80729da7
campaign SHA256SUMS    5b7471fe86dadef38466f6bdee9a4b1aa16f95bf522955d9cc5177ce86c4c117
multilayer-v1.csv      fd3a732d70ef9ddf183a14017b1df36116fd1887ec62a65330a22cb041821bd8
extraction-report      c298bf6a4a54b295af9d5f655cddb01bb90f88f80f40370945b578a1b448a3c8
feature SHA256SUMS     3f346fa29c075eed43538c874cd86b100cdf23fc3fae4f9da996c81565c7b4ec
ledger                 27af2f54df8f8bf67a542c9e3ca6778b243b1712da68a735a0fb91e0974dc6d3
```

Todos los hashes pasaron y la captura residual quedó inactiva. El ensamblador informó 145 campañas esperadas, 27 aceptadas, 0 inválidas, 0 advertencias, 0 duplicados y 118 faltantes. El dataset completo todavía no puede construirse.

## Decisión

Claude emitió **ACEPTAR CON LIMITACIONES** y destacó correctamente que NXDOMAIN controlado puede etiquetarse benigno en este contexto, pero no es un predictor autónomo de ataque; también señaló el sesgo del orden fijo y la falta de evidencia F3 para demostrar separabilidad. Sus respuestas introdujeron conteos, siguiente perfil, número de filas, span y nombres de escenarios incorrectos; todos quedaron corregidos contra los artefactos y se preservan en la revisión independiente.

**CANARIO DNS-MIXED-50-10 ACEPTADO CON LIMITACIONES.** Aporta un segundo nivel legítimo de NXDOMAIN con captura íntegra y feature exacta. Quedan dos gaps R01: `PING-10` y `PING-100`. El siguiente exacto es `PING-10/R01`, con preflight nuevo.
