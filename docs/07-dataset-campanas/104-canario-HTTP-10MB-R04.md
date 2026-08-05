# Séptimo canario oficial R04 — HTTP-10MB

Fecha: 4 de agosto de 2026. Campaña `F1N-HTTP-10MB-R04`, partición `validation`. Estado: **ACEPTADA CON LIMITACIONES**.

## Autorización y resultado

El perfil descarga 10 MiB legítimos a límite `2M` para validar tráfico pesado sin equipararlo a ataque. El preflight pasó en commit limpio `db80f8bf5e8b1d86845b4119430e6a385fd1c7d1`, con NTP máximo 1.7 ms, almacenamiento, aislamiento, servicios, rutas, DNS, recurso HTTP, generador, IDs y captura en `PASS`. Matriz SHA `ad22ce5f8b41110b201f0eeacd2b5f13cc9f945c92cf539e9913e87fefdfa824`; argumentos SHA `aeb9c2b281a4803e43ed76ad2ab7f270d6e6e7c1ba15664a5bd764aa2f90526a`. Claude autorizó una ejecución sin scoring.

`curl` obtuvo HTTP 200, exactamente 10,485,760 bytes en 4.504886 s, velocidad 2,327,641 B/s y stderr vacío. EVE contiene un HTTP `GET /files/10MB.bin` con status 200, un `fileinfo` y diez stats; no hay alertas, anomalías ni flows. `fileinfo.state=TRUNCATED` y `size=102400` describen el límite de inspección de archivo de Suricata, no la transferencia: bytes curl y PCAP demuestran que la descarga terminó.

| Control | Resultado |
|---|---:|
| PCAP capturado / recibido / parseado | 7,829 / 7,829 / 7,829 |
| PCAP | 1 archivo / 11,129,596 bytes |
| Drops tcpdump | 0 |
| Suricata / PCAP | 7,831 / 7,829 |
| drops / ifdrops / decoder / overflow | 0 / 0 / 0 / 0 |
| IPv4 500–1500 | 7,245 / 7,829 = 92.5406 % |
| IPv4 exactamente 1500 | 7,236 |
| longitud media / máxima | 1,391.58 / 1,500 bytes |

El delta Suricata +2 queda sin causa atribuida. El PCAP causal está íntegro.

## Feature, recursos e integridad

El extractor produjo una fila elegible: `packet_count_10s=7829`, `packet_rate_10s=782.9`, `byte_rate_10s=1089470.2`, `mean_ip_len_10s=1391.58283306`, `large_ip_ratio_10s=0.92540554`, un intento/SYN/HTTP, `syn_completion_ratio_10s=1` y `http_error_ratio_60s=0`. No coincide exactamente con R01, R02 ni R03; es una observación nueva de `validation`.

El Sensor produjo 56 muestras: CPU 0–2.99 %, RSS constante 781,720 KiB, memoria disponible 14,085,992–14,166,964 KiB y load1 0.15–0.37. Ambos bundles pasaron; PCAP remoto/local SHA `c215d3d91b51707209cc8e8c04f2a6dc03961fa4995776548cf064282a0da3ba`. Manifest `2ff44eaf…`, EVE `c3f5f5ff…`, CSV `b9a7ea08…`, ledger `348dd80b…`.

El auditor limpio aceptó 94/145, R04 7/29, 51 faltantes, cero inválidas/advertencias. Permanecen 21 coincidencias y cuatro cruces; esta campaña no incrementa ninguno.

**ACEPTADA CON LIMITACIONES.** Aporta 7,245 paquetes legítimos pesados, fila nueva e integridad completa; conserva fileinfo truncado por inspección y delta +2. Sin scoring. Siguiente autorizado: sólo preflight de `F1N-HTTP-100MB-R04`.
