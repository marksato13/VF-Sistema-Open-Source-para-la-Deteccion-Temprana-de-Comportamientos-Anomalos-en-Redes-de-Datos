#!/usr/bin/env python3
"""Puntua un CSV de ventanas con el modelo PRELIMINAR y su umbral congelado.

Detecta = decision_function(x) < umbral. Sobre un CSV de anomalias, la fraccion
detectada es el TPR (tasa de deteccion). Sobre normal, seria el FPR.

    python3 puntuar_deteccion.py --modelo /tmp/recal/modelo.joblib \
        --csv anomalias.csv [--etiqueta anomaly]
"""
from __future__ import annotations
import argparse, csv, json
import numpy as np
import joblib


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--modelo", required=True)
    ap.add_argument("--csv", required=True)
    ap.add_argument("--etiqueta", default="", help="si el CSV mezcla clases, filtra por columna label")
    a = ap.parse_args()

    paq = joblib.load(a.modelo)
    modelo, escalador = paq["modelo"], paq["escalador"]
    feats, umbral = paq["features"], float(paq["umbral"])

    with open(a.csv, newline="", encoding="utf-8") as f:
        filas = list(csv.DictReader(f))
    if a.etiqueta:
        filas = [r for r in filas if r.get("label", "") == a.etiqueta]
    if not filas:
        print(json.dumps({"error": "sin filas"})); return 1

    faltan = [c for c in feats if c not in filas[0]]
    if faltan:
        print(json.dumps({"error": "faltan features en el CSV", "faltan": faltan})); return 1

    X = np.asarray([[float(r[c] or 0) for c in feats] for r in filas], dtype=float)
    Z = escalador.transform(X)
    score = modelo.decision_function(Z)
    detectadas = int(np.sum(score < umbral))
    n = len(filas)
    print(json.dumps({
        "csv": a.csv,
        "filas": n,
        "umbral": round(umbral, 6),
        "detectadas (score<umbral)": detectadas,
        "tasa_deteccion": round(detectadas / n, 6),
        "score_min": round(float(score.min()), 4),
        "score_mediana": round(float(np.median(score)), 4),
        "score_max": round(float(score.max()), 4),
    }, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
