# Plan de formalización v2.1 — cerrar `fragment_ratio_10s` y `http_status_5xx_ratio_60s` en el dataset oficial

- **Fecha:** 2026-08-14
- **Autor:** Claude
- **Estado:** **SOLO DISEÑO — nada de esto se ha ejecutado ni se ha modificado `configs/campaigns/multilayer-v2-normal.json`.** El usuario decidió explícitamente revisar el plan antes de autorizar la ejecución (que implica horas de campañas reales en el laboratorio).

## Por qué hace falta esto y no basta con las calibraciones ya hechas

Las calibraciones `CAL-G7-API-5XX-R02` y `CAL-FRAG-UDP-01-R01` demostraron que ambas señales son técnicamente alcanzables, pero **ninguna entra al dataset**: viven con `purpose=calibration`/`partition=excluded_calibration`, deliberadamente excluidas. Para que el modelo vea estas señales en entrenamiento/validación/test hace falta una matriz oficial de repeticiones (R01–R05), igual que los otros 10 perfiles ya congelados.

Verifiqué dos cosas antes de escribir este plan (sin ejecutar campañas, solo lectura/sondas puntuales):

1. **El fix de `/api/error` en VM03 es persistente**, no se revirtió tras la calibración: `curl http://10.30.0.10/api/error` devuelve `500` ahora mismo, y el archivo desplegado (`/usr/local/lib/ppi-api/ppi-api.py`) es idéntico byte a byte al versionado en `configs/server/ppi-api.py`.
2. **El perfil `API-NORMAL-20` ya existe en la matriz oficial y ya declara `http_status_5xx_ratio_60s` como feature cubierta**, pero sus 5 repeticiones (`F2N-API-NORMAL-20-R01-B`...`R05-B`) se ejecutaron **antes** del fix — confirmado en el CSV congelado: `http_error_ratio_60s=0.20` (sí hubo errores) pero `http_status_5xx_ratio_60s=0.00` en las 5 (el `/api/error` de esas corridas devolvía 404, no 500). No se puede "arreglar" esto retroactivamente sin recalcular el dataset ya congelado — hay que agregar un perfil nuevo.

## Perfiles nuevos propuestos

### 1. `FRAG-UDP-V2`

Basado en la calibración `CAL-FRAG-UDP-01-R01` (exitosa, `fragment_ratio_10s` = 0.99661877 / 0.99160749).

```json
{
  "id": "FRAG-UDP-V2",
  "scenario": "frag-udp",
  "args": ["3000", "10"],
  "estimated_pcap_bytes": 7000000,
  "stratum": "ip-fragmentation",
  "feature_coverage": ["fragment_ratio_10s"]
}
```

- `estimated_pcap_bytes` estimado a partir de la evidencia real de la calibración (6,584,488 bytes con parámetros de campaña simplificados, no la matriz oficial completa con `warmup_seconds=60`/`settle_seconds=9`) — dejar margen, ajustar tras el primer piloto si se decide correr uno.
- Requiere que `scripts/f1/run-benign.sh` en VM05 tenga el escenario `frag-udp` desplegado — **ya está** (lo desplegué y verifiqué durante la calibración de hoy, commit `3c2a1dc`).

### 2. `API-5XX-V2`

Mismo escenario que `API-NORMAL-20` (mismo generador, mismos argumentos), pero como perfil nuevo para que sus episodios no se mezclen con los ya congelados de `API-NORMAL-20` (que siguen siendo válidos como evidencia de tráfico normal — solo que sin 5xx real, lo cual también es información legítima, no un error a "corregir" retroactivamente).

```json
{
  "id": "API-5XX-V2",
  "scenario": "api-normal",
  "args": ["20"],
  "estimated_pcap_bytes": 300000,
  "stratum": "api-5xx",
  "feature_coverage": ["http_status_5xx_ratio_60s", "http_request_rate_60s", "http_method_entropy_60s"]
}
```

- No requiere ningún cambio de código — `run-benign.sh api-normal 20` ya incluye `/api/error` en su rotación de 6 casos (1 de cada 20 solicitudes cae en `GET /api/error`), y el servicio ya está corregido de forma persistente.
- Alternativa considerada y descartada: aumentar la frecuencia de `/api/error` en la rotación para una señal más fuerte por ventana. Se descarta porque cambiaría el comportamiento de `api-normal` para *ambos* perfiles (`API-NORMAL-20` y el nuevo), rompiendo la comparabilidad entre ellos sin necesidad — 1/6 ya demostró producir `0.15` en la calibración, señal suficiente para no ser constante.

## Lo que NO se propone tocar

- **`configs/campaigns/multilayer-v2-normal.json` no se modifica todavía** — los bloques JSON de arriba son una propuesta a copiar/pegar cuando se autorice, no un diff ya aplicado.
- **`tls_handshake_failure_ratio_60s` queda fuera de este plan.** Como documenté en `175-limite-tls-handshake-failure-ratio.md`, no hay una técnica confirmada con tráfico benigno controlado — no tiene sentido diseñar un perfil para una señal que no se sabe producir todavía.
- **Ningún episodio ya congelado se re-ejecuta, se borra ni se recalcula.** `API-NORMAL-20-R01..R05` permanecen exactamente como están; sus filas con `http_status_5xx_ratio_60s=0.0` son evidencia válida de tráfico normal sin errores de servidor, no un defecto a limpiar.

## Costo estimado de ejecución (si se autoriza)

Dos perfiles nuevos × 5 repeticiones (R01–R05, mismo esquema de partición que el resto: R01–R03→train, R04→validation, R05→test) = 10 campañas oficiales. Cada una requiere, por perfil de la matriz existente:

- Preflight versionado (`scripts/f1/preflight_profile.sh`) — gates de Git, NTP, SSH, NIC externas, bypass, Suricata, captura libre, servicios, firewall, listener, hash del generador.
- Warm-up de captura + escenario + `settle_seconds=9` + `cooldown_seconds=30` entre campañas.
- Auditoría (`scripts/dataset/audit_multilayer_v2.py`) tras cada repetición o al cerrar la matriz.

Basado en el ritmo histórico de campañas similares de este proyecto (perfiles de duración comparable, ~10 s de escenario), cada repetición completa —incluyendo preflight y cooldown— tomó entre 3 y 10 minutos en corridas anteriores documentadas. Estimación conservadora para 10 campañas: **entre 1 y 3 horas de trabajo activo en el laboratorio**, sin contar imprevistos (el mismo tipo de fallos transitorios de NTP/SSH que aparecieron hoy pueden repetirse).

## Siguiente paso

Pendiente de que el usuario autorice: (a) aplicar estos dos bloques a `configs/campaigns/multilayer-v2-normal.json`, y (b) lanzar la matriz — completa, o empezando por un piloto de 1 repetición por perfil como opción intermedia antes de comprometerse a las 5.
