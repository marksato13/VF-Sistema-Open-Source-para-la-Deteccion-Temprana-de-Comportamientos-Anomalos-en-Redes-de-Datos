# Diccionario científico de las 28 variables — `multilayer-v2`

> **Generado**, no redactado a mano: `scripts/entregables/generar_diccionario_features.py`.
>
> Las fórmulas se transcriben del extractor congelado y el script aborta si un
> nombre del contrato no aparece en él. Los rangos observados se calculan sobre
> las **1 552 ventanas** del dataset congelado.

Cierra el requisito del jurado de «diccionario, fórmulas, unidades y ventanas»
para las variables 15–28, que hasta ahora solo existían en el código.
El de las 14 primeras se mantiene en
[`01-diccionario-multicapa-G5.md`](01-diccionario-multicapa-G5.md).

## Unidad de observación
- Una fila por **IP iniciadora** y cierre de ventana `T`, emitida cada **10 s**.
- Ventanas deslizantes y **estrictamente causales**: `(T − W, T]` con `W ∈ {10, 30, 60}` s. Ningún paquete o evento posterior a `T` participa.
- Historia máxima considerada: **60 s**. Una fila solo es elegible para entrenamiento con 60 s de historia verificada.
- Identificadores, etiquetas, marca temporal y contadores de soporte **no son entradas del modelo**.

## Convenio de denominador cero
`safe_ratio(a, b) = a / b si b ≠ 0, en otro caso 0.0`. La consecuencia hay que declararla: **un 0.0 no distingue «sin actividad» de «proporción real igual a cero»**. Los contadores de soporte (`packet_count_10s`, `http_request_count_60s`, `dns_query_count_60s`, `tls_observation_count_60s`, `tcp_data_segment_count_10s`) se conservan como metadatos precisamente para desambiguarlo.

## Resumen
| # | Variable | Capa | Ventana | Unidad | Estado |
|---:|---|:--:|--:|---|---|
| 1 | `packet_rate_10s` | L3 | 10 s | `packets_per_second` | ✅ efectiva |
| 2 | `byte_rate_10s` | L3 | 10 s | `ip_bytes_per_second` | ✅ efectiva |
| 3 | `mean_ip_len_10s` | L3 | 10 s | `bytes` | ✅ efectiva |
| 4 | `large_ip_ratio_10s` | L3 | 10 s | `ratio` | ✅ efectiva |
| 5 | `unique_dst_ip_ratio_30s` | L3 | 30 s | `ratio` | ✅ efectiva |
| 6 | `icmp_ratio_10s` | L3 | 10 s | `ratio` | ✅ efectiva |
| 7 | `flow_attempt_rate_10s` | L4 | 10 s | `attempts_per_second` | ✅ efectiva |
| 8 | `syn_rate_10s` | L4 | 10 s | `syn_per_second` | ✅ efectiva |
| 9 | `syn_completion_ratio_10s` | L4 | 10 s | `ratio` | ✅ efectiva |
| 10 | `rst_ratio_10s` | L4 | 10 s | `ratio` | ✅ efectiva |
| 11 | `unique_dst_port_ratio_30s` | L4 | 30 s | `ratio` | ✅ efectiva |
| 12 | `http_error_ratio_60s` | L7 | 60 s | `ratio` | ✅ efectiva |
| 13 | `dns_nxdomain_ratio_60s` | L7 | 60 s | `ratio` | ✅ efectiva |
| 14 | `tls_session_rate_60s` | L7 | 60 s | `sessions_per_second` | ✅ efectiva |
| 15 | `ttl_mean_10s` | L3 | 10 s | `ip_ttl_mean` | ✅ efectiva |
| 16 | `fragment_ratio_10s` | L3 | 10 s | `ratio` | ✅ efectiva |
| 17 | `protocol_diversity_30s` | L3 | 30 s | `ratio` | ✅ efectiva |
| 18 | `tcp_retransmission_ratio_10s` | L4 | 10 s | `ratio` | ✅ efectiva |
| 19 | `flow_duration_mean_30s` | L4 | 30 s | `seconds` | ✅ efectiva |
| 20 | `tx_rx_byte_ratio_30s` | L4 | 30 s | `ratio` | ✅ efectiva |
| 21 | `http_request_rate_60s` | L7 | 60 s | `requests_per_second` | ✅ efectiva |
| 22 | `http_method_entropy_60s` | L7 | 60 s | `bits` | ✅ efectiva |
| 23 | `http_auth_failure_ratio_60s` | L7 | 60 s | `ratio` | ✅ efectiva |
| 24 | `dns_query_rate_60s` | L7 | 60 s | `queries_per_second` | ✅ efectiva |
| 25 | `unique_dns_name_ratio_60s` | L7 | 60 s | `ratio` | ✅ efectiva |
| 26 | `tls_handshake_failure_ratio_60s` | L7 | 60 s | `ratio` | 🔴 no observable |
| 27 | `tls_version_ratio_60s` | L7 | 60 s | `ratio` | ✅ efectiva |
| 28 | `http_status_5xx_ratio_60s` | L7 | 60 s | `ratio` | ✅ efectiva |

**28 variables definidas · 27 con variación observable · 1 no observable.**

---

## Notación
Para la entidad `e` y el cierre `T`, sobre la ventana `W`:

- `P_W` paquetes IPv4 atribuidos a `e`
- `B_W` suma de `total_length` IPv4; `B^tx` saliente, `B^rx` entrante
- `A_W` intentos de flujo nuevos (primer paquete de una clave canónica)
- `TCP_W` subconjunto TCP; `TCPD_W` segmentos TCP con carga > 0
- `SYN_W` SYN salientes sin ACK; `SYNACK_W` SYN-ACK entrantes
- `F_W` flujos distintos con al menos un paquete en la ventana
- `HTTP_W`, `DNSQ_W`, `NX_W`, `TLS_W` eventos EVE de cada tipo

---

## Fichas

### Capa 3 — `L3`

#### 1. `packet_rate_10s`

$$ \|P_{10}\| / 10 $$

| | |
|---|---|
| **Ventana** | 10 s |
| **Unidad** | `packets_per_second` |
| **Tipo y rango teórico** | float ≥ 0 |
| **Fuente exacta** | PCAP · cuenta de paquetes IPv4 atribuidos |
| **Denominador** | constante 10 s |
| **Denominador cero** | no aplica (constante) |
| **Rango observado** | mín 0.2000 · máx 21210.9000 · media 1882.0822 · mediana 1466.6500 |
| **Observabilidad** | completa |
| **Coste en línea** | O(n) por ventana |
| **Estado** | efectiva |

#### 2. `byte_rate_10s`

$$ B_{10} / 10 $$

| | |
|---|---|
| **Ventana** | 10 s |
| **Unidad** | `ip_bytes_per_second` |
| **Tipo y rango teórico** | float ≥ 0 |
| **Fuente exacta** | PCAP · campo `total_length` de la cabecera IPv4 |
| **Denominador** | constante 10 s |
| **Denominador cero** | no aplica (constante) |
| **Rango observado** | mín 10.0000 · máx 29027968.0000 · media 2730763.5938 · mediana 2176084.2000 |
| **Observabilidad** | completa |
| **Coste en línea** | O(n) |
| **Estado** | efectiva |

#### 3. `mean_ip_len_10s`

$$ B_{10} / \|P_{10}\| $$

| | |
|---|---|
| **Ventana** | 10 s |
| **Unidad** | `bytes` |
| **Tipo y rango teórico** | float ≥ 0 |
| **Fuente exacta** | PCAP · `total_length` IPv4 |
| **Denominador** | $\|P_{10}\|$ |
| **Denominador cero** | 0.0 · ventana sin paquetes |
| **Rango observado** | mín 32.0000 · máx 1495.4244 · media 1138.9064 · mediana 1471.2677 |
| **Observabilidad** | completa |
| **Coste en línea** | O(n) |
| **Estado** | efectiva |

#### 4. `large_ip_ratio_10s`

$$ \|\{p \in P_{10} : 500 \le len(p) \le 1500\}\| / \|P_{10}\| $$

| | |
|---|---|
| **Ventana** | 10 s |
| **Unidad** | `ratio` |
| **Tipo y rango teórico** | float ∈ [0,1] |
| **Fuente exacta** | PCAP · `total_length` IPv4 |
| **Denominador** | $\|P_{10}\|$ |
| **Denominador cero** | 0.0 · ventana sin paquetes |
| **Rango observado** | mín 0.0000 · máx 1.0000 · media 0.7505 · mediana 0.9811 |
| **Observabilidad** | completa |
| **Coste en línea** | O(n) |
| **Estado** | efectiva · exigida por el jurado para tráfico legítimo pesado |

#### 5. `unique_dst_ip_ratio_30s`

$$ \|\{peer(a) : a \in A_{30}\}\| / \|A_{30}\| $$

| | |
|---|---|
| **Ventana** | 30 s |
| **Unidad** | `ratio` |
| **Tipo y rango teórico** | float ∈ [0,1] |
| **Fuente exacta** | PCAP · IP destino del primer paquete de cada flujo |
| **Denominador** | $\|A_{30}\|$ |
| **Denominador cero** | 0.0 · ventana sin intentos nuevos |
| **Rango observado** | mín 0.0000 · máx 1.0000 · media 0.1471 · mediana 0.0000 |
| **Observabilidad** | completa |
| **Coste en línea** | O(n) + conjunto O(f) |
| **Estado** | efectiva |

#### 6. `icmp_ratio_10s`

$$ \|\{p \in P_{10} : proto = 1\}\| / \|P_{10}\| $$

| | |
|---|---|
| **Ventana** | 10 s |
| **Unidad** | `ratio` |
| **Tipo y rango teórico** | float ∈ [0,1] |
| **Fuente exacta** | PCAP · campo `protocol` IPv4 |
| **Denominador** | $\|P_{10}\|$ |
| **Denominador cero** | 0.0 · ventana sin paquetes |
| **Rango observado** | mín 0.0000 · máx 1.0000 · media 0.0335 · mediana 0.0000 |
| **Observabilidad** | completa |
| **Coste en línea** | O(n) |
| **Estado** | efectiva |

### Capa 4 — `L4`

#### 7. `flow_attempt_rate_10s`

$$ \|A_{10}\| / 10 $$

| | |
|---|---|
| **Ventana** | 10 s |
| **Unidad** | `attempts_per_second` |
| **Tipo y rango teórico** | float ≥ 0 |
| **Fuente exacta** | PCAP · primer paquete de cada clave canónica de flujo |
| **Denominador** | constante 10 s |
| **Denominador cero** | no aplica (constante) |
| **Rango observado** | mín 0.0000 · máx 100.0000 · media 1.8784 · mediana 0.0000 |
| **Observabilidad** | completa |
| **Coste en línea** | O(n) + diccionario O(f) |
| **Estado** | efectiva |

#### 8. `syn_rate_10s`

$$ \|SYN_{10}\| / 10 $$

| | |
|---|---|
| **Ventana** | 10 s |
| **Unidad** | `syn_per_second` |
| **Tipo y rango teórico** | float ≥ 0 |
| **Fuente exacta** | PCAP · `SYN` activo y `ACK` inactivo, en sentido saliente |
| **Denominador** | constante 10 s |
| **Denominador cero** | no aplica (constante) |
| **Rango observado** | mín 0.0000 · máx 100.0000 · media 1.5670 · mediana 0.0000 |
| **Observabilidad** | completa |
| **Coste en línea** | O(n) |
| **Estado** | efectiva · exigida por el jurado como señal L4 |

#### 9. `syn_completion_ratio_10s`

$$ \min(\|SYNACK_{10}\|, \|SYN_{10}\|) / \|SYN_{10}\| $$

| | |
|---|---|
| **Ventana** | 10 s |
| **Unidad** | `ratio` |
| **Tipo y rango teórico** | float ∈ [0,1] |
| **Fuente exacta** | PCAP · SYN salientes y SYN-ACK entrantes |
| **Denominador** | $\|SYN_{10}\|$ |
| **Denominador cero** | 0.0 · ventana sin SYN salientes |
| **Rango observado** | mín 0.0000 · máx 1.0000 · media 0.1598 · mediana 0.0000 |
| **Observabilidad** | completa |
| **Coste en línea** | O(n) |
| **Estado** | efectiva · el `min` acota el ratio a 1 cuando llegan SYN-ACK de SYN anteriores a la ventana |

#### 10. `rst_ratio_10s`

$$ \|\{p \in TCP_{10} : RST\}\| / \|TCP_{10}\| $$

| | |
|---|---|
| **Ventana** | 10 s |
| **Unidad** | `ratio` |
| **Tipo y rango teórico** | float ∈ [0,1] |
| **Fuente exacta** | PCAP · bit `RST` de la cabecera TCP |
| **Denominador** | $\|TCP_{10}\|$ |
| **Denominador cero** | 0.0 · ventana sin paquetes TCP |
| **Rango observado** | mín 0.0000 · máx 0.5000 · media 0.0164 · mediana 0.0000 |
| **Observabilidad** | completa |
| **Coste en línea** | O(n) |
| **Estado** | efectiva |

#### 11. `unique_dst_port_ratio_30s`

$$ \|\{port(a) : a \in A_{30}, port > 0\}\| / \|\{a \in A_{30} : port > 0\}\| $$

| | |
|---|---|
| **Ventana** | 30 s |
| **Unidad** | `ratio` |
| **Tipo y rango teórico** | float ∈ [0,1] |
| **Fuente exacta** | PCAP · puerto destino del primer paquete del flujo |
| **Denominador** | intentos TCP/UDP con puerto destino > 0 |
| **Denominador cero** | 0.0 · ventana sin intentos con puerto |
| **Rango observado** | mín 0.0000 · máx 1.0000 · media 0.1496 · mediana 0.0000 |
| **Observabilidad** | completa |
| **Coste en línea** | O(n) + conjunto |
| **Estado** | efectiva |

### Capa 7 — `L7`

#### 12. `http_error_ratio_60s`

$$ \|\{h \in HTTP_{60} : status \ge 400\}\| / \|HTTP_{60}\| $$

| | |
|---|---|
| **Ventana** | 60 s |
| **Unidad** | `ratio` |
| **Tipo y rango teórico** | float ∈ [0,1] |
| **Fuente exacta** | EVE · `http.status` |
| **Denominador** | $\|HTTP_{60}\|$ |
| **Denominador cero** | 0.0 · ventana sin transacciones HTTP |
| **Rango observado** | mín 0.0000 · máx 1.0000 · media 0.0389 · mediana 0.0000 |
| **Observabilidad** | solo HTTP en claro; HTTPS no es observable sin descifrar |
| **Coste en línea** | O(e) |
| **Estado** | efectiva |

#### 13. `dns_nxdomain_ratio_60s`

$$ \|NX_{60}\| / \|DNSQ_{60}\| $$

| | |
|---|---|
| **Ventana** | 60 s |
| **Unidad** | `ratio` |
| **Tipo y rango teórico** | float ∈ [0,1] |
| **Fuente exacta** | EVE · `dns.rcode == NXDOMAIN` en respuestas, atribuido por `dest_ip` |
| **Denominador** | $\|DNSQ_{60}\|$ |
| **Denominador cero** | 0.0 · ventana sin consultas DNS |
| **Rango observado** | mín 0.0000 · máx 1.0000 · media 0.0204 · mediana 0.0000 |
| **Observabilidad** | solo DNS en claro |
| **Coste en línea** | O(e) |
| **Estado** | efectiva |

#### 14. `tls_session_rate_60s`

$$ \|\{flow\_id(t) : t \in TLS_{60}\}\| / 60 $$

| | |
|---|---|
| **Ventana** | 60 s |
| **Unidad** | `sessions_per_second` |
| **Tipo y rango teórico** | float ≥ 0 |
| **Fuente exacta** | EVE · `flow_id`, con respaldo en `community_id` y en el timestamp |
| **Denominador** | constante 60 s |
| **Denominador cero** | no aplica (constante) |
| **Rango observado** | mín 0.0000 · máx 1.6667 · media 0.0150 · mediana 0.0000 |
| **Observabilidad** | no requiere descifrar; cuenta sesiones, no contenido |
| **Coste en línea** | O(e) + conjunto |
| **Estado** | efectiva |

### Capa 3 — `L3`

#### 15. `ttl_mean_10s`

$$ \left(\sum_{p \in P_{10}} ttl(p)\right) / \|P_{10}\| $$

| | |
|---|---|
| **Ventana** | 10 s |
| **Unidad** | `ip_ttl_mean` |
| **Tipo y rango teórico** | float ∈ [0,255] |
| **Fuente exacta** | PCAP · campo `TTL` IPv4 |
| **Denominador** | $\|P_{10}\|$ |
| **Denominador cero** | 0.0 · ventana sin paquetes |
| **Rango observado** | mín 54.3750 · máx 64.0000 · media 63.0533 · mediana 63.0178 |
| **Observabilidad** | completa · en esta topología revela saltos de router |
| **Coste en línea** | O(n) |
| **Estado** | efectiva |

#### 16. `fragment_ratio_10s`

$$ \|\{p \in P_{10} : MF \lor offset > 0\}\| / \|P_{10}\| $$

| | |
|---|---|
| **Ventana** | 10 s |
| **Unidad** | `ratio` |
| **Tipo y rango teórico** | float ∈ [0,1] |
| **Fuente exacta** | PCAP · bit *More Fragments* y campo *fragment offset* IPv4 |
| **Denominador** | $\|P_{10}\|$ |
| **Denominador cero** | 0.0 · ventana sin paquetes |
| **Rango observado** | mín 0.0000 · máx 0.9970 · media 0.0128 · mediana 0.0000 |
| **Observabilidad** | completa |
| **Coste en línea** | O(n) |
| **Estado** | efectiva · dejó de ser constante tras la calibración de fragmentación IP real; ver `docs/fase03-dataset/174-cierre-calibracion-fragmentacion-ip-real.md` |

#### 17. `protocol_diversity_30s`

$$ \|\{proto(p) : p \in P_{30}\}\| / \|P_{30}\| $$

| | |
|---|---|
| **Ventana** | 30 s |
| **Unidad** | `ratio` |
| **Tipo y rango teórico** | float ∈ (0,1] |
| **Fuente exacta** | PCAP · campo `protocol` IPv4 |
| **Denominador** | $\|P_{30}\|$ |
| **Denominador cero** | 0.0 · ventana sin paquetes |
| **Rango observado** | mín 0.0000 · máx 0.5000 · media 0.0062 · mediana 0.0000 |
| **Observabilidad** | completa |
| **Coste en línea** | O(n) |
| **Estado** | efectiva · **normalizada por paquetes, no por protocolos**: tiende a 0 cuando el volumen crece, así que mide diversidad *por paquete*, no riqueza de protocolos |

### Capa 4 — `L4`

#### 18. `tcp_retransmission_ratio_10s`

$$ \|\{p \in TCPD_{10} : seq\ visto\}\| / \|TCPD_{10}\| $$

| | |
|---|---|
| **Ventana** | 10 s |
| **Unidad** | `ratio` |
| **Tipo y rango teórico** | float ∈ [0,1] |
| **Fuente exacta** | PCAP · número de secuencia TCP repetido en la misma dirección |
| **Denominador** | $\|TCPD_{10}\|$ |
| **Denominador cero** | 0.0 · ventana sin segmentos TCP con carga |
| **Rango observado** | mín 0.0000 · máx 0.1250 · media 0.0008 · mediana 0.0006 |
| **Observabilidad** | heurística por `seq` repetido: no distingue retransmisión de duplicado de captura |
| **Coste en línea** | O(n) + conjunto por dirección |
| **Estado** | efectiva |

#### 19. `flow_duration_mean_30s`

$$ \left(\sum_{f} \max_{p \in f} (t_p - t_{inicio(f)})\right) / \|F_{30}\| $$

| | |
|---|---|
| **Ventana** | 30 s |
| **Unidad** | `seconds` |
| **Tipo y rango teórico** | float ≥ 0 (segundos) |
| **Fuente exacta** | PCAP · marca temporal del primer paquete de cada flujo |
| **Denominador** | flujos distintos con al menos un paquete en la ventana |
| **Denominador cero** | 0.0 · ventana sin flujos |
| **Rango observado** | mín 0.0000 · máx 511.5502 · media 125.9290 · mediana 72.1394 |
| **Observabilidad** | **duración hasta `T`, no duración final**: se calcula sin esperar el cierre, por diseño causal |
| **Coste en línea** | O(n) + diccionario por flujo |
| **Estado** | efectiva |

#### 20. `tx_rx_byte_ratio_30s`

$$ B^{tx}_{30} / (B^{tx}_{30} + B^{rx}_{30}) $$

| | |
|---|---|
| **Ventana** | 30 s |
| **Unidad** | `ratio` |
| **Tipo y rango teórico** | float ∈ [0,1] |
| **Fuente exacta** | PCAP · sentido del paquete respecto a la entidad iniciadora |
| **Denominador** | B^{tx}_{30} + B^{rx}_{30} |
| **Denominador cero** | 0.0 · ventana sin bytes |
| **Rango observado** | mín 0.0001 · máx 1.0000 · media 0.2212 · mediana 0.0007 |
| **Observabilidad** | completa |
| **Coste en línea** | O(n) |
| **Estado** | efectiva · normalizada al total, no un cociente tx/rx: evita la división por cero y acota el rango |

### Capa 7 — `L7`

#### 21. `http_request_rate_60s`

$$ \|HTTP_{60}\| / 60 $$

| | |
|---|---|
| **Ventana** | 60 s |
| **Unidad** | `requests_per_second` |
| **Tipo y rango teórico** | float ≥ 0 |
| **Fuente exacta** | EVE · eventos `event_type = http` con `src_ip` en la red de entidades |
| **Denominador** | constante 60 s |
| **Denominador cero** | no aplica (constante) |
| **Rango observado** | mín 0.0000 · máx 0.8333 · media 0.0307 · mediana 0.0000 |
| **Observabilidad** | solo HTTP en claro |
| **Coste en línea** | O(e) |
| **Estado** | efectiva |

#### 22. `http_method_entropy_60s`

$$ -\sum_{m} p_m \log_2 p_m,\quad p_m = \|\{h : method = m\}\| / \|HTTP_{60}\| $$

| | |
|---|---|
| **Ventana** | 60 s |
| **Unidad** | `bits` |
| **Tipo y rango teórico** | float ≥ 0 (bits) |
| **Fuente exacta** | EVE · `http.http_method`, normalizado a mayúsculas |
| **Denominador** | $\|HTTP_{60}\|$ |
| **Denominador cero** | 0.0 · ventana sin transacciones HTTP |
| **Rango observado** | mín 0.0000 · máx 1.9219 · media 0.0222 · mediana 0.0000 |
| **Observabilidad** | solo HTTP en claro |
| **Coste en línea** | O(e) + conteo por método |
| **Estado** | efectiva · **0.0 es ambiguo**: significa tanto «sin peticiones» como «todas del mismo método»; se desambigua con `http_request_count_60s` |

#### 23. `http_auth_failure_ratio_60s`

$$ \|\{h \in HTTP_{60} : status \in \{401, 403\}\}\| / \|HTTP_{60}\| $$

| | |
|---|---|
| **Ventana** | 60 s |
| **Unidad** | `ratio` |
| **Tipo y rango teórico** | float ∈ [0,1] |
| **Fuente exacta** | EVE · `http.status` |
| **Denominador** | $\|HTTP_{60}\|$ |
| **Denominador cero** | 0.0 · ventana sin transacciones HTTP |
| **Rango observado** | mín 0.0000 · máx 1.0000 · media 0.0347 · mediana 0.0000 |
| **Observabilidad** | **solo HTTP**. Los fallos de autenticación SSH van cifrados y no aparecen en EVE: asignarles cero sería falso |
| **Coste en línea** | O(e) |
| **Estado** | efectiva · es la señal L7 semántica exigida por el jurado, y la que dispara el heurístico del motor |

#### 24. `dns_query_rate_60s`

$$ \|DNSQ_{60}\| / 60 $$

| | |
|---|---|
| **Ventana** | 60 s |
| **Unidad** | `queries_per_second` |
| **Tipo y rango teórico** | float ≥ 0 |
| **Fuente exacta** | EVE · `dns.type = request` |
| **Denominador** | constante 60 s |
| **Denominador cero** | no aplica (constante) |
| **Rango observado** | mín 0.0000 · máx 3.3333 · media 0.0512 · mediana 0.0000 |
| **Observabilidad** | solo DNS en claro |
| **Coste en línea** | O(e) |
| **Estado** | efectiva |

#### 25. `unique_dns_name_ratio_60s`

$$ \|\{rrname(q) : q \in DNSQ_{60}, rrname \ne \emptyset\}\| / \|DNSQ_{60}\| $$

| | |
|---|---|
| **Ventana** | 60 s |
| **Unidad** | `ratio` |
| **Tipo y rango teórico** | float ∈ [0,1] |
| **Fuente exacta** | EVE · `dns.rrname`, con respaldo en `dns.queries[0].rrname`, en minúsculas |
| **Denominador** | $\|DNSQ_{60}\|$ |
| **Denominador cero** | 0.0 · ventana sin consultas DNS |
| **Rango observado** | mín 0.0000 · máx 1.0000 · media 0.0241 · mediana 0.0000 |
| **Observabilidad** | solo DNS en claro |
| **Coste en línea** | O(e) + conjunto |
| **Estado** | efectiva · detecta generación algorítmica de nombres |

#### 26. `tls_handshake_failure_ratio_60s`

$$ \|\{t \in TLS_{60} : version = \emptyset\}\| / \|TLS_{60}\| $$

| | |
|---|---|
| **Ventana** | 60 s |
| **Unidad** | `ratio` |
| **Tipo y rango teórico** | float ∈ [0,1] |
| **Fuente exacta** | EVE · ausencia del campo `tls.version` |
| **Denominador** | $\|TLS_{60}\|$ |
| **Denominador cero** | 0.0 · ventana sin eventos TLS |
| **Rango observado** | mín 0.0000 · máx 0.0000 · media 0.0000 · mediana 0.0000 |
| **Observabilidad** | **no observable en esta configuración**: Suricata 8.0.3 no emite el evento `tls` intermedio de un handshake fallido, así que el numerador nunca puede ser distinto de cero |
| **Coste en línea** | O(e) |
| **Estado** | **NO OBSERVABLE** · constante 0.0 en las 1 552 ventanas. Ver `docs/fase03-dataset/175-limite-tls-handshake-failure-ratio.md` |

#### 27. `tls_version_ratio_60s`

$$ \|\{t : \text{«1.3»} \in version(t)\}\| / \|\{t \in TLS_{60} : version \ne \emptyset\}\| $$

| | |
|---|---|
| **Ventana** | 60 s |
| **Unidad** | `ratio` |
| **Tipo y rango teórico** | float ∈ [0,1] |
| **Fuente exacta** | EVE · subcadena «1.3» en `tls.version` |
| **Denominador** | eventos TLS con versión conocida |
| **Denominador cero** | 0.0 · ventana sin eventos TLS con versión |
| **Rango observado** | mín 0.0000 · máx 1.0000 · media 0.0754 · mediana 0.0000 |
| **Observabilidad** | no requiere descifrar |
| **Coste en línea** | O(e) |
| **Estado** | efectiva · **coincidencia por subcadena**, no comparación semántica de versiones |

#### 28. `http_status_5xx_ratio_60s`

$$ \|\{h \in HTTP_{60} : 500 \le status \le 599\}\| / \|HTTP_{60}\| $$

| | |
|---|---|
| **Ventana** | 60 s |
| **Unidad** | `ratio` |
| **Tipo y rango teórico** | float ∈ [0,1] |
| **Fuente exacta** | EVE · `http.status` |
| **Denominador** | $\|HTTP_{60}\|$ |
| **Denominador cero** | 0.0 · ventana sin transacciones HTTP |
| **Rango observado** | mín 0.0000 · máx 0.1600 · media 0.0010 · mediana 0.0000 |
| **Observabilidad** | solo HTTP en claro |
| **Coste en línea** | O(e) |
| **Estado** | efectiva · **subconjunto de `http_error_ratio_60s`**, que ya incluye ≥ 400: redundancia declarada |

---

## Valores faltantes
El dataset **no tiene valores faltantes**, y no por relleno: la ausencia de un evento dentro de una fuente disponible vale cero legítimamente. Si falta el PCAP, el EVE o la marca `verified_at`, el envoltorio **falla** en vez de producir un dataset aparentemente válido. Una historia desconocida nunca se rellena con ceros: la fila queda `eligible_training = false`.

## Limitaciones declaradas
- **`tls_handshake_failure_ratio_60s` no es observable** en esta configuración. Debe reportarse como **27 variables efectivas de 28 definidas**, no como una señal validada.
- **`http_status_5xx_ratio_60s` es subconjunto de `http_error_ratio_60s`.** Redundancia conocida; su aporte marginal solo puede resolverlo la ablación pendiente (D-02).
- **`protocol_diversity_30s` se normaliza por paquetes, no por protocolos.** Tiende a cero al crecer el volumen: mide diversidad por paquete, no riqueza.
- **`http_method_entropy_60s` colapsa dos casos en 0.0**: sin peticiones y monomé­todo. Solo el contador de soporte los separa.
- **Las señales L7 solo ven tráfico en claro.** HTTPS y los fallos de autenticación SSH quedan fuera por diseño, no por omisión.
- **`tcp_retransmission_ratio_10s` es una heurística** por número de secuencia repetido: no separa retransmisión real de duplicado de captura.
