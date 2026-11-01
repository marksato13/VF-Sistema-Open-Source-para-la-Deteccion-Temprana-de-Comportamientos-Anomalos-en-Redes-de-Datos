#!/usr/bin/env python3
"""Publicador candidato del feed v2 (Etapa 2). NO sustituye al desplegado (publicar_feed.py).

Diferencias con el publicador desplegado:

1. Politica D3 ``if_senal`` (por omision): una ALERT del modelo (IF) NO restringe;
   se registra como senal aparte (``--senales``) con los alfa que supera. Solo
   restringen los heuristicos. ``--politica actual`` reproduce el mapeo desplegado
   (IF ALERT -> LIMIT) para comparar.
2. Destinos separados: ``dns_entropy`` -> (dc1, alcance dns, su accion); el resto de
   reglas -> (srv-dmz, alcance todo). Usa ``heuristicos`` (todas las reglas que
   disparan) cuando el registro lo trae; si no, ``heuristico`` (la mas severa).
   Una misma IP puede tener a la vez una entrada para cada destino.
3. Sin renovacion por reprocesar: cada accion nace de un ``evento_id`` (decision del
   motor + regla). Su caducidad se calcula UNA vez, desde la hora de la decision
   (``logged_at``), y se memoriza; volver a leer la misma decision no la alarga. Solo
   una decision NUEVA (otra ventana) puede ampliar o escalar la restriccion.
4. Escalera por (ip, destino), no solo por ip.
5. Feed v2 (feed.construir_v2): secuencia creciente, ``expira``, ``destino``,
   ``alcance``, ``id`` y ``evento_id`` firmados.
6. 10.10.10.21 (DC2) en NUNCA_BLOQUEAR: no se restringe, pero sus ventanas se
   siguen evaluando (el motor no lo excluye; la lista solo actua aqui y en el agente).
7. ``--seguir``: modo por eventos. Lee el registro del motor de forma incremental y
   publica en cuanto llega una decision que cambia el feed; ademas republica cada
   ``--refresco`` s para renovar ``expira``. Cada publicacion deja una linea en
   ``--traza`` con los identificadores y tiempos de cada evento nuevo.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path

try:
    from scripts.engine import escalada, feed, heuristicos
except ImportError:  # ejecutado desde scripts/engine/
    import escalada
    import feed
    import heuristicos

NUNCA_BLOQUEAR_V2 = frozenset({
    "10.10.10.30",   # bastion
    "10.10.60.11",   # sensor
    "10.10.30.1", "10.10.40.1", "10.10.60.1", "10.10.20.1",  # gateways VLAN
    "10.10.10.20",   # DC1 (DNS/AD)
    "10.10.10.21",   # DC2 (DNS/AD) -- Etapa 2
})

# Regla -> (destino, alcance). Lo no listado va a srv-dmz con alcance "todo".
DESTINO_DE_REGLA = {"dns_entropy": ("dc1", "dns")}
DESTINO_POR_OMISION = ("srv-dmz", "todo")
_SEV = {"BLOCK": 2, "LIMIT": 1}
# Umbrales alfa del IF (calibracion 2026-10-24, analisis-3b.json "umbrales").
UMBRALES_ALFA = {"0.05": -0.5694578968203694, "0.03": -0.5898535710336618,
                 "0.01": -0.6223889502095352}
RETENCION_EVENTOS_S = 2 * 3600


def acciones_de(d: dict, politica: str = "if_senal") -> list[dict]:
    """Acciones (destino, alcance, accion, regla, motivo) que propone una decision."""
    out: list[dict] = []
    if d.get("event") != "decision":
        return out
    det = str(d.get("detector_name", ""))
    if d.get("decision") == "ALERT":
        if det.endswith("_heuristic"):
            # ALERT de heuristico del propio motor (auth_failure_heuristic): fuerza bruta.
            out.append({"regla": det, "accion": "BLOCK", "motivo": det})
        elif politica == "actual":
            out.append({"regla": "modelo:" + det, "accion": "LIMIT", "motivo": "modelo:" + det})
    lista = d.get("heuristicos")
    if not isinstance(lista, list):
        h = d.get("heuristico")
        lista = [h] if isinstance(h, dict) else []
    for h in lista:
        if isinstance(h, dict) and h.get("accion") in _SEV:
            out.append({"regla": str(h.get("heuristico", "heuristico")), "accion": h["accion"],
                        "motivo": "%s: %s" % (h.get("heuristico", "?"), h.get("motivo", ""))})
    for a in out:
        a["destino"], a["alcance"] = DESTINO_DE_REGLA.get(a["regla"], DESTINO_POR_OMISION)
    return out


def senal_if(d: dict) -> dict | None:
    """Senal del IF de una decision puntuada: score y alfas superados (None si no hay score)."""
    if d.get("event") != "decision" or d.get("score") is None:
        return None
    s = float(d["score"])
    return {"decision_id": d.get("decision_id") or "%s|%s" % (d.get("entity_ip"), d.get("window_end_utc")),
            "ip": d.get("entity_ip"), "window_end_utc": d.get("window_end_utc"), "score": s,
            "alfa_superados": [a for a, u in sorted(UMBRALES_ALFA.items(), reverse=True) if s < u],
            "decision_desplegada": d.get("decision"), "logged_at": d.get("logged_at")}


def _evento_id(d: dict, regla: str) -> str:
    base = d.get("decision_id") or "%s|%s" % (d.get("entity_ip"), d.get("window_end_utc"))
    return "%s|%s" % (base, regla)


def incorporar(decisiones: list[dict], estado: dict, nunca: frozenset | set,
               politica: str = "if_senal", leido_en: float | None = None) -> list[dict]:
    """Incorpora decisiones al estado y devuelve los eventos NUEVOS (para la traza).

    estado = {"eventos": {evento_id: entrada}, "vigentes": {"ip|destino|alcance": entrada},
              "escalada": {...}, "secuencia": int}
    """
    eventos = estado.setdefault("eventos", {})
    vigentes = estado.setdefault("vigentes", {})
    esc = estado.setdefault("escalada", {})
    nuevos = []
    for d in decisiones:
        ip = str(d.get("entity_ip", ""))
        if not ip or ip in nunca:
            continue
        for a in acciones_de(d, politica):
            eid = _evento_id(d, a["regla"])
            if eid in eventos:
                continue  # mismo evento releido: no se renueva nada
            t_ev = float(d.get("logged_at") or d.get("decidido_en") or 0)
            r = escalada.procesar(esc, "%s@%s" % (ip, a["destino"]), a["accion"], t_ev, evento_ts=t_ev)
            entrada = {
                "ip": ip, "destino": a["destino"], "alcance": a["alcance"], "accion": r["accion"],
                "hasta": round(t_ev + r["timeout_s"]), "evento_id": eid,
                "motivo": a["motivo"][:160], "detector": a["regla"], "nivel": r["nivel"],
                "revisar_humano": r["revisar_humano"],
            }
            entrada["id"] = feed.id_entrada(ip, a["destino"], a["alcance"], entrada["accion"], eid)
            eventos[eid] = entrada
            clave = "%s|%s|%s" % (ip, a["destino"], a["alcance"])
            prev = vigentes.get(clave)
            if (prev is None or prev["hasta"] <= t_ev
                    or _SEV[entrada["accion"]] > _SEV[prev["accion"]]
                    or (entrada["accion"] == prev["accion"] and entrada["hasta"] > prev["hasta"])):
                vigentes[clave] = entrada
            nuevos.append({"evento_id": eid, "id": entrada["id"], "ip": ip, "destino": a["destino"],
                           "accion": entrada["accion"], "hasta": entrada["hasta"],
                           "decision_id": d.get("decision_id"), "window_end_utc": d.get("window_end_utc"),
                           "decidido_en": d.get("decidido_en"), "logged_at": d.get("logged_at"),
                           "leido_en": leido_en})
    return nuevos


def entradas_vigentes(estado: dict, ahora: float) -> list[dict]:
    return [e for e in estado.get("vigentes", {}).values() if e["hasta"] > ahora]


def podar(estado: dict, ahora: float) -> None:
    ev = estado.get("eventos", {})
    for k in [k for k, e in ev.items() if e["hasta"] < ahora - RETENCION_EVENTOS_S]:
        del ev[k]
    vig = estado.get("vigentes", {})
    for k in [k for k, e in vig.items() if e["hasta"] <= ahora]:
        del vig[k]
    escalada.podar(estado.get("escalada", {}), ahora)


def publicar(estado: dict, ahora: float, vigencia_s: float, clave_privada: Path,
             salida_feed: Path, salida_firma: Path) -> dict:
    estado["secuencia"] = int(estado.get("secuencia", 0)) + 1
    obj = feed.construir_v2(entradas_vigentes(estado, ahora), estado["secuencia"], ahora,
                            vigencia_s, umbrales=heuristicos.VERSION_UMBRALES)
    datos = feed.serializar(obj)
    firma = feed.firmar(datos, str(clave_privada))
    # Escritura atomica: firma primero, feed despues, cada uno por rename. Un lector
    # que coja feed nuevo con firma vieja (o al reves) falla la verificacion y no
    # aplica nada (fail-safe); en la siguiente lectura ya estan los dos.
    for ruta, contenido in ((salida_firma, firma), (salida_feed, datos)):
        tmp = ruta.with_name(ruta.name + ".tmp")
        tmp.write_bytes(contenido)
        os.replace(tmp, ruta)
    return obj


class LectorRegistro:
    """Lee motor_decision.log de forma incremental (con deteccion de rotacion)."""

    def __init__(self, ruta: Path, desde: float) -> None:
        self.ruta = ruta
        self.offset = 0
        self.inodo = None
        self.desde = desde

    def leer(self) -> list[dict]:
        try:
            st = self.ruta.stat()
        except FileNotFoundError:
            return []
        ino = (st.st_dev, st.st_ino)
        if self.inodo is not None and (ino != self.inodo or st.st_size < self.offset):
            self.offset = 0
        self.inodo = ino
        out = []
        with self.ruta.open("rb") as fh:
            fh.seek(self.offset)
            datos = fh.read()
        corte = datos.rfind(b"\n")
        if corte < 0:
            return []
        self.offset += corte + 1
        for linea in datos[:corte].split(b"\n"):
            try:
                d = json.loads(linea)
            except ValueError:
                continue
            if d.get("event") == "decision" and float(d.get("logged_at", 0)) >= self.desde:
                out.append(d)
        return out


def _guardar_estado(ruta: Path, estado: dict) -> None:
    tmp = ruta.with_name(ruta.name + ".tmp")
    tmp.write_text(json.dumps(estado, sort_keys=True), encoding="utf-8")
    os.replace(tmp, ruta)


def main(argv=None, reloj=time.time, dormir=time.sleep) -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--log", type=Path, required=True, help="motor_decision.log")
    p.add_argument("--estado", type=Path, required=True)
    p.add_argument("--clave-privada", type=Path, required=True)
    p.add_argument("--salida-feed", type=Path, required=True)
    p.add_argument("--salida-firma", type=Path, required=True)
    p.add_argument("--senales", type=Path, default=None, help="jsonl de senales del IF (no restringen)")
    p.add_argument("--traza", type=Path, default=None, help="jsonl de publicaciones (instrumentacion)")
    p.add_argument("--politica", choices=("if_senal", "actual"), default="if_senal")
    p.add_argument("--ventana-segundos", type=int, default=120,
                   help="al arrancar, solo decisiones de los ultimos N s")
    p.add_argument("--vigencia-segundos", type=float, default=60.0, help="expira = generado + N")
    p.add_argument("--seguir", action="store_true", help="modo por eventos (proceso continuo)")
    p.add_argument("--sondeo-segundos", type=float, default=0.25)
    p.add_argument("--refresco-segundos", type=float, default=20.0,
                   help="--seguir: republica aunque no haya cambios, para renovar expira")
    p.add_argument("--max-iteraciones", type=int, default=0, help="pruebas: corta tras N sondeos")
    a = p.parse_args(argv)

    try:
        estado = json.loads(a.estado.read_text(encoding="utf-8"))
        if not isinstance(estado, dict) or "eventos" not in estado:
            estado = {"secuencia": int(estado.get("secuencia", 0)) if isinstance(estado, dict) else 0}
    except (OSError, ValueError):
        estado = {}
    ahora = reloj()
    lector = LectorRegistro(a.log, ahora - a.ventana_segundos)
    ultima_pub = None
    vistos_senal: set[str] = set()
    it = 0
    while True:
        leido_en = reloj()
        decisiones = lector.leer()
        nuevos = incorporar(decisiones, estado, NUNCA_BLOQUEAR_V2, a.politica, leido_en)
        if a.senales is not None:
            with a.senales.open("a", encoding="utf-8") as fh:
                for d in decisiones:
                    s = senal_if(d)
                    if s and s["alfa_superados"] and s["decision_id"] not in vistos_senal:
                        vistos_senal.add(s["decision_id"])
                        s["leido_en"] = leido_en
                        fh.write(json.dumps(s, sort_keys=True) + "\n")
        ahora = reloj()
        podar(estado, ahora)
        toca = (not a.seguir or nuevos or ultima_pub is None
                or ahora - ultima_pub >= a.refresco_segundos)
        if toca:
            obj = publicar(estado, ahora, a.vigencia_segundos, a.clave_privada, a.salida_feed, a.salida_firma)
            publicado_en = reloj()
            ultima_pub = ahora
            _guardar_estado(a.estado, estado)
            reg = {"evento": "publicacion", "secuencia": obj["secuencia"], "generado": obj["generado"],
                   "publicado_en": publicado_en, "expira": obj["expira"], "politica": a.politica,
                   "entradas": [e["id"] for e in obj["entradas"]], "nuevos": nuevos}
            if a.traza is not None:
                with a.traza.open("a", encoding="utf-8") as fh:
                    fh.write(json.dumps(reg, sort_keys=True) + "\n")
            if not a.seguir:
                print(json.dumps({"secuencia": obj["secuencia"], "entradas": len(obj["entradas"]),
                                  "nuevos": len(nuevos)}, sort_keys=True))
                return 0
        it += 1
        if a.max_iteraciones and it >= a.max_iteraciones:
            return 0
        dormir(a.sondeo_segundos)


if __name__ == "__main__":
    sys.exit(main())
