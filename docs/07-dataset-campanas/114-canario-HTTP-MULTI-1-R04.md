# Decimoséptimo canario oficial R04 — HTTP-MULTI-1

Fecha: 5 de agosto de 2026. Campaña `F1N-HTTP-MULTI-1-R04`, partición `validation`. Estado: **ACEPTADA CON LIMITACIONES**.

## Objetivo y preflight

Una solicitud HTTP legítima y secuencial a cada VIP DMZ: `10.30.0.10`, `.11` y `.12`. El perfil aporta diversidad de direcciones L3 observable. Las tres VIP son direcciones lógicas de una sola VM Servidor; no representan tres hosts, enlaces ni dominios de fallo independientes.

El preflight completo pasó en un único proceso entre `13:10:39.202` y `13:11:01.349 -05:00` sobre commit limpio `b77796a63913f9effc21641361eebb75f2fb6e3f`. Pasaron contrato, volumen oficial con 124,350,873,600 bytes disponibles, NTP 5/5 (máximo absoluto 0.490 ms), IDs, SSH 4/4, NIC externas `DOWN` por MAC, bypass ICMP/TCP 22, rutas, Suricata, captura libre, servicios, tres VIP, tres probes HTTP 200, DNS, ICMP y generador. Por mejora metodológica, el resultado conserva timestamp por gate en un log runtime con SHA-256 `242776d0b570a6356089df5cc5619acf87060aa374d97a7f1ab04cbdd1fee4fb`.

Los probes ocurrieron antes de los 70 s de quietud y del checkpoint EVE. Claude autorizó exactamente una captura; no hubo reintento ni scoring.

## Evidencia y feature

La salida registra exactamente tres HTTP 200, `request=1`, uno por VIP; stderr quedó vacío.

| Control | Resultado |
|---|---:|
| PCAP capturado / recibido / parseado | 30 / 30 / 30 |
| PCAP | 1 archivo / 3,369 bytes |
| Drops tcpdump | 0 |
| Suricata / PCAP | 30 / 30 |
| drops / ifdrops / decoder / overflow | 0 / 0 / 0 / 0 |
| EVE stats / HTTP / fileinfo | 9 / 3 / 3 |
| Paquetes menores de 500 bytes | 30 / 30 |
| longitud media / máxima | 81.50 / 251 bytes |

EVE no contiene tipos adicionales. Cada VIP tiene un GET `/health` HTTP/1.1 con estado 200 y longitud 36, y un `fileinfo` `CLOSED`, `gaps=false`, `stored=false`, `size=36`. Los tres puertos origen son distintos y ninguna transacción de preflight quedó dentro del segmento.

La única fila elegible contiene 30 paquetes, tres intentos/SYN/HTTP, tasas packet 3.0/s, byte 244.5 B/s, attempt/SYN 0.3/s, finalización 1.0, ratio IP 1.0, ratio puerto 1/3 y error HTTP 0. Coincide exactamente con R01, R02 y R03. Se conserva como ejecución independiente y sexto cruce exacto `seen` train↔validation; demuestra repetibilidad de un generador determinista, no diversidad estadística nueva ni reutilización de evidencia.

El Sensor produjo 53 muestras: CPU 0–1.51 %, RSS 781,720 KiB, memoria disponible 14,070,920–14,160,324 KiB y load1 0.01–0.26. Ambos bundles pasaron. Hashes: manifest `35b3f533…`, PCAP `9614fcfa…`, EVE `dbc804f4…`, CSV `c397db62…`, extraction report `d8b2bfeb…` y ledger `19d94775…`.

El auditor limpio aceptó 104/145, R04 17/29, 41 faltantes, 23 coincidencias, seis cruces y cero inválidas/advertencias.

**ACEPTADA CON LIMITACIONES.** Las VIP son lógicas de una sola VM, el episodio es pequeño y totalmente `seen`, y no aporta tráfico pesado. No se deduplica post hoc. No hubo scoring. Claude autorizó únicamente el preflight independiente `F1N-HTTP-MULTI-5-R04`; no su captura.
