#!/usr/bin/env python3
"""Estado de EJEMPLO del reentrenamiento supervisado, para el modo demo del panel.

No es una medicion: no entrena nada ni toca ningun modelo. Escribe, en un
directorio temporal, lo mismo que dejaria ``cyberflow_aprendizaje.py`` tras dos
semanas -lotes saneados con su registro encadenado, la serie de deriva y un
candidato evaluado- para que la seccion Aprendizaje se vea funcionando en un
clon recien hecho. Las cifras son inventadas y verosimiles; el registro SI es una
cadena valida, porque se escribe con las mismas funciones que en produccion.

    python3 scripts/demo_aprendizaje.py --raiz /tmp/cyberflow-demo/aprendizaje
    # -> imprime la ruta del .toml que hay que pasar al panel con --config-toml
"""
from __future__ import annotations

import argparse
import csv
import json
import random
import shutil
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "scripts" / "modeling"))
import cyberflow_aprendizaje as ap  # noqa: E402

TOML = """# Configuracion de EJEMPLO para el modo demo. No describe ningun despliegue.
[motor]
detector = "if_recalibrado_2026_09"

[rutas]
raiz = "{raiz}"
modelo = "no-existe.joblib"
manifiesto = "no-existe.json"

[reentrenamiento]
activo = true
base = "base-de-ejemplo.csv"
ataques = "ataques-de-ejemplo.csv"
"""


def main() -> int:
    ap_ = argparse.ArgumentParser(description=__doc__,
                                  formatter_class=argparse.RawDescriptionHelpFormatter)
    ap_.add_argument("--raiz", type=Path, required=True)
    a = ap_.parse_args()
    raiz = a.raiz
    shutil.rmtree(raiz, ignore_errors=True)
    (raiz / "configs").mkdir(parents=True)
    toml = raiz / "configs" / "cyberflow.demo.toml"
    toml.write_text(TOML.format(raiz=raiz.as_posix()), encoding="utf-8")
    cfg = ap.cargar_config(toml)
    rnd = random.Random(20261011)
    hoy = datetime.now(timezone.utc).date()

    oro = cfg["dir"] / "oro" / "oro.json"
    oro.parent.mkdir(parents=True)
    ap.anotar(cfg, {"tipo": "oro", "generado": (hoy - timedelta(days=15)).isoformat() + "T09:00:00+00:00",
                    "filas": 65421, "sha256": "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
                    "particion": "test", "demo": True})
    oro.write_text(json.dumps({"tipo": "oro", "filas": 65421, "demo": True,
                               "generado": (hoy - timedelta(days=15)).isoformat(),
                               "sha256": "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"}),
                   encoding="utf-8")

    deriva = []
    for k in range(14, 0, -1):
        dia = hoy - timedelta(days=k)
        entrada = rnd.randint(11000, 13000)
        cont = rnd.randint(20, 160)
        atip = rnd.randint(0, 12)
        psi_max = round(rnd.uniform(0.04, 0.22), 3)
        estado = "aceptado"
        if k == 9:                              # el dia de la Kali: muchas IPs marcadas
            cont, psi_max = 2140, 0.31
        if k == 5:                              # un cambio de red sin avisar
            psi_max, estado = 0.74, "rechazado"
        nombre = "lote-%s.csv" % dia.strftime("%Y%m%d")
        lote = cfg["dir"] / "lotes" / nombre
        lote.parent.mkdir(parents=True, exist_ok=True)
        with lote.open("w", newline="", encoding="utf-8") as f:
            csv.writer(f).writerow(["demo", dia.isoformat()])
        ap.anotar(cfg, {"tipo": "lote", "demo": True, "dia": dia.isoformat(), "fichero": nombre,
                        "generado": dia.isoformat() + "T00:30:05+00:00", "sha256": ap.sha256(lote),
                        "estado": estado, "psi_max": psi_max,
                        "filas": {"entrada": entrada, "no_elegibles": rnd.randint(30, 90),
                                  "contaminadas": cont, "atipicas": atip,
                                  "salida": entrada - cont - atip - 60}})
        deriva.append({"tipo": "deriva", "demo": True, "dia": dia.isoformat(),
                       "detector": cfg["detector"],
                       "fpr_oro": 0.0445, "psi_puntuaciones": round(rnd.uniform(0.03, 0.12), 3),
                       "tasa_anomala_lote": round(rnd.uniform(0.035, 0.06), 4),
                       "tasa_alert_motor": round(rnd.uniform(0.04, 0.08), 4),
                       "filas_lote": entrada, "senal": False})
    # deriva[-k] es el dia hoy-k: senal el dia de la Kali y el del cambio de red.
    deriva[-9]["psi_puntuaciones"], deriva[-9]["senal"] = 0.29, True
    deriva[-5]["psi_puntuaciones"], deriva[-5]["senal"] = 0.41, True
    with (cfg["dir"] / "deriva.jsonl").open("w", encoding="utf-8") as f:
        for d in deriva:
            f.write(json.dumps(d) + "\n")

    ident = (hoy - timedelta(days=1)).strftime("%Y%m%d") + "-0031"
    carpeta = cfg["dir"] / "candidatos" / ident
    carpeta.mkdir(parents=True)
    ficha = {
        "id": ident, "demo": True, "generado": (hoy - timedelta(days=1)).isoformat() + "T00:41:12+00:00",
        "motivo": "forzado a mano", "detector": "if_aprendizaje_" + ident.replace("-", "_"),
        "veredicto": "PROMOVIBLE",
        "razon": "FPR <= vigente y deteccion >= vigente sobre los mismos conjuntos",
        "resultados": {
            "vigente": {"detector": cfg["detector"], "fpr_oro": 0.0445, "deteccion": 0.6429},
            "candidato": {"detector": "if_aprendizaje_" + ident.replace("-", "_"),
                          "fpr_oro": 0.0412, "deteccion": 0.6667}},
        "filas": {"base": 269781, "nuevas": 115620, "fraccion_nueva": 0.3,
                  "particion": {"train": 231000, "validation": 77000, "test": 77000}},
        "influencia": {"tope_por_ip": 14900, "ips_recortadas": {"10.10.20.21": 3810},
                       "tope_nuevas": 115620, "recortadas_por_fraccion": 26144},
    }
    (carpeta / "candidato.json").write_text(json.dumps(ficha, indent=2), encoding="utf-8")
    ap.anotar(cfg, {"tipo": "candidato", "demo": True, "generado": ficha["generado"],
                    "id": ident, "veredicto": "PROMOVIBLE", "motivo": ficha["motivo"]})
    print(toml)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
