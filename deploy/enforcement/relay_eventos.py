#!/usr/bin/env python3
"""Rele por eventos del feed firmado (Etapa 2, candidato). NO sustituye a relay-feed.sh.

Corre en el BASTION como proceso continuo. Cada ``--sondeo-segundos`` (1 s) trae
feed.json y feed.sig del sensor y, si la PAREJA cambio, la reenvia a cada destino
(srv-dmz y DC1).

Coherencia feed/firma (correccion de la Etapa 2, punto 2). El publicador renombra
los dos ficheros uno tras otro, asi que una lectura puede caer entre ambos (firma
nueva con feed anterior o al reves). Antes, el rele entregaba esa pareja, apuntaba
el hash del FEED como enviado y, cuando aparecia la firma correcta con el mismo
feed, ya no la entregaba: el destino se quedaba con una pareja invalida hasta la
siguiente publicacion. Ahora:

1. Lectura estable: feed, firma y otra vez feed; si el feed cambio durante la
   lectura -> ``lectura_inestable`` y se reintenta en el siguiente sondeo.
2. Verificacion de la pareja con la clave PUBLICA (el rele sigue sin poder firmar):
   una pareja que no verifica no se entrega ni se marca -> ``pareja_inconsistente``;
   el siguiente sondeo la vuelve a leer y, cuando es coherente, la entrega.
3. Seguimiento por la PAREJA: lo enviado a cada destino se identifica por
   sha256(feed) + sha256(firma); si cambia solo la firma, se reenvia.
4. Entrega en dos fases: ``.feed.sig.tmp`` y ``.feed.json.tmp`` y, solo si los dos
   llegaron, un unico paso remoto que renombra ambos. Una entrega parcial deja en el
   destino la pareja ANTERIOR intacta (coherente) y se reintenta en el siguiente
   sondeo. Un destino ausente se reintenta igual. Tras un reinicio del rele se
   reenvia la pareja actual: el agente la reconoce como ``repetido`` (misma
   secuencia) y no cambia nada.
5. Entregar != aceptar != aplicar: la traza del rele solo dice que los ficheros
   llegaron (``entregado_en``). La aceptacion (firma y contrato) y la aplicacion son
   del agente, que sigue verificando la firma.

Transporte ``ssh`` (por omision): ``ssh -i IDENTIDAD usuario@host <orden>`` con
ControlMaster; en el destino la llave lleva un comando forzado
(``cf-feed-ssh.sh``) que solo admite estas ordenes. Transporte ``local`` (pruebas).

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

sys.path.insert(0, str(Path(__file__).resolve().parent))
try:
    import feed  # co-desplegado junto al rele (bastion)
except ImportError:
    sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts" / "engine"))
    import feed

SSH_OPTS = ["-o", "BatchMode=yes", "-o", "ConnectTimeout=5", "-o", "ControlMaster=auto",
            "-o", "ControlPath=~/.ssh/cf-relay-%r@%h:%p", "-o", "ControlPersist=120"]
NOMBRES = ("feed.sig", "feed.json")


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

    def subir(self, destino: dict, nombre: str, datos: bytes) -> str | None:
        d = destino["dir"].rstrip("/")
        r = self._ssh(destino["host"], destino["identidad"], "cat > %s/.%s.tmp" % (d, nombre), datos)
        return None if r.returncode == 0 else (r.stderr.decode(errors="replace").strip()[:160] or "ssh")

    def confirmar(self, destino: dict) -> str | None:
        d = destino["dir"].rstrip("/")
        r = self._ssh(destino["host"], destino["identidad"],
                      "mv -f %s/.feed.sig.tmp %s/feed.sig && mv -f %s/.feed.json.tmp %s/feed.json" % (d, d, d, d))
        return None if r.returncode == 0 else (r.stderr.decode(errors="replace").strip()[:160] or "ssh")


class TransporteLocal:
    def traer(self, origen: dict, nombre: str) -> bytes | None:
        try:
            return (Path(origen["dir"]) / nombre).read_bytes()
        except OSError:
            return None

    def subir(self, destino: dict, nombre: str, datos: bytes) -> str | None:
        try:
            (Path(destino["dir"]) / (".%s.tmp" % nombre)).write_bytes(datos)
            return None
        except OSError as exc:
            return str(exc)[:160]

    def confirmar(self, destino: dict) -> str | None:
        d = Path(destino["dir"])
        try:
            for n in NOMBRES:
                shutil.move(str(d / (".%s.tmp" % n)), str(d / n))
            return None
        except OSError as exc:
            return str(exc)[:160]


def _secuencia(datos: bytes) -> int | None:
    try:
        return int(json.loads(datos)["secuencia"])
    except (ValueError, KeyError, TypeError):
        return None


def verificador(clave_publica: str):
    return lambda datos, firma: feed.verificar(datos, firma, clave_publica)


class Rele:
    def __init__(self, origen: dict, destinos: list[dict], transporte, traza: Path | None,
                 verificar, reloj=time.time) -> None:
        self.origen, self.destinos, self.t, self.traza_ruta, self.reloj = origen, destinos, transporte, traza, reloj
        self.verificar = verificar
        self.entregado: dict[str, str] = {}  # destino -> huella de la PAREJA entregada
        self.ultima_inconsistente: str | None = None

    def traza(self, reg: dict) -> None:
        if self.traza_ruta:
            with self.traza_ruta.open("a", encoding="utf-8") as fh:
                fh.write(json.dumps(reg, sort_keys=True) + "\n")

    def leer_pareja(self) -> tuple[bytes, bytes] | None:
        feed1 = self.t.traer(self.origen, "feed.json")
        firma = self.t.traer(self.origen, "feed.sig")
        feed2 = self.t.traer(self.origen, "feed.json")
        if not feed1 or not firma or not feed2:
            return None
        if feed1 != feed2:
            self.traza({"evento": "lectura_inestable", "t": self.reloj()})
            return None
        return feed1, firma

    def paso(self) -> dict | None:
        """Un sondeo. Devuelve el registro de traza si hubo algo que entregar."""
        par = self.leer_pareja()
        traido = self.reloj()
        if par is None:
            return None
        datos, firma = par
        sha_f, sha_s = hashlib.sha256(datos).hexdigest(), hashlib.sha256(firma).hexdigest()
        huella = sha_f[:16] + ":" + sha_s[:16]
        if not self.verificar(datos, firma):
            if self.ultima_inconsistente != huella:
                self.ultima_inconsistente = huella
                self.traza({"evento": "pareja_inconsistente", "t": traido, "huella": huella,
                            "secuencia_feed": _secuencia(datos)})
            return {"evento": "pareja_inconsistente", "huella": huella}
        self.ultima_inconsistente = None
        pendientes = [d for d in self.destinos if self.entregado.get(d["nombre"]) != huella]
        if not pendientes:
            return None
        reg = {"evento": "reenvio", "secuencia": _secuencia(datos), "sha256_feed": sha_f[:16],
               "huella": huella, "traido_en": traido, "destinos": {}}
        for d in pendientes:
            err = (self.t.subir(d, "feed.sig", firma) or self.t.subir(d, "feed.json", datos)
                   or self.t.confirmar(d))
            if err:
                reg["destinos"][d["nombre"]] = {"error": err, "t": self.reloj()}
            else:
                self.entregado[d["nombre"]] = huella
                reg["destinos"][d["nombre"]] = {"entregado_en": self.reloj()}
        self.traza(reg)
        return reg


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--origen", required=True, help="usuario@host:/dir[,identidad] del sensor")
    p.add_argument("--destino", action="append", required=True)
    p.add_argument("--clave-publica", required=True, help="clave PUBLICA del sensor (verificar la pareja)")
    p.add_argument("--transporte", choices=("ssh", "local"), default="ssh")
    p.add_argument("--traza", type=Path, default=None)
    p.add_argument("--sondeo-segundos", type=float, default=1.0)
    p.add_argument("--max-iteraciones", type=int, default=0)
    a = p.parse_args(argv)
    rele = Rele(parsear_destino("origen=" + a.origen), [parsear_destino(x) for x in a.destino],
                TransporteSSH() if a.transporte == "ssh" else TransporteLocal(), a.traza,
                verificador(a.clave_publica))
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
