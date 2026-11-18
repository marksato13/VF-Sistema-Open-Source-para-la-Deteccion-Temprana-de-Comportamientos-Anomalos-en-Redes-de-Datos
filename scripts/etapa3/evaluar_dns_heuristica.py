#!/usr/bin/env python3
"""Etapa 3 (punto 4): regla dns_entropy sobre la vista DNS (sin copias, sin reenvíos).

Pasa un eve.json por ``dns_heuristica.VistaDns`` y evalúa, cada 10 s, para cada
entidad, la regla con varias combinaciones de umbral (sensibilidad). Para cada
episodio dns_inusual de las marcas da la primera ventana que dispara (respecto al
inicio y fin del episodio); fuera de los episodios del atacante cuenta las ventanas y
entidades legítimas que dispararían. Compara con la regla vigente del motor (registro
de decisiones de un replay, si se pasa).

Uso: python evaluar_dns_heuristica.py eve.json marcas.jsonl salida.json [--decisiones motor_decision.log]
"""
from __future__ import annotations

import argparse
import collections
import datetime as dt
import itertools
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "engine"))
import dns_heuristica as dh  # noqa: E402

ATACANTE = "10.10.20.30"
CUENTAS = (20, 25, 30, 40, 50, 60)
UNICOS = (0.45, 0.8, 0.9)
NX = 0.5


def iso(s):
    return dt.datetime.fromisoformat(s.replace("Z", "+00:00")).timestamp()


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("eve", type=Path)
    ap.add_argument("marcas", type=Path)
    ap.add_argument("salida", type=Path)
    ap.add_argument("--decisiones", type=Path)
    a = ap.parse_args()
    v = dh.VistaDns()
    with a.eve.open("rb") as fh:
        for l in fh:
            v.linea(l)
    marcas = [json.loads(l) for l in a.marcas.read_text(encoding="utf-8").splitlines() if l.strip()]
    ini = {m["episodio_id"]: iso(m["reloj"]["pared_utc"]) for m in marcas if m.get("evento") == "inicio"}
    fin = {m["episodio_id"]: iso(m["reloj"]["pared_utc"]) for m in marcas if m.get("evento") == "fin"}
    episodios = sorted((e, ini[e], fin.get(e)) for e in ini if e.startswith("dns_inusual"))
    tramos_atk = [(ini[e], fin.get(e, ini[e]) + 70) for e in ini]   # cualquier episodio (+ arrastre de 60 s)
    todas = [t for lst in v.consultas.values() for t, *_ in lst]
    w0, w1 = int(min(todas) // 10 * 10) + 10, int(max(todas) // 10 * 10) + 70
    filas = {}
    for ent in v.consultas:
        for W in range(w0, w1, 10):
            c = v.campos(ent, W)
            if c["dnsh_consultas_60s"] or c["dnsh_reenvios_excluidos_60s"]:
                filas[(ent, W)] = c
    res = {"version_vista": dh.VERSION, "copias_espejo": v.copias, "combinaciones": {}}
    for n, u in itertools.product(CUENTAS, UNICOS):
        disp = {k for k, c in filas.items() if c["dnsh_consultas_60s"] >= n and
                (c["dnsh_nxdomain_ratio_60s"] >= NX or c["dnsh_nombres_unicos_ratio_60s"] >= u)}
        por_ep = {}
        for e, t0, t1 in episodios:
            ws = sorted(W for (ent, W) in disp if ent == ATACANTE and t0 < W <= (t1 or t0) + 60)
            por_ep[e] = {"primera_s_desde_inicio": round(ws[0] - t0, 1) if ws else None,
                         "antes_del_fin": (ws[0] <= t1) if ws and t1 else None,
                         "margen_s_hasta_fin": round(t1 - ws[0], 1) if ws and t1 else None,
                         "ventanas": len(ws)}
        legit = collections.Counter(ent for (ent, W) in disp if ent != ATACANTE)
        atk_fuera = sum(1 for (ent, W) in disp if ent == ATACANTE and
                        not any(s < W <= f for s, f in tramos_atk))
        res["combinaciones"]["n>=%d,unicos>=%s" % (n, u)] = {
            "episodios": por_ep, "detectados": sum(1 for x in por_ep.values() if x["ventanas"]),
            "antes_del_fin": sum(1 for x in por_ep.values() if x["antes_del_fin"]),
            "ventanas_legitimas": sum(legit.values()), "entidades_legitimas": dict(legit),
            "atacante_fuera_de_episodios": atk_fuera}
    # peor caso legítimo en la vista
    leg = [(c["dnsh_consultas_60s"], ent, W) for (ent, W), c in filas.items() if ent != ATACANTE]
    res["peor_legitimo_consultas_60s"] = max(leg) if leg else None
    res["resolvedores_reenvios_excluidos_max"] = {r: max((c["dnsh_reenvios_excluidos_60s"] for (e, W), c in filas.items()
                                                          if e == r), default=0) for r in dh.RESOLVEDORES}
    res["resolvedores_propias_max"] = {r: max((c["dnsh_consultas_60s"] for (e, W), c in filas.items() if e == r), default=0)
                                       for r in dh.RESOLVEDORES}
    if a.decisiones and a.decisiones.exists():
        vig = collections.defaultdict(list)
        for l in a.decisiones.open(encoding="utf-8"):
            try:
                d = json.loads(l)
            except ValueError:
                continue
            if any(h.get("heuristico") == "dns_entropy" for h in d.get("heuristicos") or []):
                vig[d["entity_ip"]].append(iso(d["window_end_utc"]))
        pe = {}
        for e, t0, t1 in episodios:
            ws = sorted(W for W in vig.get(ATACANTE, []) if t0 < W <= (t1 or t0) + 60)
            pe[e] = {"primera_s_desde_inicio": round(ws[0] - t0, 1) if ws else None,
                     "margen_s_hasta_fin": round(t1 - ws[0], 1) if ws and t1 else None}
        res["regla_vigente_replay"] = {"episodios": pe,
                                       "ventanas_por_entidad": {k: len(x) for k, x in vig.items()}}
    a.salida.write_text(json.dumps(res, indent=1), encoding="utf-8")
    print("peor legitimo", res["peor_legitimo_consultas_60s"], "resolvedores propias max", res["resolvedores_propias_max"],
          "reenvios max", res["resolvedores_reenvios_excluidos_max"])
    for k, x in res["combinaciones"].items():
        print(k, "det", x["detectados"], "antes_fin", x["antes_del_fin"], "legit", x["ventanas_legitimas"], x["entidades_legitimas"],
              "1as", [y["primera_s_desde_inicio"] for y in x["episodios"].values()])
    if "regla_vigente_replay" in res:
        print("vigente", res["regla_vigente_replay"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
