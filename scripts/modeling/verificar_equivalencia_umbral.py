#!/usr/bin/env python3
"""Comprueba que el umbral del modelo desplegado es el mismo en las dos escalas.

`entrenar_preliminar.py` informa el umbral en `decision_function`; el motor puntúa
con `score_samples`. En un Isolation Forest de scikit-learn

    decision_function(x) = score_samples(x) - offset_

y con `contamination="auto"` el `offset_` vale -0,5. Si eso se cumple en el artefacto
REAL, el umbral -0,068892 (decision_function) y el -0,568892 (score_samples) son el
mismo punto de corte, y la promoción al motor no cambió la decisión.

Este guion lo verifica sobre el joblib desplegado, sin tocarlo:
  1. carga el modelo (Pipeline o estimador) y lee el `offset_` del Isolation Forest;
  2. puntúa filas con las dos funciones y mide la diferencia frente a `offset_`
     (filas del CSV si se da; si no, filas sintéticas del tamaño de entrada del
     modelo: la relación es algebraica y no depende de los datos);
  3. lee el umbral del manifiesto y, si se pasa, el umbral en decision_function del
     informe de calibración, y comprueba que difieren exactamente en `offset_`;
  4. escribe un JSON de evidencia con los SHA-256 de lo que se comprobó.

No modifica el modelo, el manifiesto ni el servicio. Sale con código 0 si todo es
equivalente y 1 si algo no cuadra.

    python3 scripts/modeling/verificar_equivalencia_umbral.py \\
        --modelo artifacts/preliminar/if_recalibrado_desplegable.joblib \\
        --manifiesto artifacts/preliminar/manifest-if-recalibrado.json \\
        --detector if_recalibrado_2026_09 \\
        --umbral-decision -0.06889178778834089 \\
        --salida /tmp/equivalencia-umbral.json
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import sys
from pathlib import Path

import joblib
import numpy as np

TOLERANCIA = 1e-9


def sha256(ruta: Path) -> str:
    return hashlib.sha256(Path(ruta).read_bytes()).hexdigest()


def desempaquetar(obj):
    """El joblib puede ser el Pipeline, el estimador o un paquete dict con él."""
    if isinstance(obj, dict):
        for clave in ("pipeline", "modelo", "model", "estimador"):
            if clave in obj:
                return obj[clave]
        raise ValueError("paquete dict sin clave de modelo conocida: %s" % sorted(obj))
    return obj


def estimador_final(modelo):
    """El Isolation Forest: último paso si es un Pipeline, o el propio objeto."""
    pasos = getattr(modelo, "steps", None)
    return pasos[-1][1] if pasos else modelo


def filas(modelo, csv_path: Path | None, columnas: list[str] | None, n: int, semilla: int):
    if csv_path:
        with Path(csv_path).open(newline="", encoding="utf-8") as fh:
            lector = csv.DictReader(fh)
            datos = [[float(r[c]) for c in columnas] for r in lector] if columnas else None
        if not datos:
            raise ValueError("el CSV no tiene filas con las columnas del esquema")
        return np.asarray(datos[:n], dtype=float), "csv"
    d = getattr(modelo, "n_features_in_", None) or getattr(estimador_final(modelo), "n_features_in_")
    return np.random.default_rng(semilla).normal(size=(n, int(d))), "sinteticas"


def umbral_del_manifiesto(manifiesto: dict, detector: str | None) -> float:
    ev = manifiesto.get("evaluation", {})
    if detector and detector in ev:
        return float(ev[detector]["threshold_used"])
    for clave in ("threshold_used", "umbral", "threshold"):
        if clave in manifiesto:
            return float(manifiesto[clave])
    if len(ev) == 1:
        return float(next(iter(ev.values()))["threshold_used"])
    raise ValueError("no encuentro el umbral del detector %r en el manifiesto" % detector)


def verificar(modelo_path: Path, manifiesto_path: Path | None = None, detector: str | None = None,
              umbral_decision: float | None = None, csv_path: Path | None = None,
              esquema: Path | None = None, n: int = 256, semilla: int = 0) -> dict:
    modelo = desempaquetar(joblib.load(modelo_path))
    est = estimador_final(modelo)
    if not hasattr(est, "offset_"):
        raise ValueError("el estimador final (%s) no tiene offset_" % type(est).__name__)
    offset = float(est.offset_)

    columnas = None
    if esquema:
        columnas = [f["name"] if isinstance(f, dict) else f
                    for f in json.loads(Path(esquema).read_text(encoding="utf-8"))["features"]]
    X, origen = filas(modelo, csv_path, columnas, n, semilla)
    ss = np.asarray(modelo.score_samples(X), dtype=float)
    df = np.asarray(modelo.decision_function(X), dtype=float)
    desvio = float(np.max(np.abs((ss - df) - offset)))

    r = {
        "modelo": str(modelo_path), "sha256_modelo": sha256(modelo_path),
        "tipo": type(modelo).__name__, "estimador_final": type(est).__name__,
        "contamination": getattr(est, "contamination", None),
        "offset_": offset, "filas": int(len(X)), "origen_filas": origen,
        "max_desvio_ss_menos_df_vs_offset": desvio,
        "relacion_ss_df_ok": desvio < TOLERANCIA,
    }
    ok = r["relacion_ss_df_ok"]

    if manifiesto_path:
        man = json.loads(Path(manifiesto_path).read_text(encoding="utf-8"))
        u_ss = umbral_del_manifiesto(man, detector)
        r.update({"manifiesto": str(manifiesto_path), "sha256_manifiesto": sha256(manifiesto_path),
                  "detector": detector, "umbral_score_samples_manifiesto": u_ss,
                  "umbral_decision_function_implicito": u_ss - offset})
        if umbral_decision is not None:
            dif = abs(u_ss - (float(umbral_decision) + offset))
            r.update({"umbral_decision_function_informe": float(umbral_decision),
                      "desvio_umbrales": dif, "umbrales_equivalentes": dif < 1e-6})
            ok = ok and r["umbrales_equivalentes"]

    r["veredicto"] = "EQUIVALENTE" if ok else "NO_EQUIVALENTE"
    return r


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--modelo", type=Path, required=True, help="joblib desplegado")
    ap.add_argument("--manifiesto", type=Path, help="manifiesto del detector")
    ap.add_argument("--detector", help="clave del detector en el manifiesto")
    ap.add_argument("--umbral-decision", type=float,
                    help="umbral en decision_function del informe de calibración")
    ap.add_argument("--csv", type=Path, help="filas reales (opcional)")
    ap.add_argument("--esquema", type=Path, help="esquema de variables para leer el CSV")
    ap.add_argument("--filas", type=int, default=256)
    ap.add_argument("--salida", type=Path, help="JSON de evidencia")
    a = ap.parse_args(argv)

    r = verificar(a.modelo, a.manifiesto, a.detector, a.umbral_decision,
                  a.csv, a.esquema, a.filas)
    texto = json.dumps(r, indent=2, ensure_ascii=False, sort_keys=True)
    print(texto)
    if a.salida:
        a.salida.write_text(texto + "\n", encoding="utf-8")
    return 0 if r["veredicto"] == "EQUIVALENTE" else 1


if __name__ == "__main__":
    sys.exit(main())
