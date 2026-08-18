# Implementación del calibrador PM-F1-v1

Fecha: 6 de agosto de 2026. Estado: **IMPLEMENTADO Y PROBADO SIN PUNTUAR R04**.

## Resultado de la preparación

Se implementó `scripts/modeling/calibrate_pm_f1_v1.py` como ejecutor cerrado del
protocolo pre-registrado. No es un buscador de modelos o hiperparámetros. El IF
sin escala continúa siendo la conclusión principal aunque una sensibilidad o
comparador produzca otra cola en R04.

El código genera seis pipelines:

1. `if_window`, principal con las 224 ventanas train;
2. `if_scaled`, sensibilidad con `StandardScaler` ajustado sólo en train;
3. `if_campaign_expanded`, sensibilidad con 84 filas por cada una de 87 campañas;
4. `if_exact_collapsed`, sensibilidad pre-registrada que conserva el primer vector decimal exacto de train;
5. `lof_scaled`, comparador novelty;
6. `ocsvm_scaled`, comparador RBF.

Los cuatro IF repiten además las diez semillas enteras
`20260804..20260813`. No se escoge la mejor. LOF y OCSVM sólo son comparadores;
no pueden reemplazar al IF principal por sus resultados en R04 o R05.

## Barreras contra fuga y reejecución

- El selector construye exactamente los nombres R01–R04 desde la matriz. No usa
  `glob` sobre ledgers ni llama al auditor global, por lo que no enumera o lee R05.
- Cada uno de los 116 candidatos vuelve a pasar `validate_candidate`: SHA-256,
  manifest, ledger, PCAP/EVE, CSV, matriz, esquema, commit, partición y dominio.
- Se exigen 87 campañas/224 filas train y 29/72 validation; cualquier diferencia
  detiene el programa.
- El ensamblador rechaza valores no finitos; no existe imputación. Los scalers
  reciben `fit` sólo con R01–R03 y R04 usa únicamente `transform` implícito.
- Git debe estar limpio y coincidir con un commit completo entregado por CLI al
  inicio. Se vuelve a verificar antes de publicar el resultado.
- `--execute-once` no reemplaza una salida. Usa un directorio temporal, lock y
  `rename` final; ante error elimina el temporal y conserva el fallo en el log.
- La ruta de salida debe ser absoluta, estar bajo la raíz de artefactos y ser
  distinta de ella.

## Umbral y sellado

Para cada detector se ordenan los 72 scores R04 por `(score, índice estable)`, se
calcula `k=floor(0.05*72)=3`, se fija `threshold=s(4)` y sólo alerta
`score < threshold`. Los empates con el umbral son normales. Se reportan las
campañas del prefijo inferior y de las alertas estrictas, empates y alertas
`seen`/`unseen`; las diez ventanas vistas no se eliminan ni alteran la regla.

Antes de ejecutar `lower_tail`, el proceso serializa en memoria y calcula los
hashes de `selection.csv`, `validation-scores.csv` y `stability-scores.csv`.
Después escribe esos bytes exactos, los seis modelos, el manifest y un
`SHA256SUMS` exhaustivo. El manifest registra versiones, threadpools, código,
requisitos, esquema, matriz, fuentes, parámetros, orden, timings descriptivos y
política de modelo.

## Verificación sin evidencia R04

Se ejecutaron dos suites completas —Python del sistema y `.venv`— con 51/51
pruebas cada una, `pip check`, `py_compile` y `git diff --check`. Una prueba
sintética ajustó los seis pipelines sobre una matriz aleatoria de 14 columnas y
confirmó `score_samples` y el cuantil estricto. Eso comprueba las rutas de API,
pero no es evidencia de desempeño y no leyó R04.

El siguiente gate es publicar esta implementación, ejecutar únicamente
`--preflight` contra el commit limpio y someter su JSON a revisión. Sólo después
se podrá autorizar un comando exacto `--execute-once`. R05 sigue bloqueada.
