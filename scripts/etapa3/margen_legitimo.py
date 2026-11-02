#!/usr/bin/env python3
"""Etapa 3: margen de la regla temprana frente al tráfico de capturas (excluido el atacante).

Para cada tabla de intentos (extraer_syn.py) calcula, por par origen→destino que NO sale
del atacante (10.10.20.30), el máximo de puertos distintos fallidos simultáneos en W s con
cada g, y los disparos que daría cada K. Informa también los del atacante aparte.

Uso: python margen_legitimo.py salida.json tabla1.json.gz [tabla2.json.gz ...]
"""
from __future__ import annotations

import gzip
import itertools
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from evaluar_regla_temprana import disparos  # noqa: E402

ATACANTE = "10.10.20.30"
W_ = (1.0, 2.0, 5.0)
G_ = (0.05, 0.1, 0.2, 1.0)
K_ = (3, 4, 5, 6, 8, 10, 12, 15)


def main() -> int:
    salida = Path(sys.argv[1])
    res = {}
    for p in sys.argv[2:]:
        d = json.load(gzip.open(p, "rt", encoding="utf-8"))
        intentos = {k: sorted(v, key=lambda x: x[0]) for k, v in d["intentos"].items()}
        t0 = min((x[0] for v in intentos.values() for x in v), default=0)
        t1 = max((x[0] for v in intentos.values() for x in v), default=0)
        maximos, disp = {}, {}
        for par, lista in intentos.items():
            leg = not par.startswith(ATACANTE + ">")
            for W, g in itertools.product(W_, G_):
                m = disparos(lista, W, 1, g, solo_max=True)
                maximos.setdefault(par, {"legitimo": leg, "intentos": len(lista)})["W=%s,g=%s" % (W, g)] = m
        for W, g, K in itertools.product(W_, G_, K_):
            clave = "W=%s,g=%s,K=%s" % (W, g, K)
            pares = [par for par, m in maximos.items() if m["legitimo"] and m["W=%s,g=%s" % (W, g)] >= K]
            disp[clave] = {"pares_legitimos": len(pares), "ejemplos": pares[:5],
                           "disparos_legitimos": sum(len(disparos(intentos[x], W, K, g)) for x in pares)}
        peores = sorted(((par, m["W=2.0,g=0.1"]) for par, m in maximos.items() if m["legitimo"]),
                        key=lambda x: -x[1])[:10]
        res[Path(p).name] = {"estadisticas": d["estadisticas"], "horas": round((t1 - t0) / 3600, 2),
                             "pares": len(intentos), "pares_legitimos": sum(1 for m in maximos.values() if m["legitimo"]),
                             "intentos_legitimos": sum(m["intentos"] for m in maximos.values() if m["legitimo"]),
                             "peores_pares_W2_g0.1": peores, "disparos_por_parametro": disp,
                             "maximos": maximos}
        print(Path(p).name, "horas", res[Path(p).name]["horas"], "pares", len(intentos), "peores", peores[:5])
        for k in ("W=2.0,g=0.1,K=4", "W=2.0,g=0.1,K=5", "W=2.0,g=0.1,K=6", "W=2.0,g=0.1,K=8", "W=2.0,g=0.1,K=10"):
            print("  ", k, disp[k]["pares_legitimos"], disp[k]["disparos_legitimos"], disp[k]["ejemplos"])
    salida.write_text(json.dumps(res, indent=1), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
