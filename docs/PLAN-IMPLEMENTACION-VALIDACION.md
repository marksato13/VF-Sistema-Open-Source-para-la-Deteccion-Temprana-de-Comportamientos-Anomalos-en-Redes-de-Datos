# Plan de implementación — producto listo para validación interna

**Objetivo:** cerrar la parte **técnica/producto** que pidió el profesor (demo de
ingeniería), por **bloques de ejecución**. Cada bloque se implementa Y se prueba
antes de pasar al siguiente, para no arrastrar errores.

## Gate de pruebas (se aplica en CADA bloque)
1. `python3 -m py_compile <ficheros .py tocados>` → compila.
2. Panel JS: extraer el `<script>` y `node --check` → sintaxis válida.
3. `python3 -m unittest discover -s tests -p 'test_*.py'` → suite verde.
4. **Validación en el sensor** (medir, no afirmar): correr el caso real y leer el
   resultado (log/feed/nft), no asumir.
5. Commit en `producto-as-deployed` (sin trailer) con el criterio de salida escrito.
6. (Opcional) `/code-review` sobre el diff antes de desplegar.

**Regla:** un bloque NO se da por cerrado si su "criterio de salida" no se cumple
medido. Nada de "debería funcionar".

---

## BLOQUE 0 — Confirmaciones base (rápido, condiciona el discurso)
**Objetivo:** cerrar incógnitas que afectan a la narrativa de la demo.
- **0.1 Capa 2 en el modelo desplegado:** leer `configs/features/multilayer-v2.json`
  + `manifest.feature_names` → ¿hay features L2? Documentar la respuesta (si no, la
  L2 entra por la deduplicación/v3; explicar el porqué).
- **0.2 Columna Acción con el motor nuevo:** confirmar que `/api/decisions` devuelve
  `heuristico` y el panel pinta PERMIT/LIMIT/BLOCK (ya verificado en código; validar
  en vivo con una decisión reciente).
**Pruebas/salida:** una línea escrita por cada punto (sí/no + evidencia). Sin cambios
de código salvo documentar.
**Depende de:** nada.

---

## BLOQUE 1 — Medición de los 3 tiempos (núcleo técnico; lo pidió el profe)
**Objetivo:** medir y diferenciar, por episodio de ataque, los tres tiempos que el
profesor exigió separar (audio 6):
- `t_detección` = primera ventana del motor que marca (ALERT o heurístico) − t_inicio.
- `t_decisión`  = instante en que `publicar_feed` emite la acción para esa IP − t_inicio.
- `t_respuesta` = instante en que el agente aplica la regla `nft` en el host − t_inicio.

**Implementación:**
- Script `scripts/analysis/medir_tiempos.py` (nuevo) que, dado `t_inicio` (reloj del
  sensor) y una IP, lee: `logs/motor_decision.log` (detección), `~/feed/feed.json`
  (`generado` + entrada de la IP = decisión), y en el host `~/enforce/shadow.log`
  (`aplicado`) / `nft list` (regla) = respuesta. Devuelve los 3 deltas + orden.
- Anclar SIEMPRE al **reloj del sensor** (no al de la Kali) — ya aprendido.

**Pruebas / criterio de salida:**
- Correr un escaneo controlado; obtener los 3 tiempos con `detección ≤ decisión ≤
  respuesta` (orden lógico). Repetir ≥3 → intervalos.
- Guardar `docs/evidencias/tiempos-<fecha>.md` con la tabla.
**Depende de:** motor con el fix (ya desplegado), enforcement en vivo.

---

## BLOQUE 2 — GUI: mostrar los tiempos + reforzar modelo-vs-heurístico
**Objetivo:** que el panel RESPONDA en vivo a "¿qué tan rápido detecta/responde?" y
deje clara la historia "sin firma" (quién cazó, modelo o heurístico).

**Implementación (`scripts/engine/dashboard.py`):**
- 2.1 En la tabla de Decisiones, mostrar el **detector/heurístico** que disparó de
  forma destacada (hoy está el detector; resaltar cuando es heurístico = "sin firma").
- 2.2 Si el log trae los tiempos (Bloque 1 los calcula), añadir una **vista/tarjeta
  "Tiempos de respuesta"** (detección/decisión/bloqueo) por entidad o agregada.
- Cambios SOLO de presentación (el panel sigue solo-lectura).

**Pruebas / criterio de salida:**
- `py_compile` + `node --check` del JS + `unittest` de dashboard verdes.
- Validación visual: con una decisión de ataque reciente, la GUI muestra la acción y
  el/los tiempo(s).
**Depende de:** Bloque 1 (para los datos de tiempo).

---

## BLOQUE 3 — GUI: datos auténticos + arquitectura lista para proyectar
**Objetivo:** responder "los datos no están manipulados" y proyectar la arquitectura.
**Implementación (`dashboard.py`):**
- 3.1 Enlazar en la GUI la **línea base** y los **parámetros** (pps, umbrales,
  `VERSION_UMBRALES`) — un panel/sección que cite las cifras medidas.
- 3.2 Verificar que la **topología** (vista Completa, horizontal) carga bien a
  **pantalla completa** para proyectar (ya existe; solo QA).
**Pruebas/salida:** `node --check` + visual a pantalla completa.
**Depende de:** nada (independiente del Bloque 1).

---

## BLOQUE 4 — E2-brute (4ª familia; cierra la tabla comparativa)
**Objetivo:** demostrar `brute_force`→BLOCK sobre un endpoint real con 401.
**Implementación:**
- 4.1 (**tú**) Preparar un endpoint con **autenticación 401** en el servidor DMZ.
- 4.2 Correr `hydra` sostenido; medir con el harness del Bloque 1.
**Pruebas / criterio de salida:**
- `brute_force` dispara → BLOCK en el motor; FPR 0 sobre la línea base (como DNS/scan).
- Fila E2 añadida a la tabla comparativa (nota 26) + los 3 tiempos.
**Depende de:** 4.1 (endpoint 401) y Bloque 1.

---

## BLOQUE 5 — Cuarentena / aislar (decisión de alcance)
**Objetivo:** cerrar lo que el profe listó como acción ("aislar").
**Implementación (decisión, luego quizá código):**
- Opción A (documentar): LIMIT/BLOCK ya cubren degradar/cortar; "cuarentena" = BLOCK
  total de la entidad. Se documenta y no se añade código.
- Opción B (código): acción `QUARANTINE` = BLOCK de toda la IP (no solo flujo) con
  timeout largo + lista de revisión humana. Toca heurísticos/feed/agente.
**Pruebas/salida:** si B, los mismos gates + prueba e2e de aislamiento.
**Depende de:** tu decisión A/B.

---

## BLOQUE 6 — Guion de demo + ensayo e2e (cierre)
**Objetivo:** un guion reproducible para el jueves.
**Implementación:** `docs/GUION-DEMO.md` con pasos: mostrar arquitectura (topología) →
lanzar ataque → verlo en el panel (detección + acción + tiempos) → mostrar el corte
real en el host (`nft`/curl http_000) → mostrar el código y dónde está el modelo.
**Pruebas / criterio de salida:** **ensayo completo** de principio a fin sin fallos,
cronometrado. Si algo falla, se corrige antes de darlo por cerrado.
**Depende de:** Bloques 1–3 (y 4 si el 401 está).

---

## Orden recomendado y dependencias
```
B0 (confirmaciones) ─┬─> B1 (tiempos) ──> B2 (GUI tiempos) ─┐
                     └─> B3 (GUI datos/arquitectura) ───────┼─> B6 (guion + ensayo)
B4 (E2-brute, necesita 401 tuyo) ───────────────────────────┤
B5 (cuarentena, decisión tuya) ─────────────────────────────┘
```
**Camino crítico para el jueves:** B0 → B1 → B2 → B6. B3 en paralelo. B4/B5 cuando
estén tus dependencias (401 / decisión).

## Qué necesita de ti (lo demás lo hago yo)
- Endpoint **401** (B4).
- Decisión **cuarentena** A/B (B5).
- **Push** del repo y lo **organizativo** (grabar sesión, coordinar expertos).
