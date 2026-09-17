# Dashboard multilayer-v2

Dashboard local sin dependencias externas. Se activa después de construir el
dataset:

```bash
python3 dashboard/app.py --dataset /srv/ppi-evidence/dataset/multilayer-v2.csv
```

Abrir `http://127.0.0.1:8787/`. En una VM remota usar un túnel SSH; no se
expone el puerto a Internet.
