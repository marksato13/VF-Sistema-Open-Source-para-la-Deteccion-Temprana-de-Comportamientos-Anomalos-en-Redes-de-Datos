#!/usr/bin/env python3
"""S1, S6, S8, S9 y S10 de E-carga v2 (= O1, O6, O8, O9 y O10 de CRITERIOS-FIJADOS §4) desde muestras.txt del bastión.
SOLO LECTURA. Mismas lecturas que la observación del 06-nov; el resultado es true, false o null (sin medida).

  derivar_bastion.py MUESTRAS.txt DESDE HASTA  -> JSON {"periodo", "muestras", "cobertura", "S1".."S10": {...}}

Cobertura (criterio de §4: lecturas cada <= 60 s): se usan las muestras en [DESDE − 60, HASTA + 60]. Debe haber una
a <= 60 s antes de DESDE (o en DESDE), otra a <= 60 s después de HASTA (o en HASTA) y ningún hueco > 60 s. Si no, todos
los S de este fichero son null: una ventana sin lecturas no cumple ni deja de cumplir.
Un S cuyo dato falta en alguna muestra de la ventana es null, nunca true.
  S1  (O1)  relé, ppi-motor, ppi-motor-capture, ppi-via-rapida@ens37, suricata, ppi-publicar-feed-v2 y el agente
            activos, con el mismo PID y NRestarts en todas las muestras.
  S6  (O6)  /home libre >= 2 GiB en todas (2 GiB es la lectura prudente de «2 GB»); carga y memoria se informan.
  S8  (O8)  firma_invalida y paquete_invalido sin aumento (Δ = 0) en la ventana.
  S9  (O9)  panel HTTPS 401 en todas las muestras y agente activo en srv-dmz.
  S10 (O10) 0 eventos aplicacion nuevos; ruleset de Sensor1 y de srv-dmz constantes; 0 procesos --aplicar/--enforce;
            agente sin --aplicar; v1 inactivos (relé, publicador y agente).
"""
import json
import re
import sys

MARGEN = 60.0
HOME_MIN_KB = 2097152
SERV_S = ("ppi-motor", "ppi-motor-capture", "ppi-via-rapida@ens37", "suricata", "ppi-publicar-feed-v2")


def bloques(texto):
    for b in texto.split("### ")[1:]:
        cab, _, cuerpo = b.partition("\n")
        try:
            yield float(cab.split()[1]), cuerpo
        except (IndexError, ValueError):
            continue


def g(p, c, n=1, conv=str):
    # 2026-11-06.2: una lectura que muestreo_bastion 2026-11-06.2 marca como ERROR deja el dato sin medida (None);
    # antes un estado «ERROR» contaba como servicio no activo o v1 no inactivo (false en vez de null).
    r = re.search(p, c, re.M)
    if not r or "ERROR" in r.groups():
        return None
    v = [conv(x) for x in r.groups()]
    return v[0] if n == 1 else v


def leer(t, c):
    m = {"t": t, "serv": {}}
    m["serv"]["relay"] = g(r"^B relay pid=(\d+) nr=(\d+) (\S+)", c, 3)
    for u in SERV_S:
        m["serv"][u] = g(r"^S %s pid=(\d+) nr=(\d+) (\S+)" % re.escape(u), c, 3)
    ag = g(r"^D agente pid=(\d+) nr=(\d+) (\S+) aplicar_cmd=(\d+) v1=(\S+)", c, 5)
    m["serv"]["agente"] = ag[:3] if ag else None
    m["aplicar_cmd"] = int(ag[3]) if ag else None
    m["v1_agente"] = ag[4] if ag else None
    v1b = g(r"^B relay .* v1timer=(\S+) v1=(\S+)", c, 2)
    m["v1_rele"] = v1b
    v1s = g(r"^S v1 (\S+)/(\S+) enforce_aplicar=(\d+)", c, 3)
    m["v1_pub"] = v1s[:2] if v1s else None
    m["enforce_aplicar"] = int(v1s[2]) if v1s else None
    m["panel"] = g(r"^B panel_https=(\d{3})", c)
    rec = g(r"home_libre_kb=(\d+) carga=(\S+) \S+ \S+ memdisp_kb=(\d+)", c, 3)
    m["home_kb"], m["carga1"], m["mem_kb"] = (int(rec[0]), float(rec[1]), int(rec[2])) if rec else (None, None, None)
    m["ruleset_s"] = g(r"^S ruleset=([0-9a-f]{16})$", c)
    d = g(r"^D aplicacion=(\d+) firma_invalida=(\d+) paquete_invalido=(\d+) ruleset=([0-9a-f]{16})$", c, 4)
    m["aplicacion"], m["firma"], m["paquete"], m["ruleset_d"] = (int(d[0]), int(d[1]), int(d[2]), d[3]) if d else (None,) * 4
    return m


def tri(cond_ok, falta):
    return None if falta else bool(cond_ok)


def derivar(texto, desde, hasta):
    todas = [leer(t, c) for t, c in bloques(texto)]
    sel = sorted((m for m in todas if desde - MARGEN <= m["t"] <= hasta + MARGEN), key=lambda m: m["t"])
    ven = [m for m in sel if desde <= m["t"] <= hasta]
    ts = [m["t"] for m in sel]
    huecos = [b - a for a, b in zip(ts, ts[1:])]
    cob = {"muestras_margen": len(sel), "muestras_ventana": len(ven),
           "antes_de_desde_s": round(desde - max([t for t in ts if t <= desde], default=float("-inf")), 1) if ts else None,
           "despues_de_hasta_s": round(min([t for t in ts if t >= hasta], default=float("inf")) - hasta, 1) if ts else None,
           "hueco_max_s": round(max(huecos), 1) if huecos else None}
    cob["ok"] = bool(ven) and cob["antes_de_desde_s"] is not None and cob["antes_de_desde_s"] <= MARGEN \
        and cob["despues_de_hasta_s"] is not None and cob["despues_de_hasta_s"] <= MARGEN \
        and (cob["hueco_max_s"] or 0) <= MARGEN
    res = {"version": "derivar_bastion 2026-11-06.2", "periodo": [desde, hasta], "cobertura": cob}
    if not cob["ok"]:
        for s in ("S1", "S6", "S8", "S9", "S10"):
            res[s] = {"valor": None, "motivo": "cobertura de lecturas insuficiente (criterio <= 60 s)"}
        return res
    # S1
    falta = [m["t"] for m in sel if any(v is None for v in m["serv"].values())]
    base = sel[0]["serv"]
    cambios = sorted({u for m in sel for u, v in m["serv"].items() if v and base.get(u) and v[:2] != base[u][:2]})
    inactivos = sorted({u for m in sel for u, v in m["serv"].items() if v and v[2] != "active"})
    res["S1"] = {"valor": tri(not cambios and not inactivos, falta), "pid_nr": {u: v[:2] if v else None for u, v in base.items()},
                 "cambios": cambios, "inactivos": inactivos, "muestras_sin_dato": falta[:10]}
    # S6
    falta = [m["t"] for m in ven if m["home_kb"] is None]
    hk = [m["home_kb"] for m in ven if m["home_kb"] is not None]
    mk = [m["mem_kb"] for m in ven if m["mem_kb"] is not None]
    ca = sorted(m["carga1"] for m in ven if m["carga1"] is not None)
    res["S6"] = {"valor": tri(hk and min(hk) >= HOME_MIN_KB, falta or not hk), "home_libre_min_kb": min(hk) if hk else None,
                 "memdisp_min_kb": min(mk) if mk else None, "carga1_max": ca[-1] if ca else None,
                 "carga1_mediana": ca[len(ca) // 2] if ca else None, "muestras_sin_dato": falta[:10]}
    # S8
    falta = [m["t"] for m in sel if m["firma"] is None]
    f = [(m["firma"], m["paquete"]) for m in sel if m["firma"] is not None]
    res["S8"] = {"valor": tri(f and len(set(f)) == 1, falta or not f),
                 "firma_invalida_ini_fin": [f[0][0], f[-1][0]] if f else None,
                 "paquete_invalido_ini_fin": [f[0][1], f[-1][1]] if f else None, "muestras_sin_dato": falta[:10]}
    # S9
    falta = [m["t"] for m in ven if m["panel"] is None or m["serv"]["agente"] is None]
    no401 = [m["t"] for m in ven if m["panel"] not in (None, "401")]
    ag_inact = [m["t"] for m in ven if m["serv"]["agente"] and m["serv"]["agente"][2] != "active"]
    res["S9"] = {"valor": tri(not no401 and not ag_inact, falta), "panel_401": f"{sum(1 for m in ven if m['panel'] == '401')}/{len(ven)}",
                 "no_401": no401[:10], "agente_no_activo": ag_inact[:10], "muestras_sin_dato": falta[:10]}
    # S10
    falta = [m["t"] for m in sel if None in (m["aplicacion"], m["ruleset_s"], m["ruleset_d"], m["enforce_aplicar"],
                                             m["aplicar_cmd"], m["v1_rele"], m["v1_pub"], m["v1_agente"])]
    ok_m = [m for m in sel if m["aplicacion"] is not None]
    apl = (ok_m[-1]["aplicacion"] - ok_m[0]["aplicacion"]) if ok_m else None
    rs = {m["ruleset_s"] for m in sel if m["ruleset_s"]}
    rd = {m["ruleset_d"] for m in sel if m["ruleset_d"]}
    forz = [m["t"] for m in sel if (m["enforce_aplicar"] or 0) > 0 or (m["aplicar_cmd"] or 0) > 0]
    v1 = [m["t"] for m in sel if any(x not in (None, "inactive") for x in (*(m["v1_rele"] or ()), *(m["v1_pub"] or ()), m["v1_agente"]))]
    res["S10"] = {"valor": tri(apl == 0 and len(rs) == 1 and len(rd) == 1 and not forz and not v1, falta or apl is None),
                  "aplicaciones_nuevas": apl, "rulesets_sensor1": sorted(rs), "rulesets_srvdmz": sorted(rd),
                  "con_aplicar_o_enforce": forz[:10], "v1_no_inactivo": v1[:10], "muestras_sin_dato": falta[:10]}
    return res


if __name__ == "__main__":
    with open(sys.argv[1], encoding="utf-8", errors="replace") as fh:
        print(json.dumps(derivar(fh.read(), float(sys.argv[2]), float(sys.argv[3])), ensure_ascii=False, indent=1))
