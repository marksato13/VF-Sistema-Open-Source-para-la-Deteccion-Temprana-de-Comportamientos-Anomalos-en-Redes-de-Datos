# Decimoctavo canario oficial R04 — HTTP-MULTI-5

Fecha: 5 de agosto de 2026. Campaña `F1N-HTTP-MULTI-5-R04`, partición `validation`. Estado: **ACEPTADA CON LIMITACIONES**.

## Objetivo y preflight

Cinco solicitudes HTTP legítimas y secuenciales a cada VIP DMZ `10.30.0.10`, `.11` y `.12`: quince solicitudes totales. Las VIP son direcciones lógicas de una sola VM Servidor y no representan tres hosts o dominios de fallo independientes.

El preflight completo pasó en un único proceso entre `13:24:13.372` y `13:24:35.178 -05:00` sobre commit limpio `3478b06eba747f3d5e74a027d3cbd8fbe2e6e485`. Pasaron contrato, volumen oficial con 124,350,676,992 bytes disponibles, NTP 5/5 (máximo absoluto 0.352 ms), IDs, SSH, NIC externas `DOWN`, bypass, rutas, Suricata, captura, servicios, VIP, probes HTTP 200, DNS, ICMP y generador. El log runtime por gate tiene SHA-256 `07ca45d098296c5df9d9e539338983ebefcf2795153ed61c7937cc53f9eb01ca`. Claude autorizó exactamente una captura; no hubo reintento ni scoring.

## Evidencia y feature

La salida contiene exactamente quince HTTP 200, requests `1..5` para cada VIP; stderr quedó vacío.

| Control | Resultado |
|---|---:|
| PCAP capturado / recibido / parseado | 150 / 150 / 150 |
| PCAP | 1 archivo / 16,749 bytes |
| Drops tcpdump | 0 |
| Suricata / PCAP | 152 / 150 |
| drops / ifdrops / decoder / overflow | 0 / 0 / 0 / 0 |
| EVE stats / HTTP / fileinfo | 9 / 15 / 15 |
| Paquetes menores de 500 bytes | 150 / 150 |
| longitud media / máxima | 81.50 / 251 bytes |

El delta Suricata +2 queda sin causa atribuida. EVE no contiene otros tipos: por cada VIP hay cinco GET `/health` HTTP 200 de longitud 36 y cinco `fileinfo` `CLOSED`, `gaps=false`, `size=36`; los quince puertos origen son distintos.

La única fila elegible contiene 150 paquetes, quince intentos/SYN/HTTP, tasas packet 15/s, byte 1,222.5 B/s, attempt/SYN 1.5/s, finalización 1.0, ratio IP 0.2, ratio puerto 1/15 y error HTTP 0. Coincide exactamente con R01, R02 y R03. Se conserva como repetición independiente y séptimo cruce `seen` train↔validation; no aporta diversidad estadística nueva y no se deduplica post hoc.

El Sensor produjo 54 muestras: CPU 0–1.51 %, RSS 781,720 KiB, memoria disponible 14,089,436–14,158,836 KiB y load1 0–0.16. Ambos bundles pasaron. Hashes: manifest `c6dae74b…`, PCAP `860174e4…`, EVE `ed34f0f0…`, CSV `506aad7d…` y ledger `ce1abd27…`.

El auditor limpio aceptó 105/145, R04 18/29, 40 faltantes, 24 coincidencias, siete cruces y cero inválidas/advertencias.

**ACEPTADA CON LIMITACIONES.** Es una firma determinista `seen`, pequeña, sin tráfico pesado y basada en tres VIP de una sola VM; conserva delta +2. No hubo scoring. Claude autorizó únicamente el preflight independiente `F1N-HTTP-C2-R04`; no su captura.
