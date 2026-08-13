# Anomalías v2 aisladas

`run_v2_anomaly.py` ejecuta únicamente la matriz de evaluación ciega
`multilayer-v2-anomalies.json`. Cada episodio queda en `partition=
evaluation_only` y `label=anomaly`; nunca se agrega al CSV normal.
