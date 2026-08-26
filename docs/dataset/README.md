# Documentación del corpus

Documentos canónicos sobre los **datos**, separados de los que describen el
modelo y el sistema desplegado. La separación es deliberada: un datasheet
responde por la procedencia y los límites de los datos; confundirlo con las
métricas del modelo es lo que hace que ninguna de las dos cosas quede clara.

| Documento | Responde por |
|---|---|
| [`DATASHEET_MULTILAYER_V2.md`](DATASHEET_MULTILAYER_V2.md) | **Los datos** — procedencia, estructura, particiones, calidad, sesgos y privacidad |
| [`../fase02-features-multicapa/03-diccionario-multicapa-v2.md`](../fase02-features-multicapa/03-diccionario-multicapa-v2.md) | **Las variables** — fórmula, denominador, rangos, observabilidad y coste |

## Pendientes

| Documento | Contenido previsto |
|---|---|
| *Model card* | OCSVM congelado: hiperparámetros, umbral, métricas por familia y la selección posterior declarada |
| *System card* | Motor en tiempo real, bloqueo en línea, lead-time y falso positivo operativo |

Ambos se ensamblan a partir de material ya existente en
[`docs/entregables/01-evaluacion-critica/`](../entregables/01-evaluacion-critica/informe-evaluacion-critica.md)
y [`docs/fase07-validacion-final/`](../fase07-validacion-final/).

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
```
