# Primer canario oficial R05 — DNS-VALID-10

Fecha: 6 de agosto de 2026. Campaña `F1N-DNS-VALID-10-R05`, partición
`test`. Estado: **ACEPTADA CON LIMITACIONES**.

## Alcance y controles previos

Esta es la primera de 29 celdas de evaluación final R05. Generó diez consultas
DNS A legítimas desde Cliente `10.20.0.20` hacia Servidor `10.30.0.10`. La
ejecución sirve para validar la cadena captura→extracción en `test`; por ser un
generador determinista y de baja diversidad no basta para demostrar
generalización del modelo.

El preflight continuo pasó sus nueve gates entre `22:25:07.843` y
`22:25:40.211 -05:00` sobre el commit limpio y sincronizado
`057f1fcfca9d37f5aa6b4000d70a75250df747a0`. Fijó:

| Control | Resultado |
|---|---|
| Propósito / partición | `experiment` / `test` |
| Matriz | `ad22ce5f…dfa824` |
| Argumentos | `6e32bc5b…496a60` |
| Warm-up / quietud / settle / cooldown | 60 / 70 / 9 / 30 s |
| NTP | 5/5; máximo absoluto 0.459 ms |
| Capacidad libre | 121,458,872,320 bytes |
| SSH / identidades | 4/4; `useransible` |
| NIC externas | 4/4 `DOWN` por MAC |
| Aislamiento y rutas | bypass bloqueado; rutas por Sensor |
| Suricata / captura previa | limpio / inactiva |
| Servicios y probes | HTTP, DNS, ICMP e iperf3 correctos |
| Log de preflight | `45ab877e…7117` |

Después del preflight Claude autorizó una sola captura. El orquestador ejecutó
una vez `run_matrix_profile.py --profile DNS-VALID-10 --repetition 5`; no hubo
reintento, carga del modelo ni cálculo de score.

## Tráfico y evidencia primaria

El escenario terminó con código cero, stderr vacío y diez respuestas
`10.30.0.10`. El PCAP contiene exactamente diez solicitudes y diez respuestas
UDP DNS. Los diez IDs son únicos; todas las respuestas son `NOERROR`, incluyen
`server.ppi.lab A 10.30.0.10` y el intervalo DNS completo es de 0.249023 s.

| Control | Resultado |
|---|---:|
| PCAP archivos / bytes | 1 / 2,324 |
| Capturados / recibidos por filtro / parseados | 20 / 20 / 20 |
| Drops / transferencia / límite | 0 / verificada / no alcanzado |
| EVE esperado / extraído | 29 / 29, mismo inode |
| Composición EVE | 20 DNS + 9 stats |
| Delta Suricata / PCAP | 24 / 20 |
| drops / ifdrops / decoder / overflow | 0 / 0 / 0 / 0 |
| Muestras Sensor / stderr | 53 / vacío |

Los cuatro paquetes adicionales del contador de Suricata no están en el PCAP
filtrado. El patrón `+24` frente a 20 aparece también en R01, R02 y R04; R03 no
lo presentó. El Sensor inspecciona toda `ens35` mientras tcpdump aplica el
filtro LAN↔DMZ, pero no se capturó evidencia suficiente para atribuir esos
cuatro paquetes a una causa concreta. Se registra como limitación no resuelta,
no como pérdida: todos los contadores de drop son cero y las veinte
transacciones esperadas se reconcilian.

Las longitudes IPv4 fueron 20 paquetes menores de 500 bytes, ninguno entre
500–1500 ni mayor de 1500, media 85 bytes y máximo 87. Es correcto para este
estrato DNS ligero; la cobertura de tráfico pesado se aporta mediante los
perfiles HTTP/HTTPS/TCP/UDP de la matriz completa.

## Extracción y comparación entre particiones

La extracción consumió 20 observaciones de paquete y diez observaciones de
aplicación, y produjo una fila elegible:

| Feature no nula | Valor |
|---|---:|
| `packet_rate_10s` | 2.0 |
| `byte_rate_10s` | 170.0 |
| `mean_ip_len_10s` | 85.0 |
| `unique_dst_ip_ratio_30s` | 0.1 |
| `flow_attempt_rate_10s` | 1.0 |
| `unique_dst_port_ratio_30s` | 0.1 |

Las otras ocho features son cero, incluido `dns_nxdomain_ratio_60s`. Las
catorce features de R05 coinciden exactamente con `DNS-VALID-10` R01, R02, R03
y R04. No existe reutilización de PCAP, EVE, timestamps o artefactos: es una
repetición independiente que colapsa al mismo vector por el diseño determinista
del perfil.

Este es el primer cruce exacto `train↔test` y eleva los duplicados cruzados de
10 a 11. Es una **limitación científica de diversidad**, no fuga operacional:
el split estaba prefijado, R05 no se leyó durante entrenamiento/calibración y
no se consultó el modelo durante la captura. La fila se conserva conforme al
protocolo congelado; no se deduplica ni se reemplaza. En la evaluación final la
métrica primaria incluirá toda R05 y podrá acompañarse de un análisis
descriptivo `seen`/`unseen`, claramente secundario y sin cambiar el conjunto
test.

El ledger usa el nombre heredado `eligible_training_rows=1` aun cuando la
partición es `test`. El campo que gobierna el split es `partition=test`; el
nombre se considera deuda semántica de `f1-run-ledger-v1`, no evidencia de que
la fila haya entrado al entrenamiento. No se cambia el esquema durante R05.

## Recursos, integridad y auditoría

Durante las 53 muestras el Sensor registró CPU 0.00–1.51 %, RSS estable en
782,504 KiB, memoria disponible 14,093,980–14,162,556 KiB y load1 0.17–0.32.
Estas cifras describen el episodio ligero; no constituyen un SLA ni validan por
sí solas suficiencia bajo carga.

```text
preflight             45ab877ef456f86c19eba9452282eee5fea17e13759b5b2b4d8161809fb77117
manifest              ac893e64ef1f3e49e3bd84b68e72ca4e8ca28cd48f488123227a5c886d4ea8aa
pcap                  2646ebb737c8729fd423d596c3c861e6b7a84f6a47cd53b85a9a1f74792da885
eve                   2df2ac88a5d9cc67e714ed25ac7815fc4eb458b3d8e50e53c520a8ce90807306
campaign SHA256SUMS   754a59f40465a8372aa4e206025d239530727c9e84c400733be1723913845d85
features CSV          e5b10ed3b8a6174b05880f82464a944f4496cc98338379693fe64a7e8641de36
extraction report     575c7576af1c54e743c050f3e9e682b84cdaf4df5dc1139ef43545833198c471
feature SHA256SUMS    e4bcb0ea425d4be2d47ec82e321dfe9b4e748c23a5e6cc3675b40d51e7159dbf
ledger                34dcaa075b6546cd98c0215d3aaf48a9da936b892dfc0f3624469bdd7afe43eb
```

Los bundles de campaña y features y el listado remoto del PCAP pasaron. Una
primera invocación manual de `sha256sum -c` para features se lanzó desde el
directorio padre, por lo que sus nombres relativos no resolvieron; se repitió
desde el directorio correcto y pasó. Fue un error de ubicación del comando, no
un fallo de integridad, y no regeneró ni modificó evidencia.

El auditor oficial aceptó 117/145 campañas: R05 1/29, 28 faltantes, cero
inválidas y cero advertencias. Registra 28 duplicados totales y 11 cruzados. El
resumen R05 tiene una fila y `gate_pass=false` exclusivamente porque faltan 28
perfiles; no es rechazo del canario.

Claude leyó los artefactos en modo restringido y emitió **ACEPTAR CON
LIMITACIONES**. No pudo ejecutar hashes, abrir el PCAP binario ni reproducir el
auditor; Codex realizó esas verificaciones. Se corrigieron dos formulaciones de
su revisión: el contrato contiene 14 features, no «24 columnas numéricas», y no
se anticipa cuántas filas tendrá R05 completa ni que el efecto del duplicado se
«diluya».

**Decisión:** `F1N-DNS-VALID-10-R05` queda cerrada como episodio test íntegro
con limitación de diversidad y delta +4 no atribuido. Siguiente permitido tras
publicar este documento: únicamente un preflight nuevo y continuo de
`F1N-DNS-VALID-200-R05` contra el nuevo commit limpio. R05 no se puntúa hasta
completar sus 29 perfiles.
