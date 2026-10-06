#!/usr/bin/env python3
"""Modelo PRELIMINAR: entrena con trafico limpio y congela el umbral.

No es el modelo definitivo de la tesis. Es para el ensayo funcional: entrenar
con la linea base limpia que se esta capturando, congelar el umbral desde
validacion, y GUARDAR el modelo para poder puntuar despues los ataques de la
Kali y comprobar que los detecta.

Por que no reutiliza train_multilayer_v2.py: aquel exige un fichero de anomalias
-que aun no existe, la Kali no ha corrido- y no guarda el modelo en disco, solo
un informe. Aqui el umbral sale SOLO de validacion (no necesita anomalias) y el
modelo se serializa con su escalador y su orden de features, que es lo unico que
hace falta para puntuar ventanas nuevas de forma identica.

Entrada: el CSV ya particionado (columna `particion` de particionar_linea_base).
Se entrena sobre `train`, el umbral es el percentil `alpha` de `validation`, y se
mide la tasa de falsos positivos sobre `test` -que, por construccion, deberia
rondar alpha si el modelo generaliza-.

    python3 entrenar_preliminar.py \\
        --entrada particionado.csv \\
        --schema  configs/features/multilayer-v2.json \\
        --salida  artifacts/preliminar/if-v2.joblib \\
        --informe artifacts/preliminar/if-v2.json
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
from sklearn.ensemble import IsolationForest
from sklearn.preprocessing import StandardScaler

try:
    import joblib
except ImportError:  # el .venv del sensor lo trae; fuera, es opcional
    joblib = None


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for trozo in iter(lambda: f.read(1 << 20), b""):
            h.update(trozo)
    return h.hexdigest()


def cargar(entrada: Path, schema: Path, solo_elegibles: bool):
    contrato = json.loads(schema.read_text(encoding="utf-8"))
    nombres = [x["name"] for x in sorted(contrato["features"], key=lambda x: x["order"])]
    with entrada.open(newline="", encoding="utf-8") as f:
        filas = list(csv.DictReader(f))
    if not filas:
        raise SystemExit("el CSV no tiene filas")
    faltan = [n for n in nombres if n not in filas[0]]
    if faltan:
        raise SystemExit("faltan features del contrato: %s" % faltan)
    if solo_elegibles:
        filas = [r for r in filas if str(r.get("eligible_training", "")).lower() == "true"]
    return nombres, filas


def matriz(filas, nombres):
    return np.asarray([[float(r[k]) for k in nombres] for r in filas], dtype=float)


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--entrada", type=Path, required=True)
    p.add_argument("--schema", type=Path, required=True)
    p.add_argument("--salida", type=Path, required=True, help="joblib del modelo")
    p.add_argument("--informe", type=Path, required=True)
    p.add_argument("--alpha", type=float, default=0.05,
                   help="cola de validacion que define el umbral (y FPR objetivo)")
    p.add_argument("--n-estimators", type=int, default=500)
    p.add_argument("--semilla", type=int, default=20260813)
    p.add_argument("--con-no-elegibles", action="store_true",
                   help="incluir ventanas con historia < 60 s (por omision se excluyen)")
    a = p.parse_args()

    nombres, filas = cargar(a.entrada, a.schema, not a.con_no_elegibles)
    por = {"train": [], "validation": [], "test": []}
    for r in filas:
        if r.get("particion") in por:
            por[r["particion"]].append(r)
    for conjunto, items in por.items():
        if not items:
            raise SystemExit("particion vacia: %s. Reparte el CSV con "
                             "particionar_linea_base.py antes de entrenar." % conjunto)

    xtrain = matriz(por["train"], nombres)
    xval = matriz(por["validation"], nombres)
    xtest = matriz(por["test"], nombres)

    escalador = StandardScaler().fit(xtrain)
    ztrain, zval, ztest = (escalador.transform(x) for x in (xtrain, xval, xtest))

    modelo = IsolationForest(n_estimators=a.n_estimators, random_state=a.semilla,
                             contamination="auto", n_jobs=1, max_features=1.0).fit(ztrain)

    # decision_function: mas alto = mas normal. El umbral es la cola baja de
    # validacion; una ventana con score < umbral se marca anomala. El umbral se
    # congela AQUI y no se vuelve a tocar: evaluar la Kali con un umbral elegido
    # despues de ver la Kali seria hacer trampa.
    val = modelo.decision_function(zval)
    umbral = float(np.quantile(val, a.alpha))
    test = modelo.decision_function(ztest)

    fpr_test = float(np.mean(test < umbral))
    informe = {
        "tipo": "modelo-preliminar-ensayo-funcional",
        "generado": datetime.now(timezone.utc).isoformat(),
        "schema": a.schema.name,
        "n_features": len(nombres),
        "features": nombres,
        "filas": {k: len(v) for k, v in por.items()},
        "alpha": a.alpha,
        "umbral_decision_function": umbral,
        "fpr_validacion": round(float(np.mean(val < umbral)), 6),
        "fpr_test": round(fpr_test, 6),
        "fpr_test_objetivo": a.alpha,
        "parametros": {"n_estimators": a.n_estimators, "semilla": a.semilla},
        "entrada_sha256": sha256(a.entrada),
        "nota": "umbral congelado desde validacion; la Kali se puntua despues "
                "con este mismo modelo, sin reajustar nada",
    }

    a.salida.parent.mkdir(parents=True, exist_ok=True)
    if joblib is not None:
        joblib.dump({"modelo": modelo, "escalador": escalador, "umbral": umbral,
                     "features": nombres, "schema": a.schema.name,
                     "alpha": a.alpha}, a.salida)
        informe["salida_sha256"] = sha256(a.salida)
    else:
        informe["salida_sha256"] = "joblib no disponible: modelo no guardado"

    a.informe.parent.mkdir(parents=True, exist_ok=True)
    a.informe.write_text(json.dumps(informe, indent=2, sort_keys=True) + "\n",
                         encoding="utf-8")
    print(json.dumps(informe, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
