# Sexto canario oficial R05 — PING-100

Fecha: 7 de agosto de 2026. Campaña `F1N-PING-100-R05`, partición `test`.
Estado: **ACEPTADA CON LIMITACIONES**.

## Objetivo y autorización

El perfil genera cien echo request ICMP a intervalo nominal de 0.2 segundos
desde Cliente `10.20.0.20` hacia Servidor `10.30.0.10`, con cien replies. Es
tráfico benigno burst para dar soporte a `icmp_ratio_10s` y
`packet_rate_10s`; la alerta de laboratorio no representa ataque.

El preflight continuo pasó sus nueve gates entre `11:47:00.276` y
`11:47:32.434 -05:00` sobre el commit limpio
`86afeb464c3aa6009d14ec5b49fe5c8ef91b7776`. Confirmó `experiment/test`,
matriz `ad22ce5f…dfa824`, argumentos `412ee9eb…86fe0`, NTP 5/5 con máximo
absoluto 0.059 ms, 121,457,467,392 bytes disponibles, SSH 4/4, cuatro NIC
externas `DOWN`, aislamiento/rutas, Suricata limpio y servicios/probes.

El dry-run con volumen oficial explícito confirmó ambos storage gates, marker
y mountpoint, argumentos `100 0.2`, estimación de 150,000 bytes y
quietud/warm-up/settle/cooldown `70/60/9/30 s`. Claude autorizó exactamente una
captura y exigió conservar cualquier reparto natural de ventanas, sin piloto,
retry, scoring, carga de modelo ni entrenamiento. Se ejecutó una sola vez.

## Resultado ICMP y PCAP

| Control | Resultado |
|---|---:|
| Echo request / reply PCAP | 100 / 100 |
| ID / secuencias únicas | 12381 / 1–100 |
| Transmitidos / recibidos | 100 / 100 |
| Pérdida | 0 % |
| Duración informada | 20.548 s |
| RTT mín./prom./máx./mdev | 0.308/0.491/5.664/0.546 ms |
| PCAP capturado / recibido / parseado | 200 / 200 / 200 |
| PCAP archivos / bytes | 1 / 22,824 |
| Drops / transferencia / límite | 0 / verificada / no alcanzado |
| Longitud IPv4 media / máxima | 84 / 84 bytes |

El PCAP conserva un request y un reply por cada secuencia. Los requests van de
`11:52:03.321149` a `11:52:23.869491 -05:00`. Los 200 paquetes son IPv4
pequeños y ninguno mide 500–1500 bytes. El perfil no pretende tráfico pesado;
esa observación del jurado se cubre con las celdas HTTP/HTTPS/TCP/UDP.

## EVE y continuidad desde preflight

| Control | Resultado |
|---|---:|
| EVE esperado / extraído | 112 / 112, mismo inode |
| Tipos EVE | 100 `alert` + 11 `stats` + 1 `flow` |
| Alertas del episodio | 100 × SID `1000001`, `allowed` |
| Delta Suricata / PCAP | 204 / 200 |
| drops / ifdrops / decoder / overflow | 0 / 0 / 0 / 0 |

Las cien alertas corresponden únicamente a echo request tipo 8, firma
`PPI LAB ICMP TEST`. Son telemetría permitida para validar el laboratorio, no
una detección de ataque. Suricata incrementó cuatro paquetes más que el PCAP;
la causa no se atribuye. No se observa impacto con drops cero y 200 paquetes
reconciliados, pero esto no equivale a riesgo cero.

El único evento `flow` autónomo es una consulta DNS de control
`10.20.0.20:35515→10.30.0.10:53`, ocurrida a
`11:47:30.804095–.804562` durante el preflight y emitida por timeout a
`11:52:31.501179`. Sus paquetes preceden al inicio PCAP verificado
`11:51:02.602508` y no pertenecen al episodio.

Las cien alertas oficiales comparten `flow_id=1066177454512372`; su
`flow.start=11:47:31.051630` procede del probe ICMP del preflight. Suricata
conservó el mismo flujo por el 5-tuple ICMP sin puertos hasta la ráfaga oficial.
Esto limita la independencia temporal estricta del slice EVE, pero no añade
paquetes al PCAP ni observaciones a las features: el extractor ignora eventos
`alert/flow` y registró cero observaciones de aplicación. La telemetría se
preserva sin limpieza post hoc.

## Fase UTC, features y cruce `seen`

La ráfaga cruzó dos bordes UTC y produjo tres ventanas correlacionadas:

| Fin UTC | Paquetes | Packet rate | Byte rate | Attempts 30 s | Attempt rate 10 s | Ratio IP / ICMP |
|---|---:|---:|---:|---:|---:|---:|
| `16:52:10` | 66 | 6.6/s | 554.4 B/s | 1 | 0.1/s | 1 / 1 |
| `16:52:20` | 96 | 9.6/s | 806.4 B/s | 1 | 0.0/s | 1 / 1 |
| `16:52:30` | 38 | 3.8/s | 319.2 B/s | 1 | 0.0/s | 1 / 1 |

Las tres filas suman 200 observaciones, tienen `mean_ip_len_10s=84`,
`icmp_ratio_10s=1` y ratio de puertos 0. El intento ICMP canónico aparece una
vez en la historia de 30 s; su tasa 10 s sólo es no nula en la primera ventana.

R01 produjo ventanas 6/96/96/2; R02, 48/96/56; R03, 62/98/40; R04,
76/98/26; y R05, 66/96/38. Las ventanas 66 y 38 son nuevas. La central 96
coincide exactamente en sus catorce features con la firma primero observada en
R01 y repetida en R02. Como R01/R02 son `train` y R05 es `test`, el auditor la
clasifica correctamente como un nuevo cruce `train↔test`. Los PCAP, IDs,
tiempos y hashes son independientes: es repetición estructural por fase, no
reutilización de evidencia. Se conserva sin deduplicación post hoc.

## Recursos, integridad y auditoría

El Sensor produjo 68 muestras: CPU 0.00–1.51 %, RSS estable en 782,504 KiB,
memoria disponible 14,098,328–14,164,708 KiB y load1 0.11–0.35. Ambos stderr
están vacíos; son valores descriptivos, no SLA.

```text
preflight             932472e3ee0c369dabe9bd3708ac029a766c28be9c3b458d670cefd3f77c8524
manifest              57e05cdbf459caefdd28581c1af08641a7fa3bc157bd176d17f39c18d8dc96b7
pcap                  4b9a5bc01efbacd0b24f8b5ab5cb008ae621afb3f2d3b1c6a47397777375fe80
eve                   54e53f002f850deffe9f3bae7b09c83749e4b60e47dc7e407250f6f8ed6f731c
campaign SHA256SUMS   61c181aac7b9652c25859a660617ad62c2116f24485abbfe638c5819d6c3de05
features CSV          d99766610fef77d2382976ea284cccd465fcc64b859787682cc87ac573a180ef
extraction report     bac15dc40a0db1a3bffd3035b2227953e01f8e75eac0d58240efd908fb7e00b9
feature SHA256SUMS    eb971a7a3677692bcca776aac72eed6caf308ac986273b2a42fc6de5454d1ade
ledger                38da584e02f4917948da386eccd2440a2ea134fc194d147162bc49aae35f8f67
```

Ambos bundles y la copia PCAP remota/local pasaron. El auditor limpio aceptó
122/145 campañas: R05 6/29, 23 faltantes, cero inválidas y cero advertencias.
La ventana 96 elevó los totales a 33 duplicados y 16 cruces. El resumen R05
contiene seis perfiles, nueve filas, 804 observaciones de paquete y 304 de
aplicación, sin duplicados internos dentro de R05. El gate global permanece
falso sólo porque faltan 23 perfiles.

Claude verificó la evidencia individual y emitió **ACEPTAR CON LIMITACIONES**.
No reejecutó el auditor. Una frase de su dictamen llamó al duplicado
`train↔train`; es incorrecta para la fila actual: manifiesto, ledger y auditor
demuestran `train↔test`. Codex corrigió esa clasificación sin alterar el
veredicto ni los artefactos.

**Decisión:** `F1N-PING-100-R05` queda cerrado con limitaciones por continuidad
del flow ICMP desde preflight, DNS diferido, delta +4 no atribuido, ventanas
autocorrelacionadas y un cruce estructural `train↔test`. Después de publicar,
el siguiente paso independiente es el preflight de `F1N-HTTP-10MB-R05`. No se
realizó scoring parcial.
