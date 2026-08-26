# Protocolo de modelado `PM-multilayer-v2-v1` y hoja de ruta del sistema completo

- **Fecha:** 2026-08-17
- **Autor:** Claude
- **Estado:** ⚠️ **DOCUMENTO HISTÓRICO — SUPERADO.** Este protocolo se definió el 17 de agosto de 2026 y describe un diseño que **no es el que finalmente se ejecutó**.

> **No usar como referencia del sistema vigente.** Conserva propuestas que
> quedaron descartadas: umbrales por índice de Youden (τ1/τ2), un nivel `LIMIT`
> intermedio y bloqueo con `enforce.sh`. El sistema desplegado usa **un único
> umbral OCSVM de 1,8126**, decisiones `PERMIT`/`ALERT`/`BLOCK` **sin nivel
> intermedio**, y bloqueo con **nftables** en el propio Sensor.
>
> Se conserva sin editar porque reescribir un protocolo pasado para que
> coincida con lo que se hizo falsearía el registro. El estado vigente está en
> [`06-modelo-final-congelado-ocsvm.md`](06-modelo-final-congelado-ocsvm.md) y
> en la [model card](../dataset/MODEL_CARD_OCSVM.md).

## Por qué este documento

El usuario pidió planificar el mejor flujo posible para el sistema completo, sólido, usando como referencia (a) la planificación ya existente de este mismo repositorio y (b) el MVP anterior ya defendido (`sistema-implementable`, repo separado). Revisé ambos antes de escribir esto — no es un plan improvisado.

## Lo que ya existe y se reutiliza

**De este repo:**
- `docs/fase01-diseno-experimental/01-diseno-defendible.md`: fases F0-F4 con puertas de decisión G0-G9, criterio train=solo normal/test=separado, ablación L3/L4/L7, split por sesión no aleatorio.
- `docs/fase04-modelado/01-protocolo-modelado-F1-v2.md` (`PM-F1-v1`, congelado 2026-08-04): protocolo estadístico ya validado para el dataset anterior (14 features) — Isolation Forest principal con hiperparámetros fijos, LOF/OCSVM como comparadores (nunca reemplazan a IF por ganar una métrica), regla de umbral por cuantil (`alpha=0.05` en validación, desigualdad estricta), evaluación bloqueada en un solo paso por partición, sensibilidad por semilla/ponderación/colapso de duplicados, gates de ejecución explícitos.
- `scripts/modeling/calibrate_pm_f1_v1.py` (776 líneas, ya implementado y probado): código real de ese protocolo — validación de candidatos por hash, salida atómica, seis pipelines (IF ventana/escalado/expandido por campaña/colapsado + LOF + OCSVM), diez semillas.

**Del MVP** (`sistema-implementable`, revisado solo lectura):
- Umbrales fijados por índice de Youden (τ1) y FPR≤2% (τ2) sobre ROC — método simple y defendible, alternativa a la regla de cuantil de PM-F1-v1. Se documenta como opción, no se adopta automáticamente (ver decisión abajo).
- `motor_decision.py`: motor en tiempo real que hace tail del EVE con detección de rotación, un solo hilo para el scoring. **Lección crítica:** el MVP duplicó manualmente la función de extracción de features entre entrenamiento y motor — riesgo real de deriva si se edita una sin la otra. En este proyecto **no se debe repetir ese error**: el motor debe importar y reusar `scripts/features/extract_multilayer_v2.py` directamente, no reescribir su lógica.
- `enforce.sh` + lógica de bloqueo: doble umbral (PERMIT/LIMIT/BLOCK), bloqueo progresivo con memoria entre reinicios (5min→30min→permanente), whitelist de IPs, todo vía SSH a la VM del servidor — patrón directamente adaptable a este proyecto (SSH a VM03, nftables en vez de iptables/ipset).
- **Tres detectores heurísticos que corren en paralelo al modelo ML, no lo reemplazan** — brute-force SSH, abuso HTTP, port-scan. El port-scan está documentado explícitamente como parche a un punto ciego real: el IF del MVP puntuaba por flujo individual, y un escaneo manda 1-2 paquetes por puerto, cayendo dentro del rango normal por flujo. **Nota importante para este proyecto:** nuestras 28 features ya son agregados por ventana (10s/60s), no por flujo — `unique_dst_port_ratio_30s` existe específicamente para capturar diversidad de puertos a nivel ventana. Es posible que este punto ciego del MVP ya esté resuelto por diseño en multilayer-v2; se verificará empíricamente con las nuevas campañas de `port-scan`/`port-scan-wide` reales de Kali, no se asume.
- Dashboard: lector simple del log del motor, sin tocar modelo ni enforcement directamente — patrón simple, se reutiliza la idea.
- Validación final tipo F6: 40 corridas con el motor **activo**, midiendo FPR, latencia, disponibilidad, lead-time — se adapta como última fase antes de declarar el sistema cerrado.
- `docs/respuestas_asesor/`: Q&A pre-armadas con citas de papers (Liu et al. 2008/2012, NIST SP 800-94) para el mismo asesor de este proyecto. Recomiendo revisarlas aparte para preparar la defensa — no es parte de este documento.

## Decisión: qué se adopta y qué no

- **Se adopta** la estructura completa de PM-F1-v1 (3 modelos, hiperparámetros congelados, evaluación en un solo paso, sensibilidades) porque ya está validada en este mismo proyecto y evita repetir errores ya corregidos (ej. la fuga de selección de features que encontré y arreglé el 2026-08-14).
- **No se adopta** el método de umbral del MVP (Youden/FPR≤2%) como método principal — se mantiene la regla de cuantil `alpha=0.05` de PM-F1-v1 por continuidad metodológica dentro de este proyecto. Se reportará Youden como comparación informativa (ambos métodos son legítimos; reportar los dos fortalece la defensa).
- **Se adopta** la arquitectura de motor+enforcement+heurísticos+dashboard+validación final del MVP, adaptada a la topología actual (nftables, SSH a VM03, nombres de VM actuales) — pero **solo después** de tener modelo y umbral congelados. No se construye el motor en paralelo a la calibración del modelo.

## `PM-multilayer-v2-v1` — protocolo de modelado

### Datos (dataset consolidado `180-consolidacion-dataset-v2-ampliado.md`)

| Partición | Episodios | Ventanas | Uso permitido |
|---|---|---|---|
| `train` | 132 | 824 | ajustar modelo y preprocesamiento |
| `validation` | 44 | 273 | calibrar umbral, una sola vez |
| `test` | 44 | 276 | estimar FPR benigno, una sola vez |
| `evaluation_only` (anomalías) | 132 | 179 (161 Kali real + 18 heredadas) | detección, evaluado una sola vez, con modelo y umbral ya congelados |

### Modelos (idénticos a PM-F1-v1, sin grid search)

```text
IsolationForest(n_estimators=500, max_samples="auto", contamination="auto",
                 max_features=1.0, bootstrap=False, random_state=20260817,
                 n_jobs=1, warm_start=False)   # principal, SIN escalar
LocalOutlierFactor(n_neighbors=20, novelty=True, contamination="auto", n_jobs=1)  # comparador, escalado
OneClassSVM(kernel="rbf", gamma="scale", nu=0.05, cache_size=200)  # comparador, escalado
```

`StandardScaler` se ajusta solo con `train`, igual que antes. Ninguna decisión de qué modelo "gana" se toma antes de ver `test`+anomalías; el IF sin escalar sigue siendo la conclusión principal salvo que este documento se revise explícitamente con una razón documentada.

### Regla de umbral (idéntica a PM-F1-v1)

`alpha=0.05` sobre los 273 scores de `validation`, desigualdad estricta, `k=floor(0.05*273)=13`. Con 273 ventanas la resolución ya no tiene el problema de `n<20` que limitaba R04 del dataset anterior.

### Orden de ejecución bloqueado

1. Ajustar los 3 modelos + sensibilidades (10 semillas, ponderación por campaña, colapso de vectores exactos) solo con `train`.
2. Calcular scores de `validation`, fijar umbral. Congelar hashes antes de mirar ejemplos extremos.
3. Puntuar `test` una sola vez → FPR benigno.
4. Puntuar las 179 ventanas de `evaluation_only` una sola vez, con modelo+umbral ya congelados → detección por familia de ataque, por ventana y por episodio. Reportar el desglose Kali-real (161) vs. heredado (18) por separado.
5. Validación honesta adicional (no reemplaza el paso 2-4, es diagnóstico secundario): *leave-one-episode-out* sobre las anomalías, igual que diseñé el 2026-08-14 para evitar la fuga de selección de features — solo si se explora selección de features o ajuste adicional después del resultado principal.
6. Si el resultado motiva cambiar features, modelo o umbral: se versiona como `PM-multilayer-v2-v2` y se recolecta evaluación nueva no observada — nunca se reabre `test` ni `evaluation_only` ya puntuados.

### Verificación específica pendiente (no asumida)

¿`unique_dst_port_ratio_30s` (agregado por ventana) ya resuelve el punto ciego de port-scan que el MVP necesitó parchar con un heurístico? Se responde con los resultados reales de las familias `ANOM-KALI-PORT-SCAN`/`ANOM-KALI-PORT-SCAN-WIDE` en el paso 4 — si el modelo las detecta bien, no hace falta heurístico extra para eso; si no, se diseña un heurístico complementario (nunca un reemplazo del score ML) para esa familia específica, exactamente como hizo el MVP.

## Hoja de ruta completa del sistema (después de este protocolo)

```text
[HOY]     1. PM-multilayer-v2-v1: calibrar y comparar los 3 modelos  ← siguiente paso inmediato
          2. Documentar resultado (detección por familia, FPR, qué modelo gana y por qué)
          3. Decisión: ¿algún heurístico complementario hace falta? (basado en 1, no antes)
[DESPUÉS] 4. Motor de decisión en tiempo real (VM02):
             - reusa scripts/features/extract_multilayer_v2.py directamente (no duplicar lógica)
             - tail de eve.json con detección de rotación
             - carga modelo+umbral+heurísticos ya congelados
          5. Enforcement inline (SSH a VM03, nftables):
             - whitelist de IPs de gestión/infraestructura
             - bloqueo progresivo con memoria entre reinicios
          6. Dashboard simple (lector del log del motor)
          7. Validación final con motor ACTIVO (equivalente a F6 del MVP):
             - N corridas normales + N mixtas, motor corriendo de verdad
             - métricas: FPR operativo, latencia, disponibilidad, lead-time de detección
          8. Cierre documental: informe final, límites declarados explícitamente
                (incluyendo tls_handshake_failure_ratio_60s sin resolver,
                 18 ventanas heredadas de procedencia distinta, tamaño de
                 muestra real vs. la meta aspiracional de 2000-3000)
```

## Siguiente acción concreta

Adaptar `scripts/modeling/calibrate_pm_f1_v1.py` → `scripts/modeling/calibrate_multilayer_v2_v1.py` (mismo patrón de barreras anti-fuga: validación de candidatos por hash, salida atómica, git limpio) apuntando al dataset consolidado de 28 features y a las 179 ventanas de anomalías reales. Ejecutar primero en `--preflight`, revisar, luego `--execute-once`.
