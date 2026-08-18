# Vigesimoprimer canario oficial R04 — HTTP-C8

Fecha: 6 de agosto de 2026. Campaña `F1N-HTTP-C8-R04`, partición `validation`. Estado: **ACEPTADA CON LIMITACIONES**.

## Objetivo y preflight

Ocho descargas HTTP concurrentes de `100MB.bin` desde un Cliente hacia un Servidor, a `2M` bytes/s nominales por flujo. Mide concurrencia y tráfico pesado legítimo; ocho conexiones de un proceso no representan ocho usuarios.

El preflight completo pasó en un único proceso entre `13:06:42.886` y `13:07:06.024 -05:00` sobre commit limpio `43aa14bbb9e8a836d00369a7bee1f3122bb28b17`. Pasaron contrato, almacenamiento con 123,682,947,072 bytes, NTP 5/5 (máximo absoluto 0.318 ms), IDs, SSH, NIC externas `DOWN`, bypass TCP/22 correcto, rutas, Suricata, captura, servicios, archivo/HEAD, DNS, ICMP y generador. El log tiene SHA-256 `28ab9965cadadf4963737ff3a3dd10b8e047052f6aa178bd0204f0b99df408a4`. Claude autorizó una captura con `fileinfo` y tasa tratados según las correcciones de C4. No hubo reintento ni scoring.

## Transferencias y concurrencia

Las ocho descargas devolvieron HTTP 200 y exactamente 104,857,600 bytes cada una. Duraron entre 49.504654 y 49.519530 s, con velocidades de 2,117,499–2,118,136 B/s. Los flujos comenzaron dentro de 26.673 ms y compartieron aproximadamente 49.482 s: la concurrencia fue real.

La suma reportada fue 135.539800 Mbit/s; los 838,860,800 bytes sobre el mayor tiempo dieron 135.519994 Mbit/s. Son datos descriptivos; `curl --limit-rate` no es shaping exacto.

## Integridad y features

| Control | Resultado |
|---|---:|
| PCAP capturado / recibido / parseado | 600,491 / 600,491 / 600,491 |
| PCAP | 2 archivos / 888,812,538 bytes |
| Drops / límite / transferencia | 0 / no alcanzado / verificada |
| Suricata / PCAP | 600,499 / 600,491 |
| drops / ifdrops / decoder / overflow | 0 / 0 / 0 / 0 |
| EVE stats / HTTP / fileinfo | 21 / 8 / 8 |
| Paquetes de 500–1500 bytes | 580,006 / 600,491 (96.5886 %) |
| Paquetes de 1,500 bytes | 579,300 |
| longitud media / máxima | 1,450.14 / 1,500 bytes |

El delta Suricata +8 queda sin causa atribuida. EVE no tiene otros tipos: ocho GET `/files/100MB.bin` HTTP 200 y ocho `fileinfo TRUNCATED`, `size=102400`, `gaps=false`; es límite de inspección, no truncamiento de transferencia o PCAP.

Las seis filas elegibles contienen 93,315; 117,081; 126,697; 117,140; 109,217 y 37,041 paquetes, que suman 600,491. Sus ratios pesados están entre 0.85685045 y 0.99093393. Los ocho intentos permanecen en las primeras tres ventanas por el horizonte de 30 s y los HTTP en las seis por el de 60 s; no implica nuevas solicitudes. Todas pertenecen a un episodio y no son independientes. Ninguna coincide exactamente con R01–R03 ni con otro vector global.

El Sensor produjo 123 muestras: CPU 0–62.00 %, RSS 782,504 KiB, memoria disponible 13,966,808–14,159,756 KiB y load1 0–0.63. Ambos bundles pasaron. Hashes: manifest `a97b5827…`, PCAP0 `3485ff99…`, PCAP1 `225fd31d…`, EVE `6a8e3557…`, CSV `84c52054…` y ledger `4c79de56…`.

El auditor limpio aceptó 108/145, R04 21/29, 37 faltantes, 24 coincidencias, siete cruces y cero inválidas/advertencias.

**ACEPTADA CON LIMITACIONES.** Demuestra ocho flujos íntegros, concurrentes y pesados de un solo Cliente; no ocho usuarios. Conserva delta +8, dos PCAP y seis ventanas correlacionadas. No hubo scoring. Claude autorizó únicamente el preflight independiente `F1N-TCP-REFUSED-5-R04`; no su captura.
