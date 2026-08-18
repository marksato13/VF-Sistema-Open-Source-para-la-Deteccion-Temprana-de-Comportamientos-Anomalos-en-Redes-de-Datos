# Quinto canario oficial R05 — PING-10

Fecha: 7 de agosto de 2026. Campaña `F1N-PING-10-R05`, partición `test`.
Estado: **ACEPTADA CON LIMITACIONES**.

## Objetivo y autorización

El perfil genera diez echo request ICMP a intervalo nominal de un segundo desde
Cliente `10.20.0.20` hacia Servidor `10.30.0.10`, con sus diez replies. Es
tráfico benigno ligero que da soporte a `icmp_ratio_10s`; la alerta del
laboratorio no representa un ataque.

El preflight continuo pasó los nueve gates entre `11:24:17.417` y
`11:24:49.542 -05:00` sobre el commit limpio
`02a0f101b8d65e17f1f1b7e7089abfb2bf41d7e8`. Confirmó `experiment/test`,
matriz `ad22ce5f…dfa824`, argumentos `4027af88…db67`, NTP 5/5 con máximo
absoluto 0.078437 ms, 121,457,676,288 bytes disponibles, SSH 4/4, cuatro NIC
externas `DOWN`, aislamiento/rutas, Suricata limpio y servicios/probes.

El dry-run con `PPI_ARTIFACTS_ROOT=/srv/ppi-evidence/artifacts` confirmó ambos
storage gates, marker y mountpoint, argumentos `10 1`, estimación de 100,000
bytes y quietud/warm-up/settle/cooldown `70/60/9/30 s`. Claude aceptó de
antemano una o dos ventanas según la fase UTC y autorizó exactamente una
captura, sin retry oportunista, piloto, scoring, carga de modelo ni
entrenamiento. Se ejecutó una sola vez.

## Resultado ICMP y PCAP

| Control | Resultado |
|---|---:|
| Echo request / reply PCAP | 10 / 10 |
| ID / secuencias | 12379 / 1–10 |
| Transmitidos / recibidos | 10 / 10 |
| Pérdida | 0 % |
| Duración informada | 9.208 s |
| RTT mín./prom./máx./mdev | 0.394/0.489/0.739/0.108 ms |
| PCAP capturado / recibido / parseado | 20 / 20 / 20 |
| PCAP archivos / bytes | 1 / 2,304 |
| Drops / transferencia / límite | 0 / verificada / no alcanzado |
| Longitud IPv4 media / máxima | 84 / 84 bytes |

El PCAP conserva exactamente un request y un reply por secuencia, entre
`11:29:32.373451` y `11:29:41.581678 -05:00`. Los veinte paquetes son IPv4
pequeños; no hay ninguno de 500–1500 bytes. Esto es correcto para el perfil
ICMP ligero: la observación del jurado sobre tráfico benigno pesado se cubre
con las celdas HTTP, HTTPS, TCP y UDP.

## EVE, telemetría y alcance causal

| Control | Resultado |
|---|---:|
| EVE esperado / extraído | 22 / 22, mismo inode |
| Tipos EVE | 10 `alert` + 10 `stats` + 2 `flow` |
| Alertas del episodio | 10 × SID `1000001`, `allowed` |
| Delta Suricata / PCAP | 25 / 20 |
| drops / ifdrops / decoder / overflow | 0 / 0 / 0 / 0 |

Las diez alertas corresponden únicamente a echo request tipo 8, firma
`PPI LAB ICMP TEST`. Son telemetría permitida para validar el laboratorio, no
una clasificación de ataque. El delta Suricata +5 no tiene causa atribuida;
con PCAP reconciliado y drops cero no se observa impacto en features, pero no
se declara riesgo cero.

EVE conserva dos flows que no pertenecen al episodio modelado:

- un Router Solicitation ICMPv6 link-local `fe80::…→ff02::2`, tipo 133 y un
  paquete, ocurrido a `11:28:34.288562` durante warm-up. Queda fuera del BPF
  oficial, limitado a IPv4 `10.20.0.0/24↔10.30.0.0/24`, y no es ataque;
- una consulta DNS UDP de control `10.20.0.20:50937→10.30.0.10:53`, ocurrida
  a `11:24:47.972398–.972825` durante el preflight y emitida por timeout a
  `11:29:51.513922`. Sus paquetes preceden en casi cuatro minutos al inicio
  PCAP verificado `11:28:31.687262`.

Además, las diez alertas oficiales comparten el `flow_id=128255381313780` y
su objeto `flow.start` conserva `11:24:48.226469`, inicio del probe ICMP del
preflight. Suricata no había expirado ese flujo cuando empezó el episodio. Esto
limita la independencia temporal estricta de la telemetría EVE, aunque no
añade paquetes al PCAP ni observaciones al vector: el extractor no consume
eventos `alert` ni `flow` y registró cero observaciones de aplicación. La
evidencia se preserva sin limpieza post hoc.

## Fase UTC, features y duplicados

El episodio cruzó el borde UTC `16:29:40` y produjo dos ventanas elegibles:

| Fin UTC | Paquetes | Packet rate | Byte rate | Attempts 30 s | Attempt rate 10 s | Ratio IP / ICMP |
|---|---:|---:|---:|---:|---:|---:|
| `16:29:40` | 16 | 1.6/s | 134.4 B/s | 1 | 0.1/s | 1 / 1 |
| `16:29:50` | 4 | 0.4/s | 33.6 B/s | 1 | 0.0/s | 1 / 1 |

El intento ICMP canónico aparece una vez en la historia de 30 s de ambas
filas. En la segunda, el request quedó fuera de la ventana de tasa de 10 s;
por eso `flow_attempt_count_30s=1` y `flow_attempt_rate_10s=0` son consistentes.
Ambas filas tienen longitud media 84, `icmp_ratio_10s=1`, ratio de IP destino
1 y ratio de puertos 0 porque ICMP no usa transporte.

R01 produjo 20 paquetes en una fila; R02, 18/2; R03, 6/14; R04, 16/4; y R05,
16/4. Cada una de las dos filas R05 coincide exactamente en sus catorce
features y en orden con la fila equivalente de R04, pero las dos filas R05 no
son iguales entre sí. Los artefactos, ID ICMP, tiempos y hashes son propios:
son dos repeticiones estructurales `validation↔test` por fase coincidente, no
reutilización de PCAP/EVE. Se conservan sin deduplicación post hoc.

## Recursos, integridad y auditoría

El Sensor produjo 59 muestras: CPU 0.00–1.50 %, RSS estable en 782,504 KiB,
memoria disponible 14,106,500–14,171,000 KiB y load1 0.00–0.18. Ambos stderr
están vacíos; son observaciones descriptivas, no SLA.

```text
preflight             5a7ac83bf6077071cd2f2f80f18535c30da429df938ff4007d16467c32b22419
manifest              1eb267331a72dd788b3cb67d613de8993f6a7b86ab0c404d0d03b3bcf1b83118
pcap                  c0d4e998825b0157659604aebcbfaa8314f86f806b0d2b8cb1877ecbbbcc1718
eve                   f425d3e61aefa143e415960f4bb7e5434b99e5cce69b4314912979a87a715081
campaign SHA256SUMS   0dceac413ab1a8d393919260cd31a668948ced9e2f1b10cc94ec93efbab70d09
features CSV          b42d5e0bc89e138ec97c9c30191a3242205df006fdea50ca6cdda865a4b09a6d
extraction report     650e456b0495a7ab6ff5e29197994a438ba2d0eb2223c82f5974503177b3a7ff
feature SHA256SUMS    40b8d111a58df761c5db0b83a50cc5b449548536fe33670011f406c3bcabf217
ledger                45bae2f79a29aa90be31d88bbe77f3a0a6c4a1bc913547a71ad6170791fc790b
```

Ambos bundles y la copia PCAP remota/local pasaron. El auditor limpio aceptó
121/145 campañas: R05 5/29, 24 faltantes, cero inválidas y cero advertencias.
Las dos filas elevan los totales a 32 duplicados y 15 cruces. El resumen R05
contiene cinco perfiles, seis filas, 604 observaciones de paquete y 304 de
aplicación, sin duplicados internos de R05. `gate_pass=false` significa sólo
que aún faltan 24 perfiles.

Claude verificó la evidencia individual, descubrió la continuidad del
`flow_id` ICMP desde el preflight y emitió **ACEPTAR CON LIMITACIONES**. Su
sesión sólo lectura no reejecutó el auditor; Codex confirmó los totales y
hashes por separado.

**Decisión:** `F1N-PING-10-R05` queda cerrado con limitaciones por dos flows
fuera de alcance causal, continuidad del flow ICMP de preflight, delta +5 sin
atribución y dos repeticiones estructurales frente a R04. Después de publicar,
el siguiente paso independiente es el preflight de `F1N-PING-100-R05`. No se
realizó scoring parcial.
