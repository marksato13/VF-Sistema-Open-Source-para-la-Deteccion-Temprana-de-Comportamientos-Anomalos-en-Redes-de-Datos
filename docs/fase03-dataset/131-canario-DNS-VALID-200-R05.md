# Segundo canario oficial R05 — DNS-VALID-200

Fecha: 7 de agosto de 2026. Campaña `F1N-DNS-VALID-200-R05`, partición
`test`. Estado: **ACEPTADA CON LIMITACIONES**.

## Objetivo y preflight

El segundo perfil R05 generó una ráfaga legítima de 200 consultas DNS A desde
Cliente `10.20.0.20` hacia Servidor `10.30.0.10`. Su estrato `burst` cubre tasas
L3/L4 y comportamiento DNS L7; no pretende aportar paquetes grandes ni
diversidad de hosts, dominios o resolvers.

El preflight continuo pasó sus nueve gates entre `23:53:58.093` y
`23:54:30.229 -05:00` sobre el commit limpio y sincronizado
`87354cd2bf4a9673ebf0219e87c73799725ed9ea`:

| Control | Resultado |
|---|---|
| Propósito / partición | `experiment` / `test` |
| Matriz | `ad22ce5f…dfa824` |
| Argumentos | `4d83a1f3…f82d95` |
| Perfil / argumentos | `dns-valid` / `200` |
| Warm-up / quietud / settle / cooldown | 60 / 70 / 9 / 30 s |
| NTP | 5/5; máximo absoluto 0.217197 ms |
| Capacidad libre | 121,458,667,520 bytes |
| SSH / NIC externas | 4/4 / 4/4 `DOWN` |
| Aislamiento, rutas y Suricata | PASS; captura inactiva |
| Servicios y probes | HTTP, DNS, ICMP e iperf3 correctos |
| Log | `95b77d46…f25cb` |

Claude bloqueó inicialmente el comando propuesto porque no fijaba
`PPI_ARTIFACTS_ROOT`. El origen del JSON `storage=false` que citó no quedó
identificado en un artefacto persistido, pero la inspección de código confirmó
el problema subyacente: el preflight usa `/srv/ppi-evidence/artifacts` por
defecto y el orquestador cae en `artifacts/` del repositorio si falta la
variable.

Codex aceptó el control técnico, ejecutó otro dry-run no capturante con
`PPI_ARTIFACTS_ROOT=/srv/ppi-evidence/artifacts` y obtuvo
`matrix_storage_gate_pass=true`, `official_storage.gate_pass=true`, marker
válido, mountpoint real y los mismos commit/matriz/argumentos. Claude cerró el
bloqueo `R05-01` y autorizó exactamente una captura. El comando real conservó
la variable explícita y se ejecutó una sola vez, sin `--pilot`, reintento,
carga de modelo ni scoring.

## DNS, PCAP y EVE

El escenario terminó con código cero, stderr vacío y 200 líneas
`10.30.0.10`. La ráfaga transcurrió entre `05:08:23.853550` y
`05:08:28.056687 UTC`: 4.203137 segundos.

| Control | Resultado |
|---|---:|
| Solicitudes / respuestas DNS | 200 / 200 |
| Respuestas | 200 `NOERROR`; `server.ppi.lab A 10.30.0.10` |
| IDs DNS únicos / pares completos | 200 / 200 |
| PCAP archivos / bytes | 1 / 46,024 |
| Capturados / recibidos por filtro / parseados | 400 / 400 / 400 |
| Drops / transferencia / límite | 0 / verificada / no alcanzado |
| EVE esperado / extraído | 410 / 410, mismo inode |
| Composición EVE | 400 DNS + 10 stats; cero flows |
| Delta Suricata / PCAP | 404 / 400 |
| drops / ifdrops / decoder / overflow | 0 / 0 / 0 / 0 |
| Muestras Sensor / stderr | 56 / vacío |

EVE contiene ocho `stats` previos a la ráfaga y dos posteriores, además de los
400 eventos DNS. No contiene flows diferidos ni eventos de las sondas de
preflight. Los cuatro paquetes adicionales del contador Suricata no aparecen
en el PCAP filtrado; el mismo patrón ocurre en R01, R02 y R04, mientras R03 no
lo presentó. Su causa sigue sin atribución. Los drops cero y la reconciliación
de las 400 transacciones indican que no se observó impacto sobre esta campaña,
pero no permiten declarar riesgo nulo de forma general.

Los 400 paquetes IPv4 son menores de 500 bytes, con media 85 y máximo 87. Es
coherente con DNS; la observación del jurado sobre tráfico pesado se satisface
mediante otros estratos de la matriz, no forzando paquetes grandes en este
perfil.

## Reutilización de puerto y semántica multicapa

El Cliente usó 198 puertos origen distintos. Los puertos `45430` y `48222` se
usaron dos veces cada uno, siempre con IDs DNS diferentes. La verificación por
par `(puerto, ID)` obtuvo 200 solicitudes, 200 respuestas, 200 pares únicos,
cero respuestas faltantes y cero huérfanas.

Por eso la fila conserva simultáneamente:

| Campo | Valor | Semántica |
|---|---:|---|
| `packet_count_10s` | 400 | solicitudes + respuestas L3 |
| `dns_query_count_60s` | 200 | transacciones/consultas L7 |
| `flow_attempt_count_30s` | 198 | 5-tuplas UDP distintas L4 |
| `packet_rate_10s` | 40.0 | paquetes por segundo |
| `byte_rate_10s` | 3,400.0 | bytes IP por segundo |
| `flow_attempt_rate_10s` | 19.8 | intentos por segundo |
| `unique_dst_ip_ratio_30s` | 0.00505051 | 1 / 198 |
| `unique_dst_port_ratio_30s` | 0.00505051 | 1 / 198 |
| `dns_nxdomain_ratio_60s` | 0.0 | ninguna respuesta NXDOMAIN |

La diferencia 198↔200 demuestra por qué las features L4 y L7 no deben
interpretarse como contadores equivalentes. No es pérdida ni defecto del
extractor.

## Ventana UTC y comparación R01–R05

Toda la ráfaga cayó dentro de la ventana UTC `[05:08:20, 05:08:30)`, por lo que
produjo una sola fila con los 400 paquetes. Las repeticiones anteriores cruzaron
un borde fijo y se dividieron en dos:

| Repetición | Paquetes por ventana | Último conteo de intentos | Filas |
|---|---|---:|---:|
| R01 train | 228 / 172 | 199 | 2 |
| R02 train | 24 / 376 | 200 | 2 |
| R03 train | 64 / 336 | 200 | 2 |
| R04 validation | 274 / 126 | 200 | 2 |
| R05 test | 400 | 198 | 1 |

Todas suman 400 paquetes. El vector R05 no coincide exactamente con ninguna
fila R01–R04 ni con otra campaña. Es una variación nueva en el espacio de
features causada por la fase del borde UTC; no demuestra por sí sola diversidad
de comportamiento de red ni independencia estadística.

## Recursos, hashes y auditoría

El Sensor registró CPU 0.00–2.98 %, RSS estable en 782,504 KiB, memoria
disponible 14,089,880–14,158,904 KiB y load1 0.03–0.10. Describe esta ráfaga
ligera en bytes, no un SLA de capacidad.

```text
preflight             95b77d466c4398065d0df434e48becc79e0a044cae7ec04a3245c59507af25cb
manifest              e9bc9fd79f426fda64e1e25cd9912fab61560639d826a723d109a840c80a3cfa
pcap                  668e941570e04730aaf1c2ff0c5d071ebfb0f2bc4b6418515342e2f670c51c3a
eve                   23fa82318712a1d0610df6486580ae9eefeba48f7232f3e4e97cd8241eb5d5ee
campaign SHA256SUMS   a6ef9aa58e54ba3196c598e02d958881ed524637253c82ac141969794c9b0220
features CSV          1b665e10175150f5f6e5e507400219df3eae9d10cfa086ea24741f42c9472a60
extraction report     d03436ef6737049107b8fc63a7fabfb3daa07e46b31b071078f7be3670c3eb57
feature SHA256SUMS    00d97fc4e38dfdaff30b5091c4ca8a6e7b576105de440346d0e6461a9e9b8400
ledger                388dbc1cd3581c1daaf96c3587bd8f5828e30c1ac862bad4f4779221ce0c0c07
```

Los dos bundles y la copia remota del PCAP pasaron. El auditor oficial aceptó
118/145 campañas: R05 2/29, 27 faltantes, cero inválidas y cero advertencias.
Los duplicados permanecen en 28 totales y 11 cruzados; esta fila no añadió
ninguno. El resumen R05 contiene dos perfiles/dos filas, 420 observaciones de
paquete y 210 de aplicación, sin duplicados internos. `gate_pass=false` sólo
indica que faltan 27 perfiles.

Claude emitió **ACEPTAR CON LIMITACIONES** tras leer los artefactos. No pudo
abrir el PCAP binario, recalcular hashes ni reproducir el auditor; Codex verificó
esos elementos. Se corrigieron dos formulaciones de su dictamen: son 200
solicitudes y 200 respuestas —no «200/200 consultas»— y el delta +4 carece de
impacto observado aquí, pero no puede declararse universalmente «sin riesgo».

**Decisión:** `F1N-DNS-VALID-200-R05` queda cerrado con limitaciones por fase
UTC, reutilización legítima de puertos y delta +4 no atribuido. Después de
publicar este cierre, el único paso permitido es un preflight nuevo de
`F1N-DNS-MIXED-20-2-R05` contra el nuevo commit limpio. No hay scoring parcial
de R05.
