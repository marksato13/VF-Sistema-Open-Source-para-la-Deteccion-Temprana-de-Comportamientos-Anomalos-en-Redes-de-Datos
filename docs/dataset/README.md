# Documentación del corpus

Documentos canónicos sobre los **datos**, separados de los que describen el
modelo y el sistema desplegado. La separación es deliberada: un datasheet
responde por la procedencia y los límites de los datos; confundirlo con las
métricas del modelo es lo que hace que ninguna de las dos cosas quede clara.

| Documento | Responde por |
|---|---|
| [`DATASHEET_MULTILAYER_V2.md`](DATASHEET_MULTILAYER_V2.md) | **Los datos** — procedencia, estructura, particiones, calidad, sesgos y privacidad |
| [`../fase02-features-multicapa/03-diccionario-multicapa-v2.md`](../fase02-features-multicapa/03-diccionario-multicapa-v2.md) | **Las variables** — fórmula, denominador, rangos, observabilidad y coste |
| [`MODEL_CARD_OCSVM.md`](MODEL_CARD_OCSVM.md) | **El modelo** — hiperparámetros, umbral, métricas por familia, comparación de los siete candidatos y la selección posterior declarada |
| [`SYSTEM_CARD_MOTOR.md`](SYSTEM_CARD_MOTOR.md) | **El sistema desplegado** — detectores, acción de control, desempeño en operación y modos de fallo |

Las tres responden por cosas distintas a propósito: mezclar la procedencia de
los datos con las métricas del modelo y con el comportamiento del sistema
desplegado es lo que hace que ninguna de las tres quede clara.

## Reglas

- El corpus está **congelado**. Ninguna corrección documental modifica los CSV.
- Ninguna cifra se transcribe a mano: el datasheet y el diccionario se
  **generan** desde los artefactos, y abortan si el reporte de auditoría no
  corresponde al dataset vigente.
- Regenerar tras cualquier cambio en los datos o en el contrato de variables:

```bash
python3 scripts/dataset/audit_multilayer_v2.py \
  --normal artifacts/dataset/multilayer-v2-normal.csv \
  --anomalies artifacts/dataset/multilayer-v2-anomalies.csv \
  --output artifacts/dataset/multilayer-v2-audit-report.json
python3 scripts/entregables/generar_diccionario_features.py
python3 scripts/entregables/generar_datasheet.py
python3 scripts/entregables/generar_cards.py
bash scripts/dataset/generar_checksums.sh
```
