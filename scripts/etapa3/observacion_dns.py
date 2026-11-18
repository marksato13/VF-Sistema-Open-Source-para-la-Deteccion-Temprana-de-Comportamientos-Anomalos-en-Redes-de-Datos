#!/usr/bin/env python3
"""Cierre de la Etapa 3, punto 4: observación de varios días del DNS legítimo (SIN restringir).

Lee eve.json de Suricata (uno o varios ficheros, también .gz), se queda con las consultas
de los clientes HACIA los resolvedores internos (DC1/DC2), quita las copias del espejo
(la misma deduplicación de atribucion_dns.py) y calcula, por día local y por origen:

- consultas UDP/53 y TCP/53;
- picos: máximo de consultas UDP en 1, 10 y 60 s;
- ráfaga mínima b(r) de la envolvente de cubeta a la tasa candidata (0,5/s): con b >= b(r)
  la cubeta no descartaría ninguna consulta del origen;
- descartes SIMULADOS de la cubeta candidata (30/minuto, ráfaga 18) si el origen estuviera
  limitado por error TODO el día (peor caso; en la práctica un LIMIT dura minutos);
- errores en las respuestas: NXDOMAIN, SERVFAIL y otros rcode distintos de NOERROR;
- respuestas truncadas (TC) cuando el EVE las trae: indican uso legítimo de TCP/53.

Y evalúa el criterio FIJADO ANTES de medir (PROTOCOLO-OBSERVACION-DNS.md §3). No toca
nada: no consulta el laboratorio, no aplica reglas y no cambia la tasa ni la ráfaga.

Uso:
  observacion_dns.py salida.json eve1.json [eve2.json.gz ...] [--excluir 10.10.20.30]
                     [--utc-offset -5] [--tasa 0.5] [--rafaga 18]
"""
from __future__ import annotations

import argparse
import collections
import datetime as dt
import gzip
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import atribucion_dns as ad  # noqa: E402
from politica_limit_dns import rafaga_minima, simular  # noqa: E402

CRITERIO = {
    "P1": "0 consultas UDP/53 legitimas descartadas por la cubeta candidata en ningun origen y dia, "
          "con el origen limitado por error todo el dia (peor caso)",
    "P2": "aviso (no rechazo): origen-dia con b(0,5) > 2/3 de la rafaga candidata (margen < 1,5x)",
    "P3": "cobertura: >= 7 dias consecutivos con >= 5 laborables; sin huecos de EVE > 5 min "
          "(se comprueba aparte con la continuidad del EVE y kernel_drops)",
}


class _Gz:
    def __init__(self, p: Path) -> None:
        self.p = p

    def open(self, modo="rb"):
        return gzip.open(self.p, modo)


def picos(ts: list[float]) -> dict:
    out = {}
    for w in (1, 10, 60):
        j = m = 0
        for i in range(len(ts)):
            while ts[i] - ts[j] >= w:
                j += 1
            m = max(m, i - j + 1)
        out["max_%ds" % w] = m
    return out


def analizar(ficheros: list[Path], excluir: set, offset_h: float, tasa: float, rafaga: float) -> dict:
    tz = dt.timezone(dt.timedelta(hours=offset_h))
    udp = collections.defaultdict(list)                       # (dia, src) -> [t]
    tcp = collections.Counter()
    rcode = collections.defaultdict(collections.Counter)      # (dia, asker) -> rcode
    copias = 0
    tc = collections.Counter()
    for f in ficheros:
        consultas, respuestas, dup = ad.cargar(_Gz(f) if f.suffix == ".gz" else f)
        copias += dup
        for q in consultas:
            if q["dst"] not in ad.RESOLVEDORES or q["src"] in ad.RESOLVEDORES or q["src"] in excluir:
                continue
            dia = dt.datetime.fromtimestamp(q["t"], tz).date().isoformat()
            if str(q.get("proto")).upper() == "TCP":
                tcp[(dia, q["src"])] += 1
            else:
                udp[(dia, q["src"])].append(q["t"])
        for r in respuestas:
            asker = r["dst"] if r["src"] in ad.RESOLVEDORES else r["src"]
            if asker in ad.RESOLVEDORES or asker in excluir:
                continue
            dia = dt.datetime.fromtimestamp(r["t"], tz).date().isoformat()
            rcode[(dia, asker)][r.get("rcode") or "?"] += 1
    dias = collections.defaultdict(dict)
    claves = set(udp) | set(tcp) | set(rcode)
    for dia, src in sorted(claves):
        ts = sorted(udp.get((dia, src), []))
        b = rafaga_minima(ts, tasa) if ts else 0.0
        desc = simular(ts, tasa, rafaga) if ts else 0
        rc = rcode.get((dia, src), collections.Counter())
        dias[dia][src] = {"udp": len(ts), "tcp": tcp.get((dia, src), 0), **picos(ts),
                          "b_minima": round(b, 2), "descartes_simulados": desc,
                          "nxdomain": rc.get("NXDOMAIN", 0), "servfail": rc.get("SERVFAIL", 0),
                          "otros_errores": sum(n for k, n in rc.items() if k not in ("NOERROR", "NXDOMAIN", "SERVFAIL"))}
    p1 = [(d, s, v["descartes_simulados"]) for d, o in dias.items() for s, v in o.items() if v["descartes_simulados"]]
    p2 = [(d, s, v["b_minima"]) for d, o in dias.items() for s, v in o.items() if v["b_minima"] > rafaga * 2 / 3]
    tcp_origenes = sorted({s for (d, s), n in tcp.items() if n})
    return {
        "ficheros": [str(f) for f in ficheros], "excluidos": sorted(excluir), "utc_offset_h": offset_h,
        "cubeta": {"tasa_por_s": tasa, "rafaga": rafaga, "solo": "udp dport 53"},
        "copias_espejo_descartadas": copias, "criterio": CRITERIO,
        "resumen": {"dias": sorted(dias), "origenes": len({s for o in dias.values() for s in o}),
                    "consultas_udp": sum(len(v) for v in udp.values()), "consultas_tcp": sum(tcp.values()),
                    "origenes_con_tcp53": tcp_origenes,
                    "P1_cumple": not p1, "P1_incumplimientos": p1, "P2_avisos": p2},
        "por_dia": dias,
    }


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("salida", type=Path)
    ap.add_argument("eve", type=Path, nargs="+")
    ap.add_argument("--excluir", default="", help="origenes a excluir (p. ej. el atacante de una campana)")
    ap.add_argument("--utc-offset", type=float, default=-5.0, help="dia local (Lima: -5)")
    ap.add_argument("--tasa", type=float, default=0.5, help="consultas/s de la cubeta candidata (30/minuto)")
    ap.add_argument("--rafaga", type=float, default=18.0)
    a = ap.parse_args(argv)
    res = analizar(a.eve, {x for x in a.excluir.split(",") if x}, a.utc_offset, a.tasa, a.rafaga)
    a.salida.write_text(json.dumps(res, indent=1, ensure_ascii=False), encoding="utf-8")
    print(json.dumps(res["resumen"], indent=1, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
