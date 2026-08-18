# Duodécimo canario oficial R04 — HTTPS-100MB

Fecha: 5 de agosto de 2026. Campaña `F1N-HTTPS-100MB-R04`, partición `validation`. Estado: **ACEPTADA CON LIMITACIONES**.

## Objetivo y preflight

Transferencia legítima de 100 MiB por HTTPS limitada a `10M`, para combinar volumen L3, establecimiento L4 y una sesión TLS L7. El certificado es autofirmado y `curl --insecure` representa sólo la PKI del laboratorio.

El preflight pasó en un proceso continuo entre `00:03:59.865` y `00:04:22.359 -05:00` sobre commit limpio `d3cf74ed40d4c38a86196b951db020df6c98f0fc`: contrato, almacenamiento, NTP 5/5 (máximo 8.422 ms), aislamiento, bypass, SSH, rutas, Suricata, servicios, captura, IDs, archivo, HTTPS, DNS, ICMP y generador. Matriz SHA `ad22ce5f8b41110b201f0eeacd2b5f13cc9f945c92cf539e9913e87fefdfa824`; argumentos SHA `635178aab4823454458df3365c4a23f997293939e18208fa584b073482370d5e`. Claude autorizó una captura. No hubo reintento ni scoring.

## Evidencia

`curl` obtuvo HTTP 200, 104,857,600 bytes en 9.526879 s, velocidad 11,006,500 B/s y stderr vacío.

| Control | Resultado |
|---|---:|
| PCAP capturado / recibido / parseado | 76,726 / 76,726 / 76,726 |
| PCAP | 1 archivo / 111,350,517 bytes |
| Drops tcpdump | 0 |
| Suricata / PCAP | 76,730 / 76,726 |
| drops / ifdrops / decoder / overflow | 0 / 0 / 0 / 0 |
| IPv4 500–1500 | 72,561 / 76,726 = 94.5716 % |
| exactamente 1500 | 72,536 |
| longitud media / máxima | 1,421.27 / 1,500 bytes |

El delta Suricata +4 queda sin causa atribuida. EVE contiene once stats y una sesión TLS 1.3 con JA3, JA3S, JA4 y ALPN; no hay flow, alerta, anomalía, HTTP ni fileinfo. Los ceros HTTP expresan opacidad por cifrado, no ausencia del GET.

## Features, recursos e integridad

La transferencia produjo dos ventanas correlacionadas:

| Fin UTC | Paquetes | Packet rate | Byte rate | Mean IP | Heavy ratio | Attempt / SYN / TLS rate |
|---|---:|---:|---:|---:|---:|---:|
| `05:07:30` | 58,188 | 5,818.8/s | 8,159,757.3 B/s | 1,402.30929058 | 0.93259779 | 1 / 1 / 0.01666667 |
| `05:07:40` | 18,538 | 1,853.8/s | 2,745,114.0 B/s | 1,480.80375445 | 0.98689179 | 1 / 0 / 0.01666667 |

Ninguna fila coincide con R01–R03 ni con otro `train`. El Sensor produjo 64 muestras: CPU 0–6.65 %, RSS 781,720 KiB, memoria disponible 14,081,164–14,167,712 KiB y load1 0.13–0.27. Ambos bundles pasaron; PCAP SHA `35fa1d43…`, manifest `98d31570…`, EVE `ac835a2d…`, CSV `c8019336…` y ledger `cf5354c0…`.

El auditor limpio aceptó 99/145, R04 12/29, 46 faltantes, 21 coincidencias, cuatro cruces y cero inválidas/advertencias.

**ACEPTADA CON LIMITACIONES.** Conserva certificado autofirmado, opacidad HTTP, dos filas correlacionadas y delta +4. No hubo scoring. Siguiente autorizado: sólo preflight `F1N-HTTPS-500MB-R04`.
