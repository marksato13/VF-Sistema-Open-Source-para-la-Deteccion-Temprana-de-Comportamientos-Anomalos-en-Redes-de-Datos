#!/usr/bin/env python3
"""Resume el muestreo fino (1 s) en una ventana [desde, hasta] — cierre 4A, 4-nov-2026. Solo lectura.

Recursos alrededor del ensayo del anillo: cobertura del muestreo (huecos), PID(s) de Suricata, CPU por hilo
de Suricata (% de un núcleo, máximo por muestra y p95), CPU del host (iowait, softirq), softnet
(dropped, time_squeeze), NIC (rx_dropped, rx_missed_errors, rx_fifo_errors), disco (ms en E/S por segundo),
memoria disponible mínima, RSS máximo de Suricata y la mayor parada de crecimiento de eve.json.
Un dato que falta en una muestra se cuenta como «no legible», nunca como 0.
  analizar_fino.py --fino fino.jsonl --desde EPOCH --hasta EPOCH [--hz 100]
"""
from __future__ import annotations

import argparse
import json
import sys


def pct(v, f):
    v = sorted(v)
    return v[min(len(v) - 1, int(f * (len(v) - 1)))] if v else None


def main(argv=None) -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--fino", required=True)
    p.add_argument("--desde", type=float, required=True)
    p.add_argument("--hasta", type=float, required=True)
    p.add_argument("--hz", type=int, default=100, help="CLK_TCK")
    a = p.parse_args(argv)
    m = []
    with open(a.fino, encoding="utf-8") as fh:
        for l in fh:
            try:
                x = json.loads(l)
            except ValueError:
                continue
            if a.desde <= x["t"] <= a.hasta:
                m.append(x)
    r = {"desde": a.desde, "hasta": a.hasta, "muestras": len(m)}
    if len(m) < 2:
        r["clase"] = "no_evaluable"; print(json.dumps(r, indent=1)); return 3
    ts = [x["t"] for x in m]
    r["cobertura"] = {"primera": ts[0], "ultima": ts[-1], "margen_inicio_s": round(ts[0] - a.desde, 2),
                      "margen_fin_s": round(a.hasta - ts[-1], 2),
                      "hueco_max_s": round(max(b - c for c, b in zip(ts, ts[1:])), 2)}
    r["muestras_con_errores"] = sum(1 for x in m if x.get("errores"))
    pids = sorted({(x.get("suricata") or {}).get("pid") for x in m} - {None})
    r["pids_suricata"] = pids
    cpu_hilo_max, cpu_w = [], {}
    sirq, iow = [], []
    eve_parada = eve_par_max = 0.0
    eve_t_par = None
    disco_ms = []
    nolegible = {"nic": 0, "suricata": 0, "cpu": 0, "softnet": 0, "disco": 0, "mem": 0, "eve": 0}
    for x, y in zip(m, m[1:]):
        dt_ = y["t"] - x["t"]
        if dt_ <= 0:
            continue
        sx, sy = x.get("suricata"), y.get("suricata")
        if sx and sy and sx.get("pid") == sy.get("pid"):
            mx = 0.0
            for k, v in sy["hilos"].items():
                if k in sx["hilos"]:
                    c = 100.0 * (v - sx["hilos"][k]) / a.hz / dt_
                    mx = max(mx, c)
                    n = k.split("#")[0]
                    cpu_w.setdefault(n, []).append(c)
            cpu_hilo_max.append(mx)
        else:
            nolegible["suricata"] += 1
        if x.get("cpu") and y.get("cpu"):
            d = [b - c for c, b in zip(x["cpu"], y["cpu"])]
            tot = sum(d) or 1
            iow.append(100.0 * d[4] / tot); sirq.append(100.0 * d[6] / tot)
        else:
            nolegible["cpu"] += 1
        if x.get("disco") and y.get("disco"):
            disco_ms.append(max((y["disco"][k][2] - x["disco"][k][2]) / dt_ for k in y["disco"] if k in x["disco"]))
        else:
            nolegible["disco"] += 1
        if x.get("eve_bytes") is not None and y.get("eve_bytes") is not None:
            if y["eve_bytes"] == x["eve_bytes"]:
                eve_parada += dt_
                if eve_parada > eve_par_max:
                    eve_par_max, eve_t_par = eve_parada, y["t"]
            else:
                eve_parada = 0.0
        else:
            nolegible["eve"] += 1
    def delta(grupo, campo):
        v = [(x.get(grupo) or {}).get(campo) for x in (m[0], m[-1])]
        return None if None in v else v[1] - v[0]
    r["nic_incrementos"] = {k: delta("nic", k) for k in ("rx_packets", "rx_dropped", "rx_missed_errors", "rx_fifo_errors")}
    r["softnet_incrementos"] = {k: delta("softnet", k) for k in ("dropped", "time_squeeze")}
    mem = [x["mem_disponible_kb"] for x in m if x.get("mem_disponible_kb") is not None]
    rss = [(x.get("suricata") or {}).get("rss_kb") for x in m]
    rss = [v for v in rss if v is not None]
    r["suricata_cpu_hilo_mas_cargado_pct"] = {"p50": pct(cpu_hilo_max, .5), "p95": pct(cpu_hilo_max, .95), "max": max(cpu_hilo_max, default=None)}
    r["suricata_cpu_por_tipo_max_pct"] = {k: round(max(v), 1) for k, v in sorted(cpu_w.items())}
    r["host_softirq_pct"] = {"p95": pct(sirq, .95), "max": max(sirq, default=None)}
    r["host_iowait_pct"] = {"p95": pct(iow, .95), "max": max(iow, default=None)}
    r["disco_ms_en_es_por_s"] = {"p95": pct(disco_ms, .95), "max": max(disco_ms, default=None)}
    r["mem_disponible_min_kb"] = min(mem, default=None)
    r["suricata_rss_max_kb"] = max(rss, default=None)
    r["suricata_rss_inicio_fin_kb"] = [rss[0], rss[-1]] if rss else None
    r["eve_parada_max_s"] = round(eve_par_max, 1)
    r["eve_parada_max_termina_en"] = eve_t_par
    r["pares_no_legibles"] = nolegible
    for k in ("suricata_cpu_hilo_mas_cargado_pct", "host_softirq_pct", "host_iowait_pct", "disco_ms_en_es_por_s"):
        r[k] = {kk: (round(vv, 1) if isinstance(vv, float) else vv) for kk, vv in r[k].items()}
    print(json.dumps(r, indent=1, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
