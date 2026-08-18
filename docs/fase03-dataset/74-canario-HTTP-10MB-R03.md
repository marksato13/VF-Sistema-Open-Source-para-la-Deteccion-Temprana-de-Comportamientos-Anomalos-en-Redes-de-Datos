# Séptimo canario oficial R03 — HTTP-10MB

Fecha: 29 de julio de 2026. Campaña: `F1N-HTTP-10MB-R03`. Estado: **ACEPTADA CON LIMITACIONES**.

## Objetivo y preflight

La campaña descarga por HTTP un archivo legítimo de 10 MiB desde Servidor `10.30.0.10`, limitada a `2M` bytes/s. Es el primer perfil pesado de R03 y aporta ejemplos benignos de paquetes entre 500 y 1500 bytes.

El preflight confirmó Git limpio y sincronizado en `e8dd54464c791ec58ef3cfb6103b76e222d77a77`, ID/feature/ledger/lock libres, volumen oficial y capacidad en `PASS`, SSH y NTP en las cuatro VM, con desfase absoluto máximo de 0.826886 ms.

NGINX y Suricata estaban activos. `/srv/ppi/files/10MB.bin` medía 10,485,760 bytes y tenía SHA-256 `e5b844cc57f57094ea4585e235f36c78c1cd222262bb89d53c94dcb4d6b3e55d`. El HEAD devolvió HTTP 200 y `Content-Length: 10485760`. Rutas, generador, NIC externas y bloqueo del bypass pasaron.

| Campo | Valor |
|---|---|
| Propósito / partición | `experiment` / `train` |
| Estrato / escenario | `small-transfer` / `http` |
| Argumentos | `10MB`, `2M` |
| Quietud / warm-up / settle / cooldown | 70 / 60 / 9 / 30 s |
| SHA matriz | `ad22ce5f8b41110b201f0eeacd2b5f13cc9f945c92cf539e9913e87fefdfa824` |
| SHA argumentos | `aeb9c2b281a4803e43ed76ad2ab7f270d6e6e7c1ba15664a5bd764aa2f90526a` |

## Transferencia e integridad

`curl` obtuvo HTTP 200 y 10,485,760 bytes en 4.509243 s, a 2,325,392 B/s; stderr quedó vacío.

| Control | Resultado |
|---|---:|
| PCAP capturado / recibido / parseado | 7,823 / 7,823 / 7,823 |
| PCAP | 1 archivo / 11,128,874 bytes |
| Drops tcpdump | 0 |
| Delta Suricata / PCAP | 7,826 / 7,823 |
| Drops / ifdrops / decoder / overflow | 0 / 0 / 0 / 0 |
| EVE esperado / extraído | 13 / 13 |
| HTTP / fileinfo / flow / `stats` / alertas | 1 / 1 / 1 / 10 / 0 |
| Transferencia / límite PCAP | verificada / no alcanzado |

Los tres paquetes adicionales del contador Suricata no están identificados y no existe una tolerancia porcentual que les asigne causa.

El evento HTTP registra estado 200. `fileinfo` conserva `state=TRUNCATED` y 102,400 bytes inspeccionados; esa longitud parcial no demuestra el tamaño transferido. La integridad de descarga se acredita mediante el archivo versionado, el resultado de `curl` y el PCAP completo.

El Sensor produjo 57 muestras: CPU máxima 3.02 %, RSS máximo 781,816 KiB, memoria disponible mínima 14,091,892 KiB y carga máxima 0.16. Son observaciones.

## Cobertura del rango solicitado por el jurado

| Métrica | R01 | R02 | R03 |
|---|---:|---:|---:|
| Paquetes IPv4 | 7,912 | 9,762 | 7,823 |
| 500–1500 bytes | 7,248 | 7,243 | 7,248 |
| Porcentaje 500–1500 | 91.6077 % | 74.1959 % | 92.6499 % |
| Exactamente 1500 bytes | 7,244 | 7,242 | 7,237 |
| Menores de 500 bytes | 664 | 2,519 | 575 |
| Longitud media | 1,378.26 | 1,126.33 | 1,392.58 |
| Duración `curl` | 4.504656 s | 4.513970 s | 4.509243 s |

Las tres campañas transfirieron el mismo volumen legítimo y contienen miles de paquetes en el rango objetivo. La mezcla con paquetes pequeños varía de forma sustancial, especialmente en R02; la evidencia no atribuye esa diferencia a ACK, offloading, retransmisión o cierre.

Esto responde directamente a la observación del jurado: tamaños cercanos a 1500 bytes aparecen de forma normal en descargas legítimas y no deben interpretarse como ataque por sí solos.

## Features y comparación

R03 produjo una fila elegible:

| Feature | Valor |
|---|---:|
| `packet_rate_10s` | 782.3/s |
| `byte_rate_10s` | 1,089,416 B/s |
| `mean_ip_len_10s` | 1,392.58085134 B |
| `large_ip_ratio_10s` | 0.92649879 |
| Attempts / SYN / HTTP requests | 1 / 1 / 1 |
| Attempt rate / SYN rate | 0.1/s / 0.1/s |
| `syn_completion_ratio_10s` | 1.0 |
| Ratios destino IP / puerto | 1.0 / 1.0 |
| `http_error_ratio_60s` | 0.0 |
| Resto de las 14 features | 0.0 |

R01 produjo una fila; R02 produjo una principal de 9,758 paquetes y otra de cola de cuatro; R03 produjo una. La duración menor de diez segundos no garantiza una sola fila porque el resultado depende de la posición frente al borde UTC. Ningún vector R03 coincide exactamente con R01/R02.

## Integridad raíz

```text
manifest.json          68118fa6ea9dbc8720eda453baa61ce9937a23b4dc2e3ff63a1a498056a60490
capture.pcap0          b602f7bd5161283a48446792ed4e52f0db5bb80cbd11f8782aa1d323dc59f400
eve-slice              641c641af187349315f2ff4af664bd5fcf121bb9770f92349774fdbbe0ebf7e8
campaign SHA256SUMS    d95e445c19b968af5ff1165457c66ba0c39baad376e750d5fe9d12f4718b2927
multilayer-v1.csv      3ced382426aaff0fedd9b51e434e828eeb528fd053d5109b011da45c71cfa446
extraction-report      d384696ead4283390aa23ba85a9a15bd248d4164197b748c65f6722c9680a68b
feature SHA256SUMS     fed1cc9e3fab2ddfac3bc94c57de2bb14691cab1b135d125f5e98c5f57fd0b8a
ledger                 b3d6189841c3334a6774874bb52f156a43db94e6fef31b69a0273133d2468c1a
```

Todos los hashes pasaron. El ensamblador aceptó 65/145 campañas: R03 7/29, 80 faltantes, cero inválidas/advertencias, once coincidencias dentro de `train` —sin aumento— y cero cruces observados.

Claude aceptó con limitaciones. Se corrigieron una coincidencia R01↔R03 inexistente, causalidad TCP, paquetes frente a eventos, una explicación inválida de filas, tolerancias/umbrales inventados, contadores adelantados y bloqueo improcedente de perfiles posteriores.

**F1N-HTTP-10MB-R03 ACEPTADA CON LIMITACIONES.** Siguiente autorizado: preflight independiente de `F1N-HTTP-100MB-R03`.
