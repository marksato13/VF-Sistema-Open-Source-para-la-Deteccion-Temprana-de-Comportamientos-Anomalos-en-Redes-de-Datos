#!/usr/bin/env python3
"""Puntúa un CSV de ventanas con el MISMO criterio que el motor desplegado,
conservando el tiempo de cada ventana (para el tiempo de detección, nota 19).

Fidelidad al detector en vivo (`scripts/engine/motor_decision.py`):
  - El modelo es un **Pipeline** de sklearn: se puntúa con `score_samples(X)`.
  - ALERT si `score < umbral`, con `umbral =
    manifest["detectors"][<detector>]["calibration"]["threshold"]`
    (comparación declarada "score < threshold").
  - Las features y su ORDEN salen de `manifest["feature_names"]` (28 en v2).

A diferencia de `puntuar_deteccion.py` (agregado TPR), este emite el veredicto por
ventana y marca la PRIMERA ventana con alerta → el tiempo de detección medido
contra la línea temporal del propio PCAP (`window_end_utc`), sin reloj de pared.

    python3 20-puntuar-por-ventana.py \
        --modelo artifacts/preliminar/if_recalibrado_desplegable.joblib \
        --manifest artifacts/preliminar/manifest-if-recalibrado.json \
        --detector-name if_recalibrado_2026_09 \
        --csv ventanas.csv --t-inicio 2026-10-02T12:00:00+00:00
"""
from __future__ import annotations

import argparse
import csv
import json
from datetime import datetime
from pathlib import Path

import joblib
import numpy as np


def _a_epoch(valor: str) -> float | None:
    if valor in ("", None):
        return None
    try:
        return float(valor)
    except (TypeError, ValueError):
        pass
    try:
        return datetime.fromisoformat(valor.replace("Z", "+00:00")).timestamp()
    except ValueError:
        return None


def cargar_umbral_y_features(manifest: Path, detector: str) -> tuple[float, list[str]]:
    d = json.loads(manifest.read_text(encoding="utf-8"))
    det = d["detectors"][detector]
    comp = det["calibration"].get("comparison", "score < threshold")
    if comp != "score < threshold":
        raise SystemExit("comparación inesperada en el manifest: %r" % comp)
    umbral = float(det["calibration"]["threshold"])
    feats = d["feature_names"]
    return umbral, feats


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--modelo", required=True, type=Path, help="Pipeline .joblib")
    ap.add_argument("--manifest", required=True, type=Path)
    ap.add_argument("--detector-name", required=True)
    ap.add_argument("--csv", required=True, type=Path, help="CSV de ventanas (con window_end_utc)")
    ap.add_argument("--columna-tiempo", default="window_end_utc")
    ap.add_argument("--t-inicio", default="", help="inicio del ataque (epoch o ISO)")
    ap.add_argument("--etiqueta", default="", help="filtra por columna label si el CSV mezcla clases")
    ap.add_argument("--salida-csv", default="", help="opcional: window_end_utc,score,detectada por fila")
    a = ap.parse_args()

    pipeline = joblib.load(a.modelo)
    umbral, feats = cargar_umbral_y_features(a.manifest, a.detector_name)

    with a.csv.open(newline="", encoding="utf-8") as f:
        filas = list(csv.DictReader(f))
    if a.etiqueta:
        filas = [r for r in filas if r.get("label", "") == a.etiqueta]
    if not filas:
        print(json.dumps({"error": "sin filas"}))
        return 1
    faltan = [c for c in feats if c not in filas[0]]
    if faltan:
        print(json.dumps({"error": "faltan features en el CSV", "faltan": faltan}))
        return 1
    if a.columna_tiempo not in filas[0]:
        print(json.dumps({"error": "falta columna de tiempo", "columna": a.columna_tiempo}))
        return 1

    X = np.asarray([[float(r[c] or 0) for c in feats] for r in filas], dtype=float)
    score = pipeline.score_samples(X)          # igual que el motor
    detectada = score < umbral                 # ALERT

    t_inicio = _a_epoch(a.t_inicio) if a.t_inicio else None
    orden = sorted(range(len(filas)),
                   key=lambda i: (_a_epoch(filas[i][a.columna_tiempo]) or float("inf")))
    primera = None
    for i in orden:
        if detectada[i]:
            te = _a_epoch(filas[i][a.columna_tiempo])
            primera = {"window_end_utc": filas[i][a.columna_tiempo], "epoch": te,
                       "score": round(float(score[i]), 6)}
            if t_inicio is not None and te is not None:
                primera["tiempo_deteccion_s"] = round(te - t_inicio, 3)
            break

    if a.salida_csv:
        with open(a.salida_csv, "w", newline="", encoding="utf-8") as f:
            w = csv.writer(f)
            w.writerow(["window_end_utc", "score", "detectada"])
            for i in range(len(filas)):
                w.writerow([filas[i][a.columna_tiempo], round(float(score[i]), 6), int(detectada[i])])

    n = len(filas)
    print(json.dumps({
        "csv": str(a.csv),
        "ventanas": n,
        "umbral": round(umbral, 6),
        "detectadas": int(detectada.sum()),
        "tasa_deteccion": round(float(detectada.sum()) / n, 6),
        "primera_alerta": primera,
        "score_min": round(float(score.min()), 4),
        "score_mediana": round(float(np.median(score)), 4),
    }, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
