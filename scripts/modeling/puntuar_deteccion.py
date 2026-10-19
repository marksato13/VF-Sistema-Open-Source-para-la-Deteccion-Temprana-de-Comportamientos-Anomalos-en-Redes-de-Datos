#!/usr/bin/env python3
"""Puntua un CSV de ventanas con un modelo y su umbral congelado.

Detecta = score(x) < umbral. Sobre un CSV de ANOMALIAS la fraccion detectada es
el TPR (tasa de deteccion); sobre NORMAL es el FPR. NO despliega nada: solo lee
el modelo y el CSV y mide. Es el puntuador del ensayo en seco de reentrenamiento
(docs/RUNBOOK-REENTRENAMIENTO-DEMO.md): el MISMO CSV se puntua con el modelo
ANTES y con el DESPUES, y comparar_reentrenamiento.py empareja los dos informes.

Acepta DOS formatos de modelo, los dos que viven en el sistema:

  * Paquete preliminar (entrenar_preliminar.py): un dict
    {modelo, escalador, umbral, features}. Score = decision_function y el umbral
    esta en esa escala. No necesita manifiesto.
  * Pipeline desplegable (promover_preliminar.py) + su manifiesto: el artefacto
    que carga el motor, un Pipeline(escalador, modelo) que se puntua con
    score_samples(X_crudo); el umbral -en escala score_samples- vive en
    detectors.<nombre>.calibration del manifiesto, con la regla "score < threshold".
    Se pasa con --manifest --detector-name (y --schema para fijar el orden).

Las dos escalas difieren en offset_ (score_samples = decision_function - offset_),
pero la DECISION score<umbral es identica, asi que las tasas son comparables entre
un informe de paquete y uno de Pipeline sobre el mismo CSV.

Emite csv_sha256, tipo y features para que comparar_reentrenamiento.py pueda
emparejar dos informes del MISMO conjunto y negarse si las fuentes no coinciden.
No imputa: una feature ausente o no numerica detiene el ensayo.

    # paquete preliminar (candidato)
    python3 puntuar_deteccion.py --modelo cand.joblib --csv ataques.csv \\
        --tipo anomalias --informe tpr-despues.json
    # Pipeline desplegado (vigente)
    python3 puntuar_deteccion.py --modelo vigente.joblib --manifest manifest.json \\
        --detector-name if_recalibrado_2026_09 --schema configs/features/multilayer-v2.json \\
        --csv ataques.csv --tipo anomalias --informe tpr-antes.json
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import sys
from pathlib import Path

import numpy as np
import joblib

REGLA = "score < threshold"


def sha256(ruta: Path) -> str:
    h = hashlib.sha256()
    with Path(ruta).open("rb") as f:
        for trozo in iter(lambda: f.read(1 << 20), b""):
            h.update(trozo)
    return h.hexdigest()


def features_del_esquema(schema: Path) -> list[str]:
    contrato = json.loads(Path(schema).read_text(encoding="utf-8"))
    return [f["name"] for f in sorted(contrato["features"], key=lambda f: f["order"])]


def cargar_modelo(ruta_modelo: Path, manifest: Path | None, detector_name: str | None,
                  schema: Path | None):
    """Devuelve (puntuar(X)->scores, umbral, features, formato, detector).

    Distingue el paquete preliminar (dict) del Pipeline desplegable por el tipo
    de objeto serializado; para el Pipeline hacen falta manifiesto y detector.
    """
    obj = joblib.load(ruta_modelo)

    if isinstance(obj, dict) and {"modelo", "escalador", "umbral", "features"} <= set(obj):
        modelo, escalador = obj["modelo"], obj["escalador"]
        feats = list(obj["features"])
        if schema is not None and features_del_esquema(schema) != feats:
            raise SystemExit("las features del paquete no coinciden con --schema")
        umbral = float(obj["umbral"])

        def puntuar(X):
            return np.asarray(modelo.decision_function(escalador.transform(X)), dtype=float)

        return puntuar, umbral, feats, "paquete", None

    if manifest is None or detector_name is None:
        raise SystemExit("el joblib no es un paquete preliminar; para un Pipeline "
                         "desplegable hacen falta --manifest y --detector-name")
    man = json.loads(Path(manifest).read_text(encoding="utf-8"))
    det = (man.get("detectors") or {}).get(detector_name)
    if not det:
        raise SystemExit("el manifiesto no tiene el detector %r" % detector_name)
    cal = det.get("calibration") or {}
    if cal.get("comparison") != REGLA:
        raise SystemExit("regla de comparacion inesperada: %r (se esperaba %r)"
                         % (cal.get("comparison"), REGLA))
    umbral = float(cal["threshold"])
    if schema is not None:
        feats = features_del_esquema(schema)
        if det.get("features") and list(det["features"]) != feats:
            raise SystemExit("las features del esquema no coinciden con las del manifiesto")
    elif det.get("features"):
        feats = list(det["features"])
    else:
        raise SystemExit("no se pudieron determinar las features: pase --schema")

    def puntuar(X):
        return np.asarray(obj.score_samples(X), dtype=float)

    return puntuar, umbral, feats, "pipeline", detector_name


def leer_matriz(csv_path: Path, feats: list[str], etiqueta: str):
    with Path(csv_path).open(newline="", encoding="utf-8") as f:
        filas = list(csv.DictReader(f))
    if etiqueta:
        filas = [r for r in filas if r.get("label", "") == etiqueta]
    if not filas:
        raise SystemExit("sin filas" + (" con label=%s" % etiqueta if etiqueta else ""))
    faltan = [c for c in feats if c not in filas[0]]
    if faltan:
        raise SystemExit("faltan features en el CSV: %s" % faltan)
    X = np.empty((len(filas), len(feats)), dtype=float)
    for i, r in enumerate(filas):
        for j, c in enumerate(feats):
            v = r[c]
            try:
                X[i, j] = float(v)
            except (TypeError, ValueError):
                raise SystemExit("fila %d, feature %r con valor no numerico %r: el ensayo "
                                 "no imputa, revise el CSV" % (i, c, v))
    return X, len(filas)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--modelo", type=Path, required=True)
    ap.add_argument("--csv", type=Path, required=True)
    ap.add_argument("--manifest", type=Path, help="manifiesto del Pipeline desplegable")
    ap.add_argument("--detector-name", help="detector dentro del manifiesto")
    ap.add_argument("--schema", type=Path, help="contrato v2 (fija el orden de features)")
    ap.add_argument("--tipo", default="", choices=["", "normal", "anomalias"],
                    help="normal -> la tasa es FPR; anomalias -> TPR")
    ap.add_argument("--particion", default=None, help="etiqueta del hold-out (informativo)")
    ap.add_argument("--etiqueta", default="", help="si el CSV mezcla clases, filtra por label")
    ap.add_argument("--sha256", default=None,
                    help="aborta si el joblib no tiene este sha256 (un joblib es codigo)")
    ap.add_argument("--informe", type=Path, help="guardar el informe JSON")
    a = ap.parse_args(argv)

    modelo_sha = sha256(a.modelo)
    if a.sha256 and a.sha256 != modelo_sha:
        raise SystemExit("el modelo %s tiene sha256 %s, no %s: no se carga"
                         % (a.modelo, modelo_sha, a.sha256))

    puntuar, umbral, feats, formato, detector = cargar_modelo(
        a.modelo, a.manifest, a.detector_name, a.schema)
    X, n = leer_matriz(a.csv, feats, a.etiqueta)
    score = puntuar(X)
    detectadas = int(np.sum(score < umbral))
    tasa = round(detectadas / n, 6)

    informe = {
        "csv": str(a.csv), "csv_sha256": sha256(a.csv),
        "modelo": str(a.modelo), "modelo_sha256": modelo_sha,
        "formato": formato, "detector": detector,
        "tipo": a.tipo, "particion": a.particion,
        "n_features": len(feats), "features": feats,
        "filas": n, "umbral": round(umbral, 6),
        "detectadas": detectadas, "tasa_deteccion": tasa,
        "score_min": round(float(score.min()), 4),
        "score_mediana": round(float(np.median(score)), 4),
        "score_max": round(float(score.max()), 4),
    }
    if a.tipo == "normal":
        informe["fpr"] = tasa
    elif a.tipo == "anomalias":
        informe["tpr"] = tasa

    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    print(json.dumps(informe, indent=2, ensure_ascii=False))
    if a.informe:
        a.informe.parent.mkdir(parents=True, exist_ok=True)
        a.informe.write_text(json.dumps(informe, indent=2, ensure_ascii=False) + "\n",
                             encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
