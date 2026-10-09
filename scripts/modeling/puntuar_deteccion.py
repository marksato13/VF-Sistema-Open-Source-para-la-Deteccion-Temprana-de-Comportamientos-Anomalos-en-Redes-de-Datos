#!/usr/bin/env python3
"""Puntua un CSV de ventanas con el modelo PRELIMINAR y su umbral congelado.

Detecta = decision_function(x) < umbral. Sobre un CSV de anomalias, la fraccion
detectada es el TPR (tasa de deteccion). Sobre normal, seria el FPR.

    python3 puntuar_deteccion.py --modelo /tmp/recal/modelo.joblib \
        --csv anomalias.csv [--etiqueta anomaly]
"""
from __future__ import annotations
import argparse, csv, hashlib, json
from pathlib import Path
import numpy as np
import joblib


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--modelo", required=True)
    ap.add_argument("--csv", required=True)
    ap.add_argument("--etiqueta", default="", help="si el CSV mezcla clases, filtra por columna label")
    ap.add_argument("--particion", default="", help="filtra train/validation/test si el CSV está particionado")
    ap.add_argument("--tipo", choices=("anomalias", "normal"), default="anomalias")
    ap.add_argument("--manifest", type=Path, help="obligatorio para un Pipeline desplegado")
    ap.add_argument("--detector-name", help="clave en detectors del manifiesto")
    ap.add_argument("--schema", type=Path, help="esquema de features del Pipeline desplegado")
    ap.add_argument("--informe", type=Path, help="guarda JSON con fuente y SHA-256")
    a = ap.parse_args()

    ruta_csv = Path(a.csv)
    h = hashlib.sha256()
    with ruta_csv.open("rb") as archivo:
        for bloque in iter(lambda: archivo.read(1 << 20), b""):
            h.update(bloque)
    detector = None
    if a.manifest:
        if not (a.detector_name and a.schema):
            ap.error("--manifest requiere --detector-name y --schema")
        manifest = json.loads(a.manifest.read_text(encoding="utf-8"))
        detector = manifest["detectors"][a.detector_name]
        hmodelo = detector.get("model_sha256")
        if not hmodelo:
            raise SystemExit("El manifiesto no declara SHA-256 del modelo: no cargar joblib")
        if hashlib.sha256(Path(a.modelo).read_bytes()).hexdigest() != hmodelo:
            raise SystemExit("SHA-256 del modelo no coincide con el manifiesto")
    paq = joblib.load(a.modelo)
    pipeline = not isinstance(paq, dict)
    if pipeline:
        if not (detector and a.schema):
            ap.error("Pipeline desplegado: requiere --manifest, --detector-name y --schema")
        esquema = json.loads(a.schema.read_text(encoding="utf-8"))
        feats = [x["name"] for x in sorted(esquema["features"], key=lambda x: x["order"])]
        umbral = float(detector["calibration"]["threshold"])
    else:
        modelo, escalador = paq["modelo"], paq["escalador"]
        feats, umbral = paq["features"], float(paq["umbral"])

    with open(a.csv, newline="", encoding="utf-8") as f:
        filas = list(csv.DictReader(f))
    if a.etiqueta:
        filas = [r for r in filas if r.get("label", "") == a.etiqueta]
    if a.particion:
        filas = [r for r in filas if r.get("particion", "") == a.particion]
    if not filas:
        print(json.dumps({"error": "sin filas"})); return 1
    if "label" in filas[0] and not a.etiqueta:
        etiquetas = {r.get("label", "") for r in filas}
        esperado = {"normal"} if a.tipo == "normal" else {"anomaly"}
        if etiquetas != esperado:
            raise SystemExit("Etiquetas incompatibles o mixtas: indicar --etiqueta y revisar la fuente")

    faltan = [c for c in feats if c not in filas[0]]
    if faltan:
        print(json.dumps({"error": "faltan features en el CSV", "faltan": faltan})); return 1

    try:
        X = np.asarray([[float(r[c]) for c in feats] for r in filas], dtype=float)
    except (ValueError, TypeError) as exc:
        raise SystemExit("Feature ausente o inválida; no imputar ceros: %s" % exc)
    if not np.isfinite(X).all():
        raise SystemExit("Features no finitas; no puntuar")
    score = paq.score_samples(X) if pipeline else modelo.decision_function(escalador.transform(X))
    detectadas = int(np.sum(score < umbral))
    n = len(filas)
    informe = {
        "csv": a.csv,
        "csv_sha256": h.hexdigest(),
        "modelo": str(a.modelo),
        "modelo_tipo": "pipeline-score_samples" if pipeline else "preliminar-decision_function",
        "schema": a.schema.name if pipeline else paq.get("schema"),
        "features": feats,
        "n_features": len(feats),
        "tipo": a.tipo,
        "particion": a.particion,
        "filas": n,
        "umbral": round(umbral, 6),
        "detectadas (score<umbral)": detectadas,
        "tasa_deteccion": round(detectadas / n, 6),
        "score_min": round(float(score.min()), 4),
        "score_mediana": round(float(np.median(score)), 4),
        "score_max": round(float(score.max()), 4),
    }
    informe["fpr" if a.tipo == "normal" else "tpr"] = informe["tasa_deteccion"]
    if a.informe:
        a.informe.parent.mkdir(parents=True, exist_ok=True)
        a.informe.write_text(json.dumps(informe, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps(informe, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
