# Noveno canario oficial R04 — HTTP-500MB

Fecha: 4 de agosto de 2026. Campaña `F1N-HTTP-500MB-R04`, partición `validation`. Estado: **ACEPTADA CON LIMITACIONES**.

## Objetivo y autorización

El perfil descarga 500 MiB legítimos con límite `20M` para validar una transferencia pesada, la rotación de PCAP y el soporte benigno de paquetes de 500–1500 bytes. El preflight se ejecutó sobre commit limpio `c3ea76ac8c9e372ce2577cf20b686a9456f59981`: almacenamiento, NTP 5/5 (máximo 0.916144 ms), SSH, Suricata, servicios, rutas, DNS, recurso HTTP, generador, IDs, ledger, lock y captura quedaron en `PASS`. Matriz SHA `ad22ce5f8b41110b201f0eeacd2b5f13cc9f945c92cf539e9913e87fefdfa824`; argumentos SHA `fb20617a24731156f625c1a420f67e2189a940a57121a3b21a699a918b33cc3f`.

El primer bloque de comprobación de bypass contenía `nc ... "$h" 22>/dev/null`: el shell interpretó `22>` como redirección del descriptor 22 y `nc` no recibió puerto. Aunque la negación produjo falsos `PASS`, Codex invalidó íntegramente ese resultado, no abrió campaña ni artefactos y repitió el bloque con `nc ... "$h" 22 >/dev/null`. La repetición correcta confirmó NIC externas desconectadas, ICMP/TCP 22 bloqueados y todos los demás gates. Claude autorizó una única captura después de esta corrección. No hubo reintento de campaña ni scoring.

## Transferencia y captura

`curl` obtuvo HTTP 200, exactamente 524,288,000 bytes en 24.506818 s, velocidad 21,393,556 B/s y stderr vacío. EVE contiene un `GET /files/500MB.bin` con status 200, un `fileinfo` y dieciséis stats; no hay alerta, anomalía ni flow. `fileinfo.state=TRUNCATED`, `size=102400`, refleja el límite de inspección de Suricata y no una descarga incompleta.

| Control | Resultado |
|---|---:|
| PCAP capturado / recibido / parseado | 371,072 / 371,072 / 371,072 |
| PCAP | 2 archivos / 554,952,099 bytes |
| Drops tcpdump | 0 |
| Suricata / PCAP | 371,076 / 371,072 |
| drops / ifdrops / decoder / overflow | 0 / 0 / 0 / 0 |
| IPv4 500–1500 | 362,240 / 371,072 = 97.6199 % |
| IPv4 exactamente 1500 | 362,237 |
| longitud media / máxima | 1,465.54 / 1,500 bytes |

La rotación produjo dos PCAP y preservó el conteo remoto/local. El delta Suricata +4 se conserva sin causa atribuida.

## Fase y features

La transferencia cruzó tres ventanas elegibles:

| Fin UTC | Paquetes | Packet rate | Byte rate | Mean IP | Large ratio | SYN / HTTP |
|---|---:|---:|---:|---:|---:|---:|
| `04:01:20` | 159,164 | 15,916.4/s | 22,767,944.5 B/s | 1,430.47074087 | 0.95197406 | 1 / 1 |
| `04:01:30` | 146,599 | 14,659.9/s | 21,870,534.8 B/s | 1,491.86111774 | 0.99437922 | 0 / 1 |
| `04:01:40` | 65,309 | 6,530.9/s | 9,743,509.8 B/s | 1,491.90920088 | 0.99442650 | 0 / 1 |

Las tres conservan un intento y una observación HTTP en sus historias. Sólo la primera contiene el SYN en los últimos 10 s, por lo que sus tasas SYN/attempt son 0.1 y las restantes son cero. Son filas autocorrelacionadas de un único episodio. Ninguna coincide exactamente con R01–R03; las tres son `unseen` respecto de `train`.

## Recursos, integridad y auditoría

El Sensor produjo 92 muestras: CPU 0–20.41 %, RSS constante 781,720 KiB, memoria disponible 14,067,932–14,171,120 KiB y load1 0.04–0.46. No hubo drops ni evidencia de saturación; los máximos observados no se convierten en umbrales.

Ambos bundles pasaron completos. PCAP SHA `e3366e84…` y `d8c57fc…`; manifest `f860c4c2…`; EVE `27a0ce62…`; CSV `b6f31bcd…`; ledger `4fa6bb8d…`.

El auditor limpio aceptó 96/145, R04 9/29, 49 faltantes, cero inválidas/advertencias. Permanecen 21 coincidencias y cuatro cruces; esta campaña no incrementa ninguno.

**ACEPTADA CON LIMITACIONES.** Aporta 362,240 paquetes legítimos pesados, tres filas nuevas, rotación íntegra y cero drops; conserva fileinfo truncado por inspección y delta +4. No se calcularon scores. Siguiente autorizado: sólo preflight de `F1N-HTTP-1GB-R04`.
