#!/usr/bin/env python3
"""ADAPTADOR DE PRUEBA (solo banco; NO se conecta a d5_episodio.py ni al orquestador de la campaña). Une el cliente del control D5
(d5_control.solicitar_reset) con la evidencia que permite interpretar un resultado sin acuse. Solo biblioteca estándar.

Reglas:
 - UNA solicitud por llamada. Si el acuse falta o es incierto NO se emite otra solicitud (ni con id nuevo): el caso se da por FALLIDO
   (`ok = False`), se clasifica y se CONSERVA la evidencia en `<control>.evidencia-<id>.json` (no se sobrescribe ni se borra).
 - Solo `ok = True` si el publicador acusó con ese id.
 - `diagnosticar` distingue, con evidencia y sin adivinar, si la solicitud original se consumió y qué secuencia se publicó:
     no_consumida              el cliente retiró su propio control (os.unlink tuvo éxito): nadie lo había consumido (determinada)
     consumida_y_publicada     la auditoría del publicador (independiente del acuse) tiene `consumido` y `publicado` con la secuencia (determinada)
     consumida_rechazada       la auditoría registra un rechazo (determinada)
     consumida_sin_publicacion la auditoría tiene `consumido` pero no `publicado`: el estado en memoria pudo cambiar sin republicar (INCIERTA)
     indeterminada             el control ya no está y no hay línea de auditoría con ese id (INCIERTA): puede haberse consumido o no
   Las instantáneas del feed, del estado y de la traza se guardan siempre, pero NO deciden: sin auditoría no se afirma nada."""
import json
import os
import time

import d5_control as cli


def _jsonl(ruta):
    out = []
    try:
        for l in open(ruta, encoding="utf-8", errors="replace"):
            try:
                out.append(json.loads(l))
            except ValueError:
                pass
    except OSError:
        pass
    return out


def _json(ruta):
    try:
        return json.loads(open(ruta, encoding="utf-8").read())
    except (OSError, ValueError):
        return None


def diagnosticar(control, id_, origen, feed, estado, traza, auditoria=None, retiro_del_cliente=False, ahora=time.time):
    r = {"id": id_, "t": ahora(), "control_presente": os.path.exists(control), "auditoria_disponible": bool(auditoria and os.path.exists(auditoria))}
    lin = [x for x in _jsonl(auditoria) if x.get("id") == id_] if auditoria else []
    cons = [x for x in lin if x.get("evento") == "consumido"]
    pub = [x for x in lin if x.get("evento") == "publicado"]
    f, e = _json(feed) or {}, _json(estado) or {}
    r["feed"] = {"secuencia": f.get("secuencia"), "generado": f.get("generado"), "entradas_origen": [x.get("id") for x in f.get("entradas", []) if x.get("ip") == origen]}
    r["estado"] = {"vigentes": [k for k in e.get("vigentes", {}) if k.split("|", 1)[0] == origen],
                   "escalada": [k for k in e.get("escalada", {}) if k.split("@", 1)[0] == origen]}
    r["traza_ultimas"] = [{"secuencia": x.get("secuencia"), "entradas": len(x.get("entradas", [])), "nuevos": len(x.get("nuevos", []))}
                          for x in _jsonl(traza) if x.get("evento") == "publicacion"][-5:]
    r["auditoria_del_id"] = lin
    if r["control_presente"]:
        r.update(categoria="no_consumida", determinada=True, secuencia_publicada=None)
    elif retiro_del_cliente:
        r.update(categoria="no_consumida", determinada=True, secuencia_publicada=None)
    elif cons and not cons[-1].get("ok"):
        r.update(categoria="consumida_rechazada", determinada=True, secuencia_publicada=None)
    elif cons and pub:
        r.update(categoria="consumida_y_publicada", determinada=True, secuencia_publicada=pub[-1].get("secuencia"))
        r["feed_posterior_o_igual"] = (f.get("secuencia") or 0) >= (pub[-1].get("secuencia") or 0)
    elif cons:
        r.update(categoria="consumida_sin_publicacion", determinada=False, secuencia_publicada=None)
    else:
        r.update(categoria="indeterminada", determinada=False, secuencia_publicada=None)
    return r


def _guardar_evidencia(control, id_, contenido):
    base = "%s.evidencia-%s" % (os.fspath(control), id_)
    ruta, n = base + ".json", 1
    while os.path.exists(ruta):                                       # nunca se sobrescribe evidencia
        n += 1
        ruta = "%s.%d.json" % (base, n)
    tmp = ruta + ".tmp"
    with open(tmp, "w", encoding="utf-8") as fh:
        fh.write(json.dumps(contenido, sort_keys=True, indent=1))
        fh.flush()
        os.fsync(fh.fileno())
    os.replace(tmp, ruta)
    return ruta


class AdaptadorBanco:
    def __init__(self, control, feed, estado, traza, auditoria=None, esperar_s=20.0, ahora=time.time, dormir=time.sleep, sondeo=0.05):
        self.control, self.feed, self.estado, self.traza, self.auditoria = control, feed, estado, traza, auditoria
        self.esperar_s, self.ahora, self.dormir, self.sondeo = esperar_s, ahora, dormir, sondeo

    def limpiar(self, origen):
        """Una sola solicitud. Devuelve {ok, rc, estado, categoria?, determinada?, incierto, evidencia?, secuencia?}."""
        r = cli.solicitar_reset(self.control, origen, self.esperar_s, ahora=self.ahora, dormir=self.dormir, sondeo=self.sondeo)
        if r["ok"]:
            return {"ok": True, "rc": 0, "estado": "acuse", "incierto": False, "secuencia": r.get("secuencia"), "duplicada": r.get("duplicada", False),
                    "quitado": r.get("quitado")}
        if r["estado"] == "pendiente_previa":                         # no escribimos nada: no hay id propio que diagnosticar
            return {"ok": False, "rc": r["rc"], "estado": r["estado"], "incierto": False, "evidencia": None}
        d = diagnosticar(self.control, r.get("id"), origen, self.feed, self.estado, self.traza, self.auditoria,
                         retiro_del_cliente=(r["estado"] == "sin_acuse_no_procesada"), ahora=self.ahora)
        ev = _guardar_evidencia(self.control, r.get("id"), {"resultado_cliente": r, "diagnostico": d})
        return {"ok": False, "rc": r["rc"], "estado": r["estado"], "categoria": d["categoria"], "determinada": d["determinada"],
                "incierto": not d["determinada"], "evidencia": ev, "secuencia": d["secuencia_publicada"], "id": r.get("id")}
