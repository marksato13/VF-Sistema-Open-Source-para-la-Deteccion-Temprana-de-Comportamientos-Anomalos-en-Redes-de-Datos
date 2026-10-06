# Validación interna técnica — requisitos del profesor vs estado del producto

**Alcance:** SOLO la parte **técnica / producto** (demostración de ingeniería para
la validación interna). El artículo, el mapeo de artículos semilla, Related Work y
la redacción de la metodología los lleva el compañero — **no** entran aquí.

> El profesor separó explícitamente (audios 5 y 10):
> - **Validación INTERNA = técnica**: demo funcionando + código + arquitectura +
>   parámetros + **observaciones grabadas de expertos**. (NO se usa TAM aquí.)
> - **Validación EXTERNA = aceptación**: TAM adaptado + juicio de expertos.
>
> Este documento cubre la **interna**.

## 1. Requisitos TÉCNICOS que pidió el profesor (audios 3, 5, 6, 7, 10)

1. **Escenario funcionando** en la demo (producto operativo, no una maqueta).
2. **Mostrar**: el código, **dónde está el modelo**, la **arquitectura** y sus
   componentes, y el **dashboard**.
3. **Explicar con precisión**:
   - Qué significa que CyberFlow funcione **inline / online**.
   - Si el **aprendizaje** es continuo, periódico o estático.
   - Qué pasa ante una **anomalía desconocida** (sin firma).
4. **Tiempos diferenciados**: tiempo de **detección**, de **decisión** y de
   **respuesta/mitigación** (bloqueo). No mezclar "rapidez" en una sola palabra.
5. **Acciones diferenciadas**: alertar / limitar / **cuarentena (aislar)** / bloquear.
6. **Qué anomalías** detecta, en concreto (no "detectar anomalías" genérico).
7. **Datos auténticos**: demostrar que la simulación **no está manipulada** y está
   dentro de parámetros válidos — recolección, validez, condiciones del online,
   y la **relación parámetros ↔ resultados**.
8. **Traslado simulación → red real** (distribution shift) y su efecto en los
   **falsos positivos**; cómo lo afronta CyberFlow.
9. **Variables de capa 2** (recomendación del ing. Fernando).
10. **Grabar** la sesión de revisión y convertir las observaciones en **mejoras**.

## 2. Mapeo requisito → estado del producto

| # | Requisito del profe | Estado | Evidencia / dónde |
|---|---|---|---|
| 1 | Escenario funcionando | ✅ | enforcement en vivo; `port_scan`→BLOCK confirmado en el motor |
| 2 | Código / modelo / arquitectura / dashboard | ✅ | repo `producto-as-deployed`; modelo `artifacts/preliminar/if_recalibrado_desplegable.joblib`; arquitectura = **topología del panel**; dashboard operativo |
| 3 | Explicar inline/online, aprendizaje, desconocida | ✅ | ver §3; el panel lo muestra: Modelo congelado (aprendizaje), heurísticos con umbrales+versión (sin firma), topología (inline/online) |
| 4 | Tiempos detección / decisión / respuesta | ✅ medido | **los tres, anclados al reloj del sensor** (`evidencias/tiempos-2026-10-06.md`): detección **~2–40 s** (ventana de 30 s), decisión en el tick minutely del feed, respuesta total hasta BLOCK **~1–2,5 min** (medido hasta 141 s, corte 200→000 confirmado); orden det≤dec≤resp. La respuesta la domina la cadencia minutely del feed firmado (parámetro de diseño, configurable), no el cómputo |
| 5 | Acciones alertar/limitar/**cuarentena**/bloquear | ◐ | PERMIT/LIMIT/BLOCK ✅; **"cuarentena/aislar" no existe** como acción propia (gap) |
| 6 | Qué anomalías (concreto) | ✅ | 4 familias: escaneo, DGA/DNS alta entropía, flood HTTP, fuerza bruta (nota 21) |
| 7 | Datos no manipulados / parámetros válidos | ✅ | **línea base medida** (nota 24) + umbrales **justificados** + **replay de PCAP reproducible** (el PCAP es el artefacto verificable) |
| 8 | Sim → real / falsos positivos | ✅ | **recalibración EN la red real**: FPR 92,4 %→4,45 % (nota L); es la respuesta al distribution shift |
| 9 | Variables de capa 2 | ◐ documentado | **El modelo desplegado (v2, 28 features) NO usa L2** — solo L3/L4/L7 (confirmado en `multilayer-v2.json`). La L2 se usa en la **deduplicación del espejo** (VLAN + ip_id para quitar copias) y el extractor **v3** añade features L2, pero v3 **no está desplegado**. Incorporar L2 al *scoring* exige **reentrenar + recalibrar** (v3) — siguiente paso, no en esta versión. |
| 10 | Grabar y convertir en mejoras | ⏳ | organizativo (grabar la sesión del jueves) |

## 3. Respuestas técnicas que hay que dejar claras (para la demo)

- **Inline / online:** CyberFlow **observa en línea** (online) por un **espejo SPAN**
  (pasivo, no está en el camino del tráfico), y **responde** desplegando reglas
  `nftables` **en el host protegido** (near-inline: el corte ocurre en el host, no en
  el sensor). El sensor **nunca** sale a Internet (propiedad de seguridad).
- **Aprendizaje:** el modelo está **congelado** (estático) en operación — umbral
  fijo, reproducible; y se **reentrena periódicamente** (mensual o por deriva del
  FPR). No aprende "en caliente" cada paquete: eso evita que un ataque sostenido se
  aprenda como normal.
- **Anomalía desconocida:** la cubre el **modelo one-class** (aprende lo normal y
  marca lo que se desvía, sin firma) + los **heurísticos** deterministas. Es el
  aporte frente a Suricata (firmas): detecta lo que **no tiene firma** (DGA, etc.).
- **Qué pasa DESPUÉS de detectar** (lo que marcó el audio 7): el aporte no es solo
  detectar, es la **respuesta por entidad**: PERMIT / LIMIT (degradar) / BLOCK
  (cortar), con feed firmado y caducidad escalada.

## 4. Actividades técnicas pendientes (producto)

- **Medir los 3 tiempos limpios** (detección, decisión, bloqueo) y mostrarlos — el
  profe lo pidió explícito (audio 6). Ya tenemos detección; falta decisión+bloqueo.
- **Decidir "cuarentena/aislar"**: ¿se añade una acción de aislamiento (p. ej. BLOCK
  total de la entidad, no solo del flujo) o se documenta que LIMIT/BLOCK ya cubren el
  espectro? (audio 5).
- **Confirmar capa 2** en el modelo desplegado (audio 5/7): si el v2 no la usa,
  documentar que la L2 entra vía la deduplicación y/o el v3, y el porqué.
- **E2-brute**: preparar un endpoint con **401** en el servidor y correr la familia
  de fuerza bruta (completa la tabla y la acción BLOCK por auth-fail).
- **Guion de demo**: escenario → ataque → detección (panel) → acción LIMIT/BLOCK →
  corte real en el host, con los tiempos a la vista.

## 5. Mejoras de GUI (para que la demo convenza)

- **Mostrar los tiempos**: los tres tiempos no caben en el log (el t_respuesta es
  cross-host); van **medidos** en `evidencias/tiempos-2026-10-06.md` y se enseñan
  en la demo (§3 del guion). ✅ cubierto por evidencia + guion.
- **Dejar visible la historia "sin firma"** (B2.1 ✅): la columna *Motivo* de
  Decisiones ahora resalta **qué heurístico** disparó (badge + motivo) cuando la
  decisión fue determinista; si no, la etiqueta del modelo. Desplegado al sensor.
- **Vista de arquitectura lista para demo**: la topología ya existe (horizontal, por
  fases); **QA de pantalla completa pendiente en el ensayo** (B3.2).
- **Parámetros a la vista** (B3.1 ✅): el bloque de heurísticos del panel cita los
  **umbrales exactos + `VERSION_UMBRALES` 2026-10-06.1**; Variables ya muestra
  paso/historia/esquema y valores reales del dataset. Desplegado al sensor.
- Columna **Acción (PERMIT/LIMIT/BLOCK)**: ✅ confirmada con el motor nuevo.

> **Nota de despliegue:** B2.1 y B3.1 ya están en el fichero del sensor
> (`scripts/engine/dashboard.py`, respaldo `.bak-20261006`), pero **tomarán efecto
> al reiniciar** el servicio: `sudo systemctl restart ppi-dashboard` (sudo de Mark).
