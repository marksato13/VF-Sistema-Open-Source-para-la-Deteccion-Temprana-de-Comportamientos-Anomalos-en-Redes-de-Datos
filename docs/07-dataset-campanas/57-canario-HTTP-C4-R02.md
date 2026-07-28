# Vigésimo canario oficial R02 — HTTP concurrente C4

Fecha: 28 de julio de 2026. Campaña: `F1N-HTTP-C4-R02`. Estado: **ACEPTADA CON LIMITACIONES**.

## Objetivo y preflight

El perfil descarga simultáneamente cuatro copias de `100MB.bin` desde un solo Cliente `10.20.0.20` hacia Servidor `10.30.0.10`. Cada `curl` usa `--limit-rate 5M`; demuestra cuatro conexiones solapadas, no cuatro clientes ni usuarios.

El preflight confirmó Git limpio y sincronizado en `50a71c8a6320335d6dc3363e526cf188e63d9dba`, ID libre, almacenamiento oficial válido y 137,169,334,272 bytes disponibles. El archivo midió 104,857,600 bytes, SHA-256 `20492a4d0d84f8beb1767f6616229f85d44c2827b64bdbfb260ee12fa1109e0e`; HEAD devolvió HTTP 200 y `Content-Length` correcto.

Las cuatro VM respondieron por SSH y NTP pasó con desfase absoluto máximo de 0.149 ms. Servicios, captura, generador y rutas pasaron. Las cuatro NIC externas permanecieron `DOWN`; `172.17.25.111–114` quedó bloqueado por ICMP y TCP/22.

| Campo | Valor |
|---|---|
| Propósito / partición | `experiment` / `train` |
| Escenario / argumentos | `http-concurrent` / `4 100MB 5M` |
| Quietud / warm-up / settle / cooldown | 70 / 60 / 9 / 30 s |
| SHA matriz | `ad22ce5f8b41110b201f0eeacd2b5f13cc9f945c92cf539e9913e87fefdfa824` |
| SHA argumentos | `d8197cefd6d7c50ed78fad328040916bb2b3efbe78c449c62e4c0d6502e93d73` |

## Transferencias y concurrencia

El escenario terminó con código cero y stderr vacío:

| Flujo | HTTP | Bytes | Tiempo | Velocidad |
|---|---:|---:|---:|---:|
| 1 | 200 | 104,857,600 | 19.515294 s | 5,373,098 B/s |
| 2 | 200 | 104,857,600 | 19.509444 s | 5,374,709 B/s |
| 3 | 200 | 104,857,600 | 19.514198 s | 5,373,400 B/s |
| 4 | 200 | 104,857,600 | 19.517107 s | 5,372,599 B/s |

Los puertos origen fueron `56000`, `56008`, `56014` y `56028`. Sus SYN iniciales abarcaron 13.800 ms; sus spans PCAP fueron 19.509928, 19.516914, 19.510444 y 19.514633 s. Los cuatro flujos se solaparon.

La suma de velocidades fue 171.950448 Mbit/s; los 419,430,400 bytes sobre el mayor tiempo equivalen a 171.923185 Mbit/s. Son aproximadamente 2.49 % y 2.47 % sobre el nominal agregado de 167.77216 Mbit/s, con 28.049552 Mbit/s de margen frente a 200 Mbit/s. `curl --limit-rate` no es un shaper exacto.

## Integridad, tamaños y EVE

| Control | Resultado |
|---|---:|
| PCAP archivos / bytes | 1 / 446,479,434 |
| Capturados / parseados / drops | 310,555 / 310,555 / 0 |
| TCP SYN / SYN-ACK / FIN / RST | 4 / 4 / 8 / 0 |
| Transferencia / límite PCAP | verificada / no alcanzado |
| Delta Suricata / PCAP | 310,559 / 310,555 |
| Drops / ifdrops / decoder / overflow | 0 / 0 / 0 / 0 |
| EVE extraído / esperado | 22 / 22 |
| Stats / HTTP / fileinfo | 14 / 4 / 4 |

Los cuatro paquetes adicionales del contador Suricata no están identificados y no se comparan como porcentaje con el PCAP filtrado. Los contadores de drops, no su diferencia, demuestran cero pérdidas.

Los cuatro HTTP son `GET /files/100MB.bin` con estado 200. Los cuatro `fileinfo` quedaron `TRUNCATED` a 102,400 bytes y `gaps=false`; no se afirma inspección completa del cuerpo. A diferencia de R01, R02 no tuvo eventos mDNS en su corte EVE. Esto no demuestra un cambio de alcance: solo se conserva como diferencia observada.

| Longitud IPv4 | Paquetes | Proporción |
|---|---:|---:|
| Menores de 500 bytes | 19,784 | 6.3705 % |
| De 500 a 1500 bytes | 290,771 | **93.6295 %** |
| Mayores de 1500 bytes | 0 | 0 % |
| Exactamente 1500 bytes | 290,650 | 93.5905 % |

La longitud media fue 1,407.68 bytes y la máxima, 1,500. C4 aporta tráfico pesado legítimo concurrente al rango requerido por el jurado.

## Features y ventanas

El extractor produjo tres filas elegibles del mismo episodio:

| Fin UTC | Paquetes | Packet rate | Byte rate | Mean IP | Large ratio | SYN / attempts / HTTP |
|---|---:|---:|---:|---:|---:|---:|
| `20:16:20` | 162,020 | 16,202.0 s⁻¹ | 21,548,282.0 B/s | 1,329.97666955 | 0.88252685 | 4 / 4 / 4 |
| `20:16:30` | 140,281 | 14,028.1 s⁻¹ | 20,941,352.0 B/s | 1,492.81456505 | 0.99518823 | 0 / 4 / 4 |
| `20:16:40` | 8,254 | 825.4 s⁻¹ | 1,226,642.0 B/s | 1,486.11824570 | 0.99079234 | 0 / 4 / 4 |

La tercera fila no es una cola vacía: contiene la carga final y el cierre antes de `20:16:33.919678 UTC`. Los horizontes de 30/60 s conservan attempts y HTTP; `syn_completion_ratio_10s=0` en las dos últimas filas significa que no hubo SYN nuevos en esas ventanas, no conexiones fallidas.

Todas las filas registran `unique_dst_ip_ratio_30s=0.25` y `unique_dst_port_ratio_30s=0.25`: un destino y un puerto sobre cuatro intentos.

## Comparación R01↔R02

Ambas repeticiones completaron cuatro transferencias en aproximadamente 19.52 s, sin drops. R01 produjo 301,517 paquetes y R02, 310,555. R02 suma 9,038 paquetes: 8,267 pequeños, 771 en el rango objetivo y 788 exactamente de 1,500 bytes. Su PCAP creció 1,879,976 bytes.

La proporción pesada pasó de 96.1803 % a 93.6295 %, −2.5508 puntos; la media, de 1,444.54 a 1,407.68 bytes. La causa no fue medida y no se atribuye a TCP, buffers, offloading o virtualización.

La alineación temporal también difiere. R01 repartió 176,930/124,574/13 paquetes y terminó con una cola de teardown; R02 produjo 162,020/140,281/8,254 y mantuvo carga pesada en la tercera ventana. Sus PCAP, EVE, CSV y ledger son independientes; ningún vector exacto R01↔R02 coincide.

El Sensor produjo 85 muestras: CPU máxima 72.24 %, RSS 780,308 KiB, memoria disponible mínima 14,073,708 KiB y carga de un minuto máxima 0.47. R01 alcanzó 43.41 % de CPU. La diferencia de 28.83 puntos se conserva sin causa ni extrapolación; no existe umbral formal de CPU y R02 tuvo cero drops/errores.

## Integridad raíz

```text
manifest.json          b640e671b33b3a5f29e261daeed219d1da38e95385fac6e26763cd5b19581414
capture.pcap0          0524ea6b8adc975aab9305b4d393eefbb01485b7a19abbe8d8aeac60b0ee4465
eve-slice              d78d0d8a1ef5e2f1adf55a01edacba3e6291e75c507ab3839c0e322ff1af4191
campaign SHA256SUMS    f55dc2e6097256a7c9c9c12b7d6f86c02e26695afae36b8a9ddc3f64f6c217c6
multilayer-v1.csv      67d580548bda8f1579561971416b5d56681549ecc9c432e0f60e3a7875604c1f
extraction-report      7fdbf2d92a605f4645b529d49624df969741b52cc4524a69e46c4149d975105c
feature SHA256SUMS     8c5d08a7ae32136861922a32cbfd1c866015e06cf752c1328443d76c79c789c1
ledger                 74e94ac12fa7af019027bbb72d8530132c8a13d32d08f55ed6b1b810dc44f6b0
```

El ensamblador aceptó 49/145 campañas, R02 20/29, 96 faltantes globales y 9 de R02, cero inválidas/advertencias, seis coincidencias dentro de `train` y cero entre particiones. C4 no añadió coincidencias.

Claude aceptó con limitaciones. Se descartaron su proyección lineal de CPU, requisitos y umbrales inventados, aritmética de puertos como velocidades, causas no medidas y cierre prematuro de R02.

**F1N-HTTP-C4-R02 ACEPTADA CON LIMITACIONES.** Siguiente: preflight nuevo de `F1N-HTTP-C8-R02`, ocho flujos de 100 MB a `2M`, PCAP estimado de 920,000,000 bytes.
