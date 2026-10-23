#!/usr/bin/env python3
"""Reconstruye el modelo LIMPIO (sin las ventanas Kali de excluir_ventanas) y lo
promueve a Pipeline+manifiesto desplegable, en el venv del Sensor (sklearn 1.9.0).

NO toca el motor, la captura ni el .toml vivo: solo LEE el particionado y el toml,
y ESCRIBE artefactos nuevos en --salida-dir. No reinicia nada, no usa sudo. El
swap del detector y el restart de ppi-motor los hace una persona, aparte.

Pasos:
  1. Lee excluir_ventanas del .toml del despliegue.
  2. En una COPIA del particionado, marca eligible_training=False en esas ventanas.
  3. (verificacion) Reentrena el vigente SIN exclusiones y comprueba que reproduce
     el umbral publicado -0.06889178... Si no reproduce, para: el entorno o el
     particionado no son los del modelo desplegado y no hay que seguir.
  4. Entrena el limpio (umbral desde validation, alpha=0.05) y lo promueve a
     Pipeline+manifiesto con verificacion de equivalencia.

Uso (en el Sensor, con el piloto cerrado):
  /home/m4rk/cyberflow/.venv/bin/python reconstruir_limpio.py \\
      --repo /home/m4rk/cyberflow \\
      --particionado /home/m4rk/cyberflow/artifacts/aprendizaje/base/particionado-nota-L.csv \\
      --toml /home/m4rk/cyberflow/configs/cyberflow.local.toml \\
      --salida-dir /home/m4rk/cyberflow/artifacts/preliminar/limpio-2026-10 \\
      --detector if_limpio_2026_10
"""
from __future__ import annotations

import argparse
import csv
import json
import subprocess
import sys
import tomllib
from collections import Counter
from pathlib import Path

UMBRAL_VIGENTE = -0.06889178778834089   # model card del if_recalibrado_2026_09


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--repo", type=Path, default=Path("/home/m4rk/cyberflow"))
    ap.add_argument("--particionado", type=Path,
                    default=Path("/home/m4rk/cyberflow/artifacts/aprendizaje/base/particionado-nota-L.csv"))
    ap.add_argument("--toml", type=Path,
                    default=Path("/home/m4rk/cyberflow/configs/cyberflow.local.toml"))
    ap.add_argument("--salida-dir", type=Path,
                    default=Path("/home/m4rk/cyberflow/artifacts/preliminar/limpio-2026-10"))
    ap.add_argument("--detector", default="if_limpio_2026_10")
    ap.add_argument("--schema", type=Path, default=None)
    ap.add_argument("--alpha", default="0.05")
    ap.add_argument("--n-estimators", default="500")
    ap.add_argument("--semilla", default="20260813")
    ap.add_argument("--saltar-verificacion", action="store_true")
    a = ap.parse_args()

    repo = a.repo.resolve()
    schema = a.schema or (repo / "configs/features/multilayer-v2.json")
    sys.path.insert(0, str(repo / "scripts" / "modeling"))
    import cyberflow_aprendizaje as ap_mod   # para tramos_excluidos / excluida

    PY = sys.executable
    ENTRENAR = repo / "scripts/modeling/entrenar_preliminar.py"
    PROMOVER = repo / "scripts/modeling/promover_preliminar.py"
    for p in (a.particionado, a.toml, schema, ENTRENAR, PROMOVER):
        if not Path(p).exists():
            raise SystemExit("no existe: %s" % p)

    salida = a.salida_dir
    salida.mkdir(parents=True, exist_ok=True)

    # 1. excluir_ventanas del toml vivo
    cfg = tomllib.loads(a.toml.read_text(encoding="utf-8"))
    rangos = cfg.get("reentrenamiento", {}).get("excluir_ventanas", [])
    tramos = ap_mod.tramos_excluidos(rangos)
    print("excluir_ventanas (%d rangos):" % len(rangos))
    for r in rangos:
        print("   ", r)

    # 2. copia del particionado con eligible_training=False en las excluidas
    with a.particionado.open(newline="", encoding="utf-8") as f:
        lector = csv.DictReader(f)
        cols = list(lector.fieldnames or [])
        filas = list(lector)
    if "eligible_training" not in cols or "window_end_utc" not in cols or "entity_ip" not in cols:
        raise SystemExit("el particionado no tiene eligible_training/window_end_utc/entity_ip")
    part = Counter()
    flip = Counter()
    for row in filas:
        part[row.get("particion", "")] += 1
        if ap_mod.excluida(row, tramos):
            flip[row.get("particion", "")] += 1
            row["eligible_training"] = "False"
    print("particiones:", dict(part))
    print("ventanas excluidas (eligible->False):", dict(flip), "| total", sum(flip.values()))

    limpio_csv = salida / "particionado-limpio.csv"
    with limpio_csv.open("w", newline="", encoding="utf-8") as g:
        w = csv.DictWriter(g, fieldnames=cols)
        w.writeheader()
        w.writerows(filas)
    print("escrito:", limpio_csv)

    def corre(args_):
        r = subprocess.run([PY, *map(str, args_)], capture_output=True, text=True)
        if r.returncode != 0:
            raise SystemExit(r.stdout[-2000:] + r.stderr[-2000:])
        return r.stdout

    def entrenar(entrada, tag):
        paq = salida / ("%s.joblib" % tag)
        inf = salida / ("%s.json" % tag)
        corre([ENTRENAR, "--entrada", entrada, "--schema", schema, "--salida", paq,
               "--informe", inf, "--alpha", a.alpha, "--n-estimators", a.n_estimators,
               "--semilla", a.semilla])
        d = json.loads(inf.read_text(encoding="utf-8"))
        print("[%s] umbral_df=%.8f  FPR_val=%s  FPR_test=%s  filas=%s"
              % (tag, d["umbral_decision_function"], d["fpr_validacion"],
                 d["fpr_test"], d["filas"]))
        return paq, inf, d

    # 3. verificacion: el vigente (sin exclusiones) debe reproducir -0.068892
    if not a.saltar_verificacion:
        print("\n== verificacion: reproducir el vigente sin exclusiones ==")
        _, _, dv = entrenar(a.particionado, "verif_vigente")
        if abs(dv["umbral_decision_function"] - UMBRAL_VIGENTE) < 1e-6:
            print("   OK: reproduce el umbral publicado (-0.068892). Entorno fiable.")
        else:
            raise SystemExit("DIFIERE del vigente (-0.068892): el entorno o el "
                             "particionado no son los del modelo desplegado. No se sigue.")

    # 4. entrenar limpio + promover
    print("\n== modelo limpio ==")
    paq, inf, d = entrenar(limpio_csv, a.detector)
    print("\n== promover a Pipeline+manifiesto ==")
    out = corre([PROMOVER, "--paquete", paq, "--informe", inf, "--detector", a.detector,
                 "--salida-modelo", salida / ("%s_desplegable.joblib" % a.detector),
                 "--salida-manifiesto", salida / ("manifest-%s.json" % a.detector.replace("_", "-")),
                 "--schema", schema])
    print(out)
    print("\nARTEFACTOS en:", salida)
    print("  - %s_desplegable.joblib  (el que carga el motor)" % a.detector)
    print("  - manifest-%s.json       (umbral score_samples + metadatos)"
          % a.detector.replace("_", "-"))
    print("\nEl .toml vivo NO se toco. El swap del detector + restart de ppi-motor")
    print("se hacen aparte, con sudo, por una persona.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
