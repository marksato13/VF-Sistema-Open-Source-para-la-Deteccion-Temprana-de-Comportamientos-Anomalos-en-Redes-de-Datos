# B5 — "Cuarentena / aislar": decisión de alcance

El profesor listó, entre las acciones, **aislar / poner en cuarentena** (audio 5).
Este documento resuelve si hay que añadir una acción nueva o si el producto ya la
cubre. **Recomendación: Opción A (ya está cubierta).**

## Qué hace HOY el producto (verificado en el código)

- **BLOCK = aislamiento total de la entidad.** El agente aplica
  `nft … ip saddr @cyberflow_bloqueados drop` (`agente_enforce.py`,
  `plan_nftables`): **cae TODO el tráfico** de esa IP, no un flujo concreto. Eso
  **es** poner la entidad en cuarentena.
- **LIMIT = degradar** (rate-limit), para el caso ambiguo donde cortar del todo
  sería caro si es un falso positivo.
- **Caducidad escalada y acotada** (`escalada.py`): BLOCK 300 s → 1800 s → 3600 s
  (tope automático). **Nunca `∞` automático.**
- **Cola de revisión humana**: desde la 3ª reincidencia la entrada lleva
  `revisar_humano = true`. El aislamiento permanente **lo decide una persona**
  sobre esa cola, no el sistema solo. (El `∞` es humano por diseño.)
- **Lista nunca-bloquear**: gateways, DNS/AD, sensor y bastión quedan siempre
  fuera (no se pueden aislar por accidente).

## Opción A — documentar que ya está cubierta  ✅ recomendada

"Cuarentena / aislar" = **BLOCK de la entidad** (drop de todo su tráfico) con
caducidad escalada y marca de revisión humana para el aislamiento prolongado.
No hace falta código nuevo.

- **Pro**: es verdad y es defendible con el código a la vista; cero riesgo antes
  del jueves; encaja en el discurso "tres tiempos + tres acciones
  (PERMIT/LIMIT/BLOCK)".
- **Qué decir en la demo**: *"Aislar es nuestro BLOCK: nftables descarta todo el
  tráfico de la entidad. No es permanente automático —escala 300/1800/3600 s y a
  la tercera reincidencia pasa a una cola de revisión humana, que es quien decide
  el aislamiento indefinido."*

## Opción B — añadir una acción `QUARANTINE` distinta de BLOCK

Solo si el profe insiste en la **palabra** como acción separada.

- Sería BLOCK + semántica aparte: timeout largo de entrada (no escalado) y entrada
  directa en la cola de revisión humana desde la 1ª vez.
- **Toca**: `heuristicos.py` (nueva etiqueta), `publicar_feed.py` (mapa veredicto→
  acción y severidad), `feed.py`/`agente_enforce.py` (tratar `QUARANTINE` como
  BLOCK en nft), panel (badge), y sus tests.
- **Contra**: **no añade capacidad** (el efecto en red es idéntico al BLOCK),
  solo nombre; introduce riesgo de regresión en el núcleo de enforcement a dos
  días de la demo. **No lo recomiendo** salvo petición explícita.

## Decisión

- [ ] **A** — se documenta (este archivo) y se explica en la demo. Cero código.
- [ ] **B** — se implementa la acción `QUARANTINE` (ver alcance arriba).

> Por defecto se asume **A** salvo que indiques B. Si eliges B, lo implemento con
> el mismo gate de pruebas (py_compile + node --check + unittest + validación en
> el sensor) antes de tocar el enforcement vivo.
