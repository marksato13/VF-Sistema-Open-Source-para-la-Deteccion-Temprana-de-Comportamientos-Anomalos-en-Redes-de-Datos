# Auditoría agregada de R04 — gate previo a calibración

Fecha: 6 de agosto de 2026. Repetición: `R04`. Estado: **GATE PASS — VALIDATION COMPLETA CON LIMITACIONES**.

## Alcance y reproducción

Esta auditoría cierra las 29 campañas normales de `validation`. No entrena ni puntúa modelos. Distingue paquetes, ventanas y episodios: los PCAP producen features, pero las ventanas solapadas de una campaña no son muestras independientes.

```bash
PPI_ARTIFACTS_ROOT=/srv/ppi-evidence/artifacts \
.venv/bin/python scripts/dataset/build_f1_dataset.py --audit-only

PPI_ARTIFACTS_ROOT=/srv/ppi-evidence/artifacts \
.venv/bin/python scripts/analysis/summarize_f1_repetition.py \
  --repo . \
  --repetition 4 \
  --require-complete
```

El agregador reaplica SHA-256, manifest, ledger, PCAP/EVE, CSV, Git, matriz, esquema, partición y dominio de las catorce features. Codex lo ejecutó dos veces; Claude reprodujo la segunda verificación con Bash limitado a ese comando de sólo lectura y timeout de 600 s.

## Gate de colección

| Control | Resultado |
|---|---:|
| Commit auditado | `4949eed12d4b3822de7c343b86fb842e05437f19` |
| Matriz / esquema | `ad22ce5f…dfa824` / `9ce86147…0e1df` |
| Perfiles esperados / aceptados R04 | 29 / 29 |
| Repetición / partición | R04 / `validation` |
| Campañas globales | 116 / 145 |
| Inválidas / advertencias | 0 / 0 |
| Faltantes | 29 = sólo R05 |
| Git dirty | `false` |
| `repetition_complete` / `gate_pass` | `true` / `true` |

`ready_to_build=false` es correcto: el ensamblador final exige 145/145 y R05 permanece sellada. El gate certifica integridad y completitud de R04; no certifica rendimiento, suficiencia poblacional ni separabilidad.

## Unidad real y volumen

| Métrica | R01 | R02 | R03 | R04 | R01–R04 |
|---|---:|---:|---:|---:|---:|
| Episodios | 29 | 29 | 29 | 29 | 116 |
| Filas elegibles | 77 | 75 | 72 | 72 | 296 |
| Campañas de una fila | 7 | 8 | 9 | 10 | 34 |
| Campañas multiventana | 22 | 21 | 20 | 19 | 82 |
| Filas mín./mediana/máx. | 1 / 2 / 7 | 1 / 2 / 6 | 1 / 2 / 6 | 1 / 2 / 6 | 1 / 2 / 7 |
| Paquetes observados | 4,382,327 | 4,389,895 | 4,396,719 | 4,397,060 | 17,566,001 |
| Obs. aplicación | 390 | 390 | 390 | 390 | 1,560 |
| Bytes PCAP | 6,512,478,820 | 6,514,443,996 | 6,513,387,110 | 6,512,879,931 | 26,053,189,857 |

Los 26.05 GB crudos no convierten el experimento en millones de muestras estadísticas: hasta R04 existen 116 episodios controlados y 296 ventanas correlacionadas. No existe un criterio previo de potencia que permita declarar suficiencia universal.

R04 distribuye sus 72 filas así:

| Escenario | Filas |
|---|---:|
| `https` | 13 |
| `http` | 12 |
| `http-concurrent` | 10 |
| `iperf-tcp` | 9 |
| `iperf-udp` | 9 |
| `ping` | 5 |
| `dns-valid` | 3 |
| `mixed-light` | 3 |
| `dns-mixed` | 2 |
| `http-multi` | 2 |
| `https-sessions` | 2 |
| `http-missing` | 1 |
| `tcp-refused` | 1 |

Web/TLS estricto aporta 40/72 = 55.5556 % de R04; con MIXED-LIGHT, 43/72 = 59.7222 %. En R01–R04 son 166/296 = 56.0811 % y 178/296 = 60.1351 %. Los seis PCAP mayores suman 4,804,545,789 bytes, 73.769912 % del almacenamiento R04. Bytes y filas son concentraciones distintas; ninguna recibe interpretación causal.

## Cobertura multicapa

Ninguna dimensión quedó totalmente en cero:

| Capa | Feature | Rango R04 | Filas no cero | Campañas no cero |
|---|---|---:|---:|---:|
| L3 | `packet_rate_10s` | 0.4–18,526.4/s | 72 | 29 |
| L3 | `byte_rate_10s` | 33.6–25,968,511.6 B/s | 72 | 29 |
| L3 | `mean_ip_len_10s` | 50–1,494.18932479 B | 72 | 29 |
| L3 | `large_ip_ratio_10s` | 0–1 | 58 | 19 |
| L3 | `unique_dst_ip_ratio_30s` | 0–1 | 62 | 29 |
| L3 | `icmp_ratio_10s` | 0–1 | 5 | 2 |
| L4 | `flow_attempt_rate_10s` | 0–13.7/s | 31 | 29 |
| L4 | `syn_rate_10s` | 0–1.5/s | 24 | 23 |
| L4 | `syn_completion_ratio_10s` | 0–1 | 23 | 22 |
| L4 | `rst_ratio_10s` | 0–0.5 | 1 | 1 |
| L4 | `unique_dst_port_ratio_30s` | 0–1 | 57 | 27 |
| L7 | `http_error_ratio_60s` | 0–1 | 1 | 1 |
| L7 | `dns_nxdomain_ratio_60s` | 0–0.16666667 | 2 | 2 |
| L7 | `tls_session_rate_60s` | 0–0.33333333/s | 15 | 5 |

La observación del jurado sobre comportamiento multicapa queda respondida estructuralmente con seis variables L3, cinco L4 y tres L7 implementadas, versionadas y extraídas. La cobertura L7 de errores sigue siendo escasa: en R01–R04, error HTTP aparece en 5/296 filas, NXDOMAIN en 8/296 y TLS en 58/296. Debe reportarse como limitación.

El esquema no contiene intentos fallidos de login. SSH cifra esa semántica y exigiría integrar logs de host, nuevo código/diccionario y una versión nueva del dataset; no se afirma que `multilayer-v1` la mida.

## Tráfico legítimo pesado

R04 contiene `large_ip_ratio_10s > 0` en 58/72 filas —80.5556 %— de 19/29 perfiles, con media 0.75720561, mediana 0.96037774 y rango 0–1. A nivel PCAP, 4,255,002/4,397,060 paquetes —96.769250 %— estuvieron entre 500 y 1,500 bytes.

R01–R04 acumulan ratio pesado no cero en 230/296 filas —77.702703 %— de 76 campañas. Las ventanas pequeñas de DNS, ICMP y errores se conservan. Esto amplía el rango legítimo solicitado por el jurado para que tamaño grande no equivalga por sí solo a ataque; no demuestra representatividad productiva ni separación frente a anomalías.

## Coincidencias y separación

R04 no contiene grupos de vectores repetidos dentro de su propia repetición. El diagnóstico global registra 27 coincidencias entre campañas: diecisiete internas de `train` y diez train↔validation. Las diez filas R04 `seen` son:

1. `DNS-MIXED-20-2/R04` ↔ R01;
2. `DNS-MIXED-50-10/R04` ↔ R01;
3. `DNS-VALID-10/R04` ↔ R01;
4. `HTTP-404-5/R04` ↔ R02;
5. `HTTP-MULTI-1/R04` ↔ R01;
6. `HTTP-MULTI-5/R04` ↔ R01;
7. `PING-100/R04` ↔ R03;
8. `TCP-REFUSED-5/R04` ↔ R03;
9. `UDP-25M/R04` ↔ R02;
10. `UDP-50M/R04` ↔ R01.

Son 10/72 ventanas —13.8889 %— y 10/29 episodios —34.4828 %— con al menos un vector visto. Son igualdades exactas de catorce valores, no copia de PCAP ni división de un episodio. Se preservan sin deduplicación post hoc y la calibración deberá reportar `seen`/`unseen` sin cambiar parámetros.

## Límites operativos

- Topología ESXi aislada, un Cliente y principalmente un Servidor; VIP son destinos lógicos.
- Escenarios deterministas: repetibilidad no equivale a representatividad.
- Las 72 ventanas de R04 proceden de 29 episodios y no son i.i.d.
- `UDP-50M/R04` reproduce el déficit receptor de un datagrama de R02 con secuencia PCAP íntegra y campos `lost=0`; la causa permanece abierta.
- Deltas Suricata, flows de preflight diferidos, inspección truncada y retransmisiones se preservan por campaña; no invalidaron integridad.
- R04 es normal pura: no permite precisión, recall, F1, AUC, TPR/FNR ni desempeño de detección.
- R05 permanece sin observar y no se usa para código, parámetros, umbral o depuración.

## Revisión y decisión

Claude ejecutó el agregador oficial y confirmó sin discrepancias 29/29, 72 filas, 4,397,060 paquetes, 390 observaciones de aplicación, 6,512,879,931 bytes PCAP, ninguna feature vacía, 27 coincidencias y diez cruces. Un primer comando tuvo un punto posicional inválido y una segunda sesión agotó el timeout interno; ambos fallaron sin modificar estado. La tercera usó sintaxis y timeout correctos.

**R04 GATE PASS Y CERRADO.** Se autoriza preparar un flujo de calibración atómico conforme a `PM-F1-v1`, con pruebas y revisión antes de ejecutarlo. No se autoriza iniciar R05. Como el ensamblador final exige 145/145, la preparación deberá seleccionar de forma versionada y auditable R01–R03 como `train` y R04 completa como `validation`, sin leer R05 ni cambiar el protocolo.
