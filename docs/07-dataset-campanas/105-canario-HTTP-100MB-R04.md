# Octavo canario oficial R04 — HTTP-100MB

Fecha: 4 de agosto de 2026. Campaña `F1N-HTTP-100MB-R04`, partición `validation`. Estado: **ACEPTADA CON LIMITACIONES**.

## Objetivo y autorización

El perfil descarga 100 MiB legítimos con límite `10M` para validar una transferencia media y ampliar el soporte de paquetes de 500–1500 bytes. El preflight pasó sobre commit limpio `e9189a1b23a603815a23f3e24f21c641cad97ecc`: almacenamiento, NTP 5/5 (máximo 0.939444 ms), aislamiento, bypass, SSH, Suricata, servicios, rutas, DNS, recurso HTTP, generador, IDs, ledger, lock y captura en `PASS`. Matriz SHA `ad22ce5f8b41110b201f0eeacd2b5f13cc9f945c92cf539e9913e87fefdfa824`; argumentos SHA `635178aab4823454458df3365c4a23f997293939e18208fa584b073482370d5e`.

Claude emitió autorización condicional a esos gates vivos; Codex ya los había ejecutado y confirmado. Se abrió exactamente una captura, sin reintento ni scoring.

## Transferencia y captura

`curl` obtuvo HTTP 200, exactamente 104,857,600 bytes en 9.506541 s, velocidad 11,030,047 B/s y stderr vacío. EVE contiene un `GET /files/100MB.bin` con status 200, un `fileinfo` y once stats; no hay alerta, anomalía ni flow. `fileinfo.state=TRUNCATED`, `size=102400`, refleja el límite de inspección Suricata y no una descarga incompleta.

| Control | Resultado |
|---|---:|
| PCAP capturado / recibido / parseado | 78,509 / 78,509 / 78,509 |
| PCAP | 1 archivo / 111,355,451 bytes |
| Drops tcpdump | 0 |
| Suricata / PCAP | 78,513 / 78,509 |
| drops / ifdrops / decoder / overflow | 0 / 0 / 0 / 0 |
| IPv4 500–1500 | 72,459 / 78,509 = 92.2939 % |
| IPv4 exactamente 1500 | 72,446 |
| longitud media / máxima | 1,388.38 / 1,500 bytes |

El delta Suricata +4 se conserva sin causa atribuida. No hubo rotación: el único PCAP quedó muy por debajo de 512 MB.

## Fase y features

La transferencia cruzó un borde UTC y produjo dos ventanas elegibles:

| Fin UTC | Paquetes | Packet rate | Byte rate | Mean IP | Large ratio | SYN / HTTP |
|---|---:|---:|---:|---:|---:|---:|
| `03:47:30` | 77,544 | 7,754.4/s | 10,757,498.1 B/s | 1,387.27665583 | 0.92218611 | 1 / 1 |
| `03:47:40` | 965 | 96.5/s | 142,517.6 B/s | 1,476.86632124 | 0.98341969 | 0 / 1 |

Ambas conservan un intento y una observación HTTP en sus historias. Sólo la primera contiene el SYN en sus últimos 10 s, por lo que sus tasas SYN/attempt son 0.1 y las de cierre son cero. Las filas son autocorrelacionadas de un episodio. Ninguna coincide exactamente con R01–R03; ambas son `unseen` respecto de `train`.

## Recursos, integridad y auditoría

El Sensor produjo 65 muestras: CPU 0–18.79 %, RSS constante 781,720 KiB, memoria disponible 14,081,344–14,161,012 KiB y load1 0.08–0.32. El pico de CPU no produjo drops ni saturación y se trata como observación, no umbral.

Ambos bundles pasaron completos. PCAP SHA `965047a33c4fd8e506eb73a22553877b310ff03546eb6a508991f31db7b91c50`; manifest `03e03f63…`; EVE `295b8b07…`; CSV `f9425dd6…`; ledger `f00b8ac7…`.

El auditor limpio aceptó 95/145, R04 8/29, 50 faltantes, cero inválidas/advertencias. Permanecen 21 coincidencias y cuatro cruces; esta campaña no incrementa ninguno.

**ACEPTADA CON LIMITACIONES.** Aporta 72,459 paquetes legítimos pesados, dos filas nuevas y evidencia íntegra; conserva fileinfo truncado por inspección y delta +4. No se calcularon scores. Siguiente autorizado: sólo preflight de `F1N-HTTP-500MB-R04`.
