# Sexto canario oficial R04 — PING-100

Fecha: 4 de agosto de 2026. Campaña: `F1N-PING-100-R04`. Partición: `validation`. Estado: **ACEPTADA CON LIMITACIONES**.

## Objetivo y autorización

El perfil genera cien echo request ICMP a intervalo nominal de 0.2 s desde Cliente `10.20.0.20` hacia Servidor `10.30.0.10`, con sus cien replies. Es una ráfaga benigna para ejercitar `icmp_ratio_10s` y `packet_rate_10s`; la regla ICMP del laboratorio es telemetría permitida, no etiqueta de ataque.

El preflight fijó commit limpio `c8185edf37b85da28e26151866ebb5b31f849c6e`, perfil `PING-100`, repetición 4, `validation`, argumentos `100 0.2`, matriz SHA `ad22ce5f8b41110b201f0eeacd2b5f13cc9f945c92cf539e9913e87fefdfa824` y argumentos SHA `412ee9eb50fba97316261a06e934257bc6a9467e24d73f56a2530aa368886fe0`. Almacenamiento, NTP 5/5 y los gates de aislamiento, bypass, SSH, Suricata, servicios, rutas, DNS, eco, generador, IDs, ledger, lock y captura pasaron. El máximo desfase NTP absoluto fue 1.022972 ms.

Una primera consulta a Claude falló en el servidor antes de emitir veredicto y no se tomó como autorización. La segunda devolvió `AUTORIZAR` para exactamente una captura, sin scoring, entrenamiento ni acceso a R05.

## Resultado ICMP

| Control | Resultado |
|---|---:|
| Echo request / reply PCAP | 100 / 100 |
| Secuencias request completas | 1–100, sin huecos/duplicados |
| Secuencias reply completas | 1–100, sin huecos/duplicados |
| Transmitidos / recibidos | 100 / 100 |
| Pérdida | 0 % |
| Duración informada | 20.557 s |
| Span de requests EVE | 20.556687 s |
| RTT mín./prom./máx./mdev | 0.316/0.454/3.071/0.343 ms |
| Stderr | vacío |

EVE contiene cien alertas y todas son SID `1000001`, firma `PPI LAB ICMP TEST`, severidad 3, sobre echo request tipo 8/código 0. No hay firma distinta, flow ni anomalía. Esta telemetría confirma el episodio, pero no es una detección de ataque.

## PCAP, EVE y Sensor

| Control | Resultado |
|---|---:|
| PCAP capturado / recibido / parseado | 200 / 200 / 200 |
| PCAP | 1 archivo / 22,824 bytes |
| Drops tcpdump | 0 |
| EVE esperado / extraído | 111 / 111 |
| Tipos EVE | 100 alert + 11 stats |
| Delta Suricata / PCAP | 204 / 200 |
| Drops / ifdrops / decoder / overflow | 0 / 0 / 0 / 0 |

Los 200 IPv4 miden 84 bytes, todos menores de 500. Suricata incrementó cuatro paquetes más que PCAP, como en las repeticiones ICMP previas; el valor se conserva sin atribuirle causa. La captura causal contiene exactamente los 200 paquetes y no tuvo pérdidas.

El Sensor produjo 69 muestras: CPU 0–1.52 %, RSS constante 781,720 KiB, memoria disponible 14,088,096–14,164,080 KiB y load1 0.30–0.48. Son observaciones de ejecución, no umbrales. Los stderr del escenario y muestreador están vacíos.

## Fase UTC y features

El episodio cruzó dos bordes UTC y produjo tres ventanas elegibles:

| Fin UTC | Paquetes | Pares equivalentes | Packet rate | Byte rate | Attempts 30 s | Attempt rate 10 s |
|---|---:|---:|---:|---:|---:|---:|
| `03:02:10` | 76 | 38 | 7.6/s | 638.4 B/s | 1 | 0.1/s |
| `03:02:20` | 98 | 49 | 9.8/s | 823.2 B/s | 1 | 0.0/s |
| `03:02:30` | 26 | 13 | 2.6/s | 218.4 B/s | 1 | 0.0/s |

Las tres tienen `mean_ip_len_10s=84`, `unique_dst_ip_ratio_30s=1`, `icmp_ratio_10s=1`, ratio pesado y ratios L4/L7 en cero. `flow_attempt_count_30s=1` conserva el primer request del episodio en la historia; sólo la primera ventana lo tiene dentro de sus últimos 10 s, de ahí las tasas 0.1/0/0. Son ventanas autocorrelacionadas de un episodio.

| Repetición | Reparto de paquetes | Filas |
|---|---|---:|
| R01 | 6 / 96 / 96 / 2 | 4 |
| R02 | 48 / 96 / 56 | 3 |
| R03 | 62 / 98 / 40 | 3 |
| R04 | 76 / 98 / 26 | 3 |

La ventana central R04 de 98 paquetes coincide decimal y exactamente en las catorce features con la ventana central R03. Las filas 76 y 26 son nuevas. La coincidencia se conserva como `seen` train↔validation y no se borra, deduplica ni interpreta como fuga operacional: PCAP, timestamps y hashes son independientes. Tampoco se usa para puntuar o recalibrar durante R04.

## Integridad y auditoría

Ambos bundles y la transferencia pasaron completos. El PCAP remoto/local comparte SHA-256 `5a460daf0785396698a77f51aac9c361dbe5e2c8a3faf972e4387ffcdf8bdfa2`:

```text
manifest.json          431467f33c0ecee072dc480c2ab6200d723ef45fd09fe3be20698e0aec608294
eve-slice.jsonl        376e55cd9bb26a2f5f5a18021f226c57aff52d584d2e1aecf1c7aae89dfc52d7
campaign SHA256SUMS    f0ae7999626b1a8050c2f941466588696f404e2c60114b8a166ca96122cb3b20
multilayer-v1.csv      8b5b368ce57e329926a0fb547793ba0ffb6316651a0e5558b367053f2e7d29fa
feature SHA256SUMS     98cf549149f2aa834019ad2a51c0cb67385151d1f9003262652cd86055ac1e61
ledger                 4c0aeee0fc0ac760c98c287f6d4a38b4d03c668fa59ae3d06119bd75b0c00b1f
```

El auditor ejecutado desde Git limpio aceptó 93/145, R04 6/29, 52 faltantes, cero inválidas/advertencias. La fila 98 elevó las coincidencias globales de veinte a 21 y los cruces train↔validation de tres a cuatro; el auditor identifica R03 como primera campaña de esa firma. `ready_to_build=false` significa sólo que F1 sigue incompleta.

**F1N-PING-100-R04 ACEPTADA CON LIMITACIONES.** Valida cien pares ICMP, SID permitido, PCAP íntegro y fase 76/98/26; conserva delta Suricata +4 y un cuarto vector `seen`. No se calcularon scores ni umbrales. Siguiente autorizado: sólo preflight independiente de `F1N-HTTP-10MB-R04`.
