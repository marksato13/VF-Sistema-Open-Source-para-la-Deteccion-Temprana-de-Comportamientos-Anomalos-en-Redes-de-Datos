#!/usr/bin/env python3
"""LADO SENSOR1 del transporte de la limpieza D5 sin reinicio (propuesta de banco; no instalada). Corre como el usuario del publicador (`m4rk` en el Sensor1).

Se invoca SOLO por SSH con una clave dedicada del bastión cuyo `authorized_keys` fija el comando (no hay shell):
  command="/usr/bin/python3 -I /home/m4rk/cf-b/herramientas/sensor_control_d5.py --base /home/m4rk/feed-v2/d5/control --feed /home/m4rk/feed-v2/feed.json
           --estado /home/m4rk/feed-v2/estado.json --traza /home/m4rk/feed-v2/traza.jsonl --auditoria /home/m4rk/feed-v2/d5/auditoria/d5-auditoria.jsonl --ssh-original",
  restrict ssh-ed25519 AAAA… cf-bastion-d5
Las rutas las fija el comando forzado: el cliente NO puede cambiarlas. El cliente solo puede pedir (lista blanca, ver `parsear`):
  solicitar --id <32 hex> --origen 10.10.20.30   escribe el control (atómico) y un registro `solicitudes/<id>.json`; NO espera. Idempotente por id.
  resultado --id <32 hex>                         consulta SOLO lectura: acuse | rechazado | pendiente | sin_acuse(+categoría) | desconocida
  cancelar  --id <32 hex>                         retira el control SOLO si sigue sin consumir y es de ese id
  feed --desde <epoch>                            lectura del feed (como `sensor_feed` de d5_episodio)
Quién puede solicitar y consultar: quien posea esa clave (el bastión, cuenta `gadmin`); el id lo genera el cliente y se conserva entre la solicitud y la consulta.
Nunca reinicia nada ni emite una solicitud por su cuenta."""
import argparse
import fcntl
import json
import os
import re
import shlex
import sys
import time

sys.dont_write_bytecode = True
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

ORIGEN = "10.10.20.30"
ID_RE = re.compile(r"^[0-9a-f]{32}$")
FLOAT_RE = re.compile(r"^[0-9]{1,12}(\.[0-9]{1,9})?$")


def _escribir(ruta, obj):
    tmp = ruta + ".sc.tmp"
    with open(tmp, "w", encoding="utf-8") as fh:
        fh.write(json.dumps(obj, sort_keys=True))
        fh.flush()
        os.fsync(fh.fileno())
    os.replace(tmp, ruta)


def _leer(ruta):
    try:
        with open(ruta, encoding="utf-8") as fh:
            x = json.load(fh)
        return x if isinstance(x, dict) else None
    except (OSError, ValueError):
        return None


class Cfg:
    def __init__(self, base, feed, estado, traza, auditoria):
        self.base, self.feed, self.estado, self.traza, self.auditoria = base, feed, estado, traza, auditoria
        self.control = os.path.join(base, "control.json")
        self.sol = os.path.join(base, "solicitudes")


class _Cerrojo:
    def __init__(self, cfg):
        os.makedirs(cfg.sol, exist_ok=True)
        self.fh = open(os.path.join(cfg.base, "lock"), "a")

    def __enter__(self):
        fcntl.flock(self.fh, fcntl.LOCK_EX)

    def __exit__(self, *a):
        self.fh.close()


def solicitar(cfg, id_, origen, ahora=time.time):
    if not ID_RE.match(id_ or "") or origen != ORIGEN:
        return {"ok": False, "estado": "rechazada", "motivo": "id u origen no válidos"}
    with _Cerrojo(cfg):
        reg = os.path.join(cfg.sol, id_ + ".json")
        if os.path.exists(reg):
            return {"ok": True, "estado": "ya_recibida", "id": id_}          # idempotente: no se escribe otro control
        if os.path.exists(cfg.control):
            return {"ok": False, "estado": "pendiente_previa", "id": id_}
        _escribir(reg, {"id": id_, "origen": origen, "recibida_en": ahora()})   # primero el registro: sobrevive a reinicios y a cortes
        _escribir(cfg.control, {"accion": "reset_origen", "origen": origen, "id": id_})
    return {"ok": True, "estado": "recibida", "id": id_}


def resultado(cfg, id_, ahora=time.time):
    if not ID_RE.match(id_ or ""):
        return {"ok": False, "estado": "rechazada", "motivo": "id no válido"}
    reg = _leer(os.path.join(cfg.sol, id_ + ".json"))
    if reg is None:
        return {"ok": True, "estado": "desconocida", "id": id_}
    ack = _leer(cfg.control + ".ack")
    if ack and ack.get("id") == id_:
        if ack.get("ok"):
            return {"ok": True, "estado": "acuse", "id": id_, "secuencia": ack.get("secuencia"), "quitado": ack.get("quitado"), "duplicada": bool(ack.get("duplicada"))}
        return {"ok": True, "estado": "rechazado", "id": id_, "error": ack.get("error")}
    ctl = _leer(cfg.control)
    if ctl and ctl.get("id") == id_:
        return {"ok": True, "estado": "pendiente", "id": id_}
    if reg.get("cancelada_en"):
        return {"ok": True, "estado": "sin_acuse", "id": id_, "categoria": "no_consumida", "determinada": True, "publicacion": "no_aplica", "secuencia": None}
    import adaptador_banco_rot as abr
    d = abr.diagnosticar_rot(os.path.join(cfg.base, "_no_existe"), id_, ORIGEN, cfg.feed, cfg.estado, cfg.traza, cfg.auditoria)
    return {"ok": True, "estado": "sin_acuse", "id": id_, "categoria": d["categoria"], "determinada": d["determinada"], "publicacion": d["publicacion"],
            "secuencia": d["secuencia_publicada"], "trazabilidad": d["trazabilidad"], "motivo": d.get("motivo"), "auditoria_del_id": [{k: v for k, v in x.items() if k != "_gen"} for x in d["auditoria_del_id"]]}


def cancelar(cfg, id_, ahora=time.time):
    if not ID_RE.match(id_ or ""):
        return {"ok": False, "estado": "rechazada", "motivo": "id no válido"}
    with _Cerrojo(cfg):
        regp = os.path.join(cfg.sol, id_ + ".json")
        reg = _leer(regp)
        if reg is None:
            return {"ok": True, "estado": "desconocida", "id": id_}
        ctl = _leer(cfg.control)
        if ctl and ctl.get("id") == id_:
            try:
                os.unlink(cfg.control)
            except FileNotFoundError:
                return {"ok": True, "estado": "ya_consumida", "id": id_}
            reg["cancelada_en"] = ahora()
            _escribir(regp, reg)
            return {"ok": True, "estado": "cancelada", "id": id_}
    return {"ok": True, "estado": "ya_consumida", "id": id_}


def feed(cfg, desde, ahora=time.time):
    try:
        obj = json.load(open(cfg.feed, encoding="utf-8"))
        gen, exp, ent = float(obj["generado"]), float(obj["expira"]), list(obj["entradas"])
    except (OSError, ValueError, KeyError, TypeError):
        return {"ok": False, "rc": 2, "motivo": "feed ilegible"}
    propias = [e.get("id") or e.get("accion") for e in ent if isinstance(e, dict) and e.get("ip") == ORIGEN]
    return {"ok": True, "rc": 0, "secuencia": obj.get("secuencia"), "generado": gen, "fresco": gen > desde, "vigente": exp > ahora(), "entradas_origen": propias, "limpio": not propias}


def parsear(texto):
    """Lista blanca estricta del comando recibido por SSH. Devuelve (nombre, dict) o None."""
    try:
        t = shlex.split(texto or "")
    except ValueError:
        return None
    if not t:
        return None
    n, r = t[0], t[1:]
    if n == "solicitar" and len(r) == 4 and r[0] == "--id" and r[2] == "--origen" and ID_RE.match(r[1]) and r[3] == ORIGEN:
        return n, {"id_": r[1], "origen": r[3]}
    if n in ("resultado", "cancelar") and len(r) == 2 and r[0] == "--id" and ID_RE.match(r[1]):
        return n, {"id_": r[1]}
    if n == "feed" and len(r) == 2 and r[0] == "--desde" and FLOAT_RE.match(r[1]):
        return n, {"desde": float(r[1])}
    return None


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--base", required=True)
    p.add_argument("--feed", required=True)
    p.add_argument("--estado", required=True)
    p.add_argument("--traza", required=True)
    p.add_argument("--auditoria", required=True)
    p.add_argument("--ssh-original", action="store_true")
    p.add_argument("cmd", nargs=argparse.REMAINDER)
    a = p.parse_args(argv)
    cfg = Cfg(a.base, a.feed, a.estado, a.traza, a.auditoria)
    texto = os.environ.get("SSH_ORIGINAL_COMMAND", "") if a.ssh_original else " ".join(shlex.quote(x) for x in a.cmd)
    pa = parsear(texto)
    if pa is None:
        print(json.dumps({"ok": False, "estado": "rechazada", "motivo": "comando fuera de la lista blanca"}))
        return 2
    nombre, kw = pa
    r = {"solicitar": solicitar, "resultado": resultado, "cancelar": cancelar, "feed": feed}[nombre](cfg, **kw)
    print(json.dumps(r, sort_keys=True))
    return 0


if __name__ == "__main__":
    sys.exit(main())
