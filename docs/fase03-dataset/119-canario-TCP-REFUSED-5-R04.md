# Vigesimosegundo canario oficial R04 — TCP-REFUSED-5

Fecha: 6 de agosto de 2026. Campaña `F1N-TCP-REFUSED-5-R04`, partición `validation`. Estado: **ACEPTADA CON LIMITACIONES**.

## Objetivo y preflight

Cinco intentos TCP legítimos desde Cliente `10.20.0.20` hacia un servicio ausente en `10.30.0.10:65000`. Aporta normalidad L4 de rechazo activo; no es un escaneo, no usa Kali y no implica que cualquier RST sea benigno.

El preflight pasó en un proceso continuo entre `13:26:24.194` y `13:26:45.472 -05:00` sobre commit limpio `6fda931ff8ec4f6f52609584d2f66f91e2d537cd`. Pasaron contrato, almacenamiento con 122,793,811,968 bytes, NTP 5/5 (máximo 0.724 ms), IDs, SSH, NIC externas `DOWN`, bypass, rutas, Suricata, captura y servicios. `ss` confirmó ausencia de listener en 65000; Cliente obtuvo rc 1, `Connection refused` en 11.1 ms, no timeout. DNS, ICMP y generador pasaron. Log SHA-256 `e00c239e70490e8157a3de32f0b57d65b44db1b56f0dc82f2b785ccacefee7ee`. Claude autorizó una captura. No hubo reintento ni scoring.

## Resultado TCP e integridad

El generador informó cinco intentos y cinco rechazos esperados, con stderr vacío. PCAP contiene exactamente cinco SYN hacia 65000 y cinco RST/ACK mediante cinco puertos origen; no contiene SYN/ACK ni FIN.

| Par | intervalo desde SYN anterior | latencia SYN→RST/ACK |
|---:|---:|---:|
| 1 | — | 2.611 ms |
| 2 | 0.611634 s | 0.291 ms |
| 3 | 0.611391 s | 0.221 ms |
| 4 | 0.611011 s | 0.243 ms |
| 5 | 0.614078 s | 1.895 ms |

El episodio duró 2.450009 s. Las latencias demuestran rechazo activo, aunque dos pares tardaron algunos milisegundos más que R03.

| Control | Resultado |
|---|---:|
| PCAP capturado / recibido / parseado | 10 / 10 / 10 |
| PCAP | 1 archivo / 824 bytes |
| Drops / límite / transferencia | 0 / no alcanzado / verificada |
| Suricata / PCAP | 14 / 10 |
| drops / ifdrops / decoder / overflow | 0 / 0 / 0 / 0 |
| EVE | 10 stats; sin L7 ni alertas |
| longitud media / máxima | 50 / 60 bytes |

El delta Suricata +4 queda sin causa atribuida. EVE y PCAP pasan sus propios checkpoints; no se equiparan eventos y paquetes.

La única fila contiene diez paquetes, cinco intentos/SYN, tasas packet 1/s y attempt/SYN 0.5/s, finalización 0, ratio RST 0.5 y ratios IP/puerto destino 0.2. Coincide exactamente con R03, no con R01/R02. Se conserva como ejecución independiente y octavo cruce `seen` train↔validation; no aporta diversidad estadística nueva.

El Sensor produjo 55 muestras: CPU 0–1.52 %, RSS 782,504 KiB, memoria disponible 14,064,492–14,159,588 KiB y load1 0.01–0.24. Ambos bundles pasaron. Hashes: manifest `49535601…`, PCAP `424d76d8…`, EVE `2df8144f…`, CSV `301b30e6…`, extraction report `ea6a10a7…` y ledger `15cb3b0d…`.

El auditor limpio aceptó 109/145, R04 22/29, 36 faltantes, 25 coincidencias, ocho cruces y cero inválidas/advertencias.

**ACEPTADA CON LIMITACIONES.** Es una firma L4 legítima `seen`, pequeña y específica a rechazo activo de un puerto; no generaliza a todo RST. Conserva delta +4. No hubo scoring. Claude autorizó únicamente el preflight independiente `F1N-TCP-50M-R04`; no su captura.
