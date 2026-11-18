#!/usr/bin/env python3
"""Cierre de la Etapa 3, hallazgo 2: qué cambia al exigir la vista HTTP a auth_failure_heuristic.

Uso:
  cambios_auth_failure.py LOG_REF LOG_NUEVO PUB_REF.py PUB_NUEVO.py SALIDA.json

- Clave a clave (entidad, ventana): decisiones finales que cambian entre el registro de
  referencia (motor 585da7b) y el nuevo, con la clasificación pura del IF (score frente al
  umbral, igual en los dos si el IF no cambió), la señal histórica y la vista HTTP.
- Recorrido hasta el feed: cada registro se pasa, en orden de logged_at, por SU publicador
  (referencia: publicar_feed_v2 de 585da7b; nuevo: el corregido) con la política if_senal, y
  se cuentan los eventos (nueva, renovada, escalada, mantenida, rechazada...) por regla.
"""
from __future__ import annotations

import collections
import importlib.util
import json
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RAIZ / "scripts" / "engine"))


def cargar(log: Path) -> dict:
    dec = {}
    with log.open(encoding="utf-8") as fh:
        for l in fh:
            r = json.loads(l)
            if r.get("event") == "decision":
                dec[(r["entity_ip"], r["window_end_utc"])] = r
    return dec


def publicador(ruta: Path, nombre: str):
    spec = importlib.util.spec_from_file_location(nombre, ruta)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def recorrer(pub, dec: dict) -> dict:
    st: dict = {}
    eventos = []
    for d in sorted(dec.values(), key=lambda r: (r.get("logged_at") or 0, r["entity_ip"])):
        eventos += pub.incorporar([d], st, pub.NUNCA_BLOQUEAR_V2, "if_senal", d.get("logged_at"))
    por = collections.Counter((e["tipo"], e["regla"]) for e in eventos)
    restr = [e for e in eventos if e["tipo"] in ("nueva", "renovada", "escalada")]
    return {"eventos_por_tipo_y_regla": {"%s|%s" % k: n for k, n in sorted(por.items())},
            "restricciones_creadas_o_renovadas": len(restr),
            "por_regla": dict(collections.Counter(e["regla"] for e in restr)),
            "auth_failure_ips": dict(collections.Counter(e["ip"] for e in restr
                                                         if e["regla"] == "auth_failure_heuristic")),
            "auth_failure_eventos": [{k: e.get(k) for k in ("ip", "tipo", "window_end_utc", "accion", "hasta")}
                                     for e in restr if e["regla"] == "auth_failure_heuristic"]}


def main(argv=None) -> int:
    a = argv or sys.argv[1:]
    ref, nuevo = cargar(Path(a[0])), cargar(Path(a[1]))
    pub_ref, pub_nuevo = publicador(Path(a[2]), "pub_ref"), publicador(Path(a[3]), "pub_nuevo")
    comunes = sorted(set(ref) & set(nuevo))
    cambios = []
    for k in comunes:
        r, n = ref[k], nuevo[k]
        if (r["decision"], r["detector_name"]) == (n["decision"], n["detector_name"]):
            continue
        thr = r.get("threshold")
        cambios.append({
            "entidad": k[0], "ventana": k[1],
            "referencia": [r["decision"], r["detector_name"]], "nuevo": [n["decision"], n["detector_name"]],
            "score_ref": r["score"], "score_nuevo": n["score"],
            "if_puro": None if r["score"] is None else ("ALERT" if r["score"] < thr else "PERMIT"),
            "decision_if_nuevo": n.get("decision_if"), "auth_failure": n.get("auth_failure"),
            "http_vista": n.get("http_vista")})
    trans = collections.Counter("%s/%s -> %s/%s" % (*c["referencia"], *c["nuevo"]) for c in cambios)
    ref_auth = [r for r in ref.values() if r["detector_name"] == "auth_failure_heuristic"]
    sin_valida = [r for r in ref_auth
                  if not r.get("http_vista") or r["http_vista"].get("httph_peticiones_60s", 0) < 5
                  or r["http_vista"].get("httph_fallo_auth_ratio_60s", 0) < 0.8]
    res = {
        "registros": {"referencia": str(a[0]), "nuevo": str(a[1])},
        "decisiones": {"referencia": len(ref), "nuevo": len(nuevo), "comunes": len(comunes)},
        "scores_distintos": sum(1 for k in comunes if ref[k]["score"] != nuevo[k]["score"]),
        "cambios_de_decision_final": len(cambios),
        "transiciones": dict(trans),
        "cambios_por_entidad": dict(collections.Counter(c["entidad"] for c in cambios)),
        "cambios_con_if_puro_distinto_de_la_final_nueva": sum(
            1 for c in cambios if c["if_puro"] is not None and c["if_puro"] != c["nuevo"][0]),
        "referencia_auth_failure": len(ref_auth),
        "referencia_auth_failure_sin_evidencia_valida": len(sin_valida),
        "nuevo_auth_failure": sum(1 for r in nuevo.values() if r["detector_name"] == "auth_failure_heuristic"),
        "nuevo_senal_historica_no_autorizada": sum(
            1 for r in nuevo.values() if (r.get("auth_failure") or {}).get("historico")
            and not r["auth_failure"]["autoriza"]),
        "feed": {"referencia_585da7b": recorrer(pub_ref, ref), "nuevo": recorrer(pub_nuevo, nuevo)},
        "cambios": cambios,
    }
    Path(a[4]).write_text(json.dumps(res, indent=1, ensure_ascii=False), encoding="utf-8")
    print(json.dumps({k: v for k, v in res.items() if k not in ("cambios",)}, indent=1, ensure_ascii=False)[:6000])
    return 0


if __name__ == "__main__":
    sys.exit(main())
