# Validación interna — cobertura de lo que pidió el profesor (audios)

Mapa único: cada exigencia del profesor → **dónde se demuestra** (panel, script o
doc) y **qué estado** tiene. Sirve de guion para la sesión y deja claro qué es
producto (ya listo) y qué es trabajo de artículo/tesis (aparte).

Leyenda: ✅ listo en el código/documentación local · 🟡 requiere verificación/despliegue de Mark ·
📄 es trabajo de documento/artículo (no del panel) · ⏳ pendiente real.

| # | Lo que pidió el profesor | Dónde se demuestra | Estado |
|---|---|---|---|
| 1 | **Comparación de modelos / "pruebas previas"** (no elegir a ciegas) | Panel → **Modelo**: 7 candidatos históricos + ablación por episodio 6/9·7/9·9/9; `scripts/analysis/compare_frozen_models_metrics.py`. La selección posterior a test se declara como limitación. | ✅ local / 🟡 vivo |
| 2 | **Fase de entrenamiento visible** (partición, métricas, ejecución) | Panel → **Topología → vista Entrenamiento**; código autorizado del pipeline, umbral/FPR en Modelo. El panel explica el procedimiento, no ejecuta entrenamiento. | ✅ local / 🟡 vivo |
| 3 | **Reentrenamiento definido y demostrable, con antes/después** | Runbook reparado y prueba integral **sintética** del pipeline; el comparador rechaza promoción sin normal y ataques pareados. | 🟡 faltan datos nuevos reservados y tabla real ANTES/DESPUÉS; no se despliega modelo |
| 4 | **Acreditar todo** (reproducible, no caja negra) | Panel → modo desarrollador → **Ver archivos → ◎ Ver contenido** (código del pipeline en pantalla). Manifiesto + hashes en `artifacts/`. `docs/VALIDACION-INTERNA-TECNICA.md` | 🟡 requiere panel actualizado en el sensor (push + restart) |
| 5 | **Dos diagramas: "cómo se construyó" vs "cómo funciona"** | Panel → **Topología**, toggle de 3 vistas: **Operacional** (cómo funciona), **Metodológica** (cómo se construyó, 7 fases), **Entrenamiento** (el ciclo) | 🟡 idem: push + restart |
| 6 | **Delimitaciones** (alcance y límites, con cifra) | Panel → **Alcance** y fichas; límites con dataset/denominador abajo ↓ | ✅ local / 📄 conciliar en tesis |
| 7 | **Lista de tablas + lista de figuras + esquema metodológico** | Esquema metodológico = Vista Metodológica del panel + `DIAGRAMAS/VISTA-1-METODOLOGICA`. Lista de tablas/figuras = **documento del artículo/tesis** | 📄 trabajo de artículo (no del panel) |

## Delimitaciones del sistema (lo que hay que decir con número)

Declararlas con su cifra es parte del método; sin número, "se excluyó" no es una
medición. Todas salen de evidencia real del proyecto:

- **FPR 25,81 % / 22,97 % en F6 histórico** (OCSVM/laboratorio, 16/62 y 17/74), frente al **4,45 %** del test normal retenido tras recalibrar IF en Sensor1 (65 421 ventanas). Son **entornos/modelos diferentes**: no afirmar que el FPR del IF operativo sea 23–26 % ni que su 4,45 % garantice desempeño continuo.
- **Fuerza bruta: el modelo mide flojo (50–55 %)**; quien la caza es el heurístico
  `brute_force`. La detección es del *stack*, no del modelo solo.
- **DNS de alta entropía: modelo-solo 0 %**; lo cubre el heurístico `dns_entropy`
  (validado en vivo → LIMIT).
- **Escaneo de puertos: modelo-solo 27/43 = 63 %** en la corrida de septiembre; en la batería posterior el stack fue 3/3. El heurístico `port_scan` pasó de 1/3 a 3/3 tras una corrección observando fallos; ese 3/3 no es un test independiente ciego.
- **ARP:** no entra en el scoring v2; no atribuir un TPR 0 % a una evaluación no realizada del modelo para ARP.
- **Una sola variable no observable en vivo** de las 28:
  `tls_handshake_failure_ratio_60s` (27 observables).
- **El sensor observa por espejo (SPAN), no ejecuta**: la acción (PERMIT/LIMIT/
  BLOCK) la aplica el agente en el host vía feed firmado, no el sensor.

## Lo que depende de Mark (no lo hace el panel ni Claude)

1. Revisar y publicar los **cuatro commits previos de GUI/docs más los cambios locales pendientes** de `producto-as-deployed` (sin push automático). Comparar el `dashboard.py` local con el archivo vivo y respaldar; después
   `sudo systemctl restart ppi-dashboard` en el sensor → habilita req. 2, 4, 5 en
   el panel vivo. Recargar el navegador con **Ctrl+F5**.
2. Preparar normal y ataques **nuevos/reservados** y correr el runbook corregido en un entorno aislado; guardar tabla `comparacion-*.md` basada en datos reales. La prueba sintética solo acredita que funciona el mecanismo, no un resultado científico (req. 3).
3. Lista de tablas/figuras del artículo (req. 7) — documento, con el compañero.
4. Agendar al profesor Fernando para la sesión.
