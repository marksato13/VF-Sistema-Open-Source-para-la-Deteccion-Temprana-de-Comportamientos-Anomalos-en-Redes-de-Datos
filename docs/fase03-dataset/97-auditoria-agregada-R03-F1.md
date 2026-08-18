# Auditoría agregada de R03 — gate previo a R04

Fecha: 4 de agosto de 2026. Repetición: `R03`. Estado: **GATE PASS — APTO CON CONDICIONES PARA PREPARAR R04**.

## Alcance y reproducción

Esta auditoría cierra las tres repeticiones de entrenamiento de F1 normal. Distingue el volumen crudo de la unidad que recibirá el modelo: los paquetes producen features, pero no son millones de muestras independientes. Varias ventanas de un episodio comparten tráfico e historia causal.

```bash
PPI_ARTIFACTS_ROOT=/srv/ppi-evidence/artifacts \
.venv/bin/python scripts/dataset/build_f1_dataset.py --audit-only

PPI_ARTIFACTS_ROOT=/srv/ppi-evidence/artifacts \
.venv/bin/python scripts/analysis/summarize_f1_repetition.py \
  --repetition 3 \
  --require-complete
```

El agregador vuelve a aplicar integridad SHA-256, manifiesto, ledger, PCAP/EVE, CSV, Git, matriz, esquema, partición y dominio de las catorce features antes de resumir.

## Gate de colección

| Control | Resultado |
|---|---:|
| Commit auditado | `57276b5c74286adc2e0a26f776ccef23da1e88ab` |
| Matriz / esquema | `ad22ce5f8b41110b201f0eeacd2b5f13cc9f945c92cf539e9913e87fefdfa824` / `9ce86147ce4d0dab3c789e10edf23f2c7cefd2106b89e493bfafcf3a5ac0e1df` |
| Perfiles esperados / aceptados R03 | 29 / 29 |
| Repetición / partición | R03 / `train` |
| Campañas globales | 87 / 145 |
| Inválidas / advertencias | 0 / 0 |
| Faltantes | 58 = R04 + R05 |
| Git dirty | `false` |
| `repetition_complete` / `gate_pass` | `true` / `true` |

El gate certifica integridad y completitud de colección. No certifica suficiencia estadística, separabilidad ni rendimiento de un modelo. El dataset final conserva `ready_to_build=false` hasta completar las 145 celdas.

## Unidad real y volumen

| Métrica | R01 | R02 | R03 | Train acumulado |
|---|---:|---:|---:|---:|
| Episodios | 29 | 29 | 29 | 87 |
| Filas elegibles | 77 | 75 | 72 | 224 |
| Campañas de una fila | 7 | 8 | 9 | 24 |
| Campañas multiventana | 22 | 21 | 20 | 63 |
| Filas mín./mediana/máx. | 1 / 2 / 7 | 1 / 2 / 6 | 1 / 2 / 6 | 1 / 2 / 7 |
| Observaciones de paquete | 4,382,327 | 4,389,895 | 4,396,719 | 13,168,941 |
| Observaciones de aplicación | 390 | 390 | 390 | 1,170 |
| Bytes PCAP | 6,512,478,820 | 6,514,443,996 | 6,513,387,110 | 19,540,309,926 |

Los 19.54 GB crudos no convierten al experimento en millones de muestras estadísticas: el tamaño experimental actual son 87 episodios controlados y 224 ventanas autocorrelacionadas. No existe un criterio previo de potencia o suficiencia; por ello no se califica ese número como suficiente o insuficiente.

R03 distribuye sus 72 filas así:

| Escenario | Filas R03 |
|---|---:|
| `http` | 12 |
| `https` | 12 |
| `http-concurrent` | 11 |
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

Las diferencias 77→75→72 se localizan en conteos de ventanas emitidas, no en episodios faltantes. No prueban pérdida, mejora, regresión, equivalencia ni drift.

## Concentración y peso

Web/TLS estricto aporta 40/72 = **55.5556 %** de R03; al incluir MIXED-LIGHT son 43/72 = 59.7222 %. En train acumulado son 126/224 = 56.25 % y 135/224 = 60.267857 %, respectivamente. La proporción estricta descendió descriptivamente desde 57.142857 % en R01; no se declara tendencia ni mejora.

`HTTP-1GB`, `HTTPS-1GB` y `HTTP-C8` producen seis filas cada uno, 8.333333 % individual de R03. Los seis PCAP mayores —HTTPS-1GB, HTTP-1GB, HTTP-C8, HTTPS-500MB, HTTP-500MB y TCP-200M— suman 4,804,673,358 bytes, **73.766126 %** del almacenamiento R03.

Bytes PCAP no son peso directo del modelo. Sin embargo, una política por fila da más peso a episodios que cruzan más ventanas. La política preregistrada para R04/R05 está en `../05-plan-pruebas/18-congelamiento-protocolo-R04-R05.md`.

## Cobertura de las catorce features en R03

Ninguna dimensión quedó totalmente en cero:

| Capa | Feature | Rango R03 | Filas no cero | Campañas no cero |
|---|---|---:|---:|---:|
| L3 | `packet_rate_10s` | 0.6–18,401.5/s | 72 | 29 |
| L3 | `byte_rate_10s` | 31.2–25,952,308.4 B/s | 72 | 29 |
| L3 | `mean_ip_len_10s` | 50–1,494.65300537 B | 72 | 29 |
| L3 | `large_ip_ratio_10s` | 0–1 | 56 | 19 |
| L3 | `unique_dst_ip_ratio_30s` | 0–1 | 63 | 29 |
| L3 | `icmp_ratio_10s` | 0–1 | 5 | 2 |
| L4 | `flow_attempt_rate_10s` | 0–16.8/s | 31 | 29 |
| L4 | `syn_rate_10s` | 0–1.9/s | 24 | 23 |
| L4 | `syn_completion_ratio_10s` | 0–1 | 23 | 22 |
| L4 | `rst_ratio_10s` | 0–0.5 | 1 | 1 |
| L4 | `unique_dst_port_ratio_30s` | 0–1 | 58 | 27 |
| L7 | `http_error_ratio_60s` | 0–1 | 1 | 1 |
| L7 | `dns_nxdomain_ratio_60s` | 0–0.16666667 | 2 | 2 |
| L7 | `tls_session_rate_60s` | 0–0.33333333/s | 14 | 5 |

El acumulado train conserva soporte L7 no cero limitado: error HTTP 4/224 filas de tres campañas, NXDOMAIN 6/224 de seis campañas y TLS 43/224 de quince campañas. Los ceros son datos legítimos, pero la cobertura L7 de error es la más escasa.

El esquema sí responde estructuralmente a la observación multicapa del jurado: seis variables L3, cinco L4 y tres L7. No contiene intentos fallidos de login. SSH cifra la autenticación y esa señal exigiría integrar logs del host, código, diccionario y una nueva versión de dataset; no se fingirá que existe ni se modificará `v2` a mitad de F1.

## Tráfico legítimo pesado

R03 contiene `large_ip_ratio_10s > 0` en 56/72 filas de 19/29 perfiles, con media 0.72765574, mediana 0.95767482 y rango 0–1. La longitud media por ventana alcanza 1,494.65300537 bytes.

Train acumulado contiene ratio pesado no cero en 172/224 filas —76.785714 %—, equivalentes a 57 campañas o diecinueve perfiles repetidos tres veces. Su media es 0.72277721 y su mediana 0.95962882. Las 52 ventanas con ratio cero preservan DNS, ICMP y errores pequeños benignos.

Esto responde a la primera observación del jurado con cobertura controlada de paquetes grandes legítimos. No demuestra representatividad de producción, suficiencia universal ni separación frente a ataques.

## Comparación descriptiva de features

| Feature | Media R01 | Media R02 | Media R03 | Mediana R01 | Mediana R02 | Mediana R03 |
|---|---:|---:|---:|---:|---:|---:|
| `packet_rate_10s` | 5,691.33376623 | 5,853.19333333 | 6,106.55416667 | 4,118.1 | 3,906.2 | 4,614.85 |
| `byte_rate_10s` | 8,287,023.48051948 | 8,510,328.288 | 8,863,173.06944444 | 6,013,340.7 | 5,642,677.2 | 6,429,390.2 |
| `mean_ip_len_10s` | 1,096.61904614 | 1,100.01119950 | 1,108.92767766 | 1,434.20644220 | 1,444.54385336 | 1,433.55650770 |
| `large_ip_ratio_10s` | 0.71885947 | 0.72211604 | 0.72765574 | 0.95962639 | 0.96405035 | 0.95767482 |
| `unique_dst_ip_ratio_30s` | 0.49542883 | 0.49985630 | 0.50217274 | 0.5 | 0.5 | 0.5 |
| `icmp_ratio_10s` | 0.06493506 | 0.06666667 | 0.06944444 | 0 | 0 | 0 |
| `flow_attempt_rate_10s` | 0.51688312 | 0.53200000 | 0.55416667 | 0 | 0 | 0 |
| `syn_rate_10s` | 0.10649351 | 0.10933333 | 0.11388889 | 0 | 0 | 0 |
| `syn_completion_ratio_10s` | 0.31168831 | 0.29333333 | 0.31944444 | 0 | 0 | 0 |
| `rst_ratio_10s` | 0.01298701 | 0.01333333 | 0.00694444 | 0 | 0 | 0 |
| `unique_dst_port_ratio_30s` | 0.43647908 | 0.42600123 | 0.42524038 | 0.5 | 0.5 | 0.5 |
| `http_error_ratio_60s` | 0.02597403 | 0.01333333 | 0.01388889 | 0 | 0 | 0 |
| `dns_nxdomain_ratio_60s` | 0.00334514 | 0.00343434 | 0.00357744 | 0 | 0 | 0 |
| `tls_session_rate_60s` | 0.01038961 | 0.00733333 | 0.01180556 | 0 | 0 | 0 |

Estas medias dan igual peso a cada ventana, no a cada episodio. Son descriptivas: sin hipótesis, prueba y umbral predefinidos no autorizan afirmar equivalencia, estabilidad o drift.

## Coincidencias exactas y separación

R03 no contiene grupos repetidos dentro de la propia repetición. El diagnóstico global aumentó de siete a diecisiete coincidencias dentro de `train`. Las diez nuevas relaciones son:

1. `DNS-MIXED-20-2/R03` ↔ R01;
2. `DNS-MIXED-50-10/R03` ↔ R01;
3. `DNS-VALID-10/R03` ↔ R01;
4. `HTTP-404-5/R03` ↔ R02;
5. `HTTP-C2/R03` ↔ R02;
6. `HTTP-MULTI-1/R03` ↔ R01;
7. `HTTP-MULTI-5/R03` ↔ R01;
8. `PING-10/R03` ↔ `PING-100/R01`;
9. `UDP-10M/R03` ↔ R01;
10. `UDP-25M/R03` ↔ R01.

Son igualdades del vector, no prueba de causa, copia de PCAP o fuga. Todas pertenecen a `train`. El cero cruzado entre particiones es provisional y no informa sobre R04/R05 inexistentes.

Se preservan las filas y se separan episodios completos por repetición. No habrá deduplicación posterior a la observación. El resultado principal conservará todas las ventanas; la sensibilidad balanceada por episodio y el reporte de duplicados se predefinen antes de abrir validation.

## Límites y política iperf3

- Topología fija ESXi sin Internet, un Cliente y principalmente un Servidor; VIP son destinos lógicos, no diversidad física.
- Cargas deterministas y controladas; repetibilidad no equivale a representatividad.
- F1 es benigno puro; no existen aún anomalías, separabilidad, AUC, FPR/FNR ni umbral final.
- R01–R03 son `train`; R04 será `validation` y R05, `test` bloqueado para decisiones.
- No se construye ni entrena el dataset final con 87/145.

Iperf3 3.20 queda congelado para comparabilidad hasta R05. La discrepancia de un datagrama en UDP-50M/R02 permanece sin causa; R03 no la reprodujo y no la resuelve. Cada UDP futuro debe reconciliar extremos y secuencia PCAP. Una actualización exige una enmienda/versionado explícito o se evalúa después de R05.

## Revisión Claude y decisión

Claude emitió **APTO CON CONDICIONES** y exigió congelamiento más política explícita de duplicados antes de R04. Se corrigieron dos inferencias: las coincidencias no reciben causa determinista demostrada, y la concentración web/TLS no aumentó en R03.

El congelamiento y la política se registran en `../05-plan-pruebas/18-congelamiento-protocolo-R04-R05.md`.

**R03 APTO CON CONDICIONES Y CERRADO.** Se autoriza únicamente el preflight independiente de `F1N-DNS-VALID-10-R04`; no su ejecución. Antes de ejecutar R04 debe quedar predefinido el protocolo de modelado/selección que usará validation sin tocar R05.
