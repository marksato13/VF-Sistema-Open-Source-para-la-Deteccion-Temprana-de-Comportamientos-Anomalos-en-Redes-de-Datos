#!/usr/bin/env python3
"""Compara salidas de replay_motor.py (Etapa 2): contenido frente a disponibilidad.

Contenido (debe ser IGUAL entre configuraciones que solo cambian cuando se mira):
  - claves de ventana decididas y no evaluadas;
  - las 28 caracteristicas (volcado --volcar-caracteristicas), score y decision;
  - clasificacion del IF por alfa (0,05 / 0,03 / 0,01) y heuristicos disparados.
Disponibilidad (es lo que se quiere mejorar):
  - latencia decision = logged_at - fin de ventana (p50/p90/max);
  - espera por PCAP: inicio_ciclo - marca_pcap; ciclos y su coste; memoria;
  - por episodio (marcas.jsonl): primera decision del heuristico previsto desde el
    origen de ensayo, relativa al inicio y al fin del episodio.
Uso: comparar_replays.py --referencia DIR --otros DIR... --marcas marcas.jsonl
     --esquema configs/features/multilayer-v2.json --salida comparacion.json
"""
from __future__ import annotations

import argparse
import collections
import datetime as dt
import json
import statistics
from pathlib import Path

ALFA = {"0.05": -0.5694578968203694, "0.03": -0.5898535710336618, "0.01": -0.6223889502095352}
ORIGEN = "10.10.20.30"
REGLA_PREVISTA = {"dns_inusual": "dns_entropy", "inundacion_http": "http_abuse", "escaneo_breve": "port_scan",
                  "escaneo_sostenido": "port_scan", "fuerza_bruta_http": "brute_force"}


def ts(x: str) -> float:
    return dt.datetime.fromisoformat(x.replace("Z", "+00:00")).timestamp()


def cuantiles(v: list[float]) -> dict:
    if not v:
        return {"n": 0}
    v = sorted(v)
    q = lambda p: v[min(len(v) - 1, int(round(p * (len(v) - 1))))]  # noqa: E731
    return {"n": len(v), "p50": round(q(0.5), 3), "p90": round(q(0.9), 3), "p99": round(q(0.99), 3),
            "max": round(v[-1], 3), "media": round(statistics.fmean(v), 3)}


def cargar(d: Path) -> dict:
    dec, noev = {}, {}
    for l in (d / "motor_decision.log").open(encoding="utf-8"):
        r = json.loads(l)
        k = (r.get("entity_ip"), r.get("window_end_utc"))
        if r.get("event") == "decision":
            dec[k] = r
        elif r.get("event") == "ventana_no_evaluada":
            noev[k] = r
    x = {}
    p = d / "caracteristicas.jsonl"
    if p.exists():
        for l in p.open(encoding="utf-8"):
            r = json.loads(l)
            x[(r["entity_ip"], r["window_end_utc"])] = r
    ciclos = [json.loads(l) for l in (d / "ciclos-arnes.jsonl").open(encoding="utf-8")]
    motor_ciclos = []
    p = d / "_state" / "ciclos.jsonl"
    if p.exists():
        motor_ciclos = [json.loads(l) for l in p.open(encoding="utf-8")]
    return {"dec": dec, "noev": noev, "x": x, "ciclos": ciclos, "motor_ciclos": motor_ciclos}


def reglas(r: dict) -> set:
    h = r.get("heuristicos")
    if isinstance(h, list):
        return {x["heuristico"] for x in h}
    return {r["heuristico"]["heuristico"]} if isinstance(r.get("heuristico"), dict) else set()


def clase_alfa(score) -> str:
    if score is None:
        return "sin_score"
    s = [a for a, u in sorted(ALFA.items(), reverse=True) if score < u]
    return s[-1] if s else "normal"


def contenido(ref: dict, otro: dict, nombres: list[str]) -> dict:
    kr, ko = set(ref["dec"]), set(otro["dec"])
    comunes = kr & ko
    out = {"decisiones_ref": len(kr), "decisiones_otro": len(ko), "comunes": len(comunes),
           "solo_ref": len(kr - ko), "solo_otro": len(ko - kr),
           "no_evaluadas_ref": len(ref["noev"]), "no_evaluadas_otro": len(otro["noev"]),
           "ejemplos_solo_ref": sorted(map(list, kr - ko))[:5], "ejemplos_solo_otro": sorted(map(list, ko - kr))[:5]}
    iguales_x = dif_x = 0
    por_car: dict[str, int] = {}
    max_dif: dict[str, float] = {}
    for k in comunes & set(ref["x"]) & set(otro["x"]):
        a, b = ref["x"][k]["x"], otro["x"][k]["x"]
        if a == b:
            iguales_x += 1
            continue
        dif_x += 1
        for n, u, v in zip(nombres, a, b):
            if u != v:
                por_car[n] = por_car.get(n, 0) + 1
                max_dif[n] = max(max_dif.get(n, 0.0), abs(u - v))
    out["caracteristicas"] = {"vectores_iguales": iguales_x, "vectores_distintos": dif_x,
                              "por_caracteristica": dict(sorted(por_car.items(), key=lambda t: -t[1])),
                              "max_dif_abs": {k: round(v, 6) for k, v in max_dif.items()}}
    s_ig = sum(1 for k in comunes if ref["dec"][k].get("score") == otro["dec"][k].get("score"))
    d_ig = sum(1 for k in comunes if ref["dec"][k]["decision"] == otro["dec"][k]["decision"])
    a_ig = sum(1 for k in comunes if clase_alfa(ref["dec"][k].get("score")) == clase_alfa(otro["dec"][k].get("score")))
    h_ig = sum(1 for k in comunes if reglas(ref["dec"][k]) == reglas(otro["dec"][k]))
    out.update(score_igual=s_ig, decision_igual=d_ig, clase_alfa_igual=a_ig, heuristicos_iguales=h_ig)
    # Totales por alfa y por regla en cada configuracion (todas sus decisiones, no solo comunes).
    for nombre, r in (("ref", ref), ("otro", otro)):
        tot = {a: 0 for a in ALFA}
        reg: dict[str, int] = {}
        for d in r["dec"].values():
            sc = d.get("score")
            for a, u in ALFA.items():
                if sc is not None and sc < u:
                    tot[a] += 1
            for g in reglas(d):
                reg[g] = reg.get(g, 0) + 1
        out["alertas_if_por_alfa_" + nombre] = tot
        out["heuristicos_" + nombre] = reg
    return out


def disponibilidad(r: dict) -> dict:
    lat = [d["logged_at"] - ts(d["window_end_utc"]) for d in r["dec"].values()]
    espera_pcap = [c["inicio_ciclo"] - c["marca_pcap"] for c in r["motor_ciclos"] if c.get("marca_pcap")]
    dur = [c["dur_s"] for c in r["ciclos"] if not c.get("arranque")]
    disparos: dict[str, int] = {}
    for c in r["motor_ciclos"]:
        disparos[c.get("disparo", "?")] = disparos.get(c.get("disparo", "?"), 0) + 1
    pend = [c.get("ventanas_pendientes", 0) for c in r["motor_ciclos"]]
    lat_score = [d["logged_at"] - ts(d["window_end_utc"]) for d in r["dec"].values() if d.get("score") is not None]
    lat_sin = [d["logged_at"] - ts(d["window_end_utc"]) for d in r["dec"].values() if d.get("score") is None]
    return {"latencia_decision_s": cuantiles(lat),
            "latencia_decision_con_score_s": cuantiles(lat_score),
            "latencia_decision_sin_score_s": cuantiles(lat_sin),
            "espera_marca_pcap_s": cuantiles(espera_pcap),
            "ciclos": len(r["ciclos"]), "duracion_ciclo_s": cuantiles(dur), "disparos": disparos,
            "pendientes_por_ciclo": cuantiles([float(x) for x in pend]),
            "memoria_pico_mb": max((c.get("pico_mb", 0) for c in r["ciclos"]), default=None),
            "memoria_rss_max_mb": max((c.get("rss_mb", 0) for c in r["ciclos"]), default=None)}


def episodios(r: dict, marcas: list[dict], desde: float, hasta: float) -> list[dict]:
    ini = {m["episodio_id"]: m for m in marcas if m.get("evento") == "inicio"}
    fin = {m["episodio_id"]: m for m in marcas if m.get("evento") == "fin"}
    out = []
    for eid, m in ini.items():
        t0 = ts(m["reloj"]["pared_utc"])
        if not desde <= t0 <= hasta:
            continue
        t1 = ts(fin[eid]["reloj"]["pared_utc"]) if eid in fin else None
        regla = REGLA_PREVISTA[m["escenario"]]
        cand = [d for d in r["dec"].values() if d["entity_ip"] == ORIGEN and regla in reglas(d)
                and ts(d["window_end_utc"]) > t0 - 10 and ts(d["window_end_utc"]) <= (t1 or t0) + 120]
        primera = min(cand, key=lambda d: d["logged_at"]) if cand else None
        if_alfa = {}
        for a, u in ALFA.items():
            c = [d for d in r["dec"].values() if d["entity_ip"] == ORIGEN and d.get("score") is not None
                 and d["score"] < u and t0 - 10 < ts(d["window_end_utc"]) <= (t1 or t0) + 120]
            if_alfa[a] = round(min(d["logged_at"] for d in c) - t0, 2) if c else None
        out.append({"episodio": eid, "regla_prevista": regla, "inicio": t0, "duracion_s": round(t1 - t0, 1) if t1 else None,
                    "t_heur_desde_inicio_s": round(primera["logged_at"] - t0, 2) if primera else None,
                    "antes_del_fin": (primera["logged_at"] <= t1) if (primera and t1) else None,
                    "ventana": primera["window_end_utc"] if primera else None,
                    "t_if_desde_inicio_s_por_alfa": if_alfa})
    return sorted(out, key=lambda e: e["inicio"])


def siete_configuraciones(r: dict, marcas: list[dict], desde: float, hasta: float) -> dict:
    """D3/punto 8: IF (3 alfa), HEUR, hibrido IF|HEUR (3 alfa). Deteccion por episodio y alarmas fuera.

    Deteccion de un episodio: alguna ventana del origen de ensayo con fin en
    (inicio - 10, fin + 120] que cumple la configuracion; t = logged_at - inicio.
    HEUR cuenta solo la regla prevista del escenario. Fuera de episodios: ventanas
    (de cualquier entidad) que cumplen la configuracion y no caen en (inicio - 10,
    fin + 120] de ningun episodio, con fin de ventana dentro de [desde, hasta].
    """
    ini = {m["episodio_id"]: m for m in marcas if m.get("evento") == "inicio"}
    fin = {m["episodio_id"]: m for m in marcas if m.get("evento") == "fin"}
    eps = []
    for eid, m in ini.items():
        t0 = ts(m["reloj"]["pared_utc"])
        t1 = ts(fin[eid]["reloj"]["pared_utc"]) if eid in fin else t0
        eps.append((eid, m["escenario"], t0, t1))
    todos = [(t0 - 10, t1 + 120) for _, _, t0, t1 in eps]
    eps = [e for e in eps if desde <= e[2] <= hasta]

    def cumple(d, cfg, regla=None):
        sc = d.get("score")
        if_ok = lambda a: sc is not None and sc < ALFA[a]  # noqa: E731
        h = reglas(d)
        h_ok = (regla in h) if regla else bool(h)
        if cfg == "HEUR":
            return h_ok
        tipo, a = cfg.split("_")
        return if_ok(a) if tipo == "IF" else (if_ok(a) or h_ok)

    cfgs = ["IF_0.05", "IF_0.03", "IF_0.01", "HEUR", "HIB_0.05", "HIB_0.03", "HIB_0.01"]
    out = {}
    for cfg in cfgs:
        det = {}
        for eid, esc, t0, t1 in eps:
            c = [d for d in r["dec"].values() if d["entity_ip"] == ORIGEN
                 and t0 - 10 < ts(d["window_end_utc"]) <= t1 + 120 and cumple(d, cfg, REGLA_PREVISTA[esc])]
            det[eid] = round(min(d["logged_at"] for d in c) - t0, 2) if c else None
        fuera = [d for d in r["dec"].values() if desde <= ts(d["window_end_utc"]) <= hasta
                 and not any(a0 < ts(d["window_end_utc"]) <= a1 for a0, a1 in todos) and cumple(d, cfg)]
        # Falsas alarmas que la cuenta "fuera" no ve: OTRAS entidades dentro de los intervalos de episodio.
        otras = [d for d in r["dec"].values() if d["entity_ip"] != ORIGEN and desde <= ts(d["window_end_utc"]) <= hasta
                 and any(a0 < ts(d["window_end_utc"]) <= a1 for a0, a1 in todos) and cumple(d, cfg)]
        out[cfg] = {"detectados": sum(1 for v in det.values() if v is not None), "episodios": len(det),
                    "alarmas_otras_entidades_en_episodios": len(otras),
                    "alarmas_otras_entidades_en_episodios_ips": sorted({d["entity_ip"] for d in otras}),
                    "t_det_s": det, "alarmas_fuera_ventanas": len(fuera),
                    "alarmas_fuera_entidades": sorted({d["entity_ip"] for d in fuera})}
        if cfg == "HEUR":
            por = collections.Counter("%s|%s" % (d["entity_ip"], g) for d in fuera for g in sorted(reglas(d)))
            out[cfg]["alarmas_fuera_por_entidad_y_regla"] = dict(sorted(por.items()))
            por2 = collections.Counter("%s|%s" % (d["entity_ip"], g) for d in otras for g in sorted(reglas(d)))
            out[cfg]["alarmas_otras_en_episodios_por_entidad_y_regla"] = dict(sorted(por2.items()))
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--referencia", type=Path, required=True)
    ap.add_argument("--otros", type=Path, nargs="+", required=True)
    ap.add_argument("--marcas", type=Path, required=True)
    ap.add_argument("--esquema", type=Path, required=True)
    ap.add_argument("--desde", type=ts, required=True)
    ap.add_argument("--hasta", type=ts, required=True)
    ap.add_argument("--salida", type=Path, required=True)
    a = ap.parse_args()
    esquema = json.loads(a.esquema.read_text(encoding="utf-8"))
    nombres = [f["name"] for f in sorted(esquema["features"], key=lambda f: f["order"])]
    marcas = [json.loads(l) for l in a.marcas.open(encoding="utf-8")]
    ref = cargar(a.referencia)
    res = {"referencia": a.referencia.name, "n_caracteristicas": len(nombres), "configuraciones": {}}
    for d in [a.referencia] + a.otros:
        r = ref if d == a.referencia else cargar(d)
        res["configuraciones"][d.name] = {
            "contenido_vs_referencia": contenido(ref, r, nombres) if d != a.referencia else None,
            "disponibilidad": disponibilidad(r),
            "episodios": episodios(r, marcas, a.desde, a.hasta),
            "siete_configuraciones": siete_configuraciones(r, marcas, a.desde, a.hasta)}
    a.salida.write_text(json.dumps(res, indent=1, sort_keys=True), encoding="utf-8")
    for n, c in res["configuraciones"].items():
        cv = c["contenido_vs_referencia"] or {}
        dl = c["disponibilidad"]["latencia_decision_s"]
        print(n, "| comunes", cv.get("comunes"), "solo_ref", cv.get("solo_ref"), "solo_otro", cv.get("solo_otro"),
              "| x_distintos", (cv.get("caracteristicas") or {}).get("vectores_distintos"), "| lat p50/p90/max",
              dl.get("p50"), dl.get("p90"), dl.get("max"), "| pico MB", c["disponibilidad"]["memoria_pico_mb"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
