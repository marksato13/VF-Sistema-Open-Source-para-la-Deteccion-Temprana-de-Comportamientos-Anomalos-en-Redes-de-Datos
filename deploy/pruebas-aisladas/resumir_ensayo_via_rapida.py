#!/usr/bin/env python3
"""Resume ensayo-via-rapida.jsonl por alternativa y carga (Etapa 3).

Cada fila del ensayo es una ejecución COMPLETA de la cadena; los percentiles se calculan
sobre ejecuciones (no se suman medianas de tramos). Tiempos en s desde el primer SYN de
la ráfaga (reloj del banco).

Uso: resumir_ensayo_via_rapida.py ensayo-via-rapida.jsonl resumen.json [tabla.md]
"""
from __future__ import annotations

import json
import sys
from collections import defaultdict


def pct(v: list[float], q: float) -> float | None:
    if not v:
        return None
    v = sorted(v)
    k = (len(v) - 1) * q
    i = int(k)
    return round(v[i] + (v[min(i + 1, len(v) - 1)] - v[i]) * (k - i), 3)


def main() -> int:
    filas = [json.loads(l) for l in open(sys.argv[1]) if l.strip()]
    g = defaultdict(list)
    for f in filas:
        g[(f["alternativa"], f["carga"])].append(f)
    res = {}

    def tramo(s, a, b):
        v = [x[b] - x[a] for x in s if x.get(a) is not None and x.get(b) is not None]
        return [pct(v, .5), pct(v, .95), round(max(v), 3) if v else None]

    for (alt, carga), fs in sorted(g.items()):
        s = [f["s_desde_rafaga"] for f in fs]
        # cierre Etapa 3: tramos por separado (p50 / p95 / máx)
        tramos = {"evidencia_a_emision": tramo(s, "evidencia", "emitida"),
                  "disponible_a_emision": tramo(s, "disponible", "emitida"),
                  "emision_a_publicacion": tramo(s, "emitida", "publicada"),
                  "publicacion_a_entrega": tramo(s, "publicada", "entregada"),
                  "entrega_a_aplicacion": tramo(s, "entregada", "aplicada"),
                  "aplicacion_a_confirmacion": tramo(s, "aplicada", "confirmada"),
                  "aplicacion_a_primer_descarte": tramo(s, "aplicada", "primer_descarte_visto"),
                  "primer_descarte_a_ultimo_syn": tramo(s, "primer_descarte_visto", "ultimo_syn")}
        conf = sum(1 for x in s if x.get("confirmada") is not None)
        apl = [x["aplicada"] for x in s if x.get("aplicada") is not None]
        dsc = [x["primer_descarte_visto"] for x in s if x.get("primer_descarte_visto") is not None]
        disp = [x["disponible"] - x["evidencia"] for x in s if x.get("disponible") is not None and x.get("evidencia") is not None]
        pub_ent = [x["entregada"] - x["publicada"] for x in s if x.get("entregada") is not None and x.get("publicada") is not None]
        ent_rec = [x["recibida_agente"] - x["entregada"] for x in s if x.get("recibida_agente") is not None and x.get("entregada") is not None]
        margen = [f["margen_s_aplicada_a_ultimo_syn"] for f in fs if f["margen_s_aplicada_a_ultimo_syn"] is not None]
        antes = sum(1 for x in s if x.get("primer_descarte_visto") is not None and x["primer_descarte_visto"] < x["ultimo_syn"])
        frac = [f["syn_tras_aplicacion"] / f["syn_escaneo_total"] for f in fs if f["syn_escaneo_total"]]
        res["%s|%s" % (alt, "carga" if carga else "sin_carga")] = {
            "n": len(fs), "sin_aplicacion": len(fs) - len(apl),
            "aplicada_p50_p95_max": [pct(apl, .5), pct(apl, .95), max(apl) if apl else None],
            "primer_descarte_p50_p95_max": [pct(dsc, .5), pct(dsc, .95), max(dsc) if dsc else None],
            "descarte_antes_del_ultimo_syn": "%d/%d" % (antes, len(fs)),
            "margen_aplicada_ultimo_syn_min_p05_p50": [min(margen) if margen else None, pct(margen, .05), pct(margen, .5)],
            "espera_disponible_p50_max": [pct(disp, .5), round(max(disp), 3) if disp else None],
            "rele_publicada_entregada_p50_max": [pct(pub_ent, .5), round(max(pub_ent), 3) if pub_ent else None],
            "agente_entregada_recibida_p50_max": [pct(ent_rec, .5), round(max(ent_rec), 3) if ent_rec else None],
            "syn_tras_aplicacion_frac_min_p50": [round(min(frac), 3) if frac else None, pct(frac, .5)],
            "confirmadas": "%d/%d" % (conf, len(fs)),
            "vlan": sorted({f.get("vlan", "quitada") for f in fs}),
            "tramos_p50_p95_max": tramos,
        }
    json.dump(res, open(sys.argv[2], "w"), indent=1)
    lineas = ["| Alternativa | Carga | n | Aplicada p50 / p95 / máx | 1.er descarte p50 / p95 / máx | Descarte antes del último SYN | Margen aplicada → último SYN mín / p50 | SYN tras aplicar (mín / p50) |",
              "|---|---|---|---|---|---|---|---|"]
    for k, v in res.items():
        alt, c = k.split("|")
        f3 = lambda t: " / ".join("—" if x is None else ("%.2f" % x).replace(".", ",") for x in t)
        lineas.append("| %s | %s | %d | %s | %s | %s | %s | %s |" % (
            alt, "sí" if c == "carga" else "no", v["n"], f3(v["aplicada_p50_p95_max"]),
            f3(v["primer_descarte_p50_p95_max"]), v["descarte_antes_del_ultimo_syn"],
            f3([v["margen_aplicada_ultimo_syn_min_p05_p50"][0], v["margen_aplicada_ultimo_syn_min_p05_p50"][2]]),
            "%s / %s" % tuple("—" if x is None else "%d %%" % round(100 * x) for x in v["syn_tras_aplicacion_frac_min_p50"])))
    txt = "\n".join(lineas)
    if len(sys.argv) > 3:
        open(sys.argv[3], "w", encoding="utf-8").write(txt + "\n")
    print(txt)
    for k, v in res.items():
        print(k, "disp", v["espera_disponible_p50_max"], "rele", v["rele_publicada_entregada_p50_max"],
              "agente", v["agente_entregada_recibida_p50_max"], "sin_apl", v["sin_aplicacion"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
