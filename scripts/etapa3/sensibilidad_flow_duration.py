#!/usr/bin/env python3
"""Etapa 3 (punto 6): efecto del tope de 230 s de flow_duration_mean_30s en las puntuaciones.

Toma el volcado de características de un replay (x = las 28 entradas del IF, en orden
del manifiesto) y, para las ventanas cuyo flow_duration_mean_30s está en el tope del
horizonte (>= 200 s: el recorte las deja en ~220 s), recalcula la puntuación con el valor sustituido por 300, 600
y 900 s (lo que habría podido valer con un horizonte más largo; el valor real es
DESCONOCIDO). Cuenta los cambios de decisión con cada α, separando atacante y
legítimos. No reentrena ni cambia nada: solo mide la sensibilidad.

Uso (con el venv del modelo):
  python sensibilidad_flow_duration.py modelo.joblib configs/features/multilayer-v2.json umbrales.json caracteristicas.jsonl salida.json
"""
from __future__ import annotations

import collections
import json
import sys

import joblib

ATK = "10.10.20.30"
TOPE = 230.0
MIN_EN_TOPE = 200.0  # el recorte deja los flujos largos en ~220 s (p90 operativo), no en 230
SUSTITUTOS = (300.0, 600.0, 900.0)


def main() -> int:
    modelo, esquema, umbrales, caract, salida = sys.argv[1:6]
    man = json.load(open(esquema, encoding="utf-8"))
    nombres = man.get("feature_names") or [f if isinstance(f, str) else f["name"] for f in man["features"]]
    i = nombres.index("flow_duration_mean_30s")
    umb = {float(k): v for k, v in json.load(open(umbrales, encoding="utf-8")).items()}
    pipe = joblib.load(modelo)
    filas = [json.loads(l) for l in open(caract, encoding="utf-8")]
    todas = len(filas)
    valores = sorted(r["x"][i] for r in filas)
    tope = [r for r in filas if r["x"][i] >= MIN_EN_TOPE]
    res = {"ventanas": todas, "en_tope": len(tope), "fraccion_en_tope": round(len(tope) / todas, 4),
           "operacion_percentiles": {p: valores[min(todas - 1, int(p * (todas - 1)))] for p in (0.5, 0.9, 0.95, 0.99)},
           "en_tope_por_entidad": dict(collections.Counter(r["entity_ip"] for r in tope).most_common(15)),
           "sustituciones": {}}
    base = [float(v) for v in pipe.score_samples([r["x"] for r in tope])] if tope else []
    for s in SUSTITUTOS:
        xs = [list(r["x"]) for r in tope]
        for x in xs:
            x[i] = s
        nuevo = [float(v) for v in pipe.score_samples(xs)] if xs else []
        por_alfa = {}
        for a, u in sorted(umb.items(), reverse=True):
            c = collections.Counter()
            for r, b, n in zip(tope, base, nuevo):
                quien = "atacante" if r["entity_ip"] == ATK else "legitimo"
                if b >= u > n:
                    c[quien + "_PERMIT_a_ALERT"] += 1
                elif n >= u > b:
                    c[quien + "_ALERT_a_PERMIT"] += 1
                c[quien + "_alert_base"] += int(b < u)
            por_alfa[str(a)] = dict(c)
        delta = [n - b for b, n in zip(base, nuevo)]
        res["sustituciones"][str(s)] = {"delta_score_medio": round(sum(delta) / len(delta), 5) if delta else None,
                                        "delta_min": round(min(delta), 5) if delta else None,
                                        "delta_max": round(max(delta), 5) if delta else None,
                                        "cambios_por_alfa": por_alfa}
    json.dump(res, open(salida, "w", encoding="utf-8"), indent=1)
    print(json.dumps({k: res[k] for k in ("ventanas", "en_tope", "fraccion_en_tope", "operacion_percentiles")}))
    for s, v in res["sustituciones"].items():
        print(s, v["delta_score_medio"], v["delta_min"], v["delta_max"], v["cambios_por_alfa"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
