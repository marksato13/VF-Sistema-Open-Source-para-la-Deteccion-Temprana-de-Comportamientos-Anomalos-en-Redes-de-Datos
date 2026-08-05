# Decimocuarto canario oficial R04 — HTTPS-1GB

Fecha: 5 de agosto de 2026. Campaña `F1N-HTTPS-1GB-R04`, partición `validation`. Estado: **ACEPTADA CON LIMITACIONES**.

## Preflight y autorización

El perfil transfiere 1 GiB legítimo por HTTPS limitado a `20M`, cerrando los tamaños HTTPS individuales. El certificado autofirmado y `curl --insecure` sólo representan la PKI del laboratorio.

Un primer preflight fue invalidado: `22>/dev/null` volvió a convertir 22 en descriptor y `nc` emitió cuatro `missing port number`, produciendo falsos controles TCP/22. No se creó captura, ledger ni artefacto. Codex repitió todo el preflight con `nc ... "$h" 22 >/dev/null` en un proceso continuo entre `09:34:07.017` y `09:34:44.087 -05:00` sobre commit limpio `22d8b92fbaa7fb640a7bd3aa24850f55fb395b23`.

Pasaron contrato, almacenamiento, NTP 5/5 (máximo 0.684689 ms), aislamiento, bypass, SSH, rutas, Suricata, servicios, captura, IDs, archivo, HTTPS, DNS, ICMP y generador. Claude autorizó una captura y aclaró que el HTTP 200 del preflight era HEAD, no la descarga. No hubo reintento de campaña ni scoring.

## Evidencia

`curl` obtuvo HTTP 200, 1,073,741,824 bytes en 51.021944 s, velocidad 21,044,706 B/s y stderr vacío.

| Control | Resultado |
|---|---:|
| PCAP capturado / recibido / parseado | 759,557 / 759,557 / 759,557 |
| PCAP | 3 archivos / 1,138,221,381 bytes |
| Drops tcpdump | 0 |
| Suricata / PCAP | 759,569 / 759,557 |
| drops / ifdrops / decoder / overflow | 0 / 0 / 0 / 0 |
| IPv4 500–1500 | 743,106 / 759,557 = 97.8341 % |
| exactamente 1500 | 742,930 |
| longitud media / máxima | 1,468.53 / 1,500 bytes |

Los PCAP miden 512,000,583; 512,001,272 y 114,219,526 bytes; validación, copia y hashes pasaron. El delta Suricata +12 queda sin causa atribuida.

EVE contiene 22 stats, una sesión TLS 1.3 y cuatro flows. Tres flows pertenecen a los preflights de `09:33:11` y `09:34:43`, antes de abrir campaña a las `09:37:19`; se emitieron por timeout, están fuera del PCAP y no entran a features. El flow real suma 16,308 + 743,249 = 759,557 paquetes, exactamente el PCAP. No hay HTTP/fileinfo por cifrado ni alerta/anomalía.

## Features, recursos e integridad

Las seis ventanas correlacionadas contienen 78,785; 147,710; 148,056; 147,842; 147,489 y 89,675 paquetes; suman 759,557. Sus ratios pesados son 0.94568763, 0.98255365, 0.97987248, 0.98204840, 0.98384286 y 0.98240312. Todas conservan `tls_session_rate_60s=0.01666667`; sólo la primera contiene SYN en 10 s y el intento sale de historia 30 s desde la cuarta. Ninguna coincide con R01–R03 ni otro `train`.

El Sensor produjo 132 muestras: CPU 0–6.75 %, RSS 781,720 KiB, memoria disponible 14,016,804–14,162,820 KiB y load1 0.11–0.62. Ambos bundles pasaron: PCAP SHA `c0bd0f83…`, `e9d253ed…`, `8796b182…`; manifest `1f0b4883…`; EVE `851ed89c…`; CSV `8d2442b0…`; ledger `c2cb2760…`.

El auditor limpio aceptó 101/145, R04 14/29, 44 faltantes, 21 coincidencias, cuatro cruces y cero inválidas/advertencias.

**ACEPTADA CON LIMITACIONES.** Conserva certificado autofirmado, opacidad HTTP, tres flows diferidos, seis filas correlacionadas y delta +12. No hubo scoring. Siguiente autorizado: sólo preflight `F1N-HTTP-404-5-R04`.
