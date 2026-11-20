#!/usr/bin/env python3
"""Analizador de la Campaña B (E2-E5 por episodio). Solo biblioteca estándar.

Entrada: un JSON con {"episodios": [...], "planificados": N}. Cada episodio:
  episodio_id, escenario, origen, accion_prevista ("BLOCK" | "LIMIT" | null),
  t_inicio, t_fin_ref, t_fin_observado (opc.), t_det (opc.), t_siguiente (opc.),
  u (incertidumbre de relojes en s; mínimo EPS), excluido (opc., motivo),
  traza_agente: eventos de /var/lib/cyberflow/agente/traza.jsonl,
  serie: bloques de 1 s [{"t","aceptadas","resp","syn"}],
  lecturas_set: [{"t","bloqueados":[ip],"limitados":[ip]}],
  control: [{"t","ok","atribuible"}].
Resultados por criterio: cumple | fallo | indeterminado | fallo_experimento | no_aplica.
Las reglas están en REGLAS-E2-E5.md; las constantes, aquí y fijadas antes de ejecutar.
"""
import json
import math
import sys

EPS = 0.01          # s, cota mínima de incertidumbre (DB-13)
BLOQUE = 1.0        # s, anchura de bloque de la serie SPAN
K_LIMIT = 5         # bloques sostenidos para LIMIT (DB-2)
K_BLOCK = 3         # bloques sostenidos para BLOCK
THETA = 0.5         # reducción mínima de LIMIT
N_BASE = 10         # bloques de línea base de LIMIT
BASE_MIN = 5.0      # conexiones/s mínimas de la línea base para poder medir una reducción
INTENTO_MIN = 0.5   # fracción de B0 de SYN que prueba que el generador siguió intentando (LIMIT)
HUECOS_MAX = 0.10   # fracción de bloques ausentes tolerada en la serie
SET_DE = {"BLOCK": "bloqueados", "LIMIT": "limitados"}


def t_fin_eval(ep):
    obs = ep.get("t_fin_observado")
    return min(ep["t_fin_ref"], obs) if obs is not None else ep["t_fin_ref"]


def _u(ep):
    return max(EPS, float(ep.get("u", EPS)))


def comparar(t_inf, t_sup, t_fin, u):
    """t_inf..t_sup acota el instante medido. cumple si t_sup+u < t_fin; fallo si t_inf-u >= t_fin."""
    if t_sup + u < t_fin:
        return "cumple"
    if t_inf - u >= t_fin:
        return "fallo"
    return "indeterminado"


# ---------------------------------------------------------------- E2
def evidencia_aplicacion(ep):
    """Devuelve dict con t_apl_inf/sup (recepción/aplicado_en), confirmación y violaciones, desde la traza."""
    origen, accion = ep["origen"], ep["accion_prevista"]
    ventana = (ep["t_inicio"] - 2, ep["t_fin_ref"] + 400)
    tr = [e for e in ep.get("traza_agente", [])]
    rec = {e["secuencia"]: e for e in tr if e.get("evento") == "recepcion" and e.get("estado") == "aceptado"}
    conf = {e["secuencia"]: e for e in tr if e.get("evento") == "confirmacion"}
    out = {"hay_traza": any(ventana[0] <= e.get("t", e.get("recibido_en", 0)) <= ventana[1] for e in tr),
           "aplicaciones": [], "violaciones": []}
    for e in tr:
        if e.get("evento") != "aplicacion":
            continue
        for n in e.get("nuevos", []):
            if n["ip"] != origen or n["set"] != SET_DE.get(accion):
                out["violaciones"].append({"ip": n["ip"], "set": n["set"], "id": n["id"]})
                continue
            if not (ventana[0] <= e["aplicado_en"] <= ventana[1]):
                continue
            c = conf.get(e["secuencia"], {})
            estado = ("confirmada" if n["id"] in c.get("confirmadas", []) else
                      "no_confirmada" if n["id"] in c.get("no_confirmadas", []) else "sin_confirmacion")
            out["aplicaciones"].append({"id": n["id"], "t_sup": e["aplicado_en"], "hasta": n.get("hasta"),
                                        "t_inf": rec.get(e["secuencia"], {}).get("recibido_en", e["aplicado_en"]),
                                        "estado": estado})
    out["aplicaciones"].sort(key=lambda a: a["t_sup"])
    return out


def e2(ep):
    if ep.get("accion_prevista") is None:
        return {"resultado": "no_aplica", "motivo": "sin punto de aplicación"}
    ev = evidencia_aplicacion(ep)
    r = {"violaciones": ev["violaciones"]}
    if ev["violaciones"]:
        return {**r, "resultado": "fallo", "motivo": "restricción fuera del origen o del set previstos (P1)"}
    if not ev["hay_traza"]:
        return {**r, "resultado": "fallo_experimento", "motivo": "sin traza del agente en la ventana"}
    if not ev["aplicaciones"]:
        return {**r, "resultado": "fallo", "motivo": "sin evidencia de regla cargada"}
    a = ev["aplicaciones"][0]
    r.update(t_apl_inf=a["t_inf"], t_apl_sup=a["t_sup"], id=a["id"], hasta=a["hasta"], confirmacion=a["estado"],
             margen_s=t_fin_eval(ep) - a["t_sup"])
    if a["estado"] == "no_confirmada":
        return {**r, "resultado": "fallo", "motivo": "el helper retornó pero el set no contiene la regla"}
    res = comparar(a["t_inf"], a["t_sup"], t_fin_eval(ep), _u(ep))
    if a["estado"] == "sin_confirmacion" and res == "cumple":
        res = "indeterminado"
    return {**r, "resultado": res, "motivo": {"cumple": "regla confirmada antes del fin",
                                              "fallo": "regla cargada después del fin",
                                              "indeterminado": "margen menor que la incertidumbre o sin confirmación"}[res]}


# ---------------------------------------------------------------- E3
def _bloques_desde(serie, t0):
    return sorted((b for b in serie if b["t"] >= t0), key=lambda b: b["t"])


def _huecos(serie, desde, hasta):
    esperados = max(1, int((hasta - desde) / BLOQUE))
    presentes = len({int((b["t"] - desde) / BLOQUE) for b in serie if desde <= b["t"] < hasta})
    return 1 - presentes / esperados


def e3(ep, r2):
    acc = ep.get("accion_prevista")
    if acc is None:
        return {"resultado": "no_aplica", "motivo": "sin punto de aplicación"}
    if r2["resultado"] in ("fallo", "fallo_experimento"):
        return {"resultado": "fallo" if r2["resultado"] == "fallo" else "fallo_experimento",
                "motivo": "dependiente de E2: " + r2["motivo"]}
    t_fin, u, serie = t_fin_eval(ep), _u(ep), ep.get("serie", [])
    t_apl = r2["t_apl_sup"]
    k = K_LIMIT if acc == "LIMIT" else K_BLOCK
    blq = [b for b in _bloques_desde(serie, math.ceil(t_apl)) if b["t"] + BLOQUE <= t_fin]
    if _huecos(serie, ep["t_inicio"], t_fin) > HUECOS_MAX:
        return _tope(r2, {"resultado": "indeterminado", "motivo": "I3 serie degradada (huecos > 10 %)"})
    campo = "aceptadas" if acc == "LIMIT" else "resp"
    b0 = None
    if acc == "LIMIT":
        previos = sorted((b for b in serie if b["t"] + BLOQUE <= t_apl), key=lambda b: b["t"])[-N_BASE:]
        if len(previos) < N_BASE:
            return _tope(r2, {"resultado": "indeterminado", "motivo": "I5 sin línea base de 10 bloques"})
        b0 = sum(b["aceptadas"] for b in previos) / N_BASE
        if b0 < BASE_MIN:
            return _tope(r2, {"resultado": "indeterminado", "motivo": "I5 línea base demasiado baja", "b0": b0})
    if len(blq) < k:
        return _tope(r2, {"resultado": "indeterminado", "motivo": "I1 menos de %d bloques tras t_apl" % k})
    umbral_syn = INTENTO_MIN * b0 if acc == "LIMIT" else 1
    lim = (1 - THETA) * b0 if acc == "LIMIT" else 0
    t_efecto, intento_sostenido = None, False
    for i in range(len(blq) - k + 1):
        run = blq[i:i + k]
        intenta = all(b["syn"] >= umbral_syn for b in run)
        intento_sostenido = intento_sostenido or intenta
        if intenta and all(b[campo] <= lim for b in run):
            t_efecto = run[0]["t"]
            break
    if t_efecto is None and not intento_sostenido:
        return _tope(r2, {"resultado": "indeterminado", "motivo": "I2 el generador no siguió intentando %d bloques tras t_apl" % k})
    if t_efecto is None:
        return {"resultado": "fallo", "motivo": "el generador siguió intentando y no se sostuvo el efecto", "b0": b0}
    res = comparar(t_efecto, t_efecto + BLOQUE, t_fin, u)
    r3 = {"resultado": res, "motivo": "efecto sostenido %d bloques" % k, "t_efecto": t_efecto, "b0": b0}
    # El efecto visto en el SPAN solo se atribuye a la regla si el propio host cuenta paquetes descartados por ella
    # (evento primer_descarte del agente, con el id de la regla): un retorno ok del helper o una regla cargada no lo prueban.
    desc = primer_descarte(ep, r2)
    r3["primer_descarte_host"] = desc
    if res == "cumple" and desc is None:
        r3.update(resultado="indeterminado", motivo="efecto en el SPAN sin contador de descartes de la regla en el host")
    return _tope(r2, r3)


def primer_descarte(ep, r2):
    t_min, t_max = r2["t_apl_inf"], ep["t_fin_ref"] + 400
    ts = [e["t"] for e in ep.get("traza_agente", []) if e.get("evento") == "primer_descarte" and e.get("id") == r2.get("id")
          and e.get("ip") == ep["origen"] and t_min <= e.get("t", 0) <= t_max]
    return min(ts) if ts else None


def _tope(r2, r3):
    """E3 no puede ser mejor que E2: con E2 indeterminada, E3 cumple pasa a indeterminada."""
    if r2["resultado"] == "indeterminado" and r3["resultado"] == "cumple":
        return {**r3, "resultado": "indeterminado", "motivo": r3["motivo"] + "; E2 indeterminada"}
    return r3


# ---------------------------------------------------------------- E4
def e4(ep):
    t0, t1 = ep["t_inicio"] - 60, t_fin_eval(ep) + 90
    tx = [c for c in ep.get("control", []) if t0 <= c["t"] <= t1]
    if not tx:
        return {"resultado": "fallo_experimento", "motivo": "sin transacciones de control en la ventana"}
    malas = [c for c in tx if not c["ok"] and c.get("atribuible")]
    if malas:
        return {"resultado": "fallo", "motivo": "%d fallo(s) atribuibles a la restricción (P4)" % len(malas), "n": len(tx)}
    return {"resultado": "cumple", "motivo": "0 fallos atribuibles", "n": len(tx)}


# ---------------------------------------------------------------- E5
def e5(ep, r2):
    if ep.get("accion_prevista") is None or r2["resultado"] in ("fallo_experimento",):
        return {"resultado": "no_aplica" if ep.get("accion_prevista") is None else "fallo_experimento",
                "motivo": "sin punto de aplicación" if ep.get("accion_prevista") is None else r2["motivo"]}
    if r2["resultado"] == "fallo" and "t_apl_sup" not in r2:
        return {"resultado": "no_aplica", "motivo": "no hubo regla que retirar"}
    s = SET_DE[ep["accion_prevista"]]
    t_fin, tsig = t_fin_eval(ep), ep.get("t_siguiente")
    lect = [x for x in ep.get("lecturas_set", []) if x["t"] >= t_fin and (tsig is None or x["t"] <= tsig)]
    if not lect:
        return {"resultado": "indeterminado", "motivo": "sin lectura del set entre el fin y el siguiente episodio"}
    ultima = max(lect, key=lambda x: x["t"])
    via = via_de_retirada(ep, r2)
    if ep["origen"] in ultima.get(s, []):
        return {"resultado": "fallo", "motivo": "el origen sigue en el set en la última lectura", "t": ultima["t"], "via": via}
    return {"resultado": "cumple", "motivo": "origen ausente del set", "t": ultima["t"], "via": via}


def via_de_retirada(ep, r2):
    """Se publican por separado: `retirada_explicita` (la puerta D5 hizo `retirar_origen` mientras la regla seguía vigente:
    d5_retirada_en < hasta) y `caducidad_natural` (la regla expiró sola antes de cualquier retirada de D5). Nunca se mezclan."""
    t_d5, hasta = ep.get("d5_retirada_en"), r2.get("hasta")
    if t_d5 is not None and (hasta is None or t_d5 < hasta):
        return "retirada_explicita"
    return "caducidad_natural"


# ---------------------------------------------------------------- conjunto
def clopper_pearson(k, n, alfa=0.05):
    if n == 0:
        return (0.0, 1.0)

    def cdf_ge(p, kk):  # P(X >= kk)
        return sum(math.comb(n, i) * p ** i * (1 - p) ** (n - i) for i in range(kk, n + 1))

    def biseca(f, objetivo):
        lo, hi = 0.0, 1.0
        for _ in range(80):
            mid = (lo + hi) / 2
            if f(mid) < objetivo:
                lo = mid
            else:
                hi = mid
        return (lo + hi) / 2
    inf = 0.0 if k == 0 else biseca(lambda p: cdf_ge(p, k), alfa / 2)
    sup = 1.0 if k == n else biseca(lambda p: cdf_ge(p, k + 1), 1 - alfa / 2)
    return (inf, sup)


def evaluar(ep):
    r2 = e2(ep)
    r = {"episodio_id": ep["episodio_id"], "escenario": ep["escenario"], "E2": r2, "E3": e3(ep, r2),
         "E4": e4(ep), "E5": e5(ep, r2)}
    if "t_apl_sup" in r2:
        r["metricas"] = {"t_apl_menos_t_inicio": r2["t_apl_sup"] - ep["t_inicio"], "margen": r2["margen_s"],
                         "t_apl_menos_t_det": (r2["t_apl_sup"] - ep["t_det"]) if ep.get("t_det") is not None else None,
                         "t_efecto_menos_t_inicio": (r["E3"]["t_efecto"] - ep["t_inicio"]) if "t_efecto" in r["E3"] else None}
    return r


def resumen(datos):
    eps = datos["episodios"]
    adm = [e for e in eps if not e.get("excluido")]
    res = [evaluar(e) for e in adm]
    cuenta = {"planificados": datos.get("planificados", len(eps)), "ejecutados": len(eps), "admitidos": len(adm),
              "excluidos": [{"episodio_id": e["episodio_id"], "motivo": e["excluido"]} for e in eps if e.get("excluido")]}
    tabla = {}
    for r in res:
        for c in ("E2", "E3", "E4", "E5"):
            t = tabla.setdefault(r["escenario"], {}).setdefault(c, {})
            t[r[c]["resultado"]] = t.get(r[c]["resultado"], 0) + 1
    e5_via = {}
    for r in res:
        if r["E5"].get("via"):
            t = e5_via.setdefault(r["E5"]["via"], {})
            t[r["E5"]["resultado"]] = t.get(r["E5"]["resultado"], 0) + 1
    cp = {}
    for esc, cs in tabla.items():
        for c, d in cs.items():
            n = sum(v for k, v in d.items() if k != "no_aplica")
            if n:
                cp[f"{esc}/{c}"] = {"cumple": d.get("cumple", 0), "n": n,
                                    "cp95": clopper_pearson(d.get("cumple", 0), n)}
    return {"contabilidad": cuenta, "episodios": res, "tabla": tabla, "e5_por_via": e5_via, "clopper_pearson": cp}


if __name__ == "__main__":
    json.dump(resumen(json.load(open(sys.argv[1], encoding="utf-8"))), sys.stdout, indent=1, ensure_ascii=False)
