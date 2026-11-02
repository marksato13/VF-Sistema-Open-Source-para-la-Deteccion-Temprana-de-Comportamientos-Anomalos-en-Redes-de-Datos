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
  5. Confirma releyendo los sets (aplicacion confirmada: el elemento esta con SU id)
     y vigila retiradas y contadores.

Instrumentacion separada (Etapa 2, punto 7). Nunca se presenta como mitigacion lo
que solo es coincidencia:
  - ``aplicacion``/``confirmacion``: la regla esta puesta y releida (no dice nada
    del trafico);
  - ``primera_coincidencia`` (solo LIMIT): el origen envio trafico que casa con la
    regla; NO implica descarte;
  - ``primer_descarte``: paquetes descartados por ESA accion (BLOCK: contador del
    elemento; LIMIT: contador por origen de ``descartes_limite``);
  - ``contadores``: deltas por intervalo e ``id`` (coincidencias y descartes), para
    interpretar cada intervalo sin mezclar acciones anteriores (cada ``anadir``
    sustituye el elemento: contadores a cero con el id nuevo);
  - el EFECTO sobre tasa, respuestas o transacciones no lo mide el agente: se mide
    fuera (ensayo aislado o sensor) y se une por ``id``/ip/intervalo.
Los ids viven en el comentario del elemento nft, asi que sobreviven al reinicio del
agente.

Reintento: si el helper falla, la secuencia no avanza y el MISMO feed se reintenta
cada ``--reintento-segundos`` sin esperar a otra publicacion; el timeout se recalcula
desde el ``hasta`` fijo de la entrada, asi que reintentar no amplia la caducidad.

Traza (``--traza``, jsonl): recepcion, rechazo, aplicacion, confirmacion, retirada,
primera_coincidencia, primer_descarte, contadores, reintento, con
``id``/``evento_id``/``secuencia`` y hora del host.
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
        ops.append({"op": "anadir", "set": destino, "ip": ip, "id": e["id"],
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
        self.estado.pop("efecto", None)            # formato anterior (primer_efecto): ya no se usa
        self.estado.setdefault("presentes", {})   # set -> {ip: id} en la ultima observacion
        self.estado.setdefault("intervalos", {})  # id -> {set, ip, coincidencias, descartes, ...}
        self.estado.setdefault("ultimo_limit", {})  # ip -> id del ultimo LIMIT (descartes tras retirarse)
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

    def _intervalo(self, id_: str, s: str, ip: str) -> dict:
        return self.estado["intervalos"].setdefault(id_, {"set": s, "ip": ip, "coincidencias": 0,
                                                          "descartes": 0, "primera_coincidencia": None,
                                                          "primer_descarte": None})

    def observar(self) -> dict | None:
        """Relee los sets: retiradas, coincidencias y descartes por id. Devuelve el estado nft."""
        est = self.helper.listar()
        if est is None:
            return None
        ahora = self.reloj()
        desc = est.get("descartes_limite") or {}
        cambios = []
        for s in ("bloqueados", "limitados"):
            elems = (est.get("sets", {}).get(s)) or {}
            antes = self.estado["presentes"].get(s, {})
            if isinstance(antes, list):  # formato anterior
                antes = {ip: None for ip in antes}
            for ip in sorted(set(antes) - set(elems)):
                self.traza("retirada", set=s, ip=ip, id=antes.get(ip))
            for ip, v in elems.items():
                id_ = v.get("id")
                if not id_:
                    continue  # elemento sin id (no lo puso este agente): no se atribuye
                it = self._intervalo(id_, s, ip)
                n = int(v.get("paquetes") or 0)
                if s == "bloqueados":
                    nuevos_desc = n - it["descartes"]
                    if n > it["descartes"]:
                        if it["primer_descarte"] is None:
                            it["primer_descarte"] = ahora
                            self.traza("primer_descarte", set=s, ip=ip, id=id_, descartes=n)
                        cambios.append({"id": id_, "set": s, "ip": ip, "d_descartes": nuevos_desc,
                                        "descartes": n})
                        it["descartes"] = n
                else:
                    self.estado["ultimo_limit"][ip] = id_
                    if n > it["coincidencias"]:
                        if it["primera_coincidencia"] is None:
                            it["primera_coincidencia"] = ahora
                            self.traza("primera_coincidencia", set=s, ip=ip, id=id_, coincidencias=n,
                                       nota="coincidencia_no_implica_descarte")
                        cambios.append({"id": id_, "set": s, "ip": ip, "d_coincidencias": n - it["coincidencias"],
                                        "coincidencias": n})
                        it["coincidencias"] = n
            self.estado["presentes"][s] = {ip: v.get("id") for ip, v in elems.items()}
        # Descartes del LIMIT por origen: se atribuyen al ultimo id de LIMIT de ese origen
        # (el helper los pone a cero en cada anadir), tambien despues de que caduque.
        for ip, v in desc.items():
            id_ = self.estado["ultimo_limit"].get(ip)
            if not id_:
                continue
            it = self._intervalo(id_, "limitados", ip)
            n = int(v.get("paquetes") or 0)
            if n > it["descartes"]:
                if it["primer_descarte"] is None:
                    it["primer_descarte"] = ahora
                    self.traza("primer_descarte", set="limitados", ip=ip, id=id_, descartes=n)
                cambios.append({"id": id_, "set": "limitados", "ip": ip, "d_descartes": n - it["descartes"],
                                "descartes": n})
                it["descartes"] = n
        if cambios:
            self.traza("contadores", observado_en=ahora, cambios=cambios)
        for k in [k for k, x in self.estado["intervalos"].items()
                  if x.get("primer_descarte") is None and x.get("primera_coincidencia") is None
                  and k not in {i for d in self.estado["presentes"].values() for i in d.values()}
                  and k not in self.estado["ultimo_limit"].values()]:
            del self.estado["intervalos"][k]
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
                return resultado  # no se avanza la secuencia: main() reintenta el MISMO feed
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
            presentes = {(s, ip, (x or {}).get("id")) for s in ("bloqueados", "limitados")
                         for ip, x in (((est2 or {}).get("sets", {}).get(s)) or {}).items()}
            self.traza("confirmacion", secuencia=v["secuencia"], confirmado_en=self.reloj(),
                       confirmadas=[n["id"] for n in nuevos if (n["set"], n["ip"], n["id"]) in presentes],
                       no_confirmadas=[n["id"] for n in nuevos if (n["set"], n["ip"], n["id"]) not in presentes])
        elif self.a.aplicar:
            self.asegurado = True
        self.estado["secuencia"] = v["secuencia"]
        for k in [k for k, x in self.estado["aplicadas"].items() if x["hasta"] < ahora - 3600]:
            del self.estado["aplicadas"][k]
        self.guardar()
        return resultado


def _leer(ruta: Path) -> bytes:
    return ruta.read_bytes()


def _huella(ruta: Path) -> tuple:
    st = ruta.stat()
    return (st.st_ino, st.st_mtime_ns, st.st_size)


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
    p.add_argument("--reintento-segundos", type=float, default=5.0,
                   help="--seguir: reintento del MISMO feed si el helper fallo (sin otra publicacion)")
    p.add_argument("--max-iteraciones", type=int, default=0)
    a = p.parse_args(argv)
    ag = Agente(a)
    ultima_huella = None
    ultima_obs = 0.0
    reintento = None  # (datos, firma, mtime, cuando)
    it = 0
    while True:
        # Se vigilan los DOS ficheros (inodo, mtime, tamano): el rele los renombra uno
        # tras otro; si se lee una pareja a medias la firma falla (fail-safe) y el
        # renombrado del otro cambia la huella y repite la lectura.
        try:
            mt = (_huella(a.feed), _huella(a.firma))
        except OSError:
            mt = None
        if mt is not None and mt != ultima_huella:
            try:
                datos, firma = _leer(a.feed), _leer(a.firma)
            except OSError as exc:
                ag.traza("rechazo", motivo="sin_feed", detalle=str(exc)[:120])
            else:
                ultima_huella = mt
                reintento = None
                res = ag.procesar(datos, firma, mt[0][1] / 1e9)
                if res["estado"] == "error_aplicacion":
                    reintento = (datos, firma, mt[0][1] / 1e9, time.time() + a.reintento_segundos)
                if not a.seguir:
                    print(json.dumps(res, sort_keys=True))
                    return 0 if res["estado"] in ("aceptado", "repetido") else 1
        elif reintento is not None and time.time() >= reintento[3]:
            ag.traza("reintento", motivo="helper")
            res = ag.procesar(reintento[0], reintento[1], reintento[2])
            reintento = ((reintento[0], reintento[1], reintento[2], time.time() + a.reintento_segundos)
                         if res["estado"] == "error_aplicacion" else None)
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
