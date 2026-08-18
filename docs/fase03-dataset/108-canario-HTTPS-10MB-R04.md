# Undécimo canario oficial R04 — HTTPS-10MB

Fecha: 4 de agosto de 2026. Campaña `F1N-HTTPS-10MB-R04`, partición `validation`. Estado: **ACEPTADA CON LIMITACIONES**.

## Objetivo y autorización

El perfil transfiere 10 MiB legítimos por HTTPS con límite `2M`. Aporta volumen L3, establecimiento L4 y una sesión TLS L7; usa certificado autofirmado y `curl --insecure`, por lo que representa este laboratorio aislado y no una PKI productiva.

Un primer preflight terminó con código 127 porque el comando remoto `curl` quedó entrecomillado como nombre de ejecutable. Codex invalidó íntegramente esa pasada antes de abrir captura, ID, ledger o artefactos y corrigió el quoting mediante argumentos escapados. El preflight completo se repitió en un único proceso entre `23:51:08.714` y `23:51:29.463 -05:00` sobre commit limpio `7af0640fc0d4615aae93edde3d25a533b6554038`.

Pasaron contrato, almacenamiento, NTP 5/5 (máximo absoluto 8.422 ms), IDs, ledger, lock, SSH 4/4, NIC externas por MAC, bypass ICMP/TCP 22, rutas, Suricata, servicios, captura, archivo, HTTPS, DNS, ICMP y generador. El HEAD obtuvo HTTP 200, `Content-Length: 10485760` y `ssl_verify_result=18`, esperado por el certificado autofirmado. Matriz SHA `ad22ce5f8b41110b201f0eeacd2b5f13cc9f945c92cf539e9913e87fefdfa824`; argumentos SHA `aeb9c2b281a4803e43ed76ad2ab7f270d6e6e7c1ba15664a5bd764aa2f90526a`. Claude autorizó exactamente una captura; no hubo reintento de campaña ni scoring.

## Transferencia, PCAP y EVE

`curl` obtuvo HTTP 200, exactamente 10,485,760 bytes en 4.513762 s, velocidad 2,323,064 B/s y stderr vacío.

| Control | Resultado |
|---|---:|
| PCAP capturado / recibido / parseado | 7,942 / 7,942 / 7,942 |
| PCAP | 1 archivo / 11,158,226 bytes |
| Drops tcpdump | 0 |
| Suricata / PCAP | 7,944 / 7,942 |
| drops / ifdrops / decoder / overflow | 0 / 0 / 0 / 0 |
| IPv4 500–1500 | 7,258 / 7,942 = 91.3876 % |
| IPv4 exactamente 1500 | 7,251 |
| longitud media / máxima | 1,374.96 / 1,500 bytes |

El PCAP local coincide con el origen remoto; el stderr del validador sólo registra su apertura informativa. El delta Suricata +2 se conserva sin causa atribuida.

EVE contiene diez stats y una única sesión TLS 1.3 desde `10.20.0.20` hacia `10.30.0.10:443`, con JA3, JA3S, JA4 y ALPN `h2`/`http/1.1`; no contiene flow, alerta, anomalía, HTTP ni fileinfo. La ausencia de HTTP/fileinfo expresa opacidad por cifrado, no ausencia demostrada del request ni descarga incompleta.

## Cobertura y feature multicapa

| Métrica | R01 | R02 | R03 | R04 |
|---|---:|---:|---:|---:|
| Paquetes IPv4 | 7,608 | 8,175 | 8,200 | 7,942 |
| 500–1500 bytes | 7,259 | 7,261 | 7,256 | 7,258 |
| Porcentaje objetivo | 95.4127 % | 88.8196 % | 88.4878 % | 91.3876 % |
| Exactamente 1500 | 7,240 | 7,245 | 7,249 | 7,251 |

Las cuatro repeticiones conservan aproximadamente 7.26 mil paquetes legítimos pesados, sin forzar una tendencia a partir de sus porcentajes distintos.

La única fila elegible contiene 7,942 paquetes, `packet_rate=794.2/s`, `byte_rate=1,091,994.2 B/s`, longitud media 1,374.96121884, ratio pesado 0.91387560, un intento, un SYN, finalización 1.0 y `tls_session_rate_60s=0.01666667`. Las features HTTP permanecen en cero por opacidad. El vector no coincide exactamente con R01–R03 ni con otro `train`; no agrega coincidencia ni cruce global.

## Recursos, integridad y auditoría

El Sensor produjo 57 muestras: CPU 0–2.99 %, RSS constante 781,720 KiB, memoria disponible 14,105,392–14,168,080 KiB y load1 0.18–0.36. No hubo drops ni evidencia de saturación; los máximos no son umbrales.

Ambos bundles pasaron completos. PCAP SHA `084165ef…`; manifest `0f7543a5…`; EVE `a3df71b5…`; CSV `db51c46b…`; ledger `b6543408…`.

El auditor limpio aceptó 98/145, R04 11/29, 47 faltantes, cero inválidas/advertencias. Permanecen 21 coincidencias y cuatro cruces; esta campaña no incrementa ninguno.

**ACEPTADA CON LIMITACIONES.** Aporta 7,258 paquetes legítimos pesados y una fila nueva TLS; conserva certificado autofirmado, opacidad HTTP y delta +2. No se calcularon scores. Siguiente autorizado: sólo preflight de `F1N-HTTPS-100MB-R04`.
