# Validación interna — cobertura de lo que pidió el profesor (audios)

Mapa único: cada exigencia del profesor → **dónde se demuestra** (panel, script o
doc) y **qué estado** tiene. Sirve de guion para la sesión y deja claro qué es
producto (ya listo) y qué es trabajo de artículo/tesis (aparte).

Leyenda: ✅ listo en el producto · 🟡 listo pero requiere una acción de Mark ·
📄 es trabajo de documento/artículo (no del panel) · ⏳ pendiente real.

| # | Lo que pidió el profesor | Dónde se demuestra | Estado |
|---|---|---|---|
| 1 | **Comparación de modelos / "pruebas previas"** (no elegir a ciegas) | Panel → **Modelo** → bloque *Pruebas previas* (7 candidatos + ablación 6/9·7/9·9/9). Script auditable `scripts/analysis/compare_frozen_models_metrics.py` | ✅ |
| 2 | **Fase de entrenamiento visible** (partición, métricas, ejecución) | Panel → **Topología → vista Entrenamiento** (ciclo). Código abrible desde el panel: `particionar_linea_base.py`, `entrenar_preliminar.py`. Umbral/FPR en **Modelo** | ✅ |
| 3 | **Reentrenamiento definido y demostrable, con antes/después** | `docs/RUNBOOK-REENTRENAMIENTO-DEMO.md` (ciclo en seco) + `scripts/modeling/comparar_reentrenamiento.py` (tabla ANTES vs DESPUÉS con Δ y veredicto). Disparadores: programado (semanal/mensual) o por deriva | 🟡 correr el runbook en seco una vez y enseñar la tabla `comparacion-*.md` |
| 4 | **Acreditar todo** (reproducible, no caja negra) | Panel → modo desarrollador → **Ver archivos → ◎ Ver contenido** (código del pipeline en pantalla). Manifiesto + hashes en `artifacts/`. `docs/VALIDACION-INTERNA-TECNICA.md` | 🟡 requiere panel actualizado en el sensor (push + restart) |
| 5 | **Dos diagramas: "cómo se construyó" vs "cómo funciona"** | Panel → **Topología**, toggle de 3 vistas: **Operacional** (cómo funciona), **Metodológica** (cómo se construyó, 7 fases), **Entrenamiento** (el ciclo) | 🟡 idem: push + restart |
| 6 | **Delimitaciones** (alcance y límites, con cifra) | Panel → **Alcance** (lo que se captura y NO se puntúa). Límites declarados abajo ↓ | ✅ / 📄 consolidar en la tesis |
| 7 | **Lista de tablas + lista de figuras + esquema metodológico** | Esquema metodológico = Vista Metodológica del panel + `DIAGRAMAS/VISTA-1-METODOLOGICA`. Lista de tablas/figuras = **documento del artículo/tesis** | 📄 trabajo de artículo (no del panel) |

## Delimitaciones del sistema (lo que hay que decir con número)

Declararlas con su cifra es parte del método; sin número, "se excluyó" no es una
medición. Todas salen de evidencia real del proyecto:

- **FPR en operación sube a ~23–26 %** (25,81 % / 22,97 % en pasadas reales),
  frente a **4,45 %** en test ciego. Causa: tráfico legítimo pegado al umbral.
  Es el límite más importante a declarar.
- **Fuerza bruta: el modelo mide flojo (50–55 %)**; quien la caza es el heurístico
  `brute_force`. La detección es del *stack*, no del modelo solo.
- **DNS de alta entropía: modelo-solo 0 %**; lo cubre el heurístico `dns_entropy`
  (validado en vivo → LIMIT).
- **Escaneo de puertos: modelo-solo 63 %**; combinado 3/3 con el heurístico.
- **ARP: 0 %** (fuera del alcance del modelo actual; límite declarado).
- **Una sola variable no observable en vivo** de las 28:
  `tls_handshake_failure_ratio_60s` (27 observables).
- **El sensor observa por espejo (SPAN), no ejecuta**: la acción (PERMIT/LIMIT/
  BLOCK) la aplica el agente en el host vía feed firmado, no el sensor.

## Lo que depende de Mark (no lo hace el panel ni Claude)

1. `git push` de `producto-as-deployed` (3 commits de GUI) y
   `sudo systemctl restart ppi-dashboard` en el sensor → habilita req. 2, 4, 5 en
   el panel vivo. Recargar el navegador con **Ctrl+F5**.
2. Correr una vez el runbook de reentrenamiento **en seco** y guardar la tabla
   `comparacion-*.md` para enseñarla (req. 3).
3. Lista de tablas/figuras del artículo (req. 7) — documento, con el compañero.
4. Agendar al profesor Fernando para la sesión.
