# Diccionario causal de 14 features — G5

Fecha de diseño: 21 de julio de 2026. Esquema: `multilayer-v1`.

## Decisión de diseño

La unidad de observación deja de ser el flujo cerrado del MVP. Cada fila representa el comportamiento de una **IP iniciadora** hasta un instante `T`, emitido cada 10 segundos. Las ventanas son deslizantes y causales:

```text
(T - W, T]   con W ∈ {10, 30, 60} segundos
```

No se usa ningún paquete o evento posterior a `T`. Esto permite decidir sin esperar el timeout o cierre del flujo de Suricata y evita fuga temporal.

El vector mantiene exactamente 14 entradas para comparar de forma controlada con las 14 del MVP, pero cambia variables estáticas o tardías por comportamiento multicapa. Identificadores, etiquetas, timestamp, contadores de soporte y estado de elegibilidad no son entradas del modelo.

## Atribución por entidad

Un flujo PCAP se identifica por protocolo y extremos canónicos. Su iniciador es:

- TCP: quien envía el primer `SYN` sin `ACK`;
- UDP: quien envía el primer datagrama observado;
- ICMP echo: quien envía `echo request`;
- si la captura comienza a mitad de una conversación: el primer emisor observado, dejando esa limitación registrada.

Todos los paquetes de respuesta se atribuyen a la misma entidad iniciadora. En esta topología solo se emiten filas para `10.20.0.0/24`, es decir, Cliente o Kali; VM03 no genera una fila independiente por responder una descarga.

## Notación

Para entidad `e`, cierre `T` y ventana `W`:

- `P_W`: paquetes IPv4 atribuidos a `e`;
- `B_W`: suma de longitud total IPv4;
- `A_W`: nuevos intentos de flujo;
- `TCP_W`, `ICMP_W`: subconjuntos por protocolo;
- `SYN_W`: SYN salientes sin ACK;
- `SYNACK_W`: SYN-ACK entrantes;
- `RST_W`: paquetes TCP con RST;
- `HTTP_W`: transacciones HTTP EVE;
- `DNSQ_W`: consultas DNS EVE;
- `NX_W`: respuestas NXDOMAIN;
- `TLS_W`: sesiones únicas por `flow_id` o `community_id`.

Si el denominador de un ratio es cero, el valor es `0.0`. Los contadores de soporte se conservan como metadatos para distinguir “sin actividad” de una proporción real igual a cero.

## Vector v1

| # | Feature | Capa | Fórmula | Razón |
|---:|---|---|---|---|
| 1 | `packet_rate_10s` | L3 | `|P10| / 10` | intensidad de paquetes sin esperar cierre |
| 2 | `byte_rate_10s` | L3 | `B10 / 10` | intensidad de volumen |
| 3 | `mean_ip_len_10s` | L3 | `B10 / |P10|` | tamaño medio, comparable al MVP pero por ventana |
| 4 | `large_ip_ratio_10s` | L3 | `count(500 ≤ ip_len ≤ 1500) / |P10|` | incorpora explícitamente tráfico legítimo pesado solicitado por el jurado |
| 5 | `unique_dst_ip_ratio_30s` | L3 | `destinos únicos en A30 / |A30|` | distingue repetición hacia un servicio de exploración horizontal |
| 6 | `icmp_ratio_10s` | L3 | `|ICMP10| / |P10|` | representa cambios de protocolo y ráfagas ICMP |
| 7 | `flow_attempt_rate_10s` | L4 | `|A10| / 10` | frecuencia de conversaciones nuevas |
| 8 | `syn_rate_10s` | L4 | `|SYN10| / 10` | frecuencia causal de flags SYN solicitada por el jurado |
| 9 | `syn_completion_ratio_10s` | L4 | `min(|SYNACK10|, |SYN10|) / |SYN10|` | separa handshakes completados de SYN sin respuesta |
| 10 | `rst_ratio_10s` | L4 | `|RST10| / |TCP10|` | errores/rechazos TCP y puertos cerrados |
| 11 | `unique_dst_port_ratio_30s` | L4 | `puertos destino únicos / intentos TCP+UDP` | exploración vertical frente a conexiones repetidas |
| 12 | `http_error_ratio_60s` | L7 | `HTTP status ≥ 400 / |HTTP60|` | errores, recursos inexistentes, rate limit y 401/403 cuando exista autenticación HTTP |
| 13 | `dns_nxdomain_ratio_60s` | L7 | `|NX60| / |DNSQ60|` | consultas inválidas o generación de nombres anómalos |
| 14 | `tls_session_rate_60s` | L7 | `sesiones TLS únicas / 60` | frecuencia de handshakes cifrados visible sin descifrar payload |

El orden se fija en `configs/features/multilayer-v1.json`. El entrenamiento y la inferencia deben leer ese contrato; nunca seleccionar “todas las columnas numéricas” del CSV.

## Metadatos de auditoría, no features

Cada fila conserva:

- `campaign_id`, `entity_ip`, `window_end_utc`;
- `history_coverage_s`, `eligible_training`;
- `packet_count_10s`, `flow_attempt_count_30s`, `syn_count_10s`;
- `http_request_count_60s`, `dns_query_count_60s`.

Estos campos explican denominadores y trazabilidad, pero alimentarlos al modelo produciría duplicación, dependencia de identidad o fuga del diseño experimental.

## Historia mínima y valores faltantes

Una fila solo es elegible para entrenamiento si la captura llevaba al menos 60 segundos verificada al cerrar la ventana. El helper PCAP registra `verified_at`; las campañas finales usarán:

```bash
PPI_CAMPAIGN_WARMUP_SECONDS=60 scripts/campaign/run-f1.sh ...
```

Las calibraciones usan un segundo y producen filas `eligible_training=false`. No se rellenará una historia desconocida con ceros.

La ausencia de un evento dentro de una fuente disponible sí vale cero. Si PCAP, EVE o `verified_at` faltan, el wrapper falla y no genera un dataset aparentemente válido.

## Decisión sobre intentos fallidos de login

No se incluye un contador de fallos SSH dentro del vector pasivo v1 porque el resultado de autenticación está cifrado y Suricata EVE no puede observarlo. Asignar cero sería científicamente falso.

La capa 7 está representada por tres variables calculables: errores HTTP, NXDOMAIN y sesiones TLS. Los estados HTTP 401/403 cuentan dentro de `http_error_ratio_60s`. Si se integra de forma segura el journal SSH o el log de NGINX, `auth_failure_count_60s` se evaluará como feature candidata suplementaria y podrá sustituir a una variable solo después de prueba y ablación.

## Comparación crítica con el MVP

| Grupo MVP | Decisión v1 |
|---|---|
| paquetes/bytes por dirección | reemplazados por tasas causales de ventana; los contadores acumulados dependían del cierre del flujo |
| `duration` | excluida del núcleo online porque necesita conocer el final del flujo |
| ratios y tamaño medio | se conserva tamaño medio; la finalización SYN representa respuesta TCP sin esperar timeout |
| `is_tcp`, `is_udp`, `is_icmp` | se reemplazan por proporciones y comportamiento; tres one-hot redundantes consumían 3 de 14 posiciones |
| `dest_port` | se elimina como número ordinal; puerto 443 no es matemáticamente “mayor” que 80 en sentido conductual |
| `pkt_rate`, `byte_rate` | se conservan conceptualmente, pero con denominador fijo y causal de 10 s |

El MVP afirma que StandardScaler era necesario porque Isolation Forest usa distancias. Esa justificación es incorrecta: Isolation Forest es un ensamble de árboles con particiones aleatorias, no un método basado en distancia. La comparación futura probará explícitamente pipeline con y sin escalado; el scaler no se incluirá por tradición.

## Prevención de fuga y partición

1. Las ventanas solo miran hacia atrás.
2. La etiqueta de campaña se une después de extraer features y nunca entra al vector.
3. Todas las filas de una misma campaña pertenecen a una sola partición.
4. Campañas de calibración quedan fuera de entrenamiento, validación y prueba.
5. Scaler, selector e hiperparámetros se ajustan solo con R01–R03 `train`. El umbral operativo se calibra una vez con R04 normal completa y R05 queda retenida, conforme a `../fase04-modelado/01-protocolo-modelado-F1-v2.md`; esta regla sustituye la redacción histórica antes de observar R04.
6. Ventanas solapadas no se reparten aleatoriamente entre conjuntos.
7. Se reportan resultados por escenario y campaña, no solo por fila altamente correlacionada.

## Coste operacional

El prototipo offline usa biblioteca estándar de Python:

- lectura PCAP: `O(n)` paquetes;
- estado de atribución: `O(f)` flujos;
- implementación actual de ventanas: búsqueda directa, adecuada para validación pero no congelada para producción;
- versión online futura: colas por entidad y ventana, inserción/amortización `O(1)` y memoria proporcional a eventos de los últimos 60 s.

Antes de desplegar inferencia en VM02 se medirá latencia, CPU y RAM con las tasas máximas aceptadas en G2.

## Alcance del parser

`extract_multilayer.py` admite PCAP clásico, Ethernet, VLAN e IPv4 con TCP, UDP e ICMP. Rechaza magic, linktype o registros truncados. IPv6, PCAP-NG, fragmentación avanzada y capturas iniciadas a mitad de flujo quedan pendientes; no se interpretan silenciosamente.

## Criterio G5

G5 documental/prototipo pasa cuando:

- el esquema contiene exactamente 14 nombres y orden fijo;
- una prueba sintética verifica valores conocidos de L3/L4/L7;
- una prueba demuestra que un evento futuro no cambia la ventana anterior;
- DNS y HTTP reales producen valores coherentes;
- las calibraciones sin 60 s quedan no elegibles;
- una campaña nueva con `verified_at` pasa el wrapper y conserva hashes de entradas/salida.

El último punto requiere desplegar el helper actualizado y una nueva calibración corta antes de cerrar G5.
