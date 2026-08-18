# Validación de pilotos de la matriz F1 — G6

Fecha: 21 de julio de 2026. Commit ejecutado: `d9b617861b8937f6ccfa6dff9cfb9dd44bfda930`. Matriz SHA-256: `29f997146e5c15161bfb669c50ed789575b4899b021cf09c9a7846dea941c6f3`.

## Decisión

**El contrato, despliegue y ejecutor G6 pasan el piloto técnico. G6 completo continúa pendiente.** Cuatro campañas benignas DNS/HTTP/RST/TLS terminaron con evidencia íntegra, cero drops y extracción causal. La campaña oficial fue bloqueada correctamente por capacidad. Estos datos tienen propósito `calibration`, partición `excluded_calibration` y no pertenecen al dataset final.

## Despliegue y controles negativos

Ansible actualizó `/home/useransible/bin/ppi-run-benign` únicamente en VM05 Cliente:

```text
ppi-client : ok=2 changed=1 unreachable=0 failed=0
```

El SHA-256 local y remoto coincidió:

```text
7701f23d35248a4605a27253c35d3ddaadc3d6a7cefe883360c91b50a87e9566
```

Antes de capturar se probaron los siguientes controles:

- `curl`, `dig`, `ping`, `iperf3`, `jq` y `timeout` existen en VM05;
- un `PPI_TARGET_IP` distinto de `10.30.0.10` es rechazado;
- TCP a 300 Mbit/s es rechazado porque supera G2;
- DNS mixto, HTTP 404, HTTPS health y conexión TCP rechazada funcionaron;
- una campaña oficial `F1N-DNS-VALID-10-R01` fue rechazada con código 1 por `storage_gate_pass=false` antes de crear directorio o ledger.

Las pruebas funcionales previas generaron tráfico benigno mínimo sin captura y no se incorporan a ninguna campaña.

## Piloto 1: error DNS legítimo

Identificador: `CAL-G6-DNS-MIXED-20-2-R01`. Perfil: 20 consultas válidas y 2 NXDOMAIN.

| Control | Resultado |
|---|---:|
| estado / evidencia | `completed` / `complete=true` |
| Git | commit limpio `d9b6178` |
| warm-up / settle | 60 s / 9 s |
| partición | `excluded_calibration` |
| paquetes capturados / parseados | 44 / 44 |
| bytes PCAP remoto / local | 5,092 / 5,092 |
| drops tcpdump / Suricata | 0 / 0 |
| `decoder.invalid` / overflow | 0 / 0 |
| EVE extraído / esperado | 59 / 59 |
| muestras del Sensor | 54 |
| filas / filas con historia completa | 1 / 1 |
| consultas DNS contadas | 22 |
| `dns_nxdomain_ratio_60s` | 0.09090909 = 2/22 |

El PCAP, el segmento EVE y el CSV superaron `sha256sum -c`. El helper remoto quedó `inactive` y no permaneció el lock local `.active`.

## Piloto 2: tráfico legítimo con paquetes grandes

Identificador: `CAL-G6-HTTP-10MB-R01`. Perfil: descarga HTTP de 10 MiB limitada a 2 MiB/s.

La descarga terminó con HTTP 200, 10,485,760 bytes, 4.503130 s y velocidad reportada de 2,328,549 B/s.

| Control | Resultado |
|---|---:|
| estado / evidencia | `completed` / `complete=true` |
| Git | commit limpio `d9b6178` |
| warm-up / settle | 60 s / 9 s |
| partición | `excluded_calibration` |
| paquetes capturados / parseados | 11,234 / 11,234 |
| bytes PCAP remoto / local | 11,414,598 / 11,414,598 |
| drops tcpdump / Suricata | 0 / 0 |
| `decoder.invalid` / overflow | 0 / 0 |
| EVE extraído / esperado | 16 / 16 |
| muestras del Sensor | 58 |
| paquetes IP de 500–1500 bytes | 7,247 / 11,234 (64.5095 %) |
| paquetes IP exactamente de 1500 bytes | 7,246 |
| longitud IP media / máxima | 986.07 / 1500 bytes |
| `large_ip_ratio_10s` | 0.64509525 |
| `mean_ip_len_10s` | 986.07388286 bytes |
| `syn_completion_ratio_10s` | 1.0 |
| `http_error_ratio_60s` | 0.0 |

Este resultado responde directamente a la observación del jurado: el pipeline captura y representa paquetes grandes en una transferencia legítima. No demuestra aún que el modelo evite falsos positivos; eso requiere las cinco repeticiones de los perfiles pesados, análisis de distribución y evaluación retenida.

## Trazabilidad comprobada

Cada manifiesto incorporó:

- commit Git con `dirty=false`;
- propósito y partición;
- SHA-256 de la matriz;
- ID del perfil y repetición;
- inventario de las cuatro VMs;
- verificación de copia PCAP remota/local;
- contadores y hashes de toda la evidencia.

El ledger del ejecutor conserva además el hash del CSV, número de filas y estado final. Los artefactos grandes permanecen fuera de Git.

## Piloto 3: conexiones TCP rechazadas legítimas

Identificador: `CAL-G6-TCP-REFUSED-5-R01`. Commit limpio: `54e7501`. Perfil: cinco conexiones del Cliente a un puerto cerrado del Servidor.

| Control | Resultado |
|---|---:|
| estado / evidencia | `completed` / `complete=true` |
| partición | `excluded_calibration` |
| intentos / rechazos esperados | 5 / 5 |
| paquetes capturados / parseados | 10 / 10 |
| bytes PCAP remoto / local | 824 / 824 |
| drops tcpdump / Suricata | 0 / 0 |
| `decoder.invalid` / overflow | 0 / 0 |
| EVE extraído / esperado | 9 / 9 |
| SYN / intentos de flujo | 5 / 5 |
| `syn_rate_10s` | 0.5/s |
| `syn_completion_ratio_10s` | 0.0 |
| `rst_ratio_10s` | 0.5 |

El resultado confirma que SYN sin handshake y RST no son exclusivos de un ataque: también aparecen cuando una aplicación legítima intenta un puerto cerrado. Este estrato debe estar en la normalidad para que esas señales se interpreten conjuntamente con tasa, diversidad y contexto.

## Piloto 4: recambio de sesiones TLS legítimas

Identificador: `CAL-G6-TLS-SESSIONS-20-R01`. Commit limpio: `54e7501`. Perfil: veinte conexiones HTTPS independientes a `/health`.

| Control | Resultado |
|---|---:|
| estado / evidencia | `completed` / `complete=true` |
| respuestas HTTP 200 | 20 / 20 |
| paquetes capturados / parseados | 433 / 433 |
| bytes PCAP remoto / local | 146,149 / 146,149 |
| drops tcpdump / Suricata | 0 / 0 |
| `decoder.invalid` / overflow | 0 / 0 |
| EVE extraído / esperado | 35 / 35 |
| observaciones TLS | 20 |
| SYN / completitud | 20 / 1.0 |
| `flow_attempt_rate_10s` | 2.0/s |
| `syn_rate_10s` | 2.0/s |
| `tls_session_rate_60s` | 0.33333333 = 20/60 s |

El extractor deduplicó correctamente veinte sesiones y no convirtió su recambio en error HTTP. Este piloto valida el soporte de la feature L7, no su capacidad discriminativa final.

## Auditoría posterior del ensamblador

Después de los pilotos, `build_f1_dataset.py --audit-only` registró:

```text
accepted_campaigns = 0
excluded_campaigns = 4
invalid_campaigns = 0
missing_cells = 135
current_git_dirty = false
ready_to_build = false
```

Los cuatro `campaign_id` de calibración aparecen explícitamente como `not_experiment`. La historia causal completa de sus CSV no cambió esa exclusión.

Esta auditoría corresponde al contrato `v1` de 135 campañas. Antes de iniciar datos oficiales, el rediseño multidestino creó `f1-normal-v2` con 145 campañas; los cuatro pilotos `v1` continúan excluidos y no se reinterpretan bajo el contrato nuevo.

## Hallazgo metodológico

`eligible_training_rows=1` significa únicamente que existe historia causal suficiente de 60 s. No significa que la fila esté autorizada para entrenamiento. El futuro ensamblador debe exigir simultáneamente:

```text
manifest.purpose == experiment
manifest.partition in {train, validation, test}
manifest.evidence.complete == true
manifest.git.dirty == false
```

y validar hashes antes de copiar filas. Usar solo `eligible_training` contaminaría el dataset con calibraciones.

## Pendientes antes de G6 PASS

1. añadir un disco de evidencias de al menos 100 GiB útiles o implementar archivado por lotes con respaldo verificado;
2. añadir diversidad legítima de destinos DMZ para probar `unique_dst_ip_ratio_30s`;
3. crear una identidad técnica SSH/SFTP sin contraseñas embebidas;
4. pilotar concurrencia HTTP, TLS repetido, RST, TCP/UDP y mezcla, comprobando el rango real de cada feature;
5. implementar el ensamblador que aplique partición, exclusiones y hashes;
6. realizar la recolección oficial completa y un informe de distribución antes de entrenar.

Por estas razones G6 conserva estado **PENDIENTE**, aunque los cuatro pilotos fueron exitosos.
