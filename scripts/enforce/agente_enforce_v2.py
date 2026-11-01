#!/usr/bin/env python3
"""Agente de enforcement v2 (Etapa 2, candidato). NO sustituye al desplegado.

Un mismo codigo con dos perfiles:
  --perfil dmz  -> destino "srv-dmz", alcance "todo", tabla inet cyberflow_dmz
  --perfil dns  -> destino "dc1",     alcance "dns",  tabla inet cyberflow_dns

Cadena por feed:
  1. Lee feed y firma; verifica ed25519 (feed.verificar). Firma invalida -> nada.
  2. feed.validar_v2: rechaza version < 2, caducado, del futuro, secuencia anterior;
     misma secuencia = repetido (no hace nada). Por entrada: destino o alcance
     desconocidos o no permitidos, accion, ip, NUNCA_BLOQUEAR, caducidad, id.
     Solo se aplican las entradas de SU destino; las de otro destino se cuentan.
  3. Plan: por ip, la accion mas severa vigente. Nunca acorta una caducidad ya
     aplicada; un LIMIT no degrada un BLOCK vivo; un BLOCK saca al origen de
     limitados. Releer el mismo id no renueva: su `hasta` es fijo.
  4. Aplica con el helper root restringido (cf_nft_helper.py) via sudo: nunca
     ejecuta ``nft -f -`` con texto propio.
  5. Confirma releyendo los sets (aplicacion confirmada) y vigila retiradas
     (el elemento desaparecio) y primer efecto (contador del elemento > 0).

Traza (``--traza``, jsonl): recepcion, rechazo, aplicacion, confirmacion,
retirada, primer_efecto, con ``id``/``evento_id``/``secuencia`` y hora del host.
Estado (``--estado``): ultima secuencia aplicada y lo ya observado.
"""
from __future__ import annotations

import argparse
import json
import os
import shlex
import subprocess
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
try:
    from scripts.engine import feed  # desde la raiz del repo
except ImportError:
    try:
        import feed  # co-desplegado junto al agente
    except ImportError:
        sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "engine"))
        import feed

PERFILES = {"dmz": "srv-dmz", "dns": "dc1"}
NUNCA_BLOQUEAR = frozenset({
    "10.10.10.30", "10.10.60.11", "10.10.30.1", "10.10.40.1", "10.10.60.1",
    "10.10.20.1", "10.10.10.20", "10.10.10.21",
})
SET_DE = {"BLOCK": "bloqueados", "LIMIT": "limitados"}
_SEV = {"BLOCK": 2, "LIMIT": 1}


def deseadas(entradas: list[dict]) -> dict[str, dict]:
    """ip -> entrada mas severa (a igual severidad, la que dura mas)."""
    out: dict[str, dict] = {}
    for e in entradas:
        p = out.get(e["ip"])
        if (p is None or _SEV[e["accion"]] > _SEV[p["accion"]]
                or (e["accion"] == p["accion"] and e["hasta"] > p["hasta"])):
            out[e["ip"]] = e
    return out


def planificar(des: dict[str, dict], actuales: dict[str, dict[str, float]], ahora: float) -> list[dict]:
    """Operaciones del helper. actuales = {set: {ip: hasta_absoluto}}."""
    ops: list[dict] = []
    blo, lim = actuales.get("bloqueados", {}), actuales.get("limitados", {})
    for ip, e in sorted(des.items()):
        destino = SET_DE[e["accion"]]
        if destino == "limitados" and ip in blo:
            continue  # LIMIT no degrada un BLOCK vivo
        if destino == "bloqueados" and ip in lim:
            ops.append({"op": "quitar", "set": "limitados", "ip": ip})
        actual = actuales.get(destino, {}).get(ip)
        if actual is not None and e["hasta"] <= actual + 1:
            continue  # nunca acortar; mismo hasta = nada que hacer
        if actual is not None:
            ops.append({"op": "quitar", "set": destino, "ip": ip})
        ops.append({"op": "anadir", "set": destino, "ip": ip,
                    "timeout": max(1, int(e["hasta"] - ahora))})
    return ops


class Helper:
    def __init__(self, perfil: str, orden: list[str]) -> None:
        self.perfil, self.orden = perfil, orden

    def __call__(self, operaciones: list[dict]) -> dict:
        r = subprocess.run(self.orden, input=json.dumps({"perfil": self.perfil, "operaciones": operaciones}),
                           capture_output=True, text=True, timeout=20)
        try:
            return json.loads(r.stdout)
        except ValueError:
            return {"ok": False, "error": (r.stderr or r.stdout or "sin salida").strip()[:200]}

    def listar(self) -> dict:
        res = self([{"op": "listar"}])
        return res.get("estado") if res.get("ok") else None


def _actuales(estado_nft: dict | None, ahora: float) -> dict[str, dict[str, float]]:
    out: dict[str, dict[str, float]] = {"bloqueados": {}, "limitados": {}}
    for s in out:
        for ip, v in ((estado_nft or {}).get("sets", {}).get(s) or {}).items():
            if v.get("expira_s") is not None:
                out[s][ip] = ahora + float(v["expira_s"])
    return out


class Agente:
    def __init__(self, a: argparse.Namespace, helper=None, reloj=time.time) -> None:
        self.a = a
        self.destino = PERFILES[a.perfil]
        self.helper = helper or Helper(a.perfil, shlex.split(a.helper))
        self.reloj = reloj
        try:
            self.estado = json.loads(a.estado.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            self.estado = {}
        self.estado.setdefault("secuencia", None)
        self.estado.setdefault("aplicadas", {})   # id -> {ip, set, hasta}
        self.estado.setdefault("efecto", {})      # "set|ip" -> primera hora con contador > 0
        self.estado.setdefault("presentes", {})   # set -> [ip] en la ultima observacion
        self.asegurado = False

    def traza(self, evento: str, **datos) -> None:
        reg = {"evento": evento, "t": self.reloj(), "perfil": self.a.perfil, **datos}
        if self.a.traza:
            with self.a.traza.open("a", encoding="utf-8") as fh:
                fh.write(json.dumps(reg, sort_keys=True) + "\n")

    def guardar(self) -> None:
        tmp = self.a.estado.with_name(self.a.estado.name + ".tmp")
        tmp.write_text(json.dumps(self.estado, sort_keys=True), encoding="utf-8")
        os.replace(tmp, self.a.estado)

    def observar(self) -> dict | None:
        """Relee los sets: retiradas y primer efecto. Devuelve el estado nft."""
        est = self.helper.listar()
        if est is None:
            return None
        ahora = self.reloj()
        for s in ("bloqueados", "limitados"):
            elems = (est.get("sets", {}).get(s)) or {}
            antes = set(self.estado["presentes"].get(s, []))
            for ip in sorted(antes - set(elems)):
                self.traza("retirada", set=s, ip=ip)
                self.estado["efecto"].pop("%s|%s" % (s, ip), None)
            for ip, v in elems.items():
                k = "%s|%s" % (s, ip)
                if (v.get("paquetes") or 0) > 0 and k not in self.estado["efecto"]:
                    self.estado["efecto"][k] = ahora
                    self.traza("primer_efecto", set=s, ip=ip, paquetes=v.get("paquetes"),
                               bytes=v.get("bytes"))
            self.estado["presentes"][s] = sorted(elems)
        return est

    def procesar(self, datos: bytes, firma: bytes, mtime: float | None = None) -> dict:
        recibido = self.reloj()
        if not feed.verificar(datos, firma, str(self.a.clave_publica)):
            self.traza("rechazo", motivo="firma_invalida", recibido_en=recibido)
            return {"estado": "rechazado", "motivo": "firma_invalida"}
        try:
            obj = json.loads(datos)
        except ValueError:
            self.traza("rechazo", motivo="json_invalido", recibido_en=recibido)
            return {"estado": "rechazado", "motivo": "json_invalido"}
        v = feed.validar_v2(obj, self.destino, recibido, self.estado["secuencia"], NUNCA_BLOQUEAR)
        self.traza("recepcion", recibido_en=recibido, mtime_feed=mtime, secuencia=obj.get("secuencia")
                   if isinstance(obj, dict) else None, generado=obj.get("generado") if isinstance(obj, dict)
                   else None, estado=v["estado"], motivo=v["motivo"], ajenas=v["ajenas"],
                   rechazadas=v["rechazadas"], ids=[e["id"] for e in v["entradas"]])
        if v["estado"] != "aceptado":
            return {"estado": v["estado"], "motivo": v["motivo"]}
        ahora = self.reloj()
        ops = []
        if not self.asegurado:
            ops.append({"op": "asegurar"})
        # Siempre se relee: tras un reinicio del agente los sets pueden tener elementos
        # (con su caducidad nativa) y `add element` sobre uno existente no la amplia.
        est = self.helper.listar()
        des = deseadas(v["entradas"])
        plan = planificar(des, _actuales(est, ahora), ahora)
        ops += plan
        resultado = {"estado": "aceptado", "secuencia": v["secuencia"], "operaciones": len(plan),
                     "rechazadas": len(v["rechazadas"]), "ajenas": v["ajenas"]}
        if self.a.aplicar and ops:
            r = self.helper(ops)
            if not r.get("ok"):
                self.traza("rechazo", motivo="helper", detalle=r)
                resultado.update(estado="error_aplicacion", detalle=r)
                return resultado  # no se avanza la secuencia: se reintenta con el siguiente feed
            self.asegurado = True
            aplicado = self.reloj()
            nuevos = []
            for o in plan:
                if o["op"] == "anadir":
                    e = des[o["ip"]]
                    self.estado["aplicadas"][e["id"]] = {"ip": e["ip"], "set": o["set"], "hasta": e["hasta"],
                                                         "evento_id": e.get("evento_id")}
                    nuevos.append({"id": e["id"], "evento_id": e.get("evento_id"), "ip": e["ip"],
                                   "set": o["set"], "hasta": e["hasta"], "timeout": o["timeout"]})
            self.traza("aplicacion", secuencia=v["secuencia"], aplicado_en=aplicado, nuevos=nuevos,
                       operaciones=ops)
            est2 = self.observar()
            presentes = {(s, ip) for s in ("bloqueados", "limitados")
                         for ip in ((est2 or {}).get("sets", {}).get(s) or {})}
            self.traza("confirmacion", secuencia=v["secuencia"], confirmado_en=self.reloj(),
                       confirmadas=[n["id"] for n in nuevos if (n["set"], n["ip"]) in presentes],
                       no_confirmadas=[n["id"] for n in nuevos if (n["set"], n["ip"]) not in presentes])
        elif self.a.aplicar:
            self.asegurado = True
        self.estado["secuencia"] = v["secuencia"]
        for k in [k for k, x in self.estado["aplicadas"].items() if x["hasta"] < ahora - 3600]:
            del self.estado["aplicadas"][k]
        self.guardar()
        return resultado


def _leer(ruta: Path) -> bytes:
    return ruta.read_bytes()


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--perfil", choices=sorted(PERFILES), required=True)
    p.add_argument("--feed", type=Path, required=True)
    p.add_argument("--firma", type=Path, required=True)
    p.add_argument("--clave-publica", type=Path, required=True)
    p.add_argument("--estado", type=Path, required=True)
    p.add_argument("--traza", type=Path, default=None)
    p.add_argument("--helper", default="sudo -n /usr/local/sbin/cf-nft-helper",
                   help="orden del helper restringido (sin argumentos para el helper)")
    p.add_argument("--aplicar", action="store_true", help="sin esto: dry-run (no llama al helper para cambiar)")
    p.add_argument("--seguir", action="store_true", help="proceso continuo: reacciona al cambio del feed")
    p.add_argument("--sondeo-segundos", type=float, default=0.5)
    p.add_argument("--observar-segundos", type=float, default=5.0,
                   help="--seguir: cada cuanto relee los sets (retiradas y primer efecto)")
    p.add_argument("--max-iteraciones", type=int, default=0)
    a = p.parse_args(argv)
    ag = Agente(a)
    ultimo_mtime = None
    ultima_obs = 0.0
    it = 0
    while True:
        # Se vigilan los DOS ficheros: si el feed llega antes que su firma, la
        # primera lectura falla (fail-safe) y el cambio de la firma la repite.
        try:
            mt = (a.feed.stat().st_mtime_ns, a.firma.stat().st_mtime_ns)
        except OSError:
            mt = None
        if mt is not None and mt != ultimo_mtime:
            try:
                datos, firma = _leer(a.feed), _leer(a.firma)
            except OSError as exc:
                ag.traza("rechazo", motivo="sin_feed", detalle=str(exc)[:120])
            else:
                ultimo_mtime = mt
                res = ag.procesar(datos, firma, mt[0] / 1e9)
                if not a.seguir:
                    print(json.dumps(res, sort_keys=True))
                    return 0 if res["estado"] in ("aceptado", "repetido") else 1
        elif not a.seguir:
            print(json.dumps({"estado": "sin-feed"}))
            return 0
        if a.seguir and a.aplicar and time.time() - ultima_obs >= a.observar_segundos:
            ultima_obs = time.time()
            if ag.observar() is not None:
                ag.guardar()
        it += 1
        if a.max_iteraciones and it >= a.max_iteraciones:
            return 0
        time.sleep(a.sondeo_segundos)


if __name__ == "__main__":
    sys.exit(main())
