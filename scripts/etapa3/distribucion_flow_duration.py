#!/usr/bin/env python3
"""Etapa 3 (punto 6): distribución de flow_duration_mean_30s en el CSV de entrenamiento.

Solo lectura: lee el CSV y escribe un JSON en stdout (se ejecuta en Sensor1 por
``ssh ... python3 - < este_fichero`` o en local con la ruta como argumento). Da, para
las filas de entrenamiento y para todas: percentiles, fracción por encima de 60/120/
180/230/300/600/900 s, máximo, y lo mismo de history_coverage_s (el horizonte efectivo).
"""
import csv
import json
import os
import sys

RUTA = sys.argv[1] if len(sys.argv) > 1 else os.path.expanduser(
    "~/cyberflow/artifacts/preliminar/limpio-2026-10/particionado-limpio.csv")
CORTES = (30, 60, 120, 180, 230, 300, 600, 900)


def resumen(v):
    v = sorted(v)
    n = len(v)
    if not n:
        return {"n": 0}
    q = lambda p: v[min(n - 1, int(p * (n - 1)))]  # noqa: E731
    return {"n": n, "p50": q(0.5), "p90": q(0.9), "p95": q(0.95), "p99": q(0.99), "p999": q(0.999), "max": v[-1],
            "fraccion_mayor_que": {str(c): round(sum(1 for x in v if x > c) / n, 5) for c in CORTES},
            "fraccion_cero": round(sum(1 for x in v if x == 0) / n, 5)}


filas = {"todas": [], "entrenamiento": []}
hist = {"todas": [], "entrenamiento": []}
columnas = None
with open(RUTA, newline="") as fh:
    r = csv.DictReader(fh)
    columnas = r.fieldnames
    col_part = next((c for c in ("particion", "split", "partition", "conjunto") if c in columnas), None)
    vals_part = {}
    for row in r:
        try:
            fd = float(row["flow_duration_mean_30s"])
            hc = float(row.get("history_coverage_s") or 0)
        except (KeyError, ValueError):
            continue
        if float(row.get("packet_count_10s") or 0) == 0:
            continue                      # el motor no puntúa ventanas sin paquetes
        filas["todas"].append(fd)
        hist["todas"].append(hc)
        p = row.get(col_part) if col_part else None
        vals_part[p] = vals_part.get(p, 0) + 1
        if col_part is None or p in ("train", "entrenamiento", "fit"):
            filas["entrenamiento"].append(fd)
            hist["entrenamiento"].append(hc)
print(json.dumps({"ruta": RUTA, "columna_particion": col_part, "valores_particion": vals_part,
                  "flow_duration_mean_30s": {k: resumen(v) for k, v in filas.items()},
                  "history_coverage_s": {k: resumen(v) for k, v in hist.items()}}, indent=1))
