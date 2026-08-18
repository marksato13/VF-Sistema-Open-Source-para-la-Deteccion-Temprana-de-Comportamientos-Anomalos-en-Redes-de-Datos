# Plan de expansión — variantes N1/N2 con parámetros ya calibrados

- **Fecha:** 2026-08-15
- **Autor:** Claude
- **Estado:** SOLO DISEÑO — nada ejecutado, `configs/campaigns/multilayer-v2-normal.json` sin modificar.
- **Decisión del usuario:** diseñar variantes nuevas antes de ejecutar, priorizando acercarse a la meta real de 2,000–3,000 ventanas del plan original (`160-plan-expansion-dataset-multicapa-v2.md`) en vez de solo repetir los 12 perfiles ya existentes.

## Realidad numérica de partida

Repetir los 12 perfiles actuales de 5 a 15 repeticiones (el mínimo que el propio plan pide) cuesta ~6.6 horas y produce solo ~270 ventanas — lejos de la meta. La razón: **cada episodio del mismo perfil con los mismos argumentos aporta poca información nueva** (ruido estadístico sobre la misma distribución), no diversidad real. El plan original ya lo decía: hacen falta escenarios *distintos* (N1: variabilidad L3/L4, N2: aplicación L7), no solo más copias.

## Criterio de diseño de esta expansión

Todos los perfiles propuestos abajo usan **combinaciones de argumentos que `scripts/f1/run-benign.sh` ya valida y acepta** (listas blancas existentes, sin tocar código, sin calibración nueva, sin riesgo de red no probado). Esto permite ejecutar de inmediato sin el ciclo de calibración que sí necesitaron `frag-udp` (fragmentación real) o el fix de `/api/error`. Se excluyen deliberadamente:

- **Duraciones >30s**: `require_duration()` en `run-benign.sh` solo acepta `{5,10,20,30}`. El plan original pedía hasta 60s; eso requeriría ampliar y volver a calibrar ese límite — no se hace aquí.
- **Más de 3 destinos reales**: solo existen las VIP `.10/.11/.12` en VM03. Agregar 4-8 destinos reales requiere cambios de infraestructura en el Servidor (nuevas VIP/certificados) — fuera de alcance de esta expansión.

Ambas limitaciones quedan como trabajo futuro, no bloquean lo que sí se puede hacer ahora.

## Perfiles nuevos propuestos (26)

Cada uno es una combinación `scenario`+`args` **no usada todavía** en `multilayer-v2-normal.json`, dentro de rangos ya blanqueados en `run-benign.sh`. Se agrupan por qué diversidad real aportan:

### Volumen/tasa TCP (iperf-tcp) — 4 nuevos
Actualmente solo existe `TCP-100M-V2` (100M, 20s). El espacio permitido es `{10M,25M,50M,100M,200M} × {5,10,20,30}s`.

| ID | args | Por qué |
|---|---|---|
| `TCP-10M-V2` | `["10M","20"]` | Extremo bajo de la escala de tasa — hoy solo hay un punto (100M). |
| `TCP-50M-V2` | `["50M","20"]` | Punto medio. |
| `TCP-200M-V2` | `["200M","20"]` | Techo calibrado (G2: 200 Mbit/s TCP). |
| `TCP-100M-SHORT-V2` | `["100M","5"]` | Misma tasa, duración corta — separa efecto de tasa vs. duración en `flow_duration_mean_30s`/`byte_rate_10s`. |

### Volumen/tasa UDP (iperf-udp) — 3 nuevos
Ningún perfil UDP puro existe hoy en la matriz v2 (solo aparece embebido dentro de `mixed-light`). Rango permitido: `{1M,10M,25M,50M} × {5,10,20,30}s`.

| ID | args | Por qué |
|---|---|---|
| `UDP-10M-V2` | `["10M","20"]` | Volumen UDP dedicado, sin HTTP/DNS mezclado. |
| `UDP-25M-V2` | `["25M","20"]` | Punto medio. |
| `UDP-50M-V2` | `["50M","20"]` | Techo calibrado (G2: 50 Mbit/s UDP). |

### Fragmentación con longitud distinta — 1 nuevo
`FRAG-UDP-V2` usa siempre `3000,10`. Repetirlo 15 veces da el mismo valor de `fragment_ratio_10s` una y otra vez (ya se observó: 0.9926–0.9968, muy poca varianza real). Un segundo punto con longitud distinta da variación genuina, no solo ruido de repetición.

| ID | args | Por qué |
|---|---|---|
| `FRAG-UDP-2000-V2` | `["2000","10"]` | Longitud de bloque distinta (2000 vs 3000 bytes) → grado de fragmentación distinto, variación real en `fragment_ratio_10s` en vez de repetir el mismo punto. |

### Concurrencia HTTP — 3 nuevos
Ningún perfil de concurrencia existe en v2 (`http-concurrent` sin usar). Solo 3 combinaciones están permitidas: `2/100MB/10M`, `4/100MB/5M`, `8/100MB/2M`.

| ID | args | Por qué |
|---|---|---|
| `HTTP-C2-V2` | `["2","100MB","10M"]` | Flujos concurrentes bajos — `flow_attempt_rate_10s`/`syn_rate_10s` con más de un flujo simultáneo, señal ausente hoy en la matriz v2 (existía en F1 v1 pero no se reincorporó a v2). |
| `HTTP-C4-V2` | `["4","100MB","5M"]` | Concurrencia media. |
| `HTTP-C8-V2` | `["8","100MB","2M"]` | Concurrencia alta — techo calibrado. |

### Diversidad de destino HTTP — 2 nuevos
`http-multi` no está en v2 (sí en F1 v1). Usa las 3 VIP existentes, sin infraestructura nueva.

| ID | args | Por qué |
|---|---|---|
| `HTTP-MULTI-1-V2` | `["1"]` | Una solicitud por VIP — `unique_dst_ip_ratio_30s` en su máximo (1.0) con volumen mínimo. |
| `HTTP-MULTI-5-V2` | `["5"]` | Cinco por VIP — mismo ratio de destino único, distinto volumen. `unique_dst_ip_ratio_30s` es de las features con mejor separación univariante encontrada en el diagnóstico de hoy; más episodios que la ejerciten con destino real fortalecen esa señal. |

### DNS — 5 nuevos
Actualmente `DNS-MULTI-10` (`dns-multi,10`) y `DNS-MIXED-V2` (`dns-mixed,20,2`, ratio NXDOMAIN fijo 10%). Rango permitido: `dns-multi∈{4,10,50,200}`, `dns-valid`/`dns-nxdomain` cualquier conteo 1-1000, `dns-mixed` cualquier par de conteos con suma ≤500.

| ID | args | Por qué |
|---|---|---|
| `DNS-MULTI-50-V2` | `["50"]` | Más consultas por episodio, mismo patrón round-robin de hostnames — más densidad de `dns_query_rate_60s`. |
| `DNS-VALID-20-V2` | `["dns-valid","20"]` | Solo consultas válidas, sin mezcla — punto de referencia limpio (`dns_nxdomain_ratio_60s=0` exacto) que hoy no existe como perfil propio en v2. |
| `DNS-MIXED-10-5-V2` | `["10","5"]` | Ratio NXDOMAIN distinto (5/15≈0.33) vs. el único punto actual (2/22≈0.09) — variación real del ratio, no repetición. |
| `DNS-MIXED-30-30-V2` | `["30","30"]` | Ratio NXDOMAIN 50/50 — tercer punto de la curva. |
| `DNS-MULTI-200-V2` | `["200"]` | Extremo alto de volumen DNS. |

### API — 4 nuevos
`API-NORMAL-20`/`API-5XX-V2` fijos en conteo 20. `API-AUTH-FAIL-20` fijo en 20. Rango permitido: `{4,10,20,50}`.

| ID | args | Por qué |
|---|---|---|
| `API-NORMAL-50-V2` | `["50"]` | Más solicitudes por episodio → más ocurrencias de `/api/error` en la rotación de 6 casos → más densidad de señal `http_status_5xx_ratio_60s` por ventana. |
| `API-AUTH-FAIL-4-V2` | `["4"]` | Extremo bajo — episodios cortos con `http_auth_failure_ratio_60s=1.0` pero menor volumen. |
| `API-AUTH-FAIL-50-V2` | `["50"]` | Extremo alto. |
| `API-NORMAL-4-V2` | `["4"]` | Episodios muy cortos — variación de `http_request_rate_60s` en el extremo bajo. |

### TLS sesiones — 2 nuevos
`HTTPS-SESSIONS-V2` fijo en 20. Rango permitido: 1-100.

| ID | args | Por qué |
|---|---|---|
| `HTTPS-SESSIONS-50-V2` | `["50"]` | Más sesiones por episodio → mayor `tls_session_rate_60s` por ventana. |
| `HTTPS-SESSIONS-100-V2` | `["100"]` | Techo permitido. |

### ICMP — 2 nuevos
`PING-V2` fijo en `10,0.5`. Rango permitido: conteo `{10,50,100}` × intervalo `{0.2,0.5,1}`.

| ID | args | Por qué |
|---|---|---|
| `PING-100-V2` | `["100","0.2"]` | Alto volumen, intervalo rápido — extremo opuesto al único punto actual. |
| `PING-50-SLOW-V2` | `["50","1"]` | Volumen medio, ritmo lento — episodio más largo en tiempo real sin más paquetes por segundo. |

## Total y estimación

**26 perfiles nuevos.** A 5 repeticiones cada uno (misma convención que los 12 ya existentes, no las 15 completas del plan — mantener esto acotado):

- 130 campañas nuevas.
- A ~187s/campaña (medido hoy): **~6.8 horas continuas**.
- Episodios nuevos: 130 (más los 8 que faltan de R02-R05 de `FRAG-UDP-V2`/`API-5XX-V2` = 138 episodios nuevos).
- Ventanas estimadas (con la razón observada ~1.5 ventanas/episodio): **~207 ventanas nuevas**.

**Total proyectado tras esta expansión:** 75 (actuales) + ~207 ≈ **~280 ventanas normales**, de **~188 episodios independientes** (50 actuales + 138 nuevos), cubriendo 38 perfiles distintos (12 actuales + 26 nuevos) en vez de 12.

Esto sigue sin alcanzar las 2,000–3,000 ventanas del plan original, pero es un salto real de diversidad (38 combinaciones distintas de tráfico legítimo en vez de 12) por un costo de tiempo similar al de solo repetir lo existente. Alcanzar 2,000-3,000 de verdad requeriría ampliar duraciones más allá de 30s (recalibrar) y/o agregar destinos reales nuevos (infraestructura) — ambos fuera de esta expansión.

## Siguiente paso

Pendiente de autorización para: (a) agregar estos 26 perfiles a `configs/campaigns/multilayer-v2-normal.json`, y (b) ejecutar — con la opción de acotar aún más (por ejemplo, empezar por un subconjunto prioritario en vez de los 26 completos) si 6.8 horas sigue pareciendo demasiado para esta sesión.
