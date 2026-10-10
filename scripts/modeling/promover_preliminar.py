#!/usr/bin/env python3
"""Convierte el paquete de entrenar_preliminar.py en un artefacto que el motor carga.

`entrenar_preliminar.py` guarda un PAQUETE: un dict con el IsolationForest, su
escalador por separado, el umbral en escala `decision_function` y el orden de
variables. El motor (`scripts/engine/motor_decision.py`) espera otra cosa:

  1. un objeto con `score_samples(X_crudo)` -> aqui, `Pipeline([escalador, modelo])`;
  2. el umbral en escala `score_samples`, en `detectors.<nombre>.calibration` del
     manifiesto con la regla `score < threshold` (`motor_decision.load_threshold`);
  3. el contrato de variables **v2** (28), en el orden exacto del extractor: el motor
     aborta si el esquema no coincide con `extract_multilayer_v2.FEATURE_NAMES`.

Este guion hace la conversión y la VERIFICA de una vez, sin tocar nada desplegado:
  - orden de variables del paquete = contrato = extractor del motor;
  - `score_samples - decision_function = offset_` sobre filas de comprobación;
  - mismas decisiones antes y después de convertir el umbral;
  - hashes del paquete, del informe y del artefacto nuevo;
  - equivalencia final con `verificar_equivalencia_umbral.py` sobre el par escrito.

Escribe el artefacto y su manifiesto en rutas nuevas; se niega a sobrescribir. El
umbral se guarda con precisión completa (sin redondear). El manifiesto lleva también
`evaluation.<nombre>` para que el panel muestre las métricas del detector correcto.

    python3 scripts/modeling/promover_preliminar.py \\
        --paquete  artifacts/preliminar/if-v2.joblib \\
        --informe  artifacts/preliminar/if-v2.json \\
        --detector if_recalibrado_AAAA_MM \\
        --salida-modelo     artifacts/preliminar/if_recalibrado_AAAA_MM_desplegable.joblib \\
        --salida-manifiesto artifacts/preliminar/manifest-if-recalibrado-AAAA-MM.json \\
        [--deteccion-global 0.69 --deteccion-kali 0.69 --deteccion-fuente "puntuar_deteccion, nota M"]
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import platform
import sys
from datetime import datetime, timezone
from pathlib import Path

import joblib
import numpy as np
import sklearn
from sklearn.pipeline import Pipeline

REPO = Path(__file__).resolve().parents[2]
ESQUEMA_V2 = REPO / "configs/features/multilayer-v2.json"
EXTRACTOR_V2 = REPO / "scripts/features/extract_multilayer_v2.py"
VERIFICADOR = REPO / "scripts/modeling/verificar_equivalencia_umbral.py"
REGLA = "score < threshold"


def sha256(ruta: Path) -> str:
    return hashlib.sha256(Path(ruta).read_bytes()).hexdigest()


def _modulo(nombre: str, ruta: Path):
    spec = importlib.util.spec_from_file_location(nombre, ruta)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def orden_del_esquema(esquema: Path) -> list[str]:
    contrato = json.loads(Path(esquema).read_text(encoding="utf-8"))
    return [f["name"] for f in sorted(contrato["features"], key=lambda f: f["order"])]


def comprobar_orden(paquete: dict, esquema: Path) -> list[str]:
    """El paquete, el contrato y el extractor del motor deben dar el MISMO orden."""
    contrato = orden_del_esquema(esquema)
    extractor = list(_modulo("extract_multilayer_v2", EXTRACTOR_V2).FEATURE_NAMES)
    if contrato != extractor:
        raise ValueError(
            "el esquema %s no es el contrato del motor (%d variables frente a %d del "
            "extractor v2). El motor solo acepta multilayer-v2.json."
            % (Path(esquema).name, len(contrato), len(extractor)))
    if list(paquete["features"]) != contrato:
        raise ValueError(
            "el paquete se entrenó con otras variables u otro orden (%d variables, "
            "esquema %r). Reentrene con --schema configs/features/multilayer-v2.json."
            % (len(paquete["features"]), paquete.get("schema")))
    return contrato


def promover(paquete_path: Path, detector: str, salida_modelo: Path, salida_manifiesto: Path,
             informe_path: Path | None = None, esquema: Path = ESQUEMA_V2,
             deteccion_global: float | None = None, deteccion_kali: float | None = None,
             deteccion_fuente: str | None = None, sobrescribir: bool = False,
             filas_control: int = 512, semilla: int = 0) -> dict:
    for destino in (salida_modelo, salida_manifiesto):
        if Path(destino).exists() and not sobrescribir:
            raise FileExistsError("ya existe %s: no se sobrescribe un artefacto" % destino)

    paquete = joblib.load(paquete_path)
    if not isinstance(paquete, dict) or not {"modelo", "escalador", "umbral", "features"} <= set(paquete):
        raise ValueError("no parece un paquete de entrenar_preliminar.py "
                         "(faltan modelo, escalador, umbral o features)")
    nombres = comprobar_orden(paquete, esquema)

    modelo, escalador = paquete["modelo"], paquete["escalador"]
    offset = float(modelo.offset_)
    umbral_df = float(paquete["umbral"])
    umbral_ss = umbral_df + offset          # decision_function = score_samples - offset_
    # Nombres de paso iguales a los del artefacto desplegado el 30-sep (runbook de
    # congelado): así, con los mismos objetos y el mismo entorno, el resultado es el
    # mismo fichero byte a byte y la promoción se puede auditar por hash.
    pipeline = Pipeline([("scaler", escalador), ("model", modelo)])

    # Comprobación con filas en la escala cruda que recibe el motor.
    rng = np.random.default_rng(semilla)
    X = escalador.inverse_transform(rng.normal(size=(filas_control, len(nombres))))
    ss = np.asarray(pipeline.score_samples(X), dtype=float)
    df = np.asarray(modelo.decision_function(escalador.transform(X)), dtype=float)
    desvio = float(np.max(np.abs((ss - df) - offset)))
    if desvio > 1e-9:
        raise ValueError("score_samples - decision_function no es offset_ (desvío %.3g)" % desvio)
    distintas = int(np.sum((ss < umbral_ss) != (df < umbral_df)))
    if distintas:
        raise ValueError("%d filas cambian de decisión al convertir el umbral" % distintas)

    salida_modelo.parent.mkdir(parents=True, exist_ok=True)
    joblib.dump(pipeline, salida_modelo)

    informe = json.loads(Path(informe_path).read_text(encoding="utf-8")) if informe_path else {}
    origen = {"paquete": str(paquete_path), "paquete_sha256": sha256(paquete_path)}
    if informe_path:
        origen.update({"informe": str(informe_path), "informe_sha256": sha256(informe_path)})
        if informe.get("salida_sha256") not in (None, origen["paquete_sha256"]):
            raise ValueError("el informe no corresponde a este paquete (salida_sha256 distinto)")

    manifiesto = {
        "tipo": "manifiesto-desplegable",
        "generado": datetime.now(timezone.utc).isoformat(),
        "detectors": {detector: {
            "kind": "isolation_forest_pipeline",
            "model_path": str(salida_modelo),
            "model_sha256": sha256(salida_modelo),
            "schema": Path(esquema).name,
            "n_features": len(nombres),
            "features": nombres,
            "calibration": {
                "threshold": umbral_ss,
                "comparison": REGLA,
                "score_function": "score_samples",
                "threshold_decision_function": umbral_df,
                "offset": offset,
                "alpha": paquete.get("alpha", informe.get("alpha")),
            },
            "origen": origen,
        }},
        "evaluation": {detector: {
            "threshold_used": umbral_ss,
            "validation": {"fpr": informe.get("fpr_validacion")},
            "test": {"fpr": informe.get("fpr_test"),
                     "rows": (informe.get("filas") or {}).get("test")},
            "anomalies": {"detection_rate": deteccion_global,
                          "kali_real_detection_rate": deteccion_kali,
                          "fuente": deteccion_fuente},
        }},
        "runtime": {"python": platform.python_version(),
                    "scikit_learn": sklearn.__version__, "numpy": np.__version__},
    }
    salida_manifiesto.parent.mkdir(parents=True, exist_ok=True)
    salida_manifiesto.write_text(json.dumps(manifiesto, indent=2, ensure_ascii=False) + "\n",
                                 encoding="utf-8")

    veq = _modulo("verificar_equivalencia_umbral", VERIFICADOR).verificar(
        salida_modelo, salida_manifiesto, detector, umbral_df)
    if veq["veredicto"] != "EQUIVALENTE":
        raise ValueError("la verificación de equivalencia del par escrito falló: %s" % veq)

    return {"detector": detector, "modelo": str(salida_modelo),
            "sha256_modelo": manifiesto["detectors"][detector]["model_sha256"],
            "manifiesto": str(salida_manifiesto), "sha256_manifiesto": sha256(salida_manifiesto),
            "n_features": len(nombres), "schema": Path(esquema).name,
            "umbral_score_samples": umbral_ss, "umbral_decision_function": umbral_df,
            "offset_": offset, "filas_control": filas_control,
            "max_desvio_ss_menos_df_vs_offset": desvio,
            "equivalencia": veq["veredicto"], "origen": origen}


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--paquete", type=Path, required=True, help="joblib de entrenar_preliminar.py")
    ap.add_argument("--informe", type=Path, help="JSON de entrenar_preliminar.py (recomendado)")
    ap.add_argument("--detector", required=True, help="nombre del detector en el manifiesto")
    ap.add_argument("--salida-modelo", type=Path, required=True)
    ap.add_argument("--salida-manifiesto", type=Path, required=True)
    ap.add_argument("--schema", type=Path, default=ESQUEMA_V2,
                    help="contrato del motor; solo se acepta el que coincide con el extractor v2")
    ap.add_argument("--deteccion-global", type=float)
    ap.add_argument("--deteccion-kali", type=float)
    ap.add_argument("--deteccion-fuente")
    ap.add_argument("--sobrescribir", action="store_true")
    a = ap.parse_args(argv)
    r = promover(a.paquete, a.detector, a.salida_modelo, a.salida_manifiesto, a.informe,
                 a.schema, a.deteccion_global, a.deteccion_kali, a.deteccion_fuente,
                 a.sobrescribir)
    print(json.dumps(r, indent=2, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    sys.exit(main())
