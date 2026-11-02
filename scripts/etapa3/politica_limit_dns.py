#!/usr/bin/env python3
"""Etapa 3 (punto 4): política del LIMIT de DNS con datos, no con un número supuesto.

Unidad: CONSULTA DNS por origen hacia los resolvedores internos. En UDP, una consulta es
un paquete (las respuestas no pasan por el hook input del DC en sentido cliente->DC); los
reintentos del cliente (mismo id y puerto, > 5 ms) SÍ cuentan, porque nftables los ve
como paquetes nuevos. En TCP, una consulta son varios paquetes; por eso la política
limita UDP dport 53 y solo los SYN de TCP dport 53 (conexiones nuevas).

Para cada origen legítimo calcula la ENVOLVENTE de cubeta de fichas: para cada tasa r,
la ráfaga mínima b(r) tal que ninguna consulta suya se descartaría (count(Δ) <= b + r·Δ
para todo intervalo). Para el atacante simula la cubeta (r, b) sobre sus consultas
reales y da la fracción descartada (sin modelar sus reintentos: lo que haría la
herramienta ante el descarte es DESCONOCIDO y se mide en la campaña B).

Uso: python politica_limit_dns.py eve.json salida.json [--atacante 10.10.20.30]
"""
from __future__ import annotations

import argparse
import collections
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import atribucion_dns as ad  # noqa: E402

TASAS = (0.25, 0.5, 1.0, 1.5, 2.0, 3.0, 5.0)


def rafaga_minima(ts: list[float], r: float) -> float:
    """b mínima para que una cubeta (r, b) no descarte nada: max_i,j (j-i+1) - r·(t_j - t_i)."""
    mejor, peor_ini = 0.0, None
    # max sobre j de (j+1 - r t_j) - min sobre i<=j de (i - r t_i)
    m = float("inf")
    for j, t in enumerate(ts):
        m = min(m, j - r * t)
        mejor = max(mejor, (j + 1 - r * t) - m)
    return mejor


def simular(ts: list[float], r: float, b: float) -> int:
    fichas, ult, desc = b, None, 0
    for t in ts:
        if ult is not None:
            fichas = min(b, fichas + r * (t - ult))
        ult = t
        if fichas >= 1:
            fichas -= 1
        else:
            desc += 1
    return desc


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("eve", type=Path)
    ap.add_argument("salida", type=Path)
    ap.add_argument("--atacante", default="10.10.20.30")
    a = ap.parse_args()
    consultas, _, dup = ad.cargar(a.eve)
    por = collections.defaultdict(list)
    proto = collections.Counter()
    for q in consultas:
        if q["dst"] in ad.RESOLVEDORES and q["src"] not in ad.RESOLVEDORES:
            por[q["src"]].append(q["t"])
            proto[q["proto"]] += 1
    res = {"protocolos_hacia_resolvedores": dict(proto), "copias_span_descartadas": dup, "origenes": {}}
    legit_b = collections.defaultdict(float)
    for src, ts in sorted(por.items()):
        ts.sort()
        env = {str(r): round(rafaga_minima(ts, r), 2) for r in TASAS}
        pico = {}
        for w in (1, 10, 60):
            j, m = 0, 0
            for i in range(len(ts)):
                while ts[i] - ts[j] >= w:
                    j += 1
                m = max(m, i - j + 1)
            pico["max_en_%ds" % w] = m
        res["origenes"][src] = {"consultas": len(ts), "envolvente_b_por_r": env, **pico}
        if src != a.atacante:
            for r in TASAS:
                legit_b[r] = max(legit_b[r], env[str(r)])
    res["legitimos_b_minima_por_r"] = {str(r): round(b, 2) for r, b in legit_b.items()}
    ts_atk = sorted(por.get(a.atacante, []))
    tabla = []
    for r in TASAS:
        b_leg = legit_b[r]
        for factor in (1.0, 2.0):
            b = max(1.0, round(b_leg * factor))
            d = simular(ts_atk, r, b) if ts_atk else None
            tabla.append({"r_consultas_s": r, "b": b, "factor_sobre_legitimo": factor,
                          "atacante_descartadas": d, "atacante_total": len(ts_atk),
                          "fraccion": round(d / len(ts_atk), 3) if ts_atk else None})
    res["simulacion_atacante"] = tabla
    a.salida.write_text(json.dumps(res, indent=1), encoding="utf-8")
    print("protocolos", res["protocolos_hacia_resolvedores"])
    for s, v in res["origenes"].items():
        print(s, v["consultas"], v["max_en_1s"], v["max_en_10s"], v["max_en_60s"], v["envolvente_b_por_r"])
    print("legitimos b(r):", res["legitimos_b_minima_por_r"])
    for x in tabla:
        print(x)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
