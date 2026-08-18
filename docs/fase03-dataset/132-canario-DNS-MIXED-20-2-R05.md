# Tercer canario oficial R05 — DNS-MIXED-20-2

Fecha: 7 de agosto de 2026. Campaña `F1N-DNS-MIXED-20-2-R05`,
partición `test`. Estado: **ACEPTADA CON LIMITACIONES**.

## Propósito y controles previos

El perfil genera veinte resoluciones DNS válidas seguidas de dos nombres
inexistentes por diseño. Representa una tasa baja y legítima de errores L7; no
es DGA ni ataque. Su objetivo es demostrar que `dns_nxdomain_ratio_60s` puede
representar NXDOMAIN benignos sin usar el tamaño de paquete como sustituto de
comportamiento.

El preflight continuo pasó sus nueve gates entre `00:33:19.613` y
`00:33:51.533 -05:00` sobre el commit limpio
`945d7d18edd09cb22b56ff18a108f8fb941d63f7`. Confirmó `experiment/test`,
matriz `ad22ce5f…dfa824`, argumentos `4086992c…ea157`, NTP 5/5 con máximo
absoluto 0.213717 ms, 121,458,192,384 bytes libres, SSH 4/4, cuatro NIC
externas `DOWN`, aislamiento/rutas, Suricata limpio y servicios/probes.

El dry-run fijó explícitamente
`PPI_ARTIFACTS_ROOT=/srv/ppi-evidence/artifacts`; ambos storage gates, marker y
mountpoint pasaron. Claude verificó el generador, la fórmula NXDOMAIN y la
política de duplicados, y autorizó exactamente una captura. Se ejecutó una vez,
sin `--pilot`, reintento, modelo ni scoring.

## Resultado DNS y PCAP

La ráfaga ocurrió entre `00:38:52.557234` y `00:38:53.085511 -05:00`, en el
orden congelado: veinte pares `server.ppi.lab` con respuesta `NOERROR`, seguidos
de `error-legitimo-1.ppi.lab` y `error-legitimo-2.ppi.lab`, ambos `NXDOMAIN`.

| Control | Resultado |
|---|---:|
| Solicitudes / respuestas DNS | 22 / 22 |
| Respuestas válidas / NXDOMAIN | 20 / 2 |
| PCAP archivos / bytes | 1 / 5,092 |
| Capturados / recibidos / parseados | 44 / 44 / 44 |
| Drops / transferencia / límite | 0 / verificada / no alcanzado |
| Longitud IPv4 media / máxima | 85.18 / 93 bytes |
| Paquetes de 500–1500 bytes | 0 |
| EVE esperado / extraído | 56 / 56, mismo inode |
| Delta Suricata / PCAP | 48 / 44 |
| drops / ifdrops / decoder / overflow | 0 / 0 / 0 / 0 |

El escenario devolvió veinte líneas `10.30.0.10`, código cero y stderr vacío.
La ausencia de salida para NXDOMAIN es el comportamiento previsto del
generador; EVE demuestra las dos consultas y respuestas negativas.

## Dos flows diferidos, no contaminación

EVE contiene 44 DNS, diez `stats` y dos eventos `flow`. Ambos flows fueron
emitidos por timeout durante el periodo de captura, pero sus propios campos
`start/end` demuestran que los paquetes pertenecen al preflight:

| Flow | Paquetes | Inicio / fin local | Emisión |
|---|---:|---|---|
| ICMP | 2+2 | `00:33:50.164–00:33:51.182` | `00:38:54.953` |
| DNS `55711→53` | 1+1 | `00:33:49.890–00:33:49.891` | `00:38:58.941` |

Coinciden con `PROBES=HTTP200 DNS10.30.0.10 ICMP2/2`. El PCAP oficial empieza
casi cinco minutos después, a `00:38:52.557`, y no contiene esos seis paquetes.
El extractor tomó 44 observaciones PCAP y no incorporó los flows a las
features. Se preservan en EVE como evidencia real del comportamiento diferido
de Suricata; no se borran post hoc.

El delta Suricata +4 frente al PCAP presenta el patrón recurrente de otros
perfiles DNS. Con todos los drops en cero y 44 paquetes reconciliados, no se
observa impacto sobre esta fila, pero la causa de los cuatro paquetes sigue sin
atribución.

## Features y duplicado cruzado

La extracción produjo una fila con 44 observaciones de paquete y 24 de
aplicación: 22 consultas más dos marcadores NXDOMAIN. Sus señales principales
son:

| Feature | Valor |
|---|---:|
| `packet_rate_10s` | 4.4 |
| `byte_rate_10s` | 374.8 |
| `mean_ip_len_10s` | 85.18181818 |
| `flow_attempt_rate_10s` | 2.2 |
| `unique_dst_ip_ratio_30s` | 0.04545455 |
| `unique_dst_port_ratio_30s` | 0.04545455 |
| `dns_nxdomain_ratio_60s` | **0.09090909 = 2/22** |

Las catorce features coinciden decimalmente con R01, R02, R03 y R04. PCAP,
EVE, timestamps y hashes son independientes; el cruce `train↔test` proviene
del generador determinista y su orden causal fijo. Se conserva según el
protocolo congelado, no se deduplica y no se usa para reajustar el modelo. Esta
fila limita la medición de generalización, pero no constituye fuga operacional.

R05 contiene ahora tres filas sin duplicados entre sí: `DNS-VALID-10`,
`DNS-VALID-200` y esta campaña son distintas. La coincidencia aparece sólo al
comparar particiones.

## Recursos, integridad y auditoría

El Sensor registró 53 muestras, CPU 0.00–1.51 %, RSS estable en 782,504 KiB,
memoria disponible 14,071,264–14,162,356 KiB y load1 0.08–0.35. Son cifras
descriptivas de un episodio ligero, no un SLA.

```text
preflight             804f25430a0c02cb5215f395bff6b50b1593e9d499e28588e400491481cd20ce
manifest              87d9cb0a8aebf6fbd548baa9aa8283b782382f27283b42576a2ff815e648d7cd
pcap                  d89033d97a28ff6cec07b41143081bf6867d6f3e97e92c5609c2b3ac1153ca03
eve                   cddaf847e718cfdc154a3e726e95c341ece00fd28bb3a88381767225c7cce748
campaign SHA256SUMS   16c6af844f24ac1551b6f7a01859aec839b2b3d5f51e1134eef3af31620120ba
features CSV          efc3026d1431c10eeb3af5772606592c4df98b94b157e0046ccff32b4ea4eaf2
extraction report     64b9f81277a6874baceab9082340a376f360d863c3a71ca78821e07eb57878b4
feature SHA256SUMS    0a779c578e991df72227e0f30e59604910c86861508eccabca1d770e1ad4afc0
ledger                ad420d2ed2333b5194b08f2155aac6bc6a86ff1712497c0c38ed90257f1b18c9
```

Ambos bundles y la copia remota del PCAP pasaron. El auditor oficial aceptó
119/145 campañas: R05 3/29, 26 faltantes, cero inválidas y cero advertencias.
El duplicado exacto elevó los totales de 28/11 a 29 duplicados/12 cruces. El
resumen R05 registra tres perfiles, tres filas, 464 observaciones de paquete y
234 de aplicación. `gate_pass=false` significa únicamente que faltan 26
perfiles.

Claude emitió **ACEPTAR CON LIMITACIONES** después de verificar manifest, EVE,
orden DNS, flows, extracción y comparación R01–R05. No recalculó hashes ni
auditor; Codex realizó esas verificaciones.

**Decisión:** `F1N-DNS-MIXED-20-2-R05` queda cerrado con limitaciones por
generador determinista, flows diferidos y delta +4 no atribuido. Después de
publicar este cierre, el único siguiente paso es el preflight independiente de
`F1N-DNS-MIXED-50-10-R05`. R05 permanece sin scoring parcial.
