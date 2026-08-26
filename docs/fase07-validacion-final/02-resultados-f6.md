# Resultados de la validación final F6 — motor + enforcement activos

- **Fecha:** 2026-08-18
- **Protocolo:** [`01-protocolo-f6.md`](01-protocolo-f6.md)
- **Datos crudos:** `results/f6/f6_resultados.jsonl` (pase 2, lag-aware) y `results/f6/f6_resultados.pass1-contaminado.jsonl` (pase 1); análisis con `scripts/f6/analyze_f6.py`.
- **Estado:** ejecutada (2 pases de 29 corridas + 2 pruebas de aislamiento). Hallazgo principal **confirmado con evidencia limpia**.

## Resumen ejecutivo

F6 midió el sistema **desplegado** (no solo el modelo offline). El resultado más importante es honesto y contradice parcialmente la métrica offline:

> **El FPR benigno de 4.71 % medido offline NO se sostiene sobre tráfico legítimo pesado en operación.** El modelo puntúa el tráfico legítimo de alto throughput justo en el margen del umbral, y algunas ventanas caen por debajo → falso positivo → bloqueo de un cliente legítimo. Esto ocurre **incluso en aislamiento** (sin contaminación entre corridas), y responde directamente a la observación del jurado sobre tráfico legítimo pesado.

Lo que **sí** funciona bien: los ataques que llegan al objetivo se detectan y bloquean en **~8 s** (lead-time mediano), el heurístico de fuerza bruta dispara en producción, y **no se registró ninguna caída de servicio** en las 58 corridas.

## 1. FPR operativo — el hallazgo principal

### Evidencia limpia de aislamiento (sin carryover entre corridas)

Cliente en silencio 95 s antes (features de 60 s en cero), una sola corrida:

| Escenario legítimo | Ventanas del modelo (scores) | Umbral | Resultado |
|---|---|---|---|
| `ping 100×0.5s` (ICMP sostenido) | 1.991, 1.931, 1.912 | 1.8126 | PERMIT (margen mínimo, ~0.10) |
| `iperf-tcp 200M×30s` (throughput al techo) | 1.968, 1.814, **1.689**, 1.92 | 1.8126 | **1 ventana ALERT → cliente bloqueado** |

El `iperf` legítimo a 200 Mbit/s (paquetes grandes, alto volumen: hasta 185 001 paquetes/ventana) produjo un **falso positivo genuino en aislamiento**: la ventana de score 1.689 cayó bajo el umbral y el motor **bloqueó al cliente legítimo 120 s**. Los scores del tráfico pesado se apiñan en 1.69–1.99, pegados al umbral 1.8126 — el modelo no separa con margen el tráfico legítimo pesado del anómalo.

### Bajo carga concurrente/sucesiva (campaña back-to-back)

Con corridas benignas seguidas (features de 60 s solapándose), el FPR sube por acumulación de estado entre flujos del mismo host:

| Pase | Ventanas benignas | ALERT | FPR |
|---|---|---|---|
| Pase 1 | 62 | 16 | 25.81 % |
| Pase 2 (lag-aware) | 74 | 17 | 22.97 % |

Escenarios que dispararon FP de forma reproducible en ambos pases: descarga pesada (`http 500MB`, `http-concurrent 4×100MB`), `iperf 200M`, `ping` sostenido. La contaminación entre corridas **infla** este número respecto al aislamiento, pero el aislamiento demuestra que el FP sobre tráfico pesado es **real, no solo un artefacto de la medición**.

### Interpretación honesta

- El FPR real depende fuertemente de la **concentración de tráfico por host**: un host con actividad legítima intensa o concurrente (lo normal en una red real) empuja los scores bajo el umbral.
- El offline 4.71 % se midió sobre las ventanas del dataset de test, que no incluían este régimen de carga pesada sostenida por IP.
- Consecuencia operativa medida: cuando el modelo marca FP, **bloquea al cliente legítimo 120 s**, lo que además cortó corridas benignas subsecuentes (p. ej. `https 100MB` falló al conectar por estar la IP bloqueada) — un efecto de denegación de servicio autoinfligida.

## 2. Detección y lead-time de ataques

Lead-time = segundos desde el inicio del ataque al primer `ALERT`/bloqueo (motor al día, pase 2):

| Familia | Detección observada | Lead-time | Detector |
|---|---|---|---|
| `udp-probe` | 3/3 | 7.3–8.2 s | `ocsvm_scaled` |
| `password-spray` | 2/2 | 6.1–7.2 s | **`auth_failure_heuristic`** (+ ocsvm) |
| `port-scan-wide` | detectado (reps 2–3 contaminadas) | 13.7 s | `ocsvm_scaled` |
| `tcp-syn-rate` | detectado (reps 2–3 contaminadas) | 8.1 s | `ocsvm_scaled` |
| `dns-entropy` | detectado (reps 2–3 contaminadas) | 8.7 s | `ocsvm_scaled` |

**Lead-time global: mediana 8.0 s, p95 8.7 s, rango 6.1–13.7 s.** Cuando el motor está al día, detecta y bloquea en ~8 s — bueno para un ciclo de 10 s.

**`auth_failure_heuristic` confirmado en producción:** `A-password-spray-2` se detectó **puramente** por el heurístico (3 ventanas, sin el modelo), lead 6.1 s. Valida en un ataque real el camino L7 del fix `MOTOR-FP-01`.

**Limitación de medición (declarada):** la tasa de detección **por familia** está contaminada por el propio enforcement: al detectar la repetición 1 se bloquea la IP de Kali 120 s, así que las repeticiones 2–3 (disparadas antes de que expire el bloqueo, pese al `unblock` entre corridas) no alcanzan el objetivo y figuran como "no detectadas". No es un fallo de detección: es el sistema **previniendo** ataques subsecuentes del mismo origen. La tasa de detección rigurosa es la de la **evaluación bloqueada offline** (88.3 % global); F6 confirma el camino de detección+bloqueo en tiempo real y su lead-time, no re-mide esa tasa.

## 3. Latencia y atraso del motor bajo carga

`logged_at − window_end` (cuánto tras cerrar la ventana se decide):

- Con el motor al día: ~10–15 s (dentro del ciclo).
- **Bajo tráfico pesado sostenido, el motor se atrasaba progresivamente: hasta 161 s observados.** Causa: el motor reparseaba el anillo de PCAP **completo** en cada ciclo, y con el anillo lleno de tráfico ese parseo excedía el presupuesto de 10 s, acumulando atraso hasta que el tráfico cesaba.
- **Corregido después de F6 (2026-08-19, debilidad #12):** parseo **incremental** — cada PCAP se decodifica una sola vez a un buffer; la atribución de flujo se recalcula sobre el buffer en memoria. Verificado en VM02: bajo una descarga de 500 MB el atraso se mantuvo en **7–15 s** (antes crecía sin límite), con CPU ~1 % y equivalencia byte a byte confirmada. Límite que queda: el caso extremo (iperf 200 Mbit/s concurrente sostenido) aún puede exceder el ciclo por el costo de `attribute_packets` sobre millones de paquetes/ventana; el sistema se recupera al cesar la carga.
- **Impacto:** bajo carga, la detección y el bloqueo se retrasan tanto como el atraso; el atacante corre libre ese tiempo. El lead-time de ~8 s aplica cuando el motor **no** está saturado.
- El pase 2 (lag-aware) espera a que el motor digiera cada corrida antes de la siguiente, por eso sus lead-times son limpios; el pase 1 (settle fijo) mezcló atraso y detección y por eso se archiva como contaminado.

## 4. Disponibilidad

**Cero caídas registradas.** Los tres servicios (`ppi-motor`, `ppi-motor-capture`,
`ppi-dashboard`) estuvieron activos y estables antes y después de **55 de las 58
corridas** (28 del pase 2 + 27 del pase 1), sin caídas ni reinicios.

> **Corrección respecto a la redacción anterior**, que decía «100 % en 57 corridas».
> Tres corridas —`A-password-spray-3` en ambos pases y `B10` en el pase 1— **no tienen
> medición de servicios**: sus campos `services_before` y `services_after` están vacíos.
> No es una caída, es una ausencia de registro. Lo defendible es «cero caídas
> registradas sobre 58 corridas, 55 con verificación explícita»; afirmar 100 % de
> disponibilidad verificada atribuye a la medición un alcance que no tuvo.

## 5. Frontera del heurístico de fuerza bruta (inconcluso, contaminado)

`api-auth-fail` desde un cliente **legítimo**:
- `H01` (4 fallos, bajo el umbral de 5 del heurístico): fue bloqueado igual, pero **por el modelo** (`ocsvm_scaled`), no por el heurístico — el modelo ya considera anómala una ráfaga de 401.
- `H02` (10 fallos, debería disparar el heurístico): quedó **contaminado** — `H01` bloqueó la IP del cliente y `H02` corrió con la IP aún bloqueada, sin que sus 401 llegaran al servidor. No concluyente.

Se declara como límite conocido y no resuelto de F6: medir la frontera exacta del heurístico exige espaciar las corridas más de 120 s (expiración del bloqueo), pendiente de una tanda dedicada.

## 6. Conclusiones y limitaciones declaradas

**Lo que F6 confirmó que funciona:**
- Detección + bloqueo inline en tiempo real, lead-time ~8 s con el motor al día.
- El heurístico de fuerza bruta dispara en producción (validación del camino L7 del fix `MOTOR-FP-01`).
- Cero caídas de servicio registradas en 58 corridas (55 con verificación explícita).

**Limitaciones reales medidas (para declarar ante el jurado, no ocultar):**
1. **FPR operativo sobre tráfico legítimo pesado** — el offline 4.71 % no se sostiene; hay FP genuinos (iperf 200M en aislamiento) porque el modelo puntúa el tráfico pesado en el margen del umbral. Es la debilidad más importante encontrada.
2. **Atraso del motor bajo carga** (hasta 161 s) por el reparseo del anillo completo por ciclo, agravado por el anillo de 240 s.
3. **Enforcement por IP** con bloqueo de 120 s: un FP corta al cliente legítimo y puede encadenar fallos; un TP previene ataques subsecuentes del mismo origen (lo cual sesga la tasa de detección por familia hacia abajo en la medición).

**Mejoras candidatas (NO implementadas sin recalibración/evaluación nueva):** ver [`../07-mejoras-futuras/01-debilidades-y-mejoras.md`](../07-mejoras-futuras/01-debilidades-y-mejoras.md) — recalibrar el umbral incluyendo tráfico pesado operativo, parseo incremental del anillo (solo PCAP nuevos por ciclo) en vez de reparsear todo, y evaluar si conviene volver al anillo de ~120 s.
