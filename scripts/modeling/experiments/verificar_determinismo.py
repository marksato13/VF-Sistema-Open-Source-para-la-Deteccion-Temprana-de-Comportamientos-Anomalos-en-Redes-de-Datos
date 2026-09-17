#!/usr/bin/env python3
"""Verifica el determinismo del ajuste del modelo congelado (D-06).

El plan de validacion declara este umbral: SHA-256 identico del objeto
ajustado en 10 ejecuciones repetidas. Aqui se comprueba, no se afirma.

    python3 scripts/modeling/experiments/verificar_determinismo.py
"""
from __future__ import annotations
import csv, hashlib, io, json, math
from pathlib import Path

import joblib
import numpy as np
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler
from sklearn.svm import OneClassSVM

REPO = Path(__file__).resolve().parents[3]
MANIFEST = REPO / "artifacts/model/manifest.json"
NORMAL = REPO / "artifacts/dataset/multilayer-v2-normal.csv"
OUT = REPO / "results/ablacion/determinismo.json"
N_EJECUCIONES = 10


def main() -> None:
    man = json.loads(MANIFEST.read_text(encoding="utf-8"))
    feats = man["feature_names"]
    n = list(csv.DictReader(NORMAL.open(encoding="utf-8")))
    M = lambda rows: np.array([[float(r[f]) for f in feats] for r in rows], dtype=float)
    Xtr = M([r for r in n if r["partition"] == "train"])
    Xva = M([r for r in n if r["partition"] == "validation"])

    hashes, umbrales = [], []
    for i in range(1, N_EJECUCIONES + 1):
        p = Pipeline([("scaler", StandardScaler()),
                      ("detector", OneClassSVM(kernel="rbf", gamma="scale", nu=0.05, cache_size=200))])
        p.fit(Xtr)
        buf = io.BytesIO()
        joblib.dump(p, buf)
        h = hashlib.sha256(buf.getvalue()).hexdigest()
        sv = p.score_samples(Xva)
        u = float(sorted(sv)[math.floor(0.05 * len(sv))])
        hashes.append(h)
        umbrales.append(u)
        print(f"  ejecución {i:2}: sha {h[:16]}  umbral {u!r}")

    unicos_h, unicos_u = set(hashes), set(umbrales)
    ok_h, ok_u = len(unicos_h) == 1, len(unicos_u) == 1
    coincide_manifiesto = umbrales[0] == man["evaluation"]["ocsvm_scaled"]["threshold_used"]

    print(f"\n  hashes distintos : {len(unicos_h)}  → {'DETERMINISTA' if ok_h else 'NO determinista'}")
    print(f"  umbrales distintos: {len(unicos_u)}  → {'DETERMINISTA' if ok_u else 'NO determinista'}")
    print(f"  coincide con el manifiesto congelado: {'sí' if coincide_manifiesto else 'NO'}")

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps({
        "n_ejecuciones": N_EJECUCIONES,
        "hashes_distintos": len(unicos_h),
        "umbrales_distintos": len(unicos_u),
        "sha256_del_objeto_ajustado": sorted(unicos_h),
        "umbral": umbrales[0],
        "coincide_con_manifiesto": coincide_manifiesto,
        "determinista": ok_h and ok_u and coincide_manifiesto,
        "scikit_learn": man["scikit_learn"], "numpy": man["numpy"],
    }, indent=2, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")
    print(f"\nGenerado: {OUT.relative_to(REPO)}")


if __name__ == "__main__":
    main()
