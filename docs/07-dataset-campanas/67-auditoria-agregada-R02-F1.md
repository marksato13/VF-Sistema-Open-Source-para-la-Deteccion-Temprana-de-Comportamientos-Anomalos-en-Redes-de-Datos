# Auditoría agregada de R02 — gate previo a R03

Fecha: 28 de julio de 2026. Repetición: `R02`. Estado: **GATE PASS — APTO CON CONDICIONES PARA R03**.

## Alcance

Esta auditoría cierra la segunda repetición de F1 normal. No cuenta paquetes como si fueran muestras independientes: el futuro modelo recibe ventanas de features y varias ventanas pueden pertenecer al mismo episodio.

El resumen reutiliza primero todos los gates del ensamblador —SHA-256, manifiesto, ledger, PCAP/EVE, CSV, Git, matriz, esquema, partición y dominio de las 14 features— y solo después agrega campañas aceptadas.

La ejecución reproducible fue:

```bash
PPI_ARTIFACTS_ROOT=/srv/ppi-evidence/artifacts \
.venv/bin/python scripts/dataset/build_f1_dataset.py --audit-only

PPI_ARTIFACTS_ROOT=/srv/ppi-evidence/artifacts \
.venv/bin/python scripts/analysis/summarize_f1_repetition.py \
  --repetition 2 \
  --require-complete
```

No se ejecuta la construcción definitiva: faltan R03–R05 y `build_f1_dataset.py` debe negarse a construir con menos de 145 celdas válidas.

## Gate de colección

| Control | Resultado |
|---|---:|
| Commit auditado | `1eb421d7d41bc3c3bebd5b1ebf821817d35ef503` |
| Matriz / esquema | `ad22ce5f8b41110b201f0eeacd2b5f13cc9f945c92cf539e9913e87fefdfa824` / `9ce86147ce4d0dab3c789e10edf23f2c7cefd2106b89e493bfafcf3a5ac0e1df` |
| Perfiles esperados / aceptados R02 | 29 / 29 |
| Repetición / partición | R02 / `train` |
| Campañas aceptadas globales | 58 / 145 |
| Inválidas / advertencias | 0 / 0 |
| Calibraciones excluidas | 1 |
| Celdas faltantes | 87 = R03 + R04 + R05 |
| Git dirty | `false` |
| `repetition_complete` / `gate_pass` | `true` / `true` |

El gate demuestra integridad y completitud de R02. No demuestra detección de ataques, generalización ni rendimiento del Isolation Forest.

## Unidad real, volumen y peso

R02 contiene 75 filas elegibles procedentes de 29 episodios:

| Métrica | R01 | R02 | R02 − R01 |
|---|---:|---:|---:|
| Filas elegibles | 77 | 75 | −2 |
| Campañas de una fila | 7 | 8 | +1 |
| Campañas multiventana | 22 | 21 | −1 |
| Filas por campaña mín./mediana/máx. | 1 / 2 / 7 | 1 / 2 / 6 | — |
| Observaciones de paquete | 4,382,327 | 4,389,895 | +7,568 (+0.172694 %) |
| Observaciones de aplicación | 390 | 390 | 0 |
| Bytes PCAP | 6,512,478,820 | 6,514,443,996 | +1,965,176 (+0.030176 %) |

La diferencia de dos filas procede de la fase de ventanas UTC documentada por campaña. No existe un umbral predefinido para llamarla mejora, regresión o drift.

| Escenario | Filas R02 |
|---|---:|
| `http` | 14 |
| `https` | 13 |
| `http-concurrent` | 11 |
| `iperf-tcp` | 9 |
| `iperf-udp` | 9 |
| `ping` | 5 |
| `dns-valid` | 3 |
| `mixed-light` | 3 |
| `dns-mixed` | 2 |
| `http-multi` | 2 |
| `tcp-refused` | 2 |
| `http-missing` | 1 |
| `https-sessions` | 1 |

HTTP, HTTPS, concurrencia, errores, multidestino y sesiones TLS suman 42/75 = **56 %** de las filas; al incluir MIXED-LIGHT, que incorpora HTTP, son 45/75 = 60 %. Son comportamientos distintos, pero la familia web/TLS recibe más peso por cantidad de perfiles y duración.

`HTTP-1GB`, `HTTPS-1GB` y `HTTP-C8` aportan seis filas cada uno, 8 % individual. Los seis PCAP mayores suman 4,803,894,995 bytes, 73.742210 % del volumen R02. Bytes PCAP no equivalen al peso del modelo, pero muestran concentración de almacenamiento y tráfico subyacente. No se descartan campañas después de observarla; la política de peso debe definirse antes del entrenamiento.

## Cobertura de las 14 features

El esquema contiene seis features L3, cinco L4 y tres L7. Ninguna quedó totalmente en cero.

| Capa | Feature | Rango R02 | Filas no cero | Campañas no cero |
|---|---|---:|---:|---:|
| L3 | `packet_rate_10s` | 0.2–18,379.6/s | 75 | 29 |
| L3 | `byte_rate_10s` | 16.8–25,951,169.6 B/s | 75 | 29 |
| L3 | `mean_ip_len_10s` | 50–1,493.67790538 B | 75 | 29 |
| L3 | `large_ip_ratio_10s` | 0–1 | 57 | 19 |
| L3 | `unique_dst_ip_ratio_30s` | 0–1 | 64 | 29 |
| L3 | `icmp_ratio_10s` | 0–1 | 5 | 2 |
| L4 | `flow_attempt_rate_10s` | 0–18.8/s | 31 | 29 |
| L4 | `syn_rate_10s` | 0–2/s | 24 | 23 |
| L4 | `syn_completion_ratio_10s` | 0–1 | 22 | 22 |
| L4 | `rst_ratio_10s` | 0–0.5 | 2 | 1 |
| L4 | `unique_dst_port_ratio_30s` | 0–1 | 59 | 27 |
| L7 | `http_error_ratio_60s` | 0–1 | 1 | 1 |
| L7 | `dns_nxdomain_ratio_60s` | 0–0.16666667 | 2 | 2 |
| L7 | `tls_session_rate_60s` | 0–0.33333333/s | 14 | 5 |

Los ceros son datos válidos: HTTP 200, DNS `NOERROR`, ausencia de RST o una ventana posterior al establecimiento del flujo. Soporte no cero no equivale a presencia total del protocolo.

La cobertura L7 no cero es deliberadamente escasa en F1 normal y se concentra en errores legítimos controlados. El esquema no incluye intentos fallidos de login; la observación del jurado se responde mediante tres variables semánticas L7 distintas, no afirmando que exista telemetría de autenticación.

## Tráfico legítimo pesado

R02 amplía el rango de entrenamiento pedido por el jurado:

- 57/75 filas de 19/29 campañas tienen `large_ip_ratio_10s > 0`;
- la mediana es 0.96405035 y la media 0.72211604;
- el ratio recorre 0–1 y la longitud media por ventana alcanza 1,493.67790538 bytes;
- las 18 filas con ratio cero preservan DNS, ICMP y errores legítimos pequeños.

Esto demuestra presencia y variedad controlada de tráfico pesado benigno. No prueba representatividad de una población externa ni suficiencia para el modelo final.

## Comparación descriptiva R01↔R02

| Feature | Media R01 | Media R02 | Mediana R01 | Mediana R02 |
|---|---:|---:|---:|---:|
| `packet_rate_10s` | 5,691.33376623 | 5,853.19333333 | 4,118.1 | 3,906.2 |
| `byte_rate_10s` | 8,287,023.48051948 | 8,510,328.288 | 6,013,340.7 | 5,642,677.2 |
| `mean_ip_len_10s` | 1,096.61904614 | 1,100.01119950 | 1,434.20644220 | 1,444.54385336 |
| `large_ip_ratio_10s` | 0.71885947 | 0.72211604 | 0.95962639 | 0.96405035 |
| `unique_dst_ip_ratio_30s` | 0.49542883 | 0.49985630 | 0.5 | 0.5 |
| `icmp_ratio_10s` | 0.06493506 | 0.06666667 | 0 | 0 |
| `flow_attempt_rate_10s` | 0.51688312 | 0.53200000 | 0 | 0 |
| `syn_rate_10s` | 0.10649351 | 0.10933333 | 0 | 0 |
| `syn_completion_ratio_10s` | 0.31168831 | 0.29333333 | 0 | 0 |
| `rst_ratio_10s` | 0.01298701 | 0.01333333 | 0 | 0 |
| `unique_dst_port_ratio_30s` | 0.43647908 | 0.42600123 | 0.5 | 0.5 |
| `http_error_ratio_60s` | 0.02597403 | 0.01333333 | 0 | 0 |
| `dns_nxdomain_ratio_60s` | 0.00334514 | 0.00343434 | 0 | 0 |
| `tls_session_rate_60s` | 0.01038961 | 0.00733333 | 0 | 0 |

Las medias no están balanceadas por campaña: las campañas largas producen más filas. Las variables L7 escasas cambian su media cuando un episodio cruza un borde UTC y genera una o dos filas. Sin hipótesis, prueba y umbral predefinidos, la tabla es descriptiva y no autoriza afirmar estabilidad estadística, equivalencia o drift.

## Correlación y coincidencias exactas

R02 no contiene grupos de vectores exactos repetidos dentro de la repetición. El auditor global sí encuentra siete coincidencias exactas R01↔R02:

1. `DNS-MIXED-20-2`;
2. `DNS-MIXED-50-10`;
3. `DNS-VALID-10`;
4. `HTTP-MULTI-1`;
5. `HTTP-MULTI-5`;
6. `PING-100`;
7. `UDP-10M`.

Todas pertenecen a `train`; no se eliminan porque campañas independientes pueden producir el mismo vector discretizado. El conteo entre particiones es cero, pero R04 `validation` y R05 `test` aún no existen: cero no demuestra ausencia de coincidencias futuras.

Veintiuna campañas R02 producen más de una ventana. Sus filas comparten un episodio y memoria causal de 30/60 s, por lo que no son i.i.d. La separación futura debe hacerse por campaña/repetición completa, nunca dividiendo ventanas del mismo episodio entre particiones.

## Sesgos y límites que permanecen

- Topología fija en ESXi, sin Internet, con una entidad Cliente `10.20.0.20` y principalmente Servidor `10.30.0.10`; los VIP `.11/.12` amplían destinos lógicos, no diversidad física.
- F1 contiene tráfico benigno normal. Aún no se han ejecutado las campañas de anomalías ni se ha demostrado separabilidad.
- R01 y R02 son `train`; faltan R03 `train`, R04 `validation` y R05 `test`.
- Las cargas son deterministas y controladas. Repetibilidad funcional no equivale a representatividad productiva.
- HTTP/HTTPS y transferencias largas pesan más por duración; L7 de error tiene soporte no cero escaso.
- Las filas multiventana están correlacionadas.
- No se ha entrenado ni evaluado Isolation Forest; no existen todavía AUC, tasas de falsos positivos/negativos ni umbral final defendible.

## Control de versión iperf3

`UDP-50M/R02` reveló una discrepancia de un datagrama: emisor 86,331, receptor 86,330, campos de pérdida cero en iperf3 3.20 y secuencias completas en el PCAP del Sensor. La causa no está demostrada.

Para no introducir un factor de software a mitad de F1 se congela iperf3 3.20 en Cliente y Servidor durante R03–R05. Cada preflight debe verificar esa versión. Cada campaña UDP debe:

1. comparar bytes y datagramas emisor↔receptor;
2. no confiar en `lost_packets=0` si contradice otros campos;
3. auditar secuencias de datos en el PCAP, huecos y duplicados;
4. documentar cualquier discrepancia sin inventar tolerancia o localización.

Después de cerrar R05 se evaluará la actualización sincronizada a 3.21 en una fase versionada y con piloto excluido. Si se necesita actualizar antes, debe detenerse F1 y aprobarse una enmienda explícita; nunca cambiar silenciosamente entre repeticiones.

## Revisión crítica de Claude

Claude dictaminó **APTO CON CONDICIONES** y coincidió en preservar filas/duplicados, documentar sesgo/topología y resolver la política iperf3 antes de R03.

Se corrigieron:

- 56 % es la familia web/TLS estricta; 60 % incluye MIXED-LIGHT;
- soporte L7 escaso no demuestra que ataques L7 sean indetectables;
- 75 filas son un límite descriptivo, no “muestra pequeña” según un umbral inexistente;
- no existe plazo de 24 horas;
- no corresponde construir el dataset con 58/145, sino ejecutar `--audit-only`;
- no hace falta Pearson ni una “tabla de correlación” inventada para declarar que ventanas del mismo episodio están correlacionadas;
- no se predice AUC ni rendimiento;
- una actualización no permite sobrescribir o reintentar silenciosamente R02.

## Decisión y condiciones para R03

**R02 APTO CON CONDICIONES PARA CERRAR Y PREPARAR R03.**

1. Mantener congeladas matriz `v2`, esquema, generadores y topología.
2. Aplicar la política iperf3 3.20 y el refuerzo UDP anterior.
3. Ejecutar preflight independiente por campaña; no lanzar R03 en bloque.
4. Comenzar por `F1N-DNS-VALID-10-R03`, partición `train`, solo si todos sus gates pasan.
5. Preservar las 75 filas y siete coincidencias; no reponderar ni deduplicar después de observar resultados.
6. Antes de entrenar, predefinir escalado, peso por campaña y análisis de sensibilidad a ventanas/coincidencias.
7. Usar R04 `validation` solo conforme al protocolo predefinido para selección/ajuste; no usar R05 `test` para ajustar hiperparámetros, umbrales o decisiones.
8. No declarar el producto final ni desempeño del modelo hasta completar las 145 celdas, construir el dataset y ejecutar el protocolo de evaluación.

R02 queda cerrada. El siguiente paso autorizado no es entrenamiento ni ataque: es preparación y preflight de `DNS-VALID-10/R03`.
