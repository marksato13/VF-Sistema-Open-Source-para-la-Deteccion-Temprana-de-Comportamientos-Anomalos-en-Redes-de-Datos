#!/usr/bin/env python3
"""Etapa 3 (puntos 5 y 7): actividad HTTP de un origen fuera de sus episodios registrados.

Agrupa los eventos http del EVE de ``--origen`` en ráfagas (huecos > 10 s), y para cada
ráfaga da inicio, fin, peticiones, URL/método/estado/agente más frecuentes, destino y
el episodio con el que se solapa (o «ninguno»). Sirve para separar las señales del
escenario de las de peticiones concurrentes que no figuran en las marcas.

Uso: python http_no_registrado.py eve.json marcas.jsonl salida.json [--origen 10.10.20.30]
"""
from __future__ import annotations

import argparse
import collections
import datetime as dt
import json
from pathlib import Path


def iso(s):
    return dt.datetime.fromisoformat(s.replace("Z", "+00:00")).timestamp()


def ts(s):
    return dt.datetime.strptime(s[:26] + s[-5:], "%Y-%m-%dT%H:%M:%S.%f%z").timestamp()


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("eve", type=Path)
    ap.add_argument("marcas", type=Path)
    ap.add_argument("salida", type=Path)
    ap.add_argument("--origen", default="10.10.20.30")
    ap.add_argument("--hueco", type=float, default=10.0)
    a = ap.parse_args()
    m = [json.loads(l) for l in a.marcas.read_text(encoding="utf-8").splitlines() if l.strip()]
    ini = {x["episodio_id"]: iso(x["reloj"]["pared_utc"]) for x in m if x.get("evento") == "inicio"}
    fin = {x["episodio_id"]: iso(x["reloj"]["pared_utc"]) for x in m if x.get("evento") == "fin"}
    eps = sorted((ini[e], fin.get(e, ini[e]), e) for e in ini)
    clave = ('"src_ip":"%s"' % a.origen).encode()
    ev, vistos = [], set()
    with a.eve.open("rb") as fh:
        for l in fh:
            if b'"event_type":"http"' not in l or clave not in l:
                continue
            e = json.loads(l)
            h = e.get("http") or {}
            k = (e.get("flow_id"), e.get("tx_id"), h.get("url"))
            if k in vistos:          # copias del espejo: mismo flujo y transacción
                continue
            vistos.add(k)
            ev.append((ts(e["timestamp"]), e.get("dest_ip"), e.get("dest_port"), h.get("http_method"),
                       h.get("url"), h.get("status"), h.get("http_user_agent")))
    ev.sort(key=lambda x: x[0])
    rafagas, cur = [], []
    for x in ev:
        if cur and x[0] - cur[-1][0] > a.hueco:
            rafagas.append(cur)
            cur = []
        cur.append(x)
    if cur:
        rafagas.append(cur)
    out = []
    for r in rafagas:
        t0, t1 = r[0][0], r[-1][0]
        sol = [e for s, f, e in eps if s <= t1 and t0 <= f]
        c = lambda i: collections.Counter(x[i] for x in r).most_common(3)  # noqa: E731
        out.append({"inicio": dt.datetime.fromtimestamp(t0, dt.timezone.utc).isoformat(),
                    "fin": dt.datetime.fromtimestamp(t1, dt.timezone.utc).isoformat(),
                    "duracion_s": round(t1 - t0, 1), "peticiones": len(r), "episodios": sol or ["ninguno"],
                    "destino": c(1), "puerto": c(2), "metodo": c(3), "url": c(4), "estado": c(5), "agente": c(6)})
    a.salida.write_text(json.dumps(out, indent=1, ensure_ascii=False), encoding="utf-8")
    for x in out:
        print(x["inicio"][11:19], x["fin"][11:19], x["peticiones"], x["episodios"], x["puerto"], x["url"][:2],
              x["estado"][:2], x["agente"][:1])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
