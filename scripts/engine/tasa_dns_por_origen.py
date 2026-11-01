#!/usr/bin/env python3
"""Tasa de consultas DNS por origen hacia los DC (Etapa 2: elegir N del LIMIT DNS).

Lee un eve.json (Suricata) y cuenta, por IP de origen, las consultas DNS (eventos
dns de tipo query) hacia los servidores indicados, en ventanas de 1 s y 10 s.
Separa los segundos dentro de un episodio dns_inusual (marcas.jsonl, origen de
ensayo) del resto. El espejo SPAN puede registrar la misma consulta dos veces: se
deduplica por (origen, puerto origen, id DNS, nombre, segundo).

La pregunta que responde: ¿existe un N (paquetes/s por origen) que recorte al
generador del escenario sin recortar a ningun cliente legitimo observado? Si la
tasa del escenario no supera el maximo legitimo, NO existe y hay que decirlo.
"""
from __future__ import annotations

import argparse
import collections
import datetime as dt
import json
from pathlib import Path


def ts(x: str) -> float:
    return dt.datetime.fromisoformat(x.replace("Z", "+00:00").replace("+0000", "+00:00")).timestamp()


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--eve", type=Path, required=True)
    ap.add_argument("--marcas", type=Path, required=True)
    ap.add_argument("--servidores", default="10.10.10.20,10.10.10.21")
    ap.add_argument("--origen-ensayo", default="10.10.20.30")
    ap.add_argument("--salida", type=Path, required=True)
    a = ap.parse_args()
    servidores = set(a.servidores.split(","))
    marcas = [json.loads(l) for l in a.marcas.open(encoding="utf-8")]
    ini = {m["episodio_id"]: ts(m["reloj"]["pared_utc"]) for m in marcas if m.get("evento") == "inicio"}
    fin = {m["episodio_id"]: ts(m["reloj"]["pared_utc"]) for m in marcas if m.get("evento") == "fin"}
    episodios_dns = [(ini[e], fin[e]) for e in ini if e.startswith("dns_inusual") and e in fin]
    todos_ep = [(ini[e], fin[e]) for e in ini if e in fin]

    vistos = set()
    por_seg: dict[str, collections.Counter] = collections.defaultdict(collections.Counter)
    t_min = t_max = None
    with a.eve.open("rb") as fh:
        for linea in fh:
            if b'"event_type":"dns"' not in linea or b'"type":"query"' not in linea:
                continue
            e = json.loads(linea)
            if e.get("dest_ip") not in servidores or e.get("dest_port") != 53:
                continue
            t = ts(e["timestamp"])
            s = int(t)
            q = e.get("dns", {})
            clave = (e.get("src_ip"), e.get("src_port"), q.get("id"), q.get("rrname"), s)
            if clave in vistos:
                continue
            vistos.add(clave)
            por_seg[e["src_ip"]][s] += 1
            t_min = s if t_min is None else min(t_min, s)
            t_max = s if t_max is None else max(t_max, s)

    def en(s, tramos):
        return any(a0 <= s <= a1 for a0, a1 in tramos)

    res = {"servidores": sorted(servidores), "desde": t_min, "hasta": t_max, "origenes": {}}
    for ip, c in sorted(por_seg.items()):
        def resumen(segs):
            v = sorted(c[s] for s in segs)
            v10 = []
            if segs:
                for s0 in range(min(segs), max(segs) + 1, 10):
                    v10.append(sum(c.get(s, 0) for s in range(s0, s0 + 10)) / 10)
            q = lambda arr, p: arr[min(len(arr) - 1, int(p * (len(arr) - 1)))] if arr else None  # noqa: E731
            v10.sort()
            return {"segundos_con_consultas": len(v), "max_1s": v[-1] if v else 0, "p99_1s": q(v, 0.99),
                    "max_media_10s": round(v10[-1], 2) if v10 else 0, "total": sum(v)}
        segs_ep = [s for s in c if en(s, episodios_dns)]
        segs_fuera = [s for s in c if not en(s, todos_ep)]
        r = {"fuera_de_episodios": resumen(segs_fuera)}
        if ip == a.origen_ensayo:
            r["en_dns_inusual"] = resumen(segs_ep)
            r["en_dns_inusual"]["tasa_media_por_episodio"] = [
                round(sum(c.get(s, 0) for s in range(int(a0), int(a1) + 1)) / max(1, a1 - a0), 2)
                for a0, a1 in sorted(episodios_dns)]
        res["origenes"][ip] = r
    legit = [v["fuera_de_episodios"] for ip, v in res["origenes"].items() if ip != a.origen_ensayo]
    max_leg_1s = max((x["max_1s"] for x in legit), default=0)
    max_leg_10s = max((x["max_media_10s"] for x in legit), default=0)
    ens = res["origenes"].get(a.origen_ensayo, {}).get("en_dns_inusual", {})
    res["lectura"] = {
        "max_legitimo_1s": max_leg_1s, "max_legitimo_media_10s": max_leg_10s,
        "ensayo_tasas_medias": ens.get("tasa_media_por_episodio"),
        "ensayo_max_1s": ens.get("max_1s"),
        "existe_N_que_separa_por_tasa_media": bool(ens.get("tasa_media_por_episodio")) and
        min(ens["tasa_media_por_episodio"]) > max_leg_10s,
    }
    a.salida.write_text(json.dumps(res, indent=1, sort_keys=True), encoding="utf-8")
    print(json.dumps(res["lectura"], sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
