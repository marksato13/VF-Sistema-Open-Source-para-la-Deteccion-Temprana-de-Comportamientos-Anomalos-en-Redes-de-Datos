# Segundo canario oficial R04 — DNS-VALID-200

Fecha: 4 de agosto de 2026. Campaña: `F1N-DNS-VALID-200-R04`. Partición: `validation`. Estado: **ACEPTADA CON LIMITACIONES**.

## Objetivo y preflight

El perfil produce 200 consultas DNS válidas en una ráfaga controlada. Valida un nivel normal superior a `DNS-VALID-10` sin introducir NXDOMAIN ni ataque. Se ejecutó desde el commit limpio y publicado `c1ffd91b4ad2b70f716a3ac6808137e9e9727c15`, después de aceptar y documentar el primer canario R04.

El dry-run fijó `dns-valid 200`, propósito `experiment`, partición `validation`, warm-up/quietud/settle/cooldown de 60/70/9/30 s, matriz SHA `ad22ce5f8b41110b201f0eeacd2b5f13cc9f945c92cf539e9913e87fefdfa824` y argumentos SHA `4d83a1f3e47b09a57f011d4bd69c80eaaed35d7122fbd598fca53a56f2f82d95`.

NTP pasó en las cinco VMs con máximo absoluto 1.151802 ms. Las cuatro NIC externas permanecieron `DOWN`, los ocho probes de bypass quedaron bloqueados y Suricata/servicios/rutas estaban sanos. DNS resolvió por Cliente→Sensor→Servidor, el generador local/remoto mantuvo SHA `d4cd42b65f1b22cea0a3f585c2df760af68a8557799c3859eabc803d4f9b4203`, los contadores estaban en cero y no existían ID, ledger, lock ni captura activa.

## Resultado causal

Las 200 ejecuciones devolvieron `10.30.0.10`. EVE registra 200 requests `A server.ppi.lab` y 200 responses `NOERROR`, todas con `rdata=10.30.0.10`.

| Evidencia | Resultado |
|---|---:|
| DNS request / response | 200 / 200 |
| `NOERROR` / respuesta esperada | 200 / 200 |
| Paquetes PCAP capturados / recibidos / parseados | 400 / 400 / 400 |
| PCAP | 46,024 bytes, un archivo |
| Drops tcpdump | 0 |
| EVE | 410: 400 DNS + 10 stats |
| Alertas / anomalías | 0 / 0 |

El primer DNS ocurrió a `20:43:47.155840` y el último a `20:43:51.267211 -05:00`; el PCAP abarca 4.111371 s. Se usaron 200 puertos efímeros del Cliente: un puerto por transacción. Esto explica 200 intentos canónicos, pero no representa 400 flujos ni 400 transacciones.

Los 400 IPv4 son menores de 500 bytes, con media 85 y máximo 87. Este estrato mide ráfaga DNS ligera; la cobertura pesada legítima corresponde a otros perfiles y no se infiere normalidad sólo por tamaño.

## Dos ventanas y memoria causal

La ráfaga cruzó el borde UTC `01:43:50`, por lo que el extractor generó dos filas:

| Fin UTC | Paquetes 10 s | Intentos 30 s | Queries 60 s | `packet_rate_10s` | `flow_attempt_rate_10s` | Ratio puerto |
|---|---:|---:|---:|---:|---:|---:|
| `01:43:50` | 274 | 137 | 137 | 27.4 | 13.7 | 1/137 = 0.00729927 |
| `01:44:00` | 126 | 200 | 200 | 12.6 | 6.3 | 1/200 = 0.00500000 |

Los 274/126 paquetes equivalen a 137/63 pares request-response. La segunda fila conserva los 200 intentos en la ventana causal de 30 s y las 200 queries en 60 s aunque su ventana de volumen de 10 s contiene sólo los últimos 126 paquetes. `flow_attempt_rate_10s=6.3` usa por separado los 63 intentos de los últimos 10 s divididos entre 10; `flow_attempt_count_30s=200` es metadata para la diversidad de 30 s. No se deben mezclar ambos denominadores.

Las tres repeticiones train también repartieron los 400 paquetes por fase: R01 228/172, R02 24/376 y R03 64/336. R04 aporta 274/126. Ninguna de las dos filas R04 coincide exactamente en sus catorce features con una fila train; esta afirmación es igualdad decimal exacta, no distancia ni novedad estadística.

## Sensor, recursos e integridad

Suricata incrementó 404 paquetes frente a 400 en PCAP. Los cuatro adicionales no están identificados y se conservan como limitación, sin convertirlos en eventos ni pérdida. `kernel_drops`, `kernel_ifdrops`, `decoder_invalid` y `alert_queue_overflow` fueron cero; el checkpoint EVE fue completo, mismo inode y sin reset de contadores.

El muestreador produjo 56 filas con stderr vacío. CPU varió 0–2.94 %, RSS permaneció en 781,720 KiB, memoria disponible en 14,087,672–14,164,448 KiB y load1 en 0.01–0.16. Son recursos observados en una ráfaga DNS de cuatro segundos, no un benchmark de capacidad.

Los bundles de campaña/features y la copia PCAP remoto/local pasaron SHA-256. El extractor registró 400 observaciones de paquete, 200 de aplicación y dos filas elegibles. `application_observations=200` cuenta queries/transacciones DNS, no request+response por separado. Los stderr del escenario y muestreador están vacíos; los stderr tcpdump sólo contienen banners y 400/400 con cero drops.

## Auditoría y decisión

El ledger conserva commit, matriz, argumentos, `validation`, R04 y dos filas elegibles. El auditor oficial aceptó como candidatos 89/145, R04 2/29, 56 celdas pendientes, cero inválidas/advertencias, 18 coincidencias entre campañas y un único cruce train↔validation heredado de `DNS-VALID-10/R04`. `current_git_dirty=true` refleja este borrador documental posterior a una captura hecha con Git limpio; `ready_to_build=false` corresponde además a F1 incompleta. El auditor se repetirá desde el árbol publicado antes del siguiente canario.

**F1N-DNS-VALID-200-R04 ACEPTADA CON LIMITACIONES.** La ráfaga produjo 200 transacciones correctas, evidencia íntegra y dos fases no idénticas a train. El auditor y Claude aceptaron el cierre; no se calculan scores ni umbrales. Siguiente autorizado: sólo preflight independiente de `F1N-DNS-MIXED-20-2-R04`.
