# Runbook — Demostración del reentrenamiento (ensayo en seco)

**Para la validación interna.** El profesor pide que el **entrenamiento y el
reentrenamiento** sean **visibles, medibles y reproducibles** (no una caja negra):
hay que mostrar la entrada de datos, la partición, la comparación de modelos, la
selección, las métricas, el reentrenamiento y **qué cambia (antes/después)**.

> **Este runbook NO despliega nada y NO toca el modelo congelado.** Demuestra el
> **mecanismo** del ciclo sobre una copia (`/tmp` o `artifacts/preliminar/`). El
> despliegue real está en `PLAN-REENTRENAMIENTO.md` y va **después** de la validación.

## El ciclo, en una imagen

```
datos acumulados (línea base)  →  partición sin fuga  →  entrenar IF
   →  congelar umbral (percentil α=0,05 en validación)  →  evaluar (FPR test, TPR Kali)
   →  COMPARAR antes vs después  →  ¿pasa el criterio?  →  (desplegar | conservar)
```

## 1. Por qué se reentrena (disparadores) — política definida

Se reentrena en **dos casos**, nunca "porque sí":

| Disparador | Condición concreta |
|---|---|
| **Programado** | Semanal (o mensual) sobre la línea base que `cyberflow-acumular.timer` va acumulando. |
| **Por deriva (*drift*)** | Cuando el **FPR en operación** se sostiene por encima del objetivo, o cuando entra **tráfico nuevo representativo** (nuevas entidades/servicios) que el modelo actual no vio. |

En ambos casos el reentrenamiento es **en seco primero**: solo se despliega si
**mejora o iguala** sin empeorar el FPR (criterio del paso 5).

## 2. Pasos reproducibles (en el sensor, sin tocar producción)

```bash
cd /home/m4rk/cyberflow
V=$(date +%Y%m%d)

# (1) Datos: la línea base acumulada (no se toca el modelo vivo)
ls -la artifacts/linea-base/multilayer-v3.csv

# (2) Partición sin fuga temporal (bloques horarios + banda de guarda)
python3 scripts/dataset/particionar_linea_base.py \
  --entrada artifacts/linea-base/multilayer-v3.csv \
  --salida  /tmp/recal/particionado-$V.csv \
  --informe /tmp/recal/particion-$V.json

# (3) Entrenar + congelar umbral (percentil α=0,05 en validación) → informe con FPR
python3 scripts/modeling/entrenar_preliminar.py \
  --entrada /tmp/recal/particionado-$V.csv \
  --schema  configs/features/multilayer-v3.json \
  --salida  artifacts/preliminar/if-$V.joblib \
  --informe artifacts/preliminar/if-$V.json

# (4) (opcional) Detección: puntuar los ataques de la Kali con el modelo nuevo
python3 scripts/modeling/puntuar_deteccion.py \
  --modelo artifacts/preliminar/if-$V.joblib \
  --anomalias artifacts/dataset/multilayer-v2-anomalies.csv \
  --informe artifacts/preliminar/det-$V.json      # si el script lo soporta

# (5) COMPARAR antes (modelo congelado) vs después (reentrenado)
python3 scripts/modeling/comparar_reentrenamiento.py \
  --antes   artifacts/model/if_recalibrado_desplegable.json \
  --despues artifacts/preliminar/if-$V.json \
  --salida  artifacts/preliminar/comparacion-$V.md
#   (añade --tpr-antes/--tpr-despues si corriste el paso 4)
```

## 3. Qué demuestra cada artefacto (evidencia para el profesor)

| Artefacto | Qué acredita |
|---|---|
| `particion-$V.json` | Cómo se separó train/validación/prueba **sin fuga temporal** |
| `if-$V.json` | Que el entrenamiento **existe y es reproducible** (α, umbral, FPR, hashes) |
| `det-$V.json` | La **detección (TPR)** del modelo nuevo sobre ataques reales |
| `comparacion-$V.md` | **Qué cambió** (antes/después) y si **se conserva o se sustituye** el modelo |

## 4. Criterio de aceptación (del `PLAN-REENTRENAMIENTO.md`)

Desplegar el modelo reentrenado **solo si**: cobertura ≥ actual **y** FPR ≤ actual
(y mejoran ARP/DNS). Si no, **se conserva el congelado** (hay rollback en un `cp`).

## 5. Comparación de modelos (la "prueba previa" que pide el profesor)

La selección del modelo actual **ya está evidenciada** (no se eligió "el mejor" a
ciegas): ver `scripts/analysis/compare_frozen_models_metrics.py` (7 candidatos) y la
**ablación** (modelo 6/9 · heurísticos 7/9 · combinado 9/9). Esa tabla es la que se
muestra como "pruebas previas / comparación de modelos".
