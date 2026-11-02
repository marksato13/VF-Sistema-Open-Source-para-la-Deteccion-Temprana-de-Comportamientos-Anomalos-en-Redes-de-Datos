#!/usr/bin/env python3
"""Añade la vía rápida a las categorías por episodio de analizar_3b.py (Etapa 3).

No modifica analizar_3b.py ni su salida: lee su analisis-3b.json y las señales
rápidas (detector_rapido / evaluar_regla_temprana sobre el archivo) y calcula:

  RAPIDA        solo la vía rápida
  HEUR+R        HEUR (reglas por ventanas) o vía rápida, la primera disponible
  HIB_a+R       HIB a α (IF o reglas por ventanas) o vía rápida

Disponibilidad de la señal rápida: su marca de evidencia (tiempo de datos, reloj del
sensor) más un retraso fijo ``--retraso-rapida`` (s), que representa detector +
cadena hasta la señal; NO incluye publicación ni aplicación (eso es el presupuesto
del banco). Con 0 se mide la evidencia, que es lo que hace el analizador con las
ventanas (disponibilidad del registro, no aplicación).

Categorías con la misma semántica que analizar_3b.py: oportuna si alguna señal
atribuible está disponible <= fin del episodio; solo_posterior si solo después
(hasta fin + 60 s, como el episodio ampliado); si no, la categoría que diera la
configuración base. Un episodio fuera de la población principal se marca igual que
en el analizador (no se recupera ninguno).

Uso: via_rapida_episodios.py marcas.jsonl analisis-3b.json senales_rapidas.jsonl salida.json
      [--atacante 10.10.20.30] [--retraso-rapida 0] [--control INI,FIN]
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
from collections import Counter


def ts(s: str) -> float:
    return dt.datetime.fromisoformat(s.replace("Z", "+00:00")).timestamp()


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("marcas")
    p.add_argument("analisis")
    p.add_argument("rapidas")
    p.add_argument("salida")
    p.add_argument("--atacante", default="10.10.20.30")
    p.add_argument("--retraso-rapida", type=float, default=0.0)
    p.add_argument("--ampliacion", type=float, default=60.0)
    p.add_argument("--control", default="2026-11-01T07:32:00Z,2026-11-01T08:05:00Z")
    a = p.parse_args()

    ini, fin = {}, {}
    for l in open(a.marcas, encoding="utf-8"):
        r = json.loads(l)
        if r.get("evento") == "inicio":
            ini[r["episodio_id"]] = ts(r["reloj"]["pared_utc"])
        elif r.get("evento") == "fin":
            fin[r["episodio_id"]] = ts(r["reloj"]["pared_utc"])
    A = json.load(open(a.analisis, encoding="utf-8"))
    rap = [json.loads(l) for l in open(a.rapidas, encoding="utf-8") if l.strip()]

    c0, c1 = (ts(x) for x in a.control.split(","))
    en_control = [s for s in rap if c0 <= s["t_evidencia"] < c1]
    fuera_atacante = [s for s in rap if s["origen"] != a.atacante]

    bases = {"RAPIDA": None, "HEUR+R": "HEUR", "HIB_0.05+R": "HIB_0.05", "HIB_0.03+R": "HIB_0.03",
             "HIB_0.01+R": "HIB_0.01"}
    filas, cuenta = [], {k: Counter() for k in list(bases) + ["HEUR", "HIB_0.05", "HIB_0.03", "HIB_0.01"]}
    for e, x in A["episodios"].items():
        i, f = ini.get(e), fin.get(e)
        prin = x.get("en_poblacion_principal")
        sen = sorted((s for s in rap if s["origen"] == a.atacante and i is not None and f is not None
                      and i <= s["t_evidencia"] <= f + a.ampliacion), key=lambda s: s["t_evidencia"])
        disp = [s["t_evidencia"] + a.retraso_rapida for s in sen]
        if not disp:
            cat_r, t_r = None, None
        else:
            t_r = disp[0]
            cat_r = "oportuna" if t_r <= f else "solo_posterior"
        fila = {"episodio": e, "principal": prin, "inicio_utc": i, "fin_utc": f,
                "rapidas": [{"id": s["id"], "t_evidencia": s["t_evidencia"], "puertos_fallidos": s["puertos_fallidos"]}
                            for s in sen],
                "rapida_desde_inicio_s": round(t_r - i, 3) if t_r else None,
                "rapida_antes_del_fin_s": round(f - t_r, 3) if t_r else None}
        for nombre, base in bases.items():
            cb = (x.get(base) or {}).get("categoria") if base else None
            if cb == "no_evaluable":
                cat = "no_evaluable"
            elif cat_r == "oportuna" or cb == "oportuna":
                cat = "oportuna"
            elif cat_r == "solo_posterior" or cb == "solo_posterior":
                cat = "solo_posterior"
            else:
                cat = cb or "sin_senal_rapida"
            fila[nombre] = cat
            cuenta[nombre][cat if prin else "fuera:" + cat] += 1
        for base in ("HEUR", "HIB_0.05", "HIB_0.03", "HIB_0.01"):
            cb = (x.get(base) or {}).get("categoria")
            fila[base] = cb
            cuenta[base][cb if prin else "fuera:" + cb] += 1
        filas.append(fila)
    res = {"parametros": vars(a), "episodios": filas,
           "resumen": {k: dict(v) for k, v in cuenta.items()},
           "control": {"senales_rapidas": len(en_control), "pares": sorted({(s["origen"], s["destino"]) for s in en_control})},
           "senales_rapidas_total": len(rap),
           "senales_rapidas_fuera_del_atacante": len(fuera_atacante)}
    json.dump(res, open(a.salida, "w", encoding="utf-8"), indent=1, ensure_ascii=False)
    for k, v in res["resumen"].items():
        print(k, dict(sorted(v.items())))
    print("control:", res["control"], "| total:", len(rap), "| fuera del atacante:", len(fuera_atacante))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
