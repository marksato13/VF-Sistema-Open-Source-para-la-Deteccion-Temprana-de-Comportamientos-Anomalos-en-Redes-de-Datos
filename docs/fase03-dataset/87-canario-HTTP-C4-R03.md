# Vigésimo canario oficial R03 — HTTP-C4

Fecha: 31 de julio de 2026. Campaña: `F1N-HTTP-C4-R03`. Estado: **ACEPTADA CON LIMITACIONES**.

## Objetivo y preflight

Cuatro descargas HTTP concurrentes de `100MB.bin` desde un Cliente hacia un Servidor, limitadas nominalmente a `5M` bytes/s por flujo. Mide concurrencia, tasa de bytes y tráfico pesado; no representa cuatro usuarios, clientes o destinos.

El dry-run fijó Git limpio y sincronizado en `9e39cb20210e50e1911db5a759bfb7ef524c72d8`, `experiment/train`, estrato `concurrent`, argumentos `4 100MB 5M`, volumen oficial y reserva `PASS`. NTP pasó en VM01 más cuatro VM con desfase absoluto máximo de 0.460 ms. SSH 4/4, rutas por el Sensor, NIC externas `DOWN`, bypass bloqueado, Suricata y contadores en cero, captura inactiva y generador pasaron.

El archivo midió 104,857,600 bytes, SHA-256 `20492a4d0d84f8beb1767f6616229f85d44c2827b64bdbfb260ee12fa1109e0e`; HEAD devolvió 200 y Content-Length correcto antes de los 70 s de quietud y del checkpoint. Claude autorizó una ejecución.

| Campo | Valor |
|---|---|
| Quietud / warm-up / settle / cooldown | 70 / 60 / 9 / 30 s |
| SHA matriz | `ad22ce5f8b41110b201f0eeacd2b5f13cc9f945c92cf539e9913e87fefdfa824` |
| SHA argumentos | `d8197cefd6d7c50ed78fad328040916bb2b3efbe78c449c62e4c0d6502e93d73` |

## Transferencias y concurrencia

| Flujo | HTTP | Bytes | Tiempo | Velocidad |
|---|---:|---:|---:|---:|
| 1 | 200 | 104,857,600 | 19.510476 s | 5,374,425 B/s |
| 2 | 200 | 104,857,600 | 19.510451 s | 5,374,432 B/s |
| 3 | 200 | 104,857,600 | 19.542370 s | 5,365,654 B/s |
| 4 | 200 | 104,857,600 | 19.507015 s | 5,375,379 B/s |

Los SYN iniciales abarcaron 22.512 ms y los cuatro flujos permanecieron solapados aproximadamente 19.5 s. La suma reportada fue 171.919120 Mbit/s; bytes totales sobre el mayor tiempo, 171.700935 Mbit/s. Ambos agregados promedio están bajo el techo de 200 Mbit/s. No se instrumentó un pico instantáneo y `curl --limit-rate` no es un shaper exacto.

## Integridad y tamaños

| Control | Resultado |
|---|---:|
| PCAP archivos / bytes | 1 / 445,083,536 |
| Capturados / recibidos / parseados | 307,330 / 307,330 / 307,330 |
| Drops / límite / transferencia | 0 / no alcanzado / verificada |
| EVE esperado / extraído | 23 / 23 |
| `stats` / HTTP / `fileinfo` | 15 / 4 / 4 |
| Delta Suricata / PCAP | 307,334 / 307,330 |
| Drops / ifdrops / decoder / overflow | 0 / 0 / 0 / 0 |

Los cuatro paquetes adicionales del contador Suricata no están identificados y no son eventos EVE. Los cuatro GET `/files/100MB.bin` devolvieron 200. Los `fileinfo` están `TRUNCATED`, `size=102400`, `gaps=false`, `stored=false`: es límite de inspección, no truncamiento de descargas o PCAP.

De 307,330 paquetes IPv4, 290,000 (94.3611 %) están entre 500–1500 bytes, 289,869 son exactamente 1,500 y 17,330 son menores de 500. Media 1,418.23 y máximo 1,500. La campaña amplía la normalidad de tráfico pesado solicitada por el jurado.

## Features y repetibilidad

| Fila | Paquetes | Rate | Byte rate | Mean IP | Large ratio | SYN / attempts / HTTP |
|---|---:|---:|---:|---:|---:|---:|
| 1 | 82,869 | 8,286.9 p/s | 10,194,536.4 B/s | 1,230.19903703 | 0.81366977 | 4 / 4 / 4 |
| 2 | 146,932 | 14,693.2 p/s | 21,861,117.6 B/s | 1,487.83910925 | 0.99171045 | 0 / 4 / 4 |
| 3 | 77,529 | 7,752.9 p/s | 11,530,707.2 B/s | 1,487.27665777 | 0.99134517 | 0 / 4 / 4 |

Las tres filas son ventanas del mismo episodio y no muestras independientes. Las dos últimas conservan attempts/HTTP por sus horizontes; `completion=0` refleja ausencia de SYN nuevos, no fallos. Todas mantienen ratios IP/puerto de 0.25.

Ninguna fila R03 coincide exactamente con R01/R02. El contador de duplicados dentro de `train` permanece en quince; los artefactos son independientes. Validation/test aún no existen.

El Sensor produjo 84 muestras: CPU máxima 43.96 %, RSS 781,768 KiB, memoria disponible mínima 14,035,232 KiB y carga máxima 0.84. Sin umbrales definidos no se clasifica presión ni capacidad.

## Integridad raíz

```text
manifest.json          42be46eb2c2c57893d19f2fbf96963916264ff216c827b0f237cc415eefd3ad5
capture.pcap0          60977e83fd524e762ba12b5defb592ad474a2785c03361330a3d62d6bd3793bd
eve-slice              281a626b9a2aad83dc997746c246d950ee60c0d7d3e0ebecaf4a37a970a1d120
campaign SHA256SUMS    7e614e3fd481c036065125107b8ee46c28a682a84db0de1dee4e1c010ffce66a
multilayer-v1.csv      6f942f3f3435b5d7e4ed00bc420ce42d7faf0f8eaa191bfa685116835e63043b
extraction-report      9ca5da7ef37b75254014887dbdee50f09e64cfa1ac0db3851da290b04ba48962
feature SHA256SUMS     0fe8a6c79898b142a3c810a386ef938a2282c6c8f706b6f24c0fa2d8d1a80494
ledger                 8be483cf44ccc4a3215fc9306c287dd74aa5c11f9d1c9200f418e65639b09637
```

El ensamblador aceptó 78/145 campañas: R03 20/29, 67 faltantes, cero inválidas/advertencias, quince duplicados dentro de `train` y cero cruzados. Claude emitió **ACEPTAR CON LIMITACIONES** y autorizó únicamente el preflight independiente de `HTTP-C8/R03`.

**F1N-HTTP-C4-R03 ACEPTADA CON LIMITACIONES.** Siguiente autorizado: solo preflight independiente de `F1N-HTTP-C8-R03`; no su ejecución.
