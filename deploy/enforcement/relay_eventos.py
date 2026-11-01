#!/usr/bin/env python3
"""Rele por eventos del feed firmado (Etapa 2, candidato). NO sustituye a relay-feed.sh.

Corre en el BASTION como proceso continuo. Cada ``--sondeo-segundos`` (1 s) trae
feed.json y feed.sig del sensor; si la ``secuencia`` cambio, los reenvia a cada
destino (srv-dmz y DC1) en este orden: FIRMA primero, FEED despues, cada uno a
un nombre temporal y renombrado en el destino (el agente reacciona al cambio de
cualquiera de los dos y una pareja a medias falla la firma: fail-safe).

Sigue siendo un rele TONTO: no verifica la firma ni puede forjarla (la clave
privada esta solo en el sensor; cada agente verifica con la publica). Lee la
secuencia sin confiar en ella, solo para no reenviar lo mismo; si alguien
manipula el fichero en el camino, el agente lo rechaza.

Transporte ``ssh`` (por omision): ``ssh -i IDENTIDAD usuario@host cat`` para traer
y ``ssh ... 'cat > tmp && mv tmp final'`` para entregar, con ControlMaster para no
abrir una conexion por segundo. Transporte ``local`` (pruebas): rutas locales.

Traza (``--traza``, jsonl): una linea por secuencia nueva con traido_en y, por
destino, entregado_en u error. Una entrega fallida se reintenta en el siguiente
sondeo (no se marca la secuencia como entregada a ese destino).

Destinos: ``--destino nombre=usuario@host:/ruta/dir[,identidad]`` (repetible).
"""
from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import subprocess
import sys
import time
from pathlib import Path

SSH_OPTS = ["-o", "BatchMode=yes", "-o", "ConnectTimeout=5", "-o", "ControlMaster=auto",
            "-o", "ControlPath=~/.ssh/cf-relay-%r@%h:%p", "-o", "ControlPersist=120"]


def parsear_destino(texto: str) -> dict:
    nombre, resto = texto.split("=", 1)
    ident = None
    if "," in resto:
        resto, ident = resto.rsplit(",", 1)
    if ":" in resto and not (len(resto) > 1 and resto[1] == ":"):  # usuario@host:/dir (no C:\)
        host, ruta = resto.split(":", 1)
    else:
        host, ruta = None, resto
    return {"nombre": nombre, "host": host, "dir": ruta, "identidad": ident}


class TransporteSSH:
    def _ssh(self, host, ident, remoto, entrada=None):
        orden = ["ssh", *SSH_OPTS] + (["-i", ident] if ident else []) + [host, remoto]
        return subprocess.run(orden, input=entrada, capture_output=True, timeout=15)

    def traer(self, origen: dict, nombre: str) -> bytes | None:
        r = self._ssh(origen["host"], origen["identidad"], "cat %s/%s" % (origen["dir"], nombre))
        return r.stdout if r.returncode == 0 else None

    def entregar(self, destino: dict, nombre: str, datos: bytes) -> str | None:
        d = destino["dir"].rstrip("/")
        r = self._ssh(destino["host"], destino["identidad"],
                      "cat > %s/.%s.tmp && mv -f %s/.%s.tmp %s/%s" % (d, nombre, d, nombre, d, nombre), datos)
        return None if r.returncode == 0 else (r.stderr.decode(errors="replace").strip()[:160] or "ssh")


class TransporteLocal:
    def traer(self, origen: dict, nombre: str) -> bytes | None:
        try:
            return (Path(origen["dir"]) / nombre).read_bytes()
        except OSError:
            return None

    def entregar(self, destino: dict, nombre: str, datos: bytes) -> str | None:
        d = Path(destino["dir"])
        try:
            tmp = d / (".%s.tmp" % nombre)
            tmp.write_bytes(datos)
            shutil.move(str(tmp), str(d / nombre))
            return None
        except OSError as exc:
            return str(exc)[:160]


def _secuencia(datos: bytes) -> int | None:
    try:
        return int(json.loads(datos)["secuencia"])
    except (ValueError, KeyError, TypeError):
        return None


class Rele:
    def __init__(self, origen: dict, destinos: list[dict], transporte, traza: Path | None,
                 reloj=time.time) -> None:
        self.origen, self.destinos, self.t, self.traza_ruta, self.reloj = origen, destinos, transporte, traza, reloj
        self.entregado: dict[str, str] = {}  # destino -> sha del feed entregado

    def traza(self, reg: dict) -> None:
        if self.traza_ruta:
            with self.traza_ruta.open("a", encoding="utf-8") as fh:
                fh.write(json.dumps(reg, sort_keys=True) + "\n")

    def paso(self) -> dict | None:
        """Un sondeo. Devuelve el registro de traza si hubo algo que entregar."""
        feed = self.t.traer(self.origen, "feed.json")
        firma = self.t.traer(self.origen, "feed.sig")
        traido = self.reloj()
        if not feed or not firma:
            return None
        sha = hashlib.sha256(feed).hexdigest()
        pendientes = [d for d in self.destinos if self.entregado.get(d["nombre"]) != sha]
        if not pendientes:
            return None
        reg = {"evento": "reenvio", "secuencia": _secuencia(feed), "sha256_feed": sha[:16],
               "traido_en": traido, "destinos": {}}
        for d in pendientes:
            err = self.t.entregar(d, "feed.sig", firma) or self.t.entregar(d, "feed.json", feed)
            if err:
                reg["destinos"][d["nombre"]] = {"error": err, "t": self.reloj()}
            else:
                self.entregado[d["nombre"]] = sha
                reg["destinos"][d["nombre"]] = {"entregado_en": self.reloj()}
        self.traza(reg)
        return reg


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--origen", required=True, help="usuario@host:/dir[,identidad] del sensor")
    p.add_argument("--destino", action="append", required=True)
    p.add_argument("--transporte", choices=("ssh", "local"), default="ssh")
    p.add_argument("--traza", type=Path, default=None)
    p.add_argument("--sondeo-segundos", type=float, default=1.0)
    p.add_argument("--max-iteraciones", type=int, default=0)
    a = p.parse_args(argv)
    rele = Rele(parsear_destino("origen=" + a.origen), [parsear_destino(x) for x in a.destino],
                TransporteSSH() if a.transporte == "ssh" else TransporteLocal(), a.traza)
    it = 0
    while True:
        try:
            rele.paso()
        except Exception as exc:  # noqa: BLE001 - el rele no muere por un fallo de red
            rele.traza({"evento": "error", "t": time.time(), "detalle": str(exc)[:160]})
        it += 1
        if a.max_iteraciones and it >= a.max_iteraciones:
            return 0
        time.sleep(a.sondeo_segundos)


if __name__ == "__main__":
    sys.exit(main())
