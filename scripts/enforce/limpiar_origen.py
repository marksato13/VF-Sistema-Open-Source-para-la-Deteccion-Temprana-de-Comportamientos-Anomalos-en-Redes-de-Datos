#!/usr/bin/env python3
"""Limpieza D5 de UN origen de ensayo (Etapa 2, candidato). Por omision, EN SECO.

Pasos (cada uno deja constancia en el informe JSON):
  1. Respaldo: copia el estado del publicador a ``--respaldo`` con su sha256.
  2. Publicador: quita el origen del estado (formato v1 {ip: escalera} y v2
     {"eventos", "vigentes", "escalada"}), para que el siguiente feed no lo lleve.
  3. Escalada: quita su contador de reincidencia (v1: clave ip; v2: claves
     "ip@destino"), para que el proximo ensayo empiece en nivel 1.
  4. Agentes: peticion ``retirar_origen`` del helper para el perfil dmz (srv-dmz)
     y dns (DC1). En seco solo se escribe la peticion; con ``--helper-orden`` se
     ejecuta (unicamente en el banco aislado).
  5. Comprobacion: relee el estado escrito y, si hay helper, lista los sets: el
     origen no debe aparecer en ninguno.

En seco (sin ``--escribir``) trabaja sobre una COPIA del estado (``--trabajo``) y
nunca toca el original. No hay modo que borre otra IP: la IP se valida y se
rechaza si esta en NUNCA_BLOQUEAR (no es un origen de ensayo).
"""
from __future__ import annotations

import argparse
import hashlib
import ipaddress
import json
import shlex
import shutil
import subprocess
import sys
from pathlib import Path

NUNCA = frozenset({"10.10.10.30", "10.10.60.11", "10.10.30.1", "10.10.40.1", "10.10.60.1",
                   "10.10.20.1", "10.10.10.20", "10.10.10.21"})


def sha(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def quitar(estado: dict, ip: str) -> dict:
    """Quita el origen de un estado v1 o v2. Devuelve lo que quito."""
    quitado = {"v1": [], "eventos": [], "vigentes": [], "escalada": []}
    if ip in estado and isinstance(estado[ip], dict):  # v1: {ip: {bloqueos, ultimo_visto}}
        del estado[ip]
        quitado["v1"].append(ip)
    for k in [k for k, e in estado.get("eventos", {}).items() if e.get("ip") == ip]:
        del estado["eventos"][k]
        quitado["eventos"].append(k)
    for k in [k for k, e in estado.get("vigentes", {}).items() if e.get("ip") == ip]:
        del estado["vigentes"][k]
        quitado["vigentes"].append(k)
    for k in [k for k in estado.get("escalada", {}) if k == ip or k.startswith(ip + "@")]:
        del estado["escalada"][k]
        quitado["escalada"].append(k)
    return quitado


def presente(estado: dict, ip: str) -> bool:
    return (ip in estado or any(e.get("ip") == ip for e in estado.get("eventos", {}).values())
            or any(e.get("ip") == ip for e in estado.get("vigentes", {}).values())
            or any(k == ip or k.startswith(ip + "@") for k in estado.get("escalada", {})))


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--ip", required=True)
    p.add_argument("--estado-publicador", type=Path, required=True)
    p.add_argument("--respaldo", type=Path, required=True, help="directorio del respaldo (se crea)")
    p.add_argument("--trabajo", type=Path, help="copia de trabajo en seco (por omision, en --respaldo)")
    p.add_argument("--escribir", action="store_true", help="modifica el estado ORIGINAL (no en esta etapa)")
    p.add_argument("--helper-orden", action="append", default=[],
                   help="perfil=orden del helper restringido (repetible). En cada host solo existe el "
                        "helper de SU perfil (fijado por /etc/cyberflow/nft-helper.perfil)")
    p.add_argument("--informe", type=Path, required=True)
    a = p.parse_args(argv)
    ordenes = {}
    for x in a.helper_orden:
        perfil, _, orden = x.partition("=")
        if perfil not in ("dmz", "dns") or not orden:
            raise SystemExit("--helper-orden debe ser dmz=<orden> o dns=<orden>")
        ordenes[perfil] = orden
    ip = str(ipaddress.IPv4Address(a.ip))
    if ip in NUNCA:
        raise SystemExit("%s esta en NUNCA_BLOQUEAR: no es un origen de ensayo" % ip)
    inf = {"ip": ip, "modo": "escribir" if a.escribir else "seco", "pasos": {}}

    a.respaldo.mkdir(parents=True, exist_ok=True)
    copia = a.respaldo / (a.estado_publicador.name + ".respaldo")
    shutil.copy2(a.estado_publicador, copia)
    inf["pasos"]["1_respaldo"] = {"origen": str(a.estado_publicador), "copia": str(copia),
                                  "sha256": sha(copia), "igual_al_origen": sha(copia) == sha(a.estado_publicador)}

    destino = a.estado_publicador if a.escribir else (a.trabajo or a.respaldo / (a.estado_publicador.name + ".seco"))
    estado = json.loads(a.estado_publicador.read_text(encoding="utf-8"))
    quitado = quitar(estado, ip)
    destino.write_text(json.dumps(estado, sort_keys=True), encoding="utf-8")
    inf["pasos"]["2_3_publicador_y_escalada"] = {"escrito_en": str(destino), "quitado": quitado}

    peticiones = {perfil: {"perfil": perfil, "operaciones": [{"op": "retirar_origen", "ip": ip}]}
                  for perfil in ("dmz", "dns")}
    agentes = {}
    for perfil, pet in peticiones.items():
        x = {"peticion": pet}
        orden = ordenes.get(perfil)
        if orden:
            r = subprocess.run(shlex.split(orden), input=json.dumps(pet), capture_output=True, text=True)
            x["respuesta"] = json.loads(r.stdout or "{}")
            r = subprocess.run(shlex.split(orden),
                               input=json.dumps({"perfil": perfil, "operaciones": [{"op": "listar"}]}),
                               capture_output=True, text=True)
            est = json.loads(r.stdout or "{}").get("estado", {})
            x["sigue_en_sets"] = [s for s, el in (est.get("sets") or {}).items() if el and ip in el]
        agentes[perfil] = x
    inf["pasos"]["4_agentes"] = agentes

    releido = json.loads(destino.read_text(encoding="utf-8"))
    ok = not presente(releido, ip) and all(not v.get("sigue_en_sets") for v in agentes.values())
    if ordenes:
        ok = ok and all(v.get("respuesta", {}).get("ok") for k, v in agentes.items() if k in ordenes)
    inf["pasos"]["5_comprobacion"] = {"origen_ausente_en_estado": not presente(releido, ip),
                                      "agentes_comprobados": sorted(ordenes), "ok": ok}
    inf["original_intacto"] = a.escribir or sha(a.estado_publicador) == inf["pasos"]["1_respaldo"]["sha256"]
    a.informe.write_text(json.dumps(inf, indent=1, sort_keys=True), encoding="utf-8")
    print(json.dumps({"ok": ok, "modo": inf["modo"], "original_intacto": inf["original_intacto"]}))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
