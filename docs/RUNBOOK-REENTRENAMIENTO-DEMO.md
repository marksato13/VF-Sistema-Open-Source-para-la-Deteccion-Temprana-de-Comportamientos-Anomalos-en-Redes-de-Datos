# Reentrenamiento demostrable — ensayo en seco

**Estado:** el contrato y el pipeline se probaron de punta a punta **con datos sintéticos aislados** mediante `python -m unittest discover -s tests -p test_retraining_demo.py`. Eso demuestra que los comandos y formatos encajan; **no es una medición nueva de Sensor1**. La ejecución con datos reales aún debe programarse en una copia aislada. El modelo vivo no se modifica.

## Qué se muestra al profesor

```text
normal acumulado → partición con guarda → IF candidato entrenado solo con train
                  → umbral fijado en validation → FPR test descriptivo
normal EXTERNO y ataques NO usados para ajustar → puntuar ANTES y DESPUÉS
                  → tabla pareada + decisión manual (o evaluación incompleta)
```

El modelo en Sensor1 está **congelado**, no aprende cada paquete. Un candidato se prepara periódicamente o tras deriva sostenida; nunca se promociona automáticamente. No confundir la tabla de **siete modelos históricos** con una comparación antes/después del reentrenamiento operativo.

## Precondiciones

1. Usar un entorno aislado con Python/scikit-learn/joblib compatibles con el artefacto desplegado. Verificar **SHA-256 antes de `joblib.load`**; un joblib es código ejecutable. No entrenar una VM productiva ocupada ni sustituir el modelo vivo. Dejar al menos espacio para el CSV acumulado (hoy >300 MB), partición, modelo y logs.
2. Copiar, con autorización y por ruta interna, **solo los artefactos necesarios**: esquema v2, CSV de línea base, modelo Pipeline desplegado, manifiesto operativo y `ensayo-if-v2.json`. Este último es el informe ANTES real de Sensor1 (SHA-256 `ec3ed06304fdbe6367ab1b69e40498980e6eed6df890f67ae5c4001f98c86421`), no el inexistente `artifacts/model/if_recalibrado_desplegable.json`.
3. Reservar **dos CSV nuevos** no usados por ninguno de los candidatos para entrenar, calibrar, seleccionar reglas ni ajustar umbral: uno de normalidad y otro de episodios anómalos, con las 28 columnas del esquema v2. Validar procedencia/ventanas/etiquetas y guardar hashes; si no existen, la comparación de promoción queda **incompleta**. Un cambio a esquema v3/L2 exige reentrenamiento y evaluación aparte; no comparar sus scores crudos con v2.

## Comandos en la copia aislada (desde la raíz del producto)

Los nombres entre `<...>` son rutas de entrada verificadas por el operador; no son datos incluidos en Git. El ejemplo de salida en `out` tampoco se publica automáticamente.

```bash
mkdir -p /tmp/cf-reentreno-demo
R=/tmp/cf-reentreno-demo
sha256sum <modelo-IF-desplegado.joblib> <manifest-IF.json> <ensayo-if-v2.json> <normal-entrenamiento.csv> <normal-externo.csv> <ataques-externos.csv>

python3 scripts/dataset/particionar_linea_base.py \
  --entrada <normal-entrenamiento.csv> --salida "$R/particionado.csv" \
  --informe "$R/particion.json" --solo-elegibles

python3 scripts/modeling/entrenar_preliminar.py \
  --entrada "$R/particionado.csv" --schema configs/features/multilayer-v2.json \
  --salida "$R/candidato.joblib" --informe "$R/candidato.json"

# Los DOS modelos puntúan el MISMO normal externo, sin volver a calibrar umbrales.
python3 scripts/modeling/puntuar_deteccion.py --modelo <modelo-IF-desplegado.joblib> \
  --manifest <manifest-IF.json> --detector-name if_recalibrado_2026_09 \
  --schema configs/features/multilayer-v2.json --csv <normal-externo.csv> \
  --tipo normal --informe "$R/fpr-antes.json"
python3 scripts/modeling/puntuar_deteccion.py --modelo "$R/candidato.joblib" \
  --csv <normal-externo.csv> --tipo normal --informe "$R/fpr-despues.json"

# Los DOS modelos puntúan los MISMOS episodios nuevos (si existen).
python3 scripts/modeling/puntuar_deteccion.py --modelo <modelo-IF-desplegado.joblib> \
  --manifest <manifest-IF.json> --detector-name if_recalibrado_2026_09 \
  --schema configs/features/multilayer-v2.json --csv <ataques-externos.csv> \
  --tipo anomalias --informe "$R/tpr-antes.json"
python3 scripts/modeling/puntuar_deteccion.py --modelo "$R/candidato.joblib" \
  --csv <ataques-externos.csv> --tipo anomalias --informe "$R/tpr-despues.json"

python3 scripts/modeling/comparar_reentrenamiento.py \
  --antes <ensayo-if-v2.json> --despues "$R/candidato.json" \
  --fpr-antes "$R/fpr-antes.json" --fpr-despues "$R/fpr-despues.json" \
  --tpr-antes "$R/tpr-antes.json" --tpr-despues "$R/tpr-despues.json" \
  --salida "$R/comparacion.md"
```

`puntuar_deteccion.py` ya acepta ambos formatos: Pipeline activo con `--manifest --detector-name --schema` y paquete preliminar (`modelo` + `escalador`). No hace imputación: una feature inválida detiene el ensayo. Produce `csv_sha256` para impedir emparejar fuentes diferentes. Al comparar un modelo entrenado con datos nuevos, el FPR de los informes de entrenamiento **no es directamente pareable**: para decidir se usan exclusivamente los dos informes `fpr-*` sobre el mismo hold-out independiente.

## Interpretación y cierre

- Conjuntos de train/validation/test, hashes, orden de features, hiperparámetros y umbrales deben acompañar la tabla. El informe preliminar ANTES (`ensayo-if-v2.json`) tiene FPR test **0,044527** y umbral `decision_function=-0,06889178778834089`; el Pipeline vivo usa `score_samples=-0,568892`. No restar umbrales de escalas distintas como una «mejora».
- `comparar_reentrenamiento.py` informa **EVALUACIÓN INCOMPLETA — NO PROMOVER** si falta alguno de los pares externos, difiere el hash de los CSV o cambia el esquema/orden. Si FPR no empeora y TPR no baja en pares válidos, devuelve **candidato a revisión manual**, no despliegue. La cobertura por familia, estabilidad y ausencia de fuga se evalúan antes de cualquier decisión real.
- El ensayo sintético de `tests/test_retraining_demo.py` genera datos temporales y verifica partición, entrenamiento, puntuación de ambos formatos y rechazo de reportes sin par o con hash distinto. **No usar sus cifras en la tesis.** Un resultado real desfavorable también es evidencia válida y conserva el modelo desplegado.
- El reentrenamiento v3 con L2 se rige por `docs/PLAN-REENTRENAMIENTO.md` y **queda fuera de la demo en seco**. No reiniciar `ppi-motor` ni editar joblib, manifiesto o `.toml` vivo durante esta prueba.
