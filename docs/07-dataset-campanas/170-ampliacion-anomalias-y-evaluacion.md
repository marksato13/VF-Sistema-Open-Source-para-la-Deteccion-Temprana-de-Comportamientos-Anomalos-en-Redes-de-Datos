# Ampliación de anomalías y evaluación v2

Se añadieron tres episodios independientes por cada patrón (`SYN/RST`,
`DNS-NXDOMAIN` y `AUTH-FAIL`), usando `E02`–`E04`. Todas las campañas pasaron
F2, cierre, hashes y extracción. El conjunto ciego ampliado contiene 12
episodios y 18 ventanas, siempre con `label=anomaly` y
`partition=evaluation_only`.

Se repitió el protocolo sin modificar train, validation, test ni el umbral:

| Evaluación | Anomalías | Detectadas | Test normal marcado | ROC-AUC | AP |
|---|---:|---:|---:|---:|---:|
| inicial | 5 | 1 | 2/16 | 0.5375 | 0.2933 |
| ampliada | 18 | 7 | 2/16 | 0.6007 | 0.6124 |

El aumento de AP muestra que el primer resultado estaba dominado por un
muestral anómalo demasiado pequeño, pero la tasa de detección sigue siendo
7/18. Por tanto, el sistema tiene evidencia de funcionamiento parcial y
trazable, no un desempeño productivo garantizado. La selección de anomalías
debe ampliarse con más familias independientes antes de fijar una afirmación
de rendimiento fuerte.

CSV ampliado: `artifacts/dataset/multilayer-v2-anomalies.csv`.
SHA-256: `d8bf293d6427398c5091344397ec1aea3303f277cae32d0988a0dc164ada761a`.
