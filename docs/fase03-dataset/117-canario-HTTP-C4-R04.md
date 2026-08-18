# Vigésimo canario oficial R04 — HTTP-C4

Fecha: 6 de agosto de 2026. Campaña `F1N-HTTP-C4-R04`, partición `validation`. Estado: **ACEPTADA CON LIMITACIONES**.

## Objetivo y preflight

Cuatro descargas HTTP concurrentes de `100MB.bin` desde un Cliente hacia un Servidor, a `5M` bytes/s nominales por flujo. Mide concurrencia y tráfico pesado legítimo; cuatro conexiones de un proceso no representan cuatro usuarios.

Un primer preflight entre `11:36:14–11:36:32 -05:00` fue invalidado: `22>/dev/null` hizo que `nc` recibiera “missing port number” y el gate TCP/22 no fuera real. No abrió ID, ledger, captura ni artefactos; su log se conserva aparte con SHA-256 `b9742fe635dd72f04bcfdf2386e9dd58cb70ac8368bad68c171380d52e689d0d`.

Todos los gates se repitieron desde cero en un proceso continuo entre `11:37:17.370` y `11:37:40.212 -05:00`, con `nc ... 22 >/dev/null`, sobre commit limpio `8b3b31ea6346fa3d340915f8b20f3b575351f54b`. Pasaron contrato, almacenamiento (124,127,645,696 bytes), NTP 5/5 (máximo 0.781 ms), SSH, NIC, bypass, rutas, Suricata, captura, servicios, archivo/HEAD, DNS, ICMP y generador. El log válido tiene SHA-256 `667ed945223044d4c1bb600256cf02c8a1e10f79d28f9b5945eeb9725c2658b2`. Claude corrigió sus condiciones sobre `fileinfo`, hashes de cliente y tasa antes de autorizar una captura. No hubo reintento de campaña ni scoring.

## Transferencias y concurrencia

| Flujo | HTTP | Bytes | Tiempo | Velocidad |
|---|---:|---:|---:|---:|
| 1 | 200 | 104,857,600 | 19.505977 s | 5,375,665 B/s |
| 2 | 200 | 104,857,600 | 19.506243 s | 5,375,591 B/s |
| 3 | 200 | 104,857,600 | 19.505164 s | 5,375,889 B/s |
| 4 | 200 | 104,857,600 | 19.510243 s | 5,374,489 B/s |

Los cuatro flujos comenzaron en 21.336 ms y se solaparon más de 19.48 s. La suma reportada fue 172.013072 Mbit/s; los 419,430,400 bytes sobre el mayor tiempo dieron 171.983670 Mbit/s. Son datos descriptivos; `curl --limit-rate` no es un shaper exacto.

## Integridad y features

| Control | Resultado |
|---|---:|
| PCAP capturado / recibido / parseado | 299,428 / 299,428 / 299,428 |
| PCAP | 1 archivo / 444,446,992 bytes |
| Drops / límite / transferencia | 0 / no alcanzado / verificada |
| Suricata / PCAP | 299,433 / 299,428 |
| drops / ifdrops / decoder / overflow | 0 / 0 / 0 / 0 |
| EVE stats / HTTP / fileinfo | 15 / 4 / 4 |
| Paquetes de 500–1500 bytes | 290,018 / 299,428 (96.8573 %) |
| Paquetes de 1,500 bytes | 289,877 |
| longitud media / máxima | 1,454.32 / 1,500 bytes |

El delta Suricata +5 queda sin causa atribuida. EVE no tiene tipos adicionales: cuatro GET `/files/100MB.bin` HTTP 200 y cuatro `fileinfo TRUNCATED`, `size=102400`, `gaps=false`; la truncación corresponde al límite de inspección, no a las transferencias ni al PCAP.

Las tres filas elegibles contienen 118,626, 146,163 y 34,639 paquetes, que suman 299,428. Sus tasas son 11,862.6, 14,616.3 y 3,463.9 pkt/s; ratios pesados 0.93249372, 0.99214576 y 0.99266722. Pertenecen al mismo episodio y no son muestras independientes. Ninguna coincide exactamente con R01–R03 ni con otro vector global.

El Sensor produjo 84 muestras: CPU 0–32.64 %, RSS 781,720–782,504 KiB, memoria disponible 14,074,492–14,170,840 KiB y load1 0–1.03. Ambos bundles pasaron. Hashes: manifest `161bad2e…`, PCAP `ad861131…`, EVE `4231acc9…`, CSV `6b5d7228…` y ledger `f02fd087…`.

El auditor limpio aceptó 107/145, R04 20/29, 38 faltantes, 24 coincidencias, siete cruces y cero inválidas/advertencias.

**ACEPTADA CON LIMITACIONES.** Demuestra cuatro flujos concurrentes, íntegros y pesados de un solo Cliente; no cuatro usuarios. Conserva delta +5 y tres ventanas correlacionadas. No hubo scoring. Claude autorizó únicamente el preflight independiente `F1N-HTTP-C8-R04`; no su captura.
