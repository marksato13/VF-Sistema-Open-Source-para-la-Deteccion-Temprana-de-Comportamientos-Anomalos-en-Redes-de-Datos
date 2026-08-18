# Decimotercer canario oficial R04 — HTTPS-500MB

Fecha: 5 de agosto de 2026. Campaña `F1N-HTTPS-500MB-R04`, partición `validation`. Estado: **ACEPTADA CON LIMITACIONES**.

## Objetivo y preflight

Transferencia legítima de 500 MiB por HTTPS limitada a `20M`, para combinar tráfico pesado L3, establecimiento L4 y una sesión TLS L7. El certificado autofirmado y `curl --insecure` sólo representan la PKI del laboratorio.

El preflight pasó en un proceso continuo entre `09:16:56.904` y `09:17:25.631 -05:00` sobre commit limpio `0e7bbb0301e186547da8176d985e8e145dce2729`: contrato, almacenamiento, NTP 5/5 (máximo 0.897893 ms), aislamiento, bypass, SSH, rutas, Suricata, servicios, captura, IDs, archivo, HTTPS, DNS, ICMP y generador. Matriz SHA `ad22ce5f8b41110b201f0eeacd2b5f13cc9f945c92cf539e9913e87fefdfa824`; argumentos SHA `fb20617a24731156f625c1a420f67e2189a940a57121a3b21a699a918b33cc3f`. Claude autorizó una captura. No hubo reintento ni scoring.

## Evidencia

`curl` obtuvo HTTP 200, 524,288,000 bytes en 24.535224 s, velocidad 21,368,787 B/s y stderr vacío.

| Control | Resultado |
|---|---:|
| PCAP capturado / recibido / parseado | 375,137 / 375,137 / 375,137 |
| PCAP | 2 archivos / 555,977,198 bytes |
| Drops tcpdump | 0 |
| Suricata / PCAP | 375,141 / 375,137 |
| drops / ifdrops / decoder / overflow | 0 / 0 / 0 / 0 |
| IPv4 500–1500 | 362,741 / 375,137 = 96.6956 % |
| exactamente 1500 | 362,649 |
| longitud media / máxima | 1,452.06 / 1,500 bytes |

Los PCAP miden 512,000,733 y 43,976,465 bytes; copia remota/local, validación y hashes pasaron. El delta Suricata +4 queda sin causa atribuida.

EVE contiene dieciséis stats, una sesión TLS 1.3 y dos flows iniciados por sondas de preflight a las `09:17:25`, más de cuatro minutos antes de abrir la campaña a las `09:21:30`. Suricata los emitió por timeout durante la captura; están fuera del PCAP y no entran al extractor. No hay HTTP/fileinfo por cifrado ni alertas/anomalías.

## Features, recursos e integridad

| Fin UTC | Paquetes | Packet rate | Byte rate | Mean IP | Heavy ratio | Attempt / SYN / TLS rate |
|---|---:|---:|---:|---:|---:|---:|
| `14:22:40` | 56,373 | 5,637.3/s | 8,008,730.1 B/s | 1,420.66771327 | 0.94525748 | 1 / 1 / 0.01666667 |
| `14:22:50` | 149,861 | 14,986.1/s | 21,824,179.2 B/s | 1,456.29477983 | 0.96986541 | 1 / 0 / 0.01666667 |
| `14:23:00` | 150,053 | 15,005.3/s | 21,915,102.8 B/s | 1,460.49081325 | 0.97279628 | 1 / 0 / 0.01666667 |
| `14:23:10` | 18,850 | 1,885.0/s | 2,724,291.9 B/s | 1,445.24769231 | 0.96222812 | 0 / 0 / 0.01666667 |

Las cuatro filas son ventanas correlacionadas de un episodio; ninguna coincide con R01–R03 ni otro `train`. El Sensor produjo 92 muestras: CPU 0–6.81 %, RSS 781,720 KiB, memoria disponible 14,081,032–14,177,296 KiB y load1 0.04–0.35.

Ambos bundles pasaron. PCAP SHA `5dcd66dc…` y `1f165fd7…`; manifest `e312b506…`; EVE `06f7e988…`; CSV `38dde3b1…`; ledger `3b95e987…`.

El auditor limpio aceptó 100/145, R04 13/29, 45 faltantes, 21 coincidencias, cuatro cruces y cero inválidas/advertencias.

**ACEPTADA CON LIMITACIONES.** Conserva certificado autofirmado, opacidad HTTP, dos flows diferidos, cuatro filas correlacionadas y delta +4. No hubo scoring. Siguiente autorizado: sólo preflight `F1N-HTTPS-1GB-R04`.
