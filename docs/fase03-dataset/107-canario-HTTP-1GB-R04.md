# Décimo canario oficial R04 — HTTP-1GB

Fecha: 4 de agosto de 2026. Campaña `F1N-HTTP-1GB-R04`, partición `validation`. Estado: **ACEPTADA CON LIMITACIONES**.

## Objetivo y autorización

El perfil descarga 1 GiB legítimo con límite `20M` para cerrar la progresión HTTP individual, validar tres rotaciones PCAP y ampliar el soporte benigno de paquetes de 500–1500 bytes. El dry-run fijó commit limpio `dc3bd0572e7d52177f836117f160bd0659b6f52b`, matriz SHA `ad22ce5f8b41110b201f0eeacd2b5f13cc9f945c92cf539e9913e87fefdfa824` y argumentos SHA `6666c4e3e11f640a662a83aca3bbdb6688e9dd372b6f6ef1983125b593ecaf77`.

Claude rechazó un primer cierre de preflight porque sus controles quedaron repartidos entre dos bloques temporales. Codex no había abierto captura ni creado artefactos; repitió el preflight completo en un único proceso continuo entre `23:27:07.412` y `23:27:45.828 -05:00`. Pasaron contrato, almacenamiento, NTP 5/5 (máximo absoluto 6.757973 ms), IDs, ledger, lock, SSH 4/4, NIC externas por MAC, bypass ICMP/TCP 22 con sintaxis correcta, rutas, Suricata, servicios, captura, archivo, HTTP, DNS, ICMP y generador. Claude entonces autorizó exactamente una captura. No hubo reintento de campaña ni scoring.

## Transferencia y captura

`curl` obtuvo HTTP 200, exactamente 1,073,741,824 bytes en 51.003964 s, velocidad 21,052,124 B/s y stderr vacío. EVE contiene un `GET /files/1GB.bin` con status 200, un `fileinfo`, tres flows y 23 stats; no hay alerta ni anomalía. `fileinfo.state=TRUNCATED`, `size=102400` y `gaps=false` reflejan el límite de inspección de Suricata, no una descarga incompleta.

| Control | Resultado |
|---|---:|
| PCAP capturado / recibido / parseado | 751,698 / 751,698 / 751,698 |
| PCAP | 3 archivos / 1,136,073,073 bytes |
| Drops tcpdump | 0 |
| Suricata / PCAP | 751,704 / 751,698 |
| drops / ifdrops / decoder / overflow | 0 / 0 / 0 / 0 |
| IPv4 500–1500 | 742,012 / 751,698 = 98.7115 % |
| IPv4 exactamente 1500 | 742,010 |
| longitud media / máxima | 1,481.34 / 1,500 bytes |

Los tres archivos miden 512,000,127; 512,001,452 y 112,071,494 bytes. La copia local coincide con el origen remoto y el stderr del validador sólo registra la apertura informativa de esos archivos. El delta Suricata +6 se conserva sin causa atribuida.

## EVE y fronteras temporales

Dos flows fueron iniciados por sondas de preflight a las `23:23:10` y `23:27:45 -05:00`, antes de abrir la campaña a las `23:31:09`; Suricata los emitió por timeout durante la captura. Se preservan en EVE, pero sus paquetes están fuera del PCAP y no entran al extractor. El tercer flow pertenece al GET real: 9,683 paquetes hacia Servidor más 742,015 hacia Cliente suman exactamente los 751,698 del PCAP.

## Fase y features

La transferencia produjo seis ventanas elegibles autocorrelacionadas de un único episodio:

| Fin UTC | Paquetes | Packet rate | Byte rate | Mean IP | Large ratio | Attempt / SYN / HTTP |
|---|---:|---:|---:|---:|---:|---:|
| `04:32:20` | 86,527 | 8,652.7/s | 12,045,458.7 B/s | 1,392.10404845 | 0.92547991 | 1 / 1 / 1 |
| `04:32:30` | 146,550 | 14,655.0/s | 21,868,542.4 B/s | 1,492.22397816 | 0.99462982 | 1 / 0 / 1 |
| `04:32:40` | 145,501 | 14,550.1/s | 21,725,962.0 B/s | 1,493.18300218 | 0.99529213 | 1 / 0 / 1 |
| `04:32:50` | 146,379 | 14,637.9/s | 21,855,200.4 B/s | 1,493.05572521 | 0.99520423 | 0 / 0 / 1 |
| `04:33:00` | 144,503 | 14,450.3/s | 21,591,484.0 B/s | 1,494.18932479 | 0.99598624 | 0 / 0 / 1 |
| `04:33:10` | 82,238 | 8,223.8/s | 12,265,558.6 B/s | 1,491.47092585 | 0.99411464 | 0 / 0 / 1 |

El SYN sólo permanece en los últimos 10 s de la primera ventana; el intento sale de la historia de 30 s desde la cuarta, mientras el request HTTP permanece en la historia de 60 s. Los seis vectores son distintos entre sí y ninguno coincide exactamente con `train`; la auditoría global no incrementa coincidencias ni cruces.

## Recursos, integridad y auditoría

El Sensor produjo 132 muestras: CPU 0–26.58 %, RSS constante 781,720 KiB, memoria disponible 14,055,140–14,177,128 KiB y load1 0.03–0.62. No hubo drops ni evidencia de saturación; los máximos observados no son umbrales.

Ambos bundles pasaron completos. PCAP SHA `f14b31f4…`, `ff89446d…` y `8002a598…`; manifest `8b76c929…`; EVE `e3ad601b…`; CSV `e8e45c2c…`; ledger `c28f3694…`.

El auditor limpio aceptó 97/145, R04 10/29, 48 faltantes, cero inválidas/advertencias. Permanecen 21 coincidencias y cuatro cruces; esta campaña no incrementa ninguno.

**ACEPTADA CON LIMITACIONES.** Aporta 742,012 paquetes legítimos pesados, seis filas nuevas, tres PCAP íntegros y cero drops; conserva dos flows diferidos fuera de alcance, fileinfo truncado por inspección y delta +6. No se calcularon scores. Siguiente autorizado: sólo preflight de `F1N-HTTPS-10MB-R04`.
