#!/usr/bin/env python3
"""PROPUESTA DE BANCO: cliente del canal de control D5 sin reinicio (lado de d5_episodio.py). Solo biblioteca estándar.

solicitar_reset(control, origen, esperar_s): escribe el control de forma atómica, espera el acuse CON SU id y devuelve un dict con
`ok` y `estado`. Solo `ok = True` (estado «acuse») permite que la puerta D5 continúe; cualquier otro estado la FALLA (el episodio espera):
  acuse                 el publicador limpió, persistió y republicó (acuse con secuencia); `duplicada` si ya lo había hecho con ese id
  rechazado             el publicador rechazó el control (origen no permitido, mal formado, ilegible)
  pendiente_previa      ya había un control sin consumir: no se sobrescribe ni se acumula
  sin_acuse_no_procesada  venció el plazo y el control seguía ahí: se retira; el publicador no lo procesó
  sin_acuse_procesada     venció el plazo, el control ya no estaba (consumido) y no hay acuse: estado INCIERTO (no se asume limpio)
Un acuse de OTRO id (antiguo) se ignora siempre."""
import json
import os
import time
import uuid


def _leer_ack(ack, id_):
    try:
        a = json.loads(open(ack, encoding="utf-8").read())
    except (OSError, ValueError):
        return None
    return a if isinstance(a, dict) and a.get("id") == id_ else None


def solicitar_reset(control, origen, esperar_s=20.0, ahora=time.time, dormir=time.sleep, sondeo=0.05, id_=None):
    control, ack = os.fspath(control), os.fspath(control) + ".ack"
    if os.path.exists(control):
        return {"ok": False, "estado": "pendiente_previa", "rc": 4}
    id_ = id_ or uuid.uuid4().hex
    tmp = control + ".cli.tmp"
    with open(tmp, "w", encoding="utf-8") as fh:                       # atómico: el publicador nunca ve un control a medias
        fh.write(json.dumps({"accion": "reset_origen", "origen": origen, "id": id_}))
        fh.flush()
        os.fsync(fh.fileno())
    os.replace(tmp, control)
    limite = ahora() + esperar_s
    while True:
        a = _leer_ack(ack, id_)
        if a is not None:
            if a.get("ok"):
                return {"ok": True, "estado": "acuse", "id": id_, "rc": 0, "secuencia": a.get("secuencia"),
                        "quitado": a.get("quitado"), "duplicada": bool(a.get("duplicada"))}
            return {"ok": False, "estado": "rechazado", "id": id_, "rc": 3, "error": a.get("error")}
        if ahora() >= limite:
            break
        dormir(sondeo)
    try:
        os.unlink(control)                                             # nadie lo consumió: se retira para que no actúe más tarde
        return {"ok": False, "estado": "sin_acuse_no_procesada", "id": id_, "rc": 5}
    except FileNotFoundError:
        pass
    dormir(sondeo * 4)                                                 # consumido: última oportunidad de ver el acuse
    a = _leer_ack(ack, id_)
    if a is not None and a.get("ok"):
        return {"ok": True, "estado": "acuse", "id": id_, "rc": 0, "secuencia": a.get("secuencia"), "quitado": a.get("quitado"),
                "duplicada": bool(a.get("duplicada"))}
    return {"ok": False, "estado": "sin_acuse_procesada", "id": id_, "rc": 6}
