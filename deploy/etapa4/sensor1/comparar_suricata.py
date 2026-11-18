#!/usr/bin/env python3
"""Descartes de Suricata e intensidad del tráfico en una ventana [desde, hasta] (cierre 4A). Solo lectura.

Mismo método para la ventana de la 4A y para la del ensayo del anillo, para que sean comparables:
- stats.log: incrementos entre bloques consecutivos (8 s) de capture.kernel_packets / kernel_drops,
  segmentados por proceso (un uptime que baja = reinicio: el incremento que lo cruza NO se usa);
- intensidad: paquetes por intervalo de 8 s (p50/p95/máx) y nº de intervalos >= --rafaga-paquetes;
- EVE (eve.json y, si se pasan, rotados): flujos «flow» que TERMINAN en la ventana, con > --flujo-grande
  paquetes (las descargas que en la 4A coincidieron con los descartes), y volumen por cliente hacia srv-dmz.
La relación descargas-descartes que salga de aquí es CORRELACIÓN, no causa.

  comparar_suricata.py --stats /var/log/suricata/stats.log --eve /var/log/suricata/eve.json \
      --desde EPOCH --hasta EPOCH [--etiqueta 4A]
"""
from __future__ import annotations

import argparse
import datetime as dt
import gzip
import json
import re
import statistics
import sys
from pathlib import Path

RE_DATE = re.compile(r"^Date: (\d+)/(\d+)/(\d+) -- (\d+):(\d+):(\d+) \(uptime: (?:(\d+)d, )?(\d+)h (\d+)m (\d+)s\)")
RE_CONT = re.compile(r"^(capture\.kernel_packets|capture\.kernel_drops)\s+\|\s+Total\s+\|\s+(\d+)")
SRV = "10.10.30.10"


def bloques(stats: Path, desde: float, hasta: float):
    out, cur = [], None
    op = gzip.open if stats.suffix == ".gz" else open
    with op(stats, "rt", encoding="utf-8", errors="replace") as fh:
        for l in fh:
            m = RE_DATE.match(l)
            if m:
                if cur and "p" in cur and "d" in cur:
                    out.append(cur)
                mo, d, y, H, M, S = (int(m.group(i)) for i in range(1, 7))
                t = dt.datetime(y, mo, d, H, M, S, tzinfo=dt.timezone.utc).timestamp()
                up = int(m.group(7) or 0) * 86400 + int(m.group(8)) * 3600 + int(m.group(9)) * 60 + int(m.group(10))
                cur = {"t": t, "up": up} if desde - 30 <= t <= hasta + 30 else None
                continue
            if cur is not None:
                c = RE_CONT.match(l)
                if c:
                    cur["p" if c.group(1).endswith("packets") else "d"] = int(c.group(2))
    if cur and "p" in cur and "d" in cur:
        out.append(cur)
    return out


def bloques_eve(rutas: list[Path], desde: float, hasta: float):
    """Eventos «stats» de EVE (mismo intervalo de 8 s). A diferencia de stats.log —que con null-values por
    defecto OMITE los contadores a 0 y deja sin kernel_drops cada bloque sin descartes— EVE escribe
    kernel_drops: 0 explícito. Un evento sin kernel_packets o kernel_drops se ignora (no se supone 0)."""
    out = []
    for r in rutas:
        op = gzip.open if r.suffix == ".gz" else open
        with op(r, "rt", encoding="utf-8", errors="replace") as fh:
            for l in fh:
                if '"event_type":"stats"' not in l:
                    continue
                try:
                    e = json.loads(l)
                    cap = e["stats"]["capture"]
                    ts = e["timestamp"]
                    t = dt.datetime.strptime(ts[:26] + ts[-5:], "%Y-%m-%dT%H:%M:%S.%f%z").timestamp()
                    b = {"t": t, "up": int(e["stats"]["uptime"]), "p": int(cap["kernel_packets"]), "d": int(cap["kernel_drops"])}
                except (ValueError, KeyError, TypeError):
                    continue
                if desde - 30 <= t <= hasta + 30:
                    out.append(b)
    out.sort(key=lambda b: b["t"])
    return out


def leer_eve(rutas: list[Path], desde: float, hasta: float):
    flujos = []
    for r in rutas:
        op = gzip.open if r.suffix == ".gz" else open
        try:
            fh = op(r, "rt", encoding="utf-8", errors="replace")
        except OSError as exc:
            print("EVE no legible %s: %s" % (r, exc), file=sys.stderr)
            continue
        with fh:
            for l in fh:
                if '"event_type":"flow"' not in l:
                    continue
                try:
                    e = json.loads(l)
                except ValueError:
                    continue
                f = e.get("flow") or {}
                try:
                    fin = dt.datetime.strptime(f["end"][:26] + f["end"][-5:], "%Y-%m-%dT%H:%M:%S.%f%z").timestamp()
                except (KeyError, ValueError):
                    continue
                if desde <= fin <= hasta:
                    flujos.append({"src": e.get("src_ip"), "dst": e.get("dest_ip"), "proto": e.get("app_proto") or e.get("proto"),
                                   "pk": int(f.get("pkts_toserver", 0)) + int(f.get("pkts_toclient", 0)),
                                   "by": int(f.get("bytes_toserver", 0)) + int(f.get("bytes_toclient", 0)),
                                   "ini": f.get("start"), "fin": f.get("end")})
    return flujos


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--stats", type=Path, help="stats.log (omite contadores a 0: sin descartes no hay bloque válido)")
    p.add_argument("--stats-eve", type=Path, action="append", default=[],
                   help="eve.json (o rotados) de donde leer los eventos stats; tiene prioridad sobre --stats")
    p.add_argument("--eve", type=Path, action="append", default=[])
    p.add_argument("--desde", type=float, required=True)
    p.add_argument("--hasta", type=float, required=True)
    p.add_argument("--etiqueta", default="ventana")
    p.add_argument("--rafaga-paquetes", type=int, default=5000, help="paquetes en un intervalo de stats (8 s)")
    p.add_argument("--flujo-grande", type=int, default=1000)
    a = p.parse_args(argv)
    if a.stats_eve:
        fuente, bl = "eve stats", bloques_eve(a.stats_eve, a.desde, a.hasta)
    elif a.stats:
        fuente, bl = "stats.log", bloques(a.stats, a.desde, a.hasta)
    else:
        p.error("hace falta --stats-eve o --stats")
    bl = [b for b in bl if a.desde <= b["t"] <= a.hasta]
    incs, reinicios = [], 0
    for x, y in zip(bl, bl[1:]):
        if y["up"] < x["up"] or y["p"] < x["p"] or y["d"] < x["d"]:
            reinicios += 1
            continue
        incs.append({"t": y["t"], "s": y["t"] - x["t"], "p": y["p"] - x["p"], "d": y["d"] - x["d"]})
    paq = sum(i["p"] for i in incs)
    dsc = sum(i["d"] for i in incs)
    pk = sorted(i["p"] for i in incs) or [0]
    q = lambda f: pk[min(len(pk) - 1, int(f * (len(pk) - 1)))]
    raf = [i for i in incs if i["p"] >= a.rafaga_paquetes]
    con_d = [i for i in incs if i["d"] > 0]
    fl = leer_eve(a.eve, a.desde, a.hasta) if a.eve else []
    grandes = sorted([f for f in fl if f["pk"] >= a.flujo_grande], key=lambda f: -f["pk"])
    srv = {}
    for f in fl:
        if f["dst"] == SRV or f["src"] == SRV:
            c = f["src"] if f["dst"] == SRV else f["dst"]
            s = srv.setdefault(c, {"flujos": 0, "paquetes": 0, "bytes": 0})
            s["flujos"] += 1; s["paquetes"] += f["pk"]; s["bytes"] += f["by"]
    res = {
        "etiqueta": a.etiqueta, "fuente_contadores": fuente,
        "hueco_max_entre_bloques_s": round(max((y["t"] - x["t"] for x, y in zip(bl, bl[1:])), default=0), 1),
        "desde": a.desde, "hasta": a.hasta, "duracion_s": round(a.hasta - a.desde, 1),
        "bloques_stats": len(bl), "intervalos_validos": len(incs), "reinicios_suricata_en_ventana": reinicios,
        "cobertura_stats_s": round(sum(i["s"] for i in incs), 1),
        "paquetes": paq, "descartes": dsc, "descartes_por_millon": round(1e6 * dsc / paq, 3) if paq else None,
        "intervalos_con_descartes": [{"t_utc": dt.datetime.fromtimestamp(i["t"], dt.timezone.utc).strftime("%H:%M:%S"),
                                      "paquetes": i["p"], "descartes": i["d"]} for i in con_d],
        "paquetes_por_intervalo": {"p50": q(0.5), "p95": q(0.95), "max": pk[-1],
                                   "media": round(statistics.mean(pk), 1)},
        "pps_max_intervalo": round(max((i["p"] / i["s"] for i in incs if i["s"]), default=0), 1),
        "rafagas_ge_umbral": len(raf), "umbral_rafaga_paquetes_8s": a.rafaga_paquetes,
        "flujos_eve": len(fl), "flujos_grandes": len(grandes), "umbral_flujo_grande": a.flujo_grande,
        "flujos_grandes_top": grandes[:10], "paquetes_en_flujos_grandes": sum(f["pk"] for f in grandes),
        "volumen_srv_dmz_por_cliente": dict(sorted(srv.items(), key=lambda kv: -kv[1]["bytes"])),
    }
    print(json.dumps(res, indent=1, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
