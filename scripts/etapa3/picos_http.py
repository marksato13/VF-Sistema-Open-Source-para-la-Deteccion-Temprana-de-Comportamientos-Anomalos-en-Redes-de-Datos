#!/usr/bin/env python3
"""Etapa 3 (punto 5): picos de peticiones HTTP por origen en 60 s (cada 10 s), sin copias.

Copias del espejo: mismo (flow_id, tx_id, url). Para cada origen da el máximo de
peticiones y de fallos 401/403 en cualquier ventana de 60 s, y para el atacante el valor
por episodio. Base para fijar http_abuse con margen frente al tráfico legítimo.

Uso: python picos_http.py eve.json marcas.jsonl salida.json
"""
from __future__ import annotations

import bisect
import collections
import datetime as dt
import json
import sys
from pathlib import Path

ATK = "10.10.20.30"


def ts(s):
    return dt.datetime.strptime(s[:26] + s[-5:], "%Y-%m-%dT%H:%M:%S.%f%z").timestamp()


def main() -> int:
    eve, marcas, salida = map(Path, sys.argv[1:4])
    por = collections.defaultdict(list)
    vistos = set()
    with eve.open("rb") as fh:
        for l in fh:
            if b'"event_type":"http"' not in l:
                continue
            e = json.loads(l)
            h = e.get("http") or {}
            k = (e.get("flow_id"), e.get("tx_id"), h.get("url"))
            if k in vistos:
                continue
            vistos.add(k)
            por[e.get("src_ip")].append((ts(e["timestamp"]), int(h.get("status") or 0) in (401, 403)))
    m = [json.loads(x) for x in marcas.read_text(encoding="utf-8").splitlines() if x.strip()]
    iso = lambda s: dt.datetime.fromisoformat(s).timestamp()  # noqa: E731
    ini = {x["episodio_id"]: iso(x["reloj"]["pared_utc"]) for x in m if x.get("evento") == "inicio"}
    fin = {x["episodio_id"]: iso(x["reloj"]["pared_utc"]) for x in m if x.get("evento") == "fin"}
    res = {}
    for src, lst in por.items():
        lst.sort()
        t = [x[0] for x in lst]
        fallos = [0]
        for _, f in lst:
            fallos.append(fallos[-1] + f)
        w0, w1 = int(t[0] // 10 * 10) + 10, int(t[-1] // 10 * 10) + 70
        mejor = (0, 0, None)
        por_ep = {}
        for W in range(w0, w1, 10):
            i0, i1 = bisect.bisect_right(t, W - 60), bisect.bisect_right(t, W)
            n, nf = i1 - i0, fallos[i1] - fallos[i0]
            if n > mejor[0]:
                mejor = (n, nf, W)
            if src == ATK:
                for e in ini:
                    if ini[e] < W <= fin.get(e, ini[e]) + 60:
                        p = por_ep.setdefault(e, [0, 0, None])
                        if p[2] is None and n >= 1:
                            p[2] = round(W - ini[e], 1)
                        p[0] = max(p[0], n)
                        p[1] = max(p[1], nf)
        res[src] = {"peticiones": len(lst), "max_60s": mejor[0], "fallos_auth_en_max": mejor[1],
                    "ventana_max": dt.datetime.fromtimestamp(mejor[2], dt.timezone.utc).isoformat() if mejor[2] else None}
        if por_ep:
            res[src]["episodios"] = {e: {"max_60s": v[0], "max_fallos_60s": v[1]} for e, v in sorted(por_ep.items())}
    salida.write_text(json.dumps(res, indent=1), encoding="utf-8")
    for s, v in sorted(res.items(), key=lambda x: -x[1]["max_60s"]):
        print(s, v["peticiones"], "max60", v["max_60s"], "fallos", v["fallos_auth_en_max"], v["ventana_max"])
    if ATK in res:
        for e, v in res[ATK].get("episodios", {}).items():
            print("  ", e, v)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
