# Decimonoveno canario oficial R03 — HTTP-C2

Fecha: 31 de julio de 2026. Campaña: `F1N-HTTP-C2-R03`. Estado: **ACEPTADA CON LIMITACIONES**.

## Objetivo y preflight

Dos descargas HTTP concurrentes de `100MB.bin` desde un Cliente hacia un Servidor, limitadas nominalmente a `10M` bytes/s por flujo. Mide concurrencia, tasa de bytes y tráfico pesado; no representa dos usuarios, clientes o destinos.

El dry-run fijó Git limpio y sincronizado en `0c778c8b42ffba6d1ff80b411279e9ab27923925`, `experiment/train`, estrato `concurrent`, argumentos `2 100MB 10M`, volumen oficial y reserva `PASS`. NTP pasó en VM01 más cuatro VM con desfase absoluto máximo de 0.079 ms. SSH 4/4, rutas por el Sensor, NIC externas `DOWN`, bypass bloqueado, Suricata y contadores en cero, captura inactiva y generador pasaron.

El archivo midió 104,857,600 bytes, SHA-256 `20492a4d0d84f8beb1767f6616229f85d44c2827b64bdbfb260ee12fa1109e0e`; HEAD devolvió 200 y Content-Length correcto antes de los 70 s de quietud y del checkpoint. Claude autorizó una ejecución con rechazo ante drops, transferencia incompleta, límite PCAP o agregado superior a 200 Mbit/s.

| Campo | Valor |
|---|---|
| Quietud / warm-up / settle / cooldown | 70 / 60 / 9 / 30 s |
| SHA matriz | `ad22ce5f8b41110b201f0eeacd2b5f13cc9f945c92cf539e9913e87fefdfa824` |
| SHA argumentos | `1c65572c683bb319db50f0e8a31d65ac0ee998bd62b7fdc92c459d972436b976` |

## Transferencias y concurrencia

| Flujo | HTTP | Bytes | Tiempo | Velocidad |
|---|---:|---:|---:|---:|
| 1 | 200 | 104,857,600 | 9.506307 s | 11,030,319 B/s |
| 2 | 200 | 104,857,600 | 9.508924 s | 11,027,283 B/s |

Los SYN se separaron 3.343 ms y ambos flujos permanecieron activos aproximadamente 9.51 s. La suma reportada fue 176.460816 Mbit/s; bytes totales sobre el mayor tiempo, 176.436535 Mbit/s. Ambos resultados están bajo el techo de 200 Mbit/s. `curl --limit-rate` no se presenta como shaper exacto.

## Integridad y tamaños

| Control | Resultado |
|---|---:|
| PCAP archivos / bytes | 1 / 222,546,904 |
| Capturados / recibidos / parseados | 154,801 / 154,801 / 154,801 |
| Drops / límite / transferencia | 0 / no alcanzado / verificada |
| EVE esperado / extraído | 16 / 16 |
| `stats` / HTTP / `fileinfo` | 12 / 2 / 2 |
| Delta Suricata / PCAP | 154,805 / 154,801 |
| Drops / ifdrops / decoder / overflow | 0 / 0 / 0 / 0 |

Los cuatro paquetes adicionales del contador Suricata no están identificados y no son eventos EVE adicionales. Los dos GET `/files/100MB.bin` devolvieron 200. Ambos `fileinfo` están `TRUNCATED`, `size=102400`, `gaps=false`, `stored=false`: es límite de inspección de Suricata, no truncamiento de las descargas ni del PCAP.

De 154,801 paquetes IPv4, 144,929 (93.6228 %) están entre 500–1500 bytes, 144,913 son exactamente 1,500 y 9,872 son menores de 500. Media 1,407.63 y máximo 1,500. La campaña aporta tráfico pesado legítimo solicitado por el jurado.

## Features y repetibilidad

| Fila | Paquetes | Rate | Byte rate | Mean IP | Large ratio | SYN / attempts / HTTP |
|---|---:|---:|---:|---:|---:|---:|
| Principal | 154,795 | 15,479.5 p/s | 21,790,253.8 B/s | 1,407.68460222 | 0.93626409 | 2 / 2 / 2 |
| Cierre | 6 | 0.6 p/s | 31.2 B/s | 52 | 0 | 0 / 2 / 2 |

Las dos filas pertenecen al mismo episodio y no son independientes. La segunda conserva attempts/HTTP por sus horizontes de 30/60 s; `completion=0` solo refleja ausencia de SYN en esa ventana, no fallo de descarga. Ambas mantienen ratios IP/puerto de 0.5.

La fila principal R03 difiere de R01/R02. La fila de cierre coincide exactamente con la de R02 y elevó el contador global dentro de `train` de catorce a quince. Los artefactos son independientes; validation/test aún no existen.

El Sensor produjo 68 muestras: CPU máxima 31.76 %, RSS 781,768 KiB, memoria disponible mínima 14,069,576 KiB y carga máxima 0.39. Sin umbrales definidos no se clasifica presión ni capacidad.

## Integridad raíz

```text
manifest.json          2b1db53fbfe135e01e5ac0720aa0aee34d84a30140c6bb90e979675659f58044
capture.pcap0          f72dd5157e9fb6ea76b0216d9436b9ec8629751fbcb01604bb0c964fa05e23ac
eve-slice              3c059130edc4c408163338a5acbef2ad5896fd02535455033521b33013445be6
campaign SHA256SUMS    f39c5a7fa27ef43a59d00eba49626379f294e3a95e7bb7b9975c5c43453ddea6
multilayer-v1.csv      2fd9c2a032f9b8416929c746a1d01823d5666b35ae1d2aa733a2f863ecf0a96c
extraction-report      19416f4e1e684bc27be2ee4f936e34c46f3f50c888461d1ca020d05b6e9ef497
feature SHA256SUMS     13ab3b613c1815853538389065dc9433d2dd2261de164039b7487f526376d46f
ledger                 548cf811b1f7419ec8c9165c8731386883ca1e218ae7cc6129ccb3500e270228
```

El ensamblador aceptó 77/145 campañas: R03 19/29, 68 faltantes, cero inválidas/advertencias, quince duplicados dentro de `train` y cero cruzados. Claude emitió **ACEPTAR CON LIMITACIONES** y autorizó únicamente el preflight independiente de `HTTP-C4/R03`; se corrigieron sus afirmaciones sobre delta y presión.

**F1N-HTTP-C2-R03 ACEPTADA CON LIMITACIONES.** Siguiente autorizado: solo preflight independiente de `F1N-HTTP-C4-R03`; no su ejecución.
