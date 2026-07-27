# Auditoría agregada de R01 — gate previo a R02

Fecha: 27 de julio de 2026. Repetición: `R01`. Estado: **GATE PASS — APTO CON CONDICIONES PARA R02**.

## Propósito

Completar 29 campañas no implica disponer de 29 muestras equilibradas. Cada campaña produce una o más ventanas de diez segundos según su duración y alineación UTC. Esta auditoría agrega únicamente campañas que primero pasan todos los gates del ensamblador: integridad SHA-256, manifiesto, ledger, PCAP/EVE, CSV, Git, matriz, esquema, partición y dominio de las 14 features.

Se implementó `scripts/analysis/summarize_f1_repetition.py` en `5beecf8` y se reforzó en `373fcba`. El auditor:

- exige repetición completa, Git limpio y ausencia de campañas inválidas o advertencias;
- rechaza cero filas y conteos de observaciones negativos;
- valida el orden declarado 1–14 del esquema;
- informa filas, escenarios, rangos y soporte no cero;
- distingue vectores repetidos dentro de campaña, entre campañas y entre particiones;
- conserva el total de coincidencias aunque el detalle se limite.

La suite creció de 29 a 39 pruebas y quedó completamente en `PASS`.

## Gate de colección

La ejecución reproducible fue:

```bash
PPI_ARTIFACTS_ROOT=/srv/ppi-evidence/artifacts \
.venv/bin/python scripts/analysis/summarize_f1_repetition.py \
  --repetition 1 \
  --require-complete
```

| Control | Resultado |
|---|---:|
| Commit del auditor | `373fcba35fd863a17de698567f3ea32e58954e5d` |
| Perfiles esperados / aceptados | 29 / 29 |
| Repetición / partición | R01 / `train` |
| Inválidas / advertencias | 0 / 0 |
| Duplicados exactos entre campañas | 0 |
| Duplicados exactos entre particiones | 0 |
| Git dirty | `false` |
| `gate_pass` | `true` |

El ensamblador global conserva 29 campañas aceptadas, 116 faltantes y dataset no construible. `gate_pass` autoriza continuar la recolección; no autoriza entrenar ni declarar desempeño.

## Unidad real y peso por campaña

R01 contiene 77 filas elegibles, no 29:

| Métrica | Valor |
|---|---:|
| Filas totales / elegibles | 77 / 77 |
| Campañas de una fila | 7 |
| Campañas multiventana | 22 |
| Filas por campaña mín./mediana/máx. | 1 / 2 / 7 |
| Observaciones de paquete subyacentes | 4,382,327 |
| Observaciones de aplicación | 390 |

Los millones de paquetes sirven para calcular features; el futuro modelo recibirá filas. La campaña con más ventanas, `HTTPS-1GB`, aporta 7/77 = 9.090909 % de R01. La duración produce distinto número de filas y, si se entrena sin una política consciente, también distinto peso por campaña.

| Escenario | Filas |
|---|---:|
| `https` | 14 |
| `http` | 13 |
| `http-concurrent` | 11 |
| `iperf-tcp` | 9 |
| `iperf-udp` | 9 |
| `ping` | 5 |
| `dns-valid` | 3 |
| `mixed-light` | 3 |
| `dns-mixed` | 2 |
| `http-missing` | 2 |
| `http-multi` | 2 |
| `https-sessions` | 2 |
| `tcp-refused` | 2 |

Los escenarios clasificados como HTTP, HTTPS, concurrencia, errores, multidestino y sesiones TLS suman 44/77 filas = 57.142857 %, sin contar `mixed-light`, que también incorpora un componente HTTP. No son un solo comportamiento —incluyen tamaños, cifrado, errores y concurrencia distintos—, pero la familia web/TLS tiene mayor representación por duración y variedad de perfiles. Esto debe evaluarse con sensibilidad por campaña antes del entrenamiento; no se corrige descartando evidencia después de verla.

## Cobertura de las 14 features

Ninguna feature queda totalmente en cero:

| Capa | Feature | Rango R01 | Filas no cero | Campañas no cero |
|---|---|---:|---:|---:|
| L3 | `packet_rate_10s` | 0.2–18,331.2/s | 77 | 29 |
| L3 | `byte_rate_10s` | 10–25,960,830.8 B/s | 77 | 29 |
| L3 | `mean_ip_len_10s` | 50–1,494.38524672 B | 77 | 29 |
| L3 | `large_ip_ratio_10s` | 0–1 | 59 | 19 |
| L3 | `unique_dst_ip_ratio_30s` | 0–1 | 65 | 29 |
| L3 | `icmp_ratio_10s` | 0–1 | 5 | 2 |
| L4 | `flow_attempt_rate_10s` | 0–11.4/s | 33 | 29 |
| L4 | `syn_rate_10s` | 0–1.5/s | 26 | 23 |
| L4 | `syn_completion_ratio_10s` | 0–1 | 24 | 22 |
| L4 | `rst_ratio_10s` | 0–0.5 | 2 | 1 |
| L4 | `unique_dst_port_ratio_30s` | 0–1 | 61 | 27 |
| L7 | `http_error_ratio_60s` | 0–1 | 2 | 1 |
| L7 | `dns_nxdomain_ratio_60s` | 0–0.16666667 | 2 | 2 |
| L7 | `tls_session_rate_60s` | 0–0.33333333/s | 15 | 5 |

Los valores cero también son observaciones válidas: por ejemplo, HTTP 200 implica ratio de error cero y DNS válido implica ratio NXDOMAIN cero. “Soporte no cero” no equivale a presencia total del protocolo.

RST, error HTTP y NXDOMAIN tienen soporte no cero escaso dentro de una sola repetición. Esto es esperable en F1 normal, donde los errores son legítimos y controlados; no justifica introducir ataques en el entrenamiento. Las repeticiones R02/R03 ampliarán su número de episodios sin cambiar el contrato.

## Observación del jurado: tráfico pesado

R01 cubre tráfico legítimo de 500–1500 bytes:

- `mean_ip_len_10s` alcanza 1,494.38524672 bytes;
- `large_ip_ratio_10s` cubre todo el rango 0–1;
- 59/77 filas de 19/29 campañas tienen proporción pesada mayor que cero;
- la mediana de `large_ip_ratio_10s` es 0.95962639;
- 18 filas pequeñas de DNS, ICMP, errores o colas se conservan y evitan enseñar que todo paquete pequeño es anomalía.

Esto responde **parcialmente y con evidencia** a la observación del jurado: R01 ya contiene un rango legítimo amplio. El objetivo final no se declara cumplido hasta recolectar R02/R03, medir variación y entrenar/evaluar el modelo sin fuga.

## Autocorrelación y duplicados

Existe un único grupo de vectores exactos repetidos dentro de una campaña:

```text
F1N-PING-100-R01  2026-07-27T15:36:10+00:00
F1N-PING-100-R01  2026-07-27T15:36:20+00:00
```

Son dos ventanas estables del mismo ping periódico. Los conteos crudos de ambas son 96 paquetes, longitud 84, ratio ICMP 1 y el resto del vector coincide; no es pérdida de precisión ni reutilización de PCAP.

Una coincidencia exacta de las 14 features entre campañas independientes tampoco prueba fuga por sí sola. La separación causal se hace por campaña y repetición: ningún episodio puede cruzar train, validation y test. El auditor reportará:

- coincidencias dentro de campaña como autocorrelación;
- coincidencias entre campañas como posible peso repetido;
- coincidencias entre particiones para análisis de sensibilidad.

No se eliminarán filas automáticamente después de observarlas. Antes de publicar métricas se compararán resultados conservando y colapsando vectores exactos, siempre sin mezclar campañas ni ajustar decisiones con el test.

## Revisión crítica de Claude

Claude declaró inicialmente `NO APTO`, pero sustentó esa decisión en hechos y umbrales no válidos:

- llamó calibración/dry-run a R01, que es `experiment/train`;
- afirmó que faltaba histograma pesado aunque existen 59 filas no cero y mediana 0.95962639;
- confundió `PING-10` con una duración de 0.24 s y trató ventanas fijas como adaptativas;
- inventó tolerancias ±5/±10 %, límites web de 35 %, cuotas L4 de 40 % y tiempos de 7–10 días;
- propuso reducir campañas ya congeladas e introducir ataques/SSH/LDAP/Kerberos dentro de F1;
- predijo falsos positivos/negativos antes de entrenar;
- recomendó MD5 y exclusión automática de coincidencias de features.

Se conservaron dos observaciones útiles: medir variación después de R02 y explicitar la política de coincidencias. No se adoptaron porcentajes ni cambios de matriz sin evidencia.

## Decisión y condiciones para R02

**R01 APTO CON CONDICIONES PARA INICIAR R02.**

1. Mantener matriz `v2`, generadores y esquema congelados; cambiar cualquiera rompería comparabilidad con R01.
2. Ejecutar preflight completo por campaña, sin lanzar los 29 perfiles de forma ciega.
3. Comenzar por `DNS-VALID-10/R02`, que pertenece a `train`.
4. Después de completar R02, repetir esta auditoría y comparar R01↔R02 por perfil de forma descriptiva, sin umbrales inventados.
5. No entrenar Isolation Forest con R01 aislada. R01–R03 forman la partición `train`.
6. Antes del entrenamiento, evaluar peso desigual de ventanas, correlación/escala y sensibilidad con agregación por campaña.
7. Mantener F2 como estrés legítimo y F3 como anomalías; no contaminar F1 normal con ataques.
8. Antes de métricas de validation/test, auditar coincidencias exactas y demostrar separación por campaña, no solo por valor de feature.

El siguiente paso operativo autorizado es el preflight de `F1N-DNS-VALID-10-R02`.
