# Octavo canario oficial R02 — HTTP-100MB

Fecha: 27 de julio de 2026. Campaña: `F1N-HTTP-100MB-R02`. Estado: **ACEPTADA CON LIMITACIONES**.

## Objetivo y preflight

Descarga HTTP legítima de 100 MiB desde Servidor `10.30.0.10`, limitada a `10M` bytes/s. Una actualización inicial mencionó por error `5M`; el dry-run de la matriz mostró el contrato exacto `100MB/10M` y fue el único ejecutado.

El preflight confirmó Git limpio y sincronizado en `c078a0925758735342aa9735087af0def6555c2b`, ID libre, volumen oficial válido, SSH y NTP en `PASS`. `/srv/ppi/files/100MB.bin` medía 104,857,600 bytes, SHA-256 `20492a4d0d84f8beb1767f6616229f85d44c2827b64bdbfb260ee12fa1109e0e`; HEAD devolvió HTTP 200 y `Content-Length` correcto. Servicios, captura, generador, NIC externas y bypass pasaron.

| Campo | Valor |
|---|---|
| Propósito / partición | `experiment` / `train` |
| Argumentos | `100MB`, `10M` |
| Quietud / warm-up / settle / cooldown | 70 / 60 / 9 / 30 s |
| SHA matriz | `ad22ce5f8b41110b201f0eeacd2b5f13cc9f945c92cf539e9913e87fefdfa824` |
| SHA argumentos | `635178aab4823454458df3365c4a23f997293939e18208fa584b073482370d5e` |

## Transferencia, PCAP y EVE

`curl` obtuvo HTTP 200, 104,857,600 bytes en 9.525596 s, a 11,007,983 B/s; stderr quedó vacío.

| Control | Resultado |
|---|---:|
| PCAP archivos / bytes | 1 / 111,221,973 |
| Capturados / parseados / drops | 76,324 / 76,324 / 0 |
| Transferencia / límite PCAP | verificada / no alcanzado |
| EVE extraído / esperado | 14 / 14 |
| HTTP 200 / fileinfo / stats / alertas | 1 / 1 / 12 / 0 |
| Delta Suricata / PCAP | 76,328 / 76,324 |
| Drops / ifdrops / decoder / overflow | 0 / 0 / 0 / 0 |

Los cuatro paquetes adicionales del contador Suricata no están identificados. `fileinfo` registra `state=TRUNCATED`, `size=102400`, `stored=false`: limita el seguimiento del cuerpo por Suricata; no trunca la descarga acreditada por curl ni el PCAP.

El Sensor produjo 64 muestras: CPU máxima 19.92 %, RSS 780,308 KiB, memoria disponible mínima 14,110,248 KiB y carga máxima 0.31.

## Cobertura pesada y comparación

| Métrica | R01 | R02 |
|---|---:|---:|
| Paquetes IPv4 | 79,114 | 76,324 |
| 500–1500 bytes | 72,482 (91.6172 %) | 72,493 (94.9806 %) |
| Exactamente 1500 bytes | 72,469 | 72,475 |
| Menores de 500 bytes | 6,632 | 3,831 |
| Longitud media IP | 1,378.58 | 1,427.23 |
| Duración curl | 9.511591 s | 9.525596 s |

Ambas transfieren el mismo volumen en tiempos próximos y contienen unos 72.5 mil paquetes legítimos pesados. El jurado no fijó un requisito de 90 %: la evidencia relevante es ampliar el rango normal 500–1500 bytes sin enseñar que el tamaño grande implica ataque.

La diferencia se concentra en paquetes pequeños. No se atribuye a ACK, retransmisión, cierre u offloading sin análisis específico.

## Features y ventanas

El extractor produjo exactamente dos filas elegibles:

| Ventana | Paquetes | `packet_rate` | `byte_rate` | Media | Heavy ratio |
|---|---:|---:|---:|---:|---:|
| Principal | 76,319 | 7,631.9/s | 10,893,196.9 B/s | 1,427.32437532 | 0.94986832 |
| Cola temporal | 5 | 0.5/s | 26 B/s | 52 | 0 |

La principal registra un SYN, conexión completada, un request HTTP y error ratio cero. La segunda contiene cinco paquetes posteriores al borde y conserva el request en su historia; no se asigna función TCP no observada. Son ventanas autocorrelacionadas de un episodio.

R01 produjo dos filas 49,019/30,095 con ratios 0.86703115/0.996212. La distinta alineación distribuye el episodio de otra forma; ninguna fila R02 coincide exactamente con R01.

## Integridad raíz

```text
manifest.json          9d1d052a6ff23bbd5168e0043223d1a93edc75a762e503ee3e1c89712514f13b
capture.pcap0          23a2667a05fcf54b117dde385c9dec017fab3a6149a40adcf4b94c76b001fc00
eve-slice              043152bba5039419fb971200538ea35d74ac0d887f4267010f6d79efca87d3af
campaign SHA256SUMS    df9f014c6f42d9fd05799d5d7e69024eb600c07a03fe8899fd3ad75a296fa385
multilayer-v1.csv      ac34f1faeeced6136e0c4589c2cbe1816f7f9052ae6e19f286a4271e5ea32363
extraction-report      53837643a62938eace1f8aa1a16aabe296b2fa82b422bde187d0981de41f9054
feature SHA256SUMS     350d3018cca366a2b262d3e0ba5fe75756bcfe3d72715ab160bfd5e3f4525e4c
ledger                 b79e2eb2fa1030c4617f0104f5875a4f132783e34d8cdae3d15142d2dbc2f89b
```

Todos los hashes pasaron. El ensamblador aceptó 37/145 campañas, R02 8/29, 108 faltantes, cero inválidas/advertencias, cuatro coincidencias dentro de `train` y cero entre particiones.

Claude aceptó la integridad y cobertura, pero inventó un umbral >90 %, no reconoció inicialmente las dos filas, especuló causas TCP y propuso gates/tiempos nuevos. Solo se conserva la observación comprobada de `fileinfo` truncado y la autorización del siguiente preflight.

**F1N-HTTP-100MB-R02 ACEPTADA CON LIMITACIONES.** Siguiente: `F1N-HTTP-500MB-R02`.
