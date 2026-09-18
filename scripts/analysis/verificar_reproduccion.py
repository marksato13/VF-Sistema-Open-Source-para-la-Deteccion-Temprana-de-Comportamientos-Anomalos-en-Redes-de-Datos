#!/usr/bin/env python3
"""Compara un manifiesto recien calibrado con el publicado.

Uso:
    python3 scripts/analysis/verificar_reproduccion.py \\
        artifacts/model/manifest.json  /ruta/al/manifest-nuevo.json

Sale con 0 solo si los siete detectores reproducen su resultado, su umbral
hasta el ultimo bit y el hash de su modelo. Cualquier diferencia es un fallo.

Por que existe: el 2026-09-17 se recalibro el protocolo bajo scikit-learn
1.7.2 y el resultado salio, era plausible, y era distinto -- if_primary_weighted
paso de 97/179 a 103/179 porque esa version ignora sample_weight en silencio.
Que los numeros salgan no demuestra nada. Hay que comprobar que salen los
mismos, y hacerlo a mano no escala.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path


def detectados(manifiesto: dict, detector: str) -> tuple[int, int]:
    perfiles = manifiesto["evaluation"][detector]["anomalies"]["by_profile"]
    return (sum(p["detected"] for p in perfiles.values()),
            sum(p["windows"] for p in perfiles.values()))


def main() -> int:
    if len(sys.argv) != 3:
        print(__doc__, file=sys.stderr)
        return 2
    pub = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
    new = json.loads(Path(sys.argv[2]).read_text(encoding="utf-8"))

    fallos = 0
    rp, rn = pub["runtime"], new["runtime"]
    print("publicado : Python %s  scikit-learn %s" % (rp["python"], rp["packages"]["scikit-learn"]))
    print("ahora     : Python %s  scikit-learn %s" % (rn["python"], rn["packages"]["scikit-learn"]))
    print()

    for det in sorted(pub["evaluation"]):
        if det not in new["evaluation"]:
            print("  %-26s FALTA en el manifiesto nuevo" % det)
            fallos += 1
            continue
        a, b = detectados(pub, det), detectados(new, det)
        ta = pub["detectors"][det]["calibration"]["threshold"]
        tb = new["detectors"][det]["calibration"]["threshold"]
        igual = a == b and ta == tb
        fallos += not igual
        print("  %-26s %3d/%d -> %3d/%d   umbral %+.9f -> %+.9f  %s"
              % (det, a[0], a[1], b[0], b[1], ta, tb, "ok" if igual else "DIFIERE"))

    print()
    for nombre, h in sorted(pub.get("model_hashes", {}).items()):
        h2 = new.get("model_hashes", {}).get(nombre)
        igual = h == h2
        fallos += not igual
        print("  %-44s %s" % (nombre, "hash identico" if igual else "HASH DISTINTO"))

    print()
    if fallos:
        print("NO REPRODUCE: %d diferencia(s)." % fallos)
        return 1
    print("REPRODUCCION EXACTA.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
