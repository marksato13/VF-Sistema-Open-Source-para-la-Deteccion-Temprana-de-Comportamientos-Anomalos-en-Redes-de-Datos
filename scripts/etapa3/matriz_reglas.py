#!/usr/bin/env python3
"""Etapa 3 (punto 5): qué regla dispara, sobre quién y durante qué episodio.

Cruza un motor_decision.log con las marcas de la campaña. Cada ventana (entidad, fin)
con alguna regla se asigna al episodio cuyo [inicio, fin + arrastre] la contiene (o a
«fuera»). Da la matriz escenario x regla para el atacante y, aparte, todas las ventanas
de entidades que NO son el atacante (restricciones sobre legítimos), con las
magnitudes que hicieron disparar la regla.

Uso: python matriz_reglas.py motor_decision.log marcas.jsonl salida.json [--arrastre 60]
"""
from __future__ import annotations

import argparse
import collections
import datetime as dt
import json
from pathlib import Path

ATACANTE = "10.10.20.30"


def iso(s):
    return dt.datetime.fromisoformat(s.replace("Z", "+00:00")).timestamp()


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("decisiones", type=Path)
    ap.add_argument("marcas", type=Path)
    ap.add_argument("salida", type=Path)
    ap.add_argument("--arrastre", type=float, default=60.0)
    a = ap.parse_args()
    m = [json.loads(l) for l in a.marcas.read_text(encoding="utf-8").splitlines() if l.strip()]
    ini = {x["episodio_id"]: iso(x["reloj"]["pared_utc"]) for x in m if x.get("evento") == "inicio"}
    fin = {x["episodio_id"]: iso(x["reloj"]["pared_utc"]) for x in m if x.get("evento") == "fin"}
    eps = sorted((ini[e], fin.get(e, ini[e]), e) for e in ini)

    def episodio(W):
        for s, f, e in eps:
            if s < W <= f + a.arrastre:
                return e
        return "fuera"

    matriz = collections.defaultdict(collections.Counter)
    legit = []
    vistos = set()
    for l in a.decisiones.open(encoding="utf-8"):
        try:
            d = json.loads(l)
        except ValueError:
            continue
        if d.get("event") != "decision":
            continue
        k = (d["entity_ip"], d["window_end_utc"])
        if k in vistos:
            continue
        vistos.add(k)
        W = iso(d["window_end_utc"])
        ep = episodio(W)
        esc = ep.rsplit("-r", 1)[0] if ep != "fuera" else "fuera"
        for h in d.get("heuristicos") or []:
            if d["entity_ip"] == ATACANTE:
                matriz[esc][h["heuristico"]] += 1
            else:
                legit.append({"entidad": d["entity_ip"], "ventana": d["window_end_utc"], "episodio": ep,
                              "regla": h["heuristico"], "accion": h["accion"], "motivo": h["motivo"]})
        if d["entity_ip"] == ATACANTE and d.get("decision") == "ALERT":
            matriz[esc]["IF_ALERT"] += 1
    resumen_legit = collections.Counter((x["entidad"], x["regla"], x["accion"]) for x in legit)
    res = {"matriz_atacante_escenario_x_regla": {k: dict(v) for k, v in sorted(matriz.items())},
           "legitimos_por_entidad_regla": {"%s|%s|%s" % k: v for k, v in resumen_legit.most_common()},
           "legitimos": legit}
    a.salida.write_text(json.dumps(res, indent=1, ensure_ascii=False), encoding="utf-8")
    for k, v in res["matriz_atacante_escenario_x_regla"].items():
        print(k, v)
    print("legitimos:", res["legitimos_por_entidad_regla"])
    for x in legit[:12]:
        print("  ", x["entidad"], x["ventana"][11:19], x["episodio"], x["regla"], x["motivo"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
