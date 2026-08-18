# Protocolo de validación final F6 — motor + enforcement activos

- **Fecha:** 2026-08-18
- **Estado:** ejecutada; resultados en `02-resultados-f6.md`.
- **Equivalente a:** la fase F6 del MVP anterior (validación con el motor activo), adaptada a la topología actual (VM01–VM05, nftables en el propio Sensor, extractor multilayer-v2 congelado).
- **Enlaza:** [`../fase05-motor-tiempo-real/01-diseno-motor-tiempo-real.md`](../fase05-motor-tiempo-real/01-diseno-motor-tiempo-real.md), [`../fase05-motor-tiempo-real/02-fp-ventana-sin-paquetes.md`](../fase05-motor-tiempo-real/02-fp-ventana-sin-paquetes.md), [`../fase04-modelado/06-modelo-final-congelado-ocsvm.md`](../fase04-modelado/06-modelo-final-congelado-ocsvm.md)

## 1. Qué mide y por qué

El modelo y su umbral se evaluaron offline (evaluación bloqueada de un solo paso: FPR benigno 4.71 %, detección global 88.3 %). Eso mide el **modelo**, no el **sistema desplegado**. F6 mide lo que solo se puede medir con el motor + enforcement corriendo de verdad contra tráfico real del laboratorio:

| Métrica | Definición operativa | Fuente |
|---|---|---|
| **FPR operativo** | fracción de ventanas de tráfico **benigno** que el motor marca `ALERT` | `motor_decision.log` real |
| **Tasa de detección** | fracción de corridas de **ataque** con ≥1 `ALERT` para la IP ofensora | idem |
| **Lead-time** | segundos desde el inicio del ataque al primer `ALERT` y al primer bloqueo | `logged_at` − inicio real |
| **Latencia de decisión** | `logged_at` − `window_end_utc` (cuánto tarda la decisión tras cerrar la ventana) | idem |
| **Disponibilidad** | fracción de corridas con los 3 servicios activos y estables antes/después | `systemctl is-active` |
| **Frontera del heurístico** | si un cliente **legítimo** que falla ≥5 logins dispara `auth_failure_heuristic` | idem |

No se captura dataset ni se tocan los CSV congelados: F6 solo **lee** el log del motor y genera tráfico ya calibrado con los generadores versionados (`ppi-run-benign` en VM05, `ppi-run-anomaly` en Kali VM04).

## 2. Matriz de corridas (29)

**Benignas — FPR (12), desde VM05 → entity `10.20.0.20`:**
`http 100MB/10M`, `http 500MB/20M`, `https 100MB/10M`, `http-concurrent 4×100MB/5M`, `dns-valid 100`, `dns-mixed 50/50`, `api-normal 50`, `https-sessions 50`, `ping 100×0.5s`, `mixed-light`, `http-multi 5`, `iperf-tcp 200M×30s`. Cubre la observación del jurado sobre **tráfico legítimo pesado con paquetes de 500–1500 bytes**.

**Frontera del heurístico (2), desde VM05:**
`api-auth-fail 4` (por debajo del umbral, no debe disparar) y `api-auth-fail 10` (por encima, **debe** disparar → FP declarado y esperado del heurístico, mismo tradeoff que el heurístico SSH del MVP).

**Ataque — detección + lead-time (15), desde Kali VM04 → entity `10.20.0.100`, 3 repeticiones × 5 familias:**
`tcp-syn-rate 50`, `port-scan-wide 1-1000`, `udp-probe 50`, `password-spray 50`, `dns-entropy 50`. Corresponden a las familias L3/L4/L7 del dataset.

## 3. Procedimiento por corrida (`scripts/f6/run_f6.py`)

1. Registrar la línea actual de `motor_decision.log` y el reloj de VM02 (para alinear con `logged_at`).
2. Disparar el escenario real vía SSH (VM05 o VM04), con timeout por corrida.
3. Esperar el asentamiento (25 s benignas, 30 s ataques) para que el motor procese las ventanas.
4. Extraer del log solo las decisiones de la IP iniciadora desde la línea marcada.
5. Calcular por corrida: nº de ventanas, nº `ALERT`, detectores usados, primer `ALERT`, primer bloqueo, latencia de decisión.
6. **Desbloquear** la IP objetivo al terminar (nftables) para que la siguiente corrida arranque en estado limpio.

Idempotente y trazable: cada corrida es una línea JSON en `results/f6/f6_resultados.jsonl`; la agregación (`scripts/f6/analyze_f6.py`) es reproducible desde ese archivo.

## 4. Estado de partida y condiciones

- Motor con el fix `MOTOR-FP-01` ya desplegado (sin el fix, las ventanas `pkts10=0` de tráfico benigno pesado darían `ALERT` espurio y contaminarían el FPR).
- `motor_decision.log` archivado antes de F6 (`.pre-f6-*`) para que las métricas partan de un log limpio.
- Los 3 servicios (`ppi-motor`, `ppi-motor-capture`, `ppi-dashboard`) activos; Suricata activo; NIC externas aisladas.

## 5. Limitaciones declaradas del método

- El asentamiento fijo puede no capturar ventanas muy tardías de una corrida; esas ventanas tardías son de tráfico ya decaído (`no_live_packets`/`empty_window` → `PERMIT`), así que no sesgan el FPR hacia abajo de forma engañosa, pero el denominador de ventanas por corrida es el realmente observado, no uno teórico.
- El tráfico benigno se genera con los perfiles calibrados del laboratorio; no pretende cubrir toda la diversidad de una red de producción real.
- Cada familia de ataque se ejecuta con un único perfil de intensidad por repetición (el ya calibrado), no un barrido de intensidades.
