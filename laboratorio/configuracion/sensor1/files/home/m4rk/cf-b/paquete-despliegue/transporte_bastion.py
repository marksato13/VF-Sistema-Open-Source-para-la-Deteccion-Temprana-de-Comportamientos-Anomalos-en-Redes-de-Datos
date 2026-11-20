#!/usr/bin/env python3
"""LADO BASTIÓN del transporte de la limpieza D5 sin reinicio (propuesta de banco; no instalada). Solo biblioteca estándar.

`LimpiezaRemota.limpiar(origen)` sustituye a `AdaptadorBancoRot.limpiar` en `RunnersBanco`: mismo contrato de salida, pero la solicitud y la consulta viajan por
SSH al subcomando del Sensor1 (`sensor_control_d5.py`). Reglas:
 - El id lo genera el bastión y se GUARDA (fsync) en `limpieza-pendiente.json` ANTES de pedir nada: la solicitud y la consulta usan siempre ese mismo id.
 - Con un pendiente en disco NUNCA se solicita otra vez: solo se consulta ese id (una nueva invocación, una reconexión o un reinicio del bastión no producen otra limpieza).
 - Resultado incierto (SSH caído, id desconocido para el Sensor1, categoría indeterminada): `ok = False`, `incierto = True`; el pendiente se conserva si no se
   pudo determinar el desenlace; la puerta (`PuertaBanco`) queda bloqueada hasta una decisión manual registrada.
 - Descartar un pendiente (para poder emitir un id nuevo) es una acción manual registrada: `descartar_pendiente(quien, motivo)`; el caso se archiva, no se borra."""
import json
import os
import time
import uuid

ORIGEN = "10.10.20.30"


def _escribir(ruta, obj):
    tmp = ruta + ".tmp"
    with open(tmp, "w", encoding="utf-8") as fh:
        fh.write(json.dumps(obj, sort_keys=True, default=str))
        fh.flush()
        os.fsync(fh.fileno())
    os.replace(tmp, ruta)


class LimpiezaRemota:
    def __init__(self, ssh, estado_dir, esperar_s=20.0, sondeo=0.5, ahora=time.time, dormir=time.sleep, fallos_consulta=3):
        """ssh(args: list[str]) -> dict; debe lanzar OSError/ConnectionError si el transporte falla."""
        self.ssh, self.dir, self.esperar_s, self.sondeo, self.ahora, self.dormir, self.fallos = ssh, estado_dir, esperar_s, sondeo, ahora, dormir, fallos_consulta
        os.makedirs(os.path.join(estado_dir, "limpiezas"), exist_ok=True)
        self.p_pend = os.path.join(estado_dir, "limpieza-pendiente.json")

    # ------------------------------------------------------------ estado local
    def pendiente(self):
        try:
            with open(self.p_pend, encoding="utf-8") as fh:
                return json.load(fh)
        except OSError:
            return None
        except ValueError:
            return {"id": None, "ilegible": True}

    def _log(self, reg):
        with open(os.path.join(self.dir, "limpiezas", "registro.jsonl"), "a", encoding="utf-8") as fh:
            fh.write(json.dumps(dict(reg, t=self.ahora()), sort_keys=True, default=str) + "\n")

    def _archivar(self, id_, resultado):
        _escribir(os.path.join(self.dir, "limpiezas", "%s.json" % id_), {"id": id_, "resultado": resultado, "pendiente": self.pendiente()})
        if os.path.exists(self.p_pend):
            os.unlink(self.p_pend)

    def descartar_pendiente(self, quien, motivo):
        if not str(quien).strip() or not str(motivo).strip():
            raise ValueError("descartar un pendiente requiere quién y por qué")
        p = self.pendiente()
        if p is None:
            raise ValueError("no hay un pendiente que descartar")
        self._log({"evento": "pendiente_descartado_manual", "por": quien, "motivo": motivo, "id": p.get("id")})
        os.replace(self.p_pend, os.path.join(self.dir, "limpiezas", "descartado-%s-%d.json" % (p.get("id"), int(self.ahora() * 1000))))

    # ------------------------------------------------------------ transporte
    def _cmd(self, args, evid):
        try:
            r = self.ssh(args)
            evid.append({"cmd": args[0], "respuesta": r})
            return r
        except (OSError, ConnectionError) as ex:
            evid.append({"cmd": args[0], "error_transporte": ex.__class__.__name__})
            return None

    def _fallo(self, id_, estado, evid, **kw):
        base = {"ok": False, "rc": kw.pop("rc", 6), "estado": estado, "id": id_, "categoria": None, "determinada": False, "incierto": True,
                "publicacion": "publicación sin confirmar", "secuencia": None, "traza_auditoria": None}
        base.update(kw)
        ev = os.path.join(self.dir, "limpiezas", "evidencia-%s.json" % id_)
        n = 1
        while os.path.exists(ev):                                                         # la evidencia no se sobrescribe
            n += 1
            ev = os.path.join(self.dir, "limpiezas", "evidencia-%s.%d.json" % (id_, n))
        _escribir(ev, {"resultado": base, "intercambio": evid})
        base["evidencia"] = ev
        return base

    # ------------------------------------------------------------ flujo
    def limpiar(self, origen):
        evid = []
        p = self.pendiente()
        if p is not None and p.get("id") is None:                                         # pendiente ilegible: no se adivina
            return self._fallo(None, "pendiente_ilegible", evid)
        if p is None:
            id_ = uuid.uuid4().hex
            _escribir(self.p_pend, {"id": id_, "t": self.ahora(), "origen": origen})   # ANTES de la primera orden remota
            self._log({"evento": "solicitud_nueva", "id": id_})
            r = self._cmd(["solicitar", "--id", id_, "--origen", origen], evid)
            if r is not None and not r.get("ok"):                                          # el Sensor1 la rechazó o ya había otra: no se hizo nada
                est = r.get("estado")
                self._archivar(id_, {"estado": est})
                return self._fallo(id_, est, evid, rc=4, determinada=True, incierto=False, publicacion="no_aplica")
        else:
            id_ = p["id"]
            self._log({"evento": "consulta_de_pendiente", "id": id_})                      # una nueva invocación SOLO consulta
        return self._consultar(id_, evid)

    def _consultar(self, id_, evid):
        limite, fallos = self.ahora() + self.esperar_s, 0
        while True:
            r = self._cmd(["resultado", "--id", id_], evid)
            if r is None:
                fallos += 1
                if fallos >= self.fallos or self.ahora() >= limite:
                    self._log({"evento": "incierto_sin_transporte", "id": id_})
                    return self._fallo(id_, "sin_transporte", evid)                         # el pendiente se CONSERVA
                self.dormir(self.sondeo)
                continue
            est = r.get("estado")
            if est == "acuse":
                out = {"ok": True, "rc": 0, "estado": "acuse", "id": id_, "incierto": False, "secuencia": r.get("secuencia"), "quitado": r.get("quitado"), "duplicada": bool(r.get("duplicada"))}
                self._archivar(id_, out)
                return out
            if est == "rechazado":
                self._archivar(id_, r)
                return self._fallo(id_, "rechazado", evid, rc=3, determinada=True, incierto=False, publicacion="no_aplica", error=r.get("error"))
            if est == "desconocida":                                                       # el Sensor1 no la recibió… o no la ha procesado aún: incierto, sin reenviar
                self._log({"evento": "incierto_desconocida", "id": id_})
                return self._fallo(id_, "desconocida_en_sensor", evid)
            if est == "sin_acuse":
                self._archivar(id_, r)
                det = bool(r.get("determinada"))
                return self._fallo(id_, "sin_acuse_procesada" if r.get("categoria") != "no_consumida" else "sin_acuse_no_procesada", evid, categoria=r.get("categoria"),
                                   determinada=det, incierto=not det, publicacion=r.get("publicacion"), secuencia=r.get("secuencia"), rc=6 if r.get("categoria") != "no_consumida" else 5)
            if self.ahora() >= limite:                                                     # sigue «pendiente»: se cancela SOLO ese id
                c = self._cmd(["cancelar", "--id", id_], evid)
                if c is None:
                    return self._fallo(id_, "sin_transporte", evid)
                if c.get("estado") == "cancelada":
                    self._archivar(id_, c)
                    return self._fallo(id_, "sin_acuse_no_procesada", evid, categoria="no_consumida", determinada=True, incierto=False, publicacion="no_aplica", rc=5)
                limite = self.ahora() + 2.0                                                # se consumió justo ahora: una última ronda de consulta
                continue
            self.dormir(self.sondeo)


class SshReal:
    """Transporte real con OpenSSH: una orden por llamada con la clave dedicada, huésped FIJADO (`StrictHostKeyChecking=yes` + `UserKnownHostsFile`), sin agente ni
    otras identidades. El Sensor1 solo acepta la lista blanca. `uid`/`home` solo para pruebas (se ejecuta el cliente como otro usuario)."""

    def __init__(self, destino, clave, timeout=15, puerto=22, known_hosts=None, uid=None, home=None, extra=()):
        self.base = ["ssh", "-i", clave, "-p", str(puerto), "-o", "BatchMode=yes", "-o", "ConnectTimeout=8", "-o", "StrictHostKeyChecking=yes",
                     "-o", "IdentitiesOnly=yes", "-o", "IdentityAgent=none"]
        if known_hosts:
            self.base += ["-o", "UserKnownHostsFile=" + known_hosts, "-o", "GlobalKnownHostsFile=/dev/null"]
        self.base += list(extra) + [destino]
        self.timeout, self.uid, self.home = timeout, uid, home

    def __call__(self, args):
        import shlex
        import subprocess
        kw = {}
        if self.uid is not None:
            kw = {"user": self.uid, "group": self.uid, "env": {"HOME": self.home or "/", "PATH": "/usr/bin:/bin"}}
        try:
            r = subprocess.run(self.base + [" ".join(shlex.quote(a) for a in args)], capture_output=True, text=True, timeout=self.timeout, stdin=subprocess.DEVNULL, **kw)
        except subprocess.TimeoutExpired as ex:
            raise ConnectionError("ssh agotó el tiempo") from ex
        if r.returncode == 255:
            raise ConnectionError("ssh falló: " + (r.stderr or "")[:120])
        try:
            return json.loads(r.stdout)
        except ValueError as ex:
            raise ConnectionError("respuesta ilegible") from ex

def runners_distribuidos(banco, limpieza, ssh, srv_helper, agente_traza, real=True, srv=None):
    """RunnersBanco cuyo `sensor` habla SOLO por `ssh` (limpiar con transporte; `feed` remoto) y cuyo `srv` es el de srv-dmz (sintético en banco)."""
    class RD(banco.RunnersBanco):
        def srv(self, cmd, **kw):                                  # srv-dmz: sintético en banco; en el laboratorio, el runner SSH existente (`orquestar_b.SshRunners.srv`)
            return srv(cmd, **kw) if srv is not None else super().srv(cmd, **kw)

        def sensor(self, cmd, **kw):
            if cmd == "limpiar":
                return banco.limpiar_sin_reinicio(limpieza, kw["origen"], self.real, self.ahora)
            if cmd == "feed":
                try:
                    return ssh(["feed", "--desde", "%.6f" % kw["desde"]])
                except (OSError, ConnectionError):
                    return {"ok": False, "rc": 2, "motivo": "feed inaccesible (sin transporte)"}
            raise ValueError(cmd)
    return RD(limpieza, None, agente_traza, srv_helper, real=real)
