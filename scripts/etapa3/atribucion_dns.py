#!/usr/bin/env python3
"""Etapa 3 (punto 4): ¿de quién son las consultas DNS que hacen los resolvedores?

Lee un eve.json (solo eventos dns) y, para cada consulta que SALE de un resolvedor
interno (DC1/DC2) hacia otro servidor, busca la consulta de un cliente HACIA un
resolvedor con el mismo (nombre, tipo) en los ``delta`` s anteriores. Si existe, la
del resolvedor es un REENVÍO hecho por cuenta de ese cliente; si no, es PROPIA
(Samba, actualizaciones, comprobaciones del propio DC...).

También:
- deduplica las copias del espejo SPAN (mismo src, sport, dst, id, nombre, tipo en < 5 ms);
- empareja respuestas (src_ip = quien preguntó, igual que hace el extractor) para saber
  qué consultas acabaron en NXDOMAIN;
- recalcula, por ventana de 60 s cada 10 s, la regla dns_entropy con y sin reenvíos para
  los resolvedores y para cada cliente.

Uso: python atribucion_dns.py eve.json salida.json [--delta 2.0] [--marcas marcas.jsonl]
"""
from __future__ import annotations

import argparse
import bisect
import collections
import datetime as dt
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "engine"))
import heuristicos  # noqa: E402

RESOLVEDORES = ("10.10.10.20", "10.10.10.21")
RED = "10.10."


def ts(s: str) -> float:
    return dt.datetime.strptime(s[:26] + s[-5:], "%Y-%m-%dT%H:%M:%S.%f%z").timestamp()


def cargar(eve: Path):
    consultas, respuestas = [], []
    vistos = {}
    dup = 0
    with eve.open("rb") as fh:
        for l in fh:
            if b'"event_type":"dns"' not in l:
                continue
            e = json.loads(l)
            d = e.get("dns") or {}
            t = ts(e["timestamp"])
            nombre = (d.get("rrname") or ((d.get("queries") or [{}])[0].get("rrname")) or "").lower()
            tipo = d.get("rrtype") or ((d.get("queries") or [{}])[0].get("rrtype")) or ""
            clave = (d.get("type"), e.get("src_ip"), e.get("src_port"), e.get("dest_ip"), d.get("id"), nombre, tipo,
                     d.get("rcode"))
            if clave in vistos and t - vistos[clave] < 0.005:
                dup += 1
                continue
            vistos[clave] = t
            x = {"t": t, "src": e.get("src_ip"), "sport": e.get("src_port"), "dst": e.get("dest_ip"),
                 "proto": e.get("proto"), "id": d.get("id"), "nombre": nombre, "tipo": tipo}
            if d.get("type") == "query":
                consultas.append(x)
            elif d.get("type") == "answer":
                x["rcode"] = d.get("rcode")
                respuestas.append(x)
    consultas.sort(key=lambda x: x["t"])
    return consultas, respuestas, dup


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("eve", type=Path)
    ap.add_argument("salida", type=Path)
    ap.add_argument("--delta", type=float, default=2.0)
    ap.add_argument("--marcas", type=Path)
    a = ap.parse_args()
    consultas, respuestas, dup = cargar(a.eve)
    # respuestas por (quien preguntó, sport, dst, id, nombre): NXDOMAIN
    nx = {(r["src"], r["sport"], r["dst"], r["id"], r["nombre"]) for r in respuestas if r["rcode"] == "NXDOMAIN"}
    for q in consultas:
        q["nx"] = (q["src"], q["sport"], q["dst"], q["id"], q["nombre"]) in nx
    # consultas de clientes hacia resolvedores, indexadas por (nombre, tipo)
    idx = collections.defaultdict(list)
    for q in consultas:
        if q["dst"] in RESOLVEDORES and q["src"] not in RESOLVEDORES:
            idx[(q["nombre"], q["tipo"])].append((q["t"], q["src"]))
    resumen = collections.Counter()
    por_cliente = collections.Counter()
    propias_nombres = collections.Counter()
    for q in consultas:
        if q["src"] not in RESOLVEDORES:
            continue
        if q["dst"] in RESOLVEDORES:
            q["clase"] = "entre_resolvedores"
        else:
            lst = idx.get((q["nombre"], q["tipo"]), [])
            i = bisect.bisect_right(lst, (q["t"], "~"))
            cand = [c for c in lst[max(0, i - 20):i] if q["t"] - c[0] <= a.delta]
            if cand:
                q["clase"] = "reenvio"
                q["cliente"] = cand[-1][1]
                por_cliente[cand[-1][1]] += 1
            else:
                q["clase"] = "propia"
                propias_nombres[q["nombre"].split(".", 1)[-1] if q["nombre"].count(".") > 1 else q["nombre"]] += 1
        resumen[(q["src"], q["clase"], "NX" if q["nx"] else "ok")] += 1
    # reglas por ventana con y sin reenvíos
    t0 = int(consultas[0]["t"] // 10 * 10) + 60
    t1 = int(consultas[-1]["t"] // 10 * 10) + 10
    por_ent = collections.defaultdict(list)
    for q in consultas:
        if q["src"].startswith(RED):
            por_ent[q["src"]].append(q)
    disparos = collections.defaultdict(lambda: collections.Counter())
    ventanas_dc = []
    for ent, lst in por_ent.items():
        ts_ = [q["t"] for q in lst]
        for W in range(t0, t1, 10):
            i0, i1 = bisect.bisect_right(ts_, W - 60), bisect.bisect_right(ts_, W)
            if i1 - i0 < 1:
                continue
            for variante in ("todas", "sin_reenvios"):
                sel = lst[i0:i1] if variante == "todas" else [q for q in lst[i0:i1] if q.get("clase") != "reenvio"]
                n = len(sel)
                if not n:
                    continue
                fila = {"dns_query_count_60s": n,
                        "dns_nxdomain_ratio_60s": sum(q["nx"] for q in sel) / n,
                        "unique_dns_name_ratio_60s": len({q["nombre"] for q in sel}) / n}
                if heuristicos._dns_entropy(fila, heuristicos.UMBRALES_POR_DEFECTO["dns_entropy"]):
                    disparos[ent][variante] += 1
                    if ent in RESOLVEDORES and variante == "todas":
                        ventanas_dc.append(W)
    # qué clientes alimentan los disparos del resolvedor
    culpables = collections.Counter()
    for W in ventanas_dc:
        for q in por_ent.get("10.10.10.20", []):
            if W - 60 < q["t"] <= W and q.get("clase") == "reenvio" and q["nx"]:
                culpables[q["cliente"]] += 1
    marcas = []
    if a.marcas and a.marcas.exists():
        marcas = [json.loads(l) for l in a.marcas.read_text().splitlines() if l.strip()]
    res = {"delta_s": a.delta, "consultas": len(consultas), "respuestas": len(respuestas),
           "copias_span_descartadas": dup,
           "consultas_de_resolvedores": {"%s|%s|%s" % k: v for k, v in sorted(resumen.items())},
           "reenvios_por_cliente": dict(por_cliente.most_common(20)),
           "propias_por_dominio": dict(propias_nombres.most_common(25)),
           "ventanas_dns_entropy": {e: dict(c) for e, c in sorted(disparos.items())},
           "clientes_tras_nxdomain_reenviados_en_ventanas_de_dc1": dict(culpables.most_common(10)),
           "marcas": len(marcas)}
    a.salida.write_text(json.dumps(res, indent=1, ensure_ascii=False), encoding="utf-8")
    print(json.dumps({k: res[k] for k in ("consultas", "copias_span_descartadas", "consultas_de_resolvedores",
                                          "reenvios_por_cliente", "ventanas_dns_entropy",
                                          "clientes_tras_nxdomain_reenviados_en_ventanas_de_dc1")}, indent=1))
    print("propias:", list(res["propias_por_dominio"].items())[:15])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
