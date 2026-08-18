# Vigesimoprimer canario oficial R03 — HTTP-C8

Fecha: 31 de julio de 2026. Campaña: `F1N-HTTP-C8-R03`. Estado: **ACEPTADA CON LIMITACIONES**.

## Objetivo, antecedente y preflight

Ocho descargas HTTP concurrentes de `100MB.bin` desde un Cliente hacia un Servidor, limitadas nominalmente a `2M` bytes/s por flujo. Mide concurrencia y tráfico pesado; no representa ocho usuarios, clientes o destinos.

El primer intento R01 tuvo 476 drops. Después se amplió el búfer, se ejecutó una calibración excluida y los retry R01, R02 y R03 obtuvieron cero drops. Es una secuencia temporal, no demostración causal absoluta.

El dry-run fijó Git limpio y sincronizado en `f6f10b451a04fe19660cc766299796b170f8a9ad`, `experiment/train`, argumentos `8 100MB 2M`, volumen oficial y reserva `PASS`. NTP pasó en VM01 más cuatro VM con máximo absoluto 0.160 ms. SSH 4/4, rutas por Sensor, NIC externas `DOWN`, bypass bloqueado, archivo/hash/HEAD, Suricata, captura inactiva y generador pasaron.

El Sensor tenía 129,398,026,240 bytes libres. El controlador PCAP local/remoto coincidió en `f4a0bf90d1f348f1173678c717f620fdad99c31325b0c5c7d5b5d47843a74b54`, con búfer 65,536 KiB, `rmem_max=67,108,864` y rotación 512 MB × 4.

| Campo | Valor |
|---|---|
| Quietud / warm-up / settle / cooldown | 70 / 60 / 9 / 30 s |
| SHA matriz | `ad22ce5f8b41110b201f0eeacd2b5f13cc9f945c92cf539e9913e87fefdfa824` |
| SHA argumentos | `048896cb26996464f54cd1f8d12cceb7d61e49246645aea858af30019dec7bdb` |

## Transferencias y concurrencia

Las ocho descargas devolvieron 200 y 104,857,600 bytes. Sus tiempos fueron 49.504461–49.534733 s y velocidades 2,116,850–2,118,144 B/s. Los SYN abarcaron 18.043 ms y los ocho flujos se solaparon aproximadamente 49.5 s.

La suma reportada fue 135.541640 Mbit/s; bytes totales sobre el mayor tiempo, 135.478401 Mbit/s. Ambos agregados promedio están bajo el techo de 200 Mbit/s. No se midieron picos instantáneos y `curl --limit-rate` no es shaping exacto.

## Rotación, integridad y tamaños

| Control | Resultado |
|---|---:|
| PCAP archivos / bytes | 2 / 889,006,216 |
| `capture.pcap0` / `capture.pcap1` | 512,000,094 / 377,006,122 bytes |
| Capturados / recibidos / parseados | 602,402 / 602,402 / 602,402 |
| Drops / límite / transferencia | 0 / no alcanzado / verificada |
| EVE esperado / extraído | 38 / 38 |
| `stats` / HTTP / `fileinfo` | 22 / 8 / 8 |
| Delta Suricata / PCAP | 602,408 / 602,402 |
| Drops / ifdrops / decoder / overflow | 0 / 0 / 0 / 0 |

Los dos PCAP son rotación esperada, no evidencia fragmentaria. Los seis paquetes adicionales del contador Suricata no están identificados ni son eventos EVE. Los ocho GET devolvieron 200; `fileinfo TRUNCATED`, `size=102400`, `gaps=false`, `stored=false` representa límite de inspección, no descargas o PCAP truncados.

De 602,402 paquetes IPv4, 580,019 (96.2844 %) están entre 500–1500 bytes, 579,324 son exactamente 1,500 y 22,383 son menores de 500. Media 1,445.77 y máximo 1,500. C8 aporta el mayor volumen concurrente legítimo de R03 hasta este punto.

## Features y repetibilidad

El extractor produjo seis filas elegibles del mismo episodio, con 46,969 / 150,877 / 117,358 / 117,109 / 113,571 / 56,518 paquetes. Solo la primera contiene ocho SYN y `completion=1`. Las filas 2–3 conservan ocho attempts sin SYN nuevos; las filas 4–6 tienen attempts=0 al superar 30 s, mientras HTTP=8 persiste por su horizonte de 60 s. Estas transiciones son semántica causal, no pérdida de flujos.

Los ratios IP/puerto valen 0.125 mientras attempts permanece en el horizonte y cero después. Las seis filas son correlacionadas y no réplicas independientes.

Ninguna fila R03 coincide exactamente con R01/R02. El contador de duplicados dentro de `train` permanece en quince; validation/test aún no existen.

El Sensor produjo 123 muestras: CPU máxima 35.06 %, RSS 781,768 KiB, memoria disponible mínima 14,043,560 KiB y carga máxima 0.50. Sin umbrales definidos no se clasifica presión ni se extrapola escalado por cantidad de flujos.

## Integridad raíz

```text
manifest.json          d8bae874d5963bfa8bb9f20f567687e44f21b39d7cc0c0c17bb3224932b46138
capture.pcap0          11e579ef2eb439b6a7ef3991284e4eb306c26669a1eee0f7bd549d3a63d98da0
capture.pcap1          e253c20f4ea8782e443852945189d2d6c9189775af21340409765821f2a4df5f
eve-slice              c627976c3f9391280186f971a7f1f38003de68c40b6a54b9d71cf8fe6bc73c56
campaign SHA256SUMS    87d173ec0e0d9f0096c61bc4f298788b8e3c15ca208c41cb03bbe08d95e626c5
multilayer-v1.csv      3f287d5d295a95f1cab38c8f3eeec69d430496305836e1865f7c82df8bc0508d
extraction-report      1a0cfb57aa7ab516130e6a04a9b4cbca3429c939221088fd156cb0cf04e6e618
feature SHA256SUMS     80b5e5ebd8c20af985f09cf024c0f2065dabd4a4a3f733202e34ea02355362cf
ledger                 1126903c3320f96044b269ec1ed4f6c0eed1a7f7ad2ebf88bf3d6ce39541a59b
```

El ensamblador aceptó 79/145 campañas: R03 21/29, 66 faltantes, cero inválidas/advertencias, quince duplicados dentro de `train` y cero cruzados. Claude emitió **ACEPTAR CON LIMITACIONES** y autorizó únicamente el preflight independiente de `TCP-REFUSED-5/R03`.

**F1N-HTTP-C8-R03 ACEPTADA CON LIMITACIONES.** Siguiente autorizado: solo preflight independiente de `F1N-TCP-REFUSED-5-R03`; no su ejecución.
