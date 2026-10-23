#!/usr/bin/env python3
"""Compara un manifiesto recien calibrado con el publicado.

Uso:
    python3 scripts/analysis/verificar_reproduccion.py \\
        artifacts/model/manifest.json  /ruta/al/manifest-nuevo.json

Dos niveles, porque hay dos cosas distintas que pueden cambiar:

  FUNCIONAL (siempre obligatorio)
    Mismo numero de detecciones en los siete detectores, y umbrales iguales
    con una tolerancia relativa de 1e-9. Esto es lo que detecta un fallo de
    verdad: bajo scikit-learn 1.7.2 el Isolation Forest ignora sample_weight
    y su umbral se movio un 10 % (-0.506 -> -0.555), con otro resultado.

  BIT A BIT (obligatorio solo con el mismo BLAS)
    Umbral y hash del modelo identicos. OpenBLAS elige kernels distintos
    segun la CPU, el orden de las sumas cambia y el ultimo bit se mueve en los
    detectores con mas algebra lineal (Elliptic Envelope, LOF): medido una
    diferencia relativa de 5e-11 entre SkylakeX y otra CPU. Si el BLAS
    coincide con el que registra el manifiesto, cualquier diferencia es un
    fallo; si no coincide, se informa y no se falla.

Sale con 0 si todo lo obligatorio se cumple.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

TOL_RELATIVA = 1e-9


def detectados(m: dict, det: str) -> tuple[int, int]:
    perfiles = m["evaluation"][det]["anomalies"]["by_profile"]
    return (sum(p["detected"] for p in perfiles.values()),
            sum(p["windows"] for p in perfiles.values()))


def firma_blas(m: dict) -> set[tuple]:
    return {(t.get("internal_api"), t.get("architecture"), t.get("num_threads"))
            for t in m.get("threadpools", [])}


def main() -> int:
    if len(sys.argv) != 3:
        print(__doc__, file=sys.stderr)
        return 2
    pub = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
    new = json.loads(Path(sys.argv[2]).read_text(encoding="utf-8"))

    rp, rn = pub["runtime"], new["runtime"]
    print("publicado : Python %s  scikit-learn %s" % (rp["python"], rp["packages"]["scikit-learn"]))
    print("ahora     : Python %s  scikit-learn %s" % (rn["python"], rn["packages"]["scikit-learn"]))
    mismo_blas = firma_blas(pub) == firma_blas(new)
    print("BLAS      : %s" % ("el mismo que el publicado -> se exige bit a bit" if mismo_blas
                              else "distinto del publicado -> se exige igualdad funcional"))
    if not mismo_blas:
        for et, m in (("publicado", pub), ("ahora", new)):
            print("            %-9s %s" % (et, sorted(firma_blas(m), key=str)))
    print()

    fallos = avisos = 0
    for det in sorted(pub["evaluation"]):
        if det not in new["evaluation"]:
            print("  %-26s FALTA en el manifiesto nuevo" % det)
            fallos += 1
            continue
        a, b = detectados(pub, det), detectados(new, det)
        ta = pub["detectors"][det]["calibration"]["threshold"]
        tb = new["detectors"][det]["calibration"]["threshold"]
        rel = abs(ta - tb) / max(abs(ta), 1e-300)
        if a != b or rel > TOL_RELATIVA:
            estado = "DIFIERE"; fallos += 1
        elif ta != tb:
            estado = ("DIFIERE en el ultimo bit (%.1e)" % rel)
            if mismo_blas:
                fallos += 1
            else:
                estado += ", tolerado: BLAS distinto"; avisos += 1
        else:
            estado = "ok"
        print("  %-26s %3d/%d -> %3d/%d   umbral %+.9f -> %+.9f  %s"
              % (det, a[0], a[1], b[0], b[1], ta, tb, estado))

    print()
    for nombre, h in sorted(pub.get("model_hashes", {}).items()):
        if h == new.get("model_hashes", {}).get(nombre):
            print("  %-44s hash identico" % nombre)
        elif mismo_blas:
            print("  %-44s HASH DISTINTO" % nombre); fallos += 1
        else:
            print("  %-44s hash distinto (tolerado: BLAS distinto)" % nombre); avisos += 1

    print()
    if fallos:
        print("NO REPRODUCE: %d diferencia(s)." % fallos)
        return 1
    if avisos:
        print("REPRODUCCION FUNCIONAL: mismas detecciones y umbrales dentro de %.0e." % TOL_RELATIVA)
        print("No es bit a bit porque el BLAS no es el del manifiesto (%d diferencia(s) en el ultimo bit)." % avisos)
        return 0
    print("REPRODUCCION EXACTA, bit a bit.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
