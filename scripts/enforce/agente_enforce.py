#!/usr/bin/env python3
"""Agente de enforcement (corre en cada HOST protegido, no en el sensor).

Modelo un-feed/N-agentes (pull): el host trae el feed FIRMADO que publica el
sensor, verifica la firma (ed25519), y **sincroniza su propio nftables** con las
acciones vigentes. El sensor no tiene credenciales del host. Ver
01-arquitectura/DISENO-ENFORCEMENT.md.

Seguridad:
- **Fail-safe:** si la firma no verifica o el feed no se puede leer, NO se aplica
  nada nuevo (se conservan las reglas ya puestas). Ni se abre ni se cierra de golpe.
- **Nunca-bloquear:** gateways, DNS, sensor y bastión se saltan siempre.
- **Caducidad:** BLOCK entra en un `set` de nftables con `timeout` nativo -> se
  quita solo aunque el agente muera.

Uso:
    agente_enforce.py --feed URL_o_fichero --firma URL_o_fichero \\
        --clave-publica pub.pem [--aplicar]   # sin --aplicar: dry-run
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
try:
    from scripts.engine import feed  # ejecutado desde la raíz del repo
except ImportError:
    import feed  # co-desplegado junto al agente en el host

SET_BLOCK = "cyberflow_bloqueados"
SET_LIMIT = "cyberflow_limitados"
LIMIT_RATE = "100/second"

NUNCA_BLOQUEAR = {
    "10.10.10.30", "10.10.60.11",
    "10.10.30.1", "10.10.40.1", "10.10.60.1", "10.10.20.1",
    "10.10.10.20",
}


# --- Núcleo puro (testeable) ------------------------------------------------

def verificar_feed(datos: bytes, firma: bytes, pub_path: str) -> dict | None:
    """Devuelve el feed si la firma es válida; si no, None (fail-safe)."""
    if not feed.verificar(datos, firma, pub_path):
        return None
    try:
        return json.loads(datos)
    except ValueError:
        return None


def vigentes(feed_obj: dict, ahora: float, nunca: set[str]) -> dict[str, dict]:
    """IPs con acción vigente (hasta > ahora), sin las de nunca-bloquear.

    Devuelve {ip: {"accion", "hasta"}} con la acción MÁS severa por IP.
    """
    sev = {"BLOCK": 2, "LIMIT": 1}
    out: dict[str, dict] = {}
    for e in feed_obj.get("entradas", []):
        ip = e.get("ip")
        if not ip or ip in nunca:
            continue
        if float(e.get("hasta", 0)) <= ahora:
            continue
        accion = e.get("accion")
        if accion not in sev:
            continue
        prev = out.get(ip)
        if prev is None or sev[accion] > sev[prev["accion"]]:
            out[ip] = {"accion": accion, "hasta": int(e["hasta"])}
    return out


def plan_nftables(vig: dict[str, dict], ahora: float,
                  actuales: dict[str, dict[str, float]] | None = None) -> list[list[str]]:
    """Añade acciones sin acortar su caducidad nativa ni vaciar los sets."""
    blocks = {ip: v for ip, v in vig.items() if v["accion"] == "BLOCK"}
    limits = {ip: v for ip, v in vig.items() if v["accion"] == "LIMIT"}
    actuales = actuales or {SET_BLOCK: {}, SET_LIMIT: {}}
    # Tabla PROPIA y AISLADA (`inet cyberflow`): coexiste con el firewall del host
    # sin tocarlo. La cadena tiene `policy accept` -> solo cae lo que esté en los
    # sets; jamás bloquea nada más. Los sets llevan `timeout` nativo (caducidad).
    # Las reglas se recrean; los sets conservan su timeout firmado.
    cmds: list[list[str]] = [
        ["nft", "add", "table", "inet", "cyberflow"],
        ["nft", "add", "set", "inet", "cyberflow", SET_BLOCK,
         "{", "type", "ipv4_addr;", "flags", "timeout;", "}"],
        ["nft", "add", "set", "inet", "cyberflow", SET_LIMIT,
         "{", "type", "ipv4_addr;", "flags", "timeout;", "}"],
        ["nft", "add", "chain", "inet", "cyberflow", "entrada",
         "{", "type", "filter", "hook", "input", "priority", "-10;",
         "policy", "accept;", "}"],
        ["nft", "flush", "chain", "inet", "cyberflow", "entrada"],
        # BLOCK: cae todo el tráfico de esas IPs. LIMIT: cae solo lo que EXCEDE la tasa.
        ["nft", "add", "rule", "inet", "cyberflow", "entrada",
         "ip", "saddr", "@" + SET_BLOCK, "drop"],
        ["nft", "add", "rule", "inet", "cyberflow", "entrada",
         "ip", "saddr", "@" + SET_LIMIT, "limit", "rate", "over", LIMIT_RATE, "drop"],
    ]
    for ip, v in sorted(blocks.items()):
        _plan_elemento(cmds, ip, v, ahora, SET_BLOCK, SET_LIMIT, actuales)
    for ip, v in sorted(limits.items()):
        _plan_elemento(cmds, ip, v, ahora, SET_LIMIT, SET_BLOCK, actuales)
    return cmds


def _plan_elemento(cmds, ip, valor, ahora, destino, opuesto, actuales):
    """Amplía una sanción sin acortarla ni degradar un BLOCK vigente."""
    if destino == SET_LIMIT and ip in actuales.get(SET_BLOCK, {}):
        return
    if ip in actuales.get(opuesto, {}):
        cmds.append(["nft", "delete", "element", "inet", "cyberflow", opuesto,
                     "{", ip, "}"])
    hasta_actual = actuales.get(destino, {}).get(ip)
    if hasta_actual is not None and valor["hasta"] <= hasta_actual + 1:
        return
    if hasta_actual is not None:
        cmds.append(["nft", "delete", "element", "inet", "cyberflow", destino,
                     "{", ip, "}"])
    resto = max(1, int(valor["hasta"] - ahora))
    cmds.append(["nft", "add", "element", "inet", "cyberflow", destino,
                 "{", "%s timeout %ds" % (ip, resto), "}"])


def _elementos_actuales(nombre: str, ahora: float, usar_sudo: bool) -> dict[str, float]:
    orden = (["sudo", "-n"] if usar_sudo else []) + [
        "nft", "-j", "list", "set", "inet", "cyberflow", nombre]
    r = subprocess.run(orden, check=False, capture_output=True, text=True)
    if r.returncode != 0:
        return {}
    try:
        doc = json.loads(r.stdout)
        sets = [x["set"] for x in doc.get("nftables", []) if "set" in x]
        elementos = sets[0].get("elem", []) if sets else []
        return {str(e["elem"]["val"]): ahora + float(e["elem"]["expires"])
                for e in elementos if "elem" in e and "expires" in e["elem"]}
    except (KeyError, TypeError, ValueError):
        return {}


def _lote_nft(cmds: list[list[str]]) -> str:
    return "\n".join(" ".join(c[1:]) for c in cmds) + "\n"


def _ejecutar_lote(cmds, usar_sudo):
    orden = (["sudo", "-n"] if usar_sudo else []) + ["nft", "-f", "-"]
    return subprocess.run(orden, input=_lote_nft(cmds), check=False,
                          capture_output=True, text=True)


# --- I/O (fetch + aplicar) --------------------------------------------------

def _traer(origen: str) -> bytes:
    if origen.startswith(("http://", "https://")):
        with urllib.request.urlopen(origen, timeout=10) as r:  # noqa: S310
            return r.read()
    return Path(origen).read_bytes()


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--feed", required=True, help="URL o fichero del feed")
    p.add_argument("--firma", required=True, help="URL o fichero de la firma")
    p.add_argument("--clave-publica", required=True)
    p.add_argument("--aplicar", action="store_true", help="sin esto: dry-run")
    p.add_argument("--sudo", action="store_true",
                   help="ejecuta cada 'nft' con 'sudo -n' (para el cron de un "
                        "usuario con sudo SIN contrasena solo para nft). Minimo "
                        "privilegio: se eleva el nft, no el proceso entero.")
    a = p.parse_args()

    try:
        datos = _traer(a.feed)
        firma = _traer(a.firma)
    except Exception as exc:  # noqa: BLE001 - fail-safe: no tocar nada
        print(json.dumps({"estado": "sin-feed", "motivo": str(exc)}))
        return 0

    feed_obj = verificar_feed(datos, firma, a.clave_publica)
    if feed_obj is None:
        print(json.dumps({"estado": "firma-invalida", "accion": "no se toca nada"}))
        return 0

    ahora = time.time()
    vig = vigentes(feed_obj, ahora, NUNCA_BLOQUEAR)
    actuales = {nombre: _elementos_actuales(nombre, ahora, a.sudo)
                for nombre in (SET_BLOCK, SET_LIMIT)}
    cmds = plan_nftables(vig, ahora, actuales)

    errores: list[str] = []
    if a.aplicar:
        r = _ejecutar_lote(cmds, a.sudo)
        if r.returncode != 0:
            # Releer si una entrada caducó entre el snapshot y el lote atómico.
            ahora = time.time()
            actuales = {nombre: _elementos_actuales(nombre, ahora, a.sudo)
                        for nombre in (SET_BLOCK, SET_LIMIT)}
            cmds = plan_nftables(vig, ahora, actuales)
            r = _ejecutar_lote(cmds, a.sudo)
        if r.returncode != 0:
            errores.append((r.stderr or r.stdout or "fallo nft").strip()[:160])
    salida = {
        "estado": "aplicado" if a.aplicar else "dry-run",
        "block": sorted(ip for ip, v in vig.items() if v["accion"] == "BLOCK"),
        "limit": sorted(ip for ip, v in vig.items() if v["accion"] == "LIMIT"),
        "comandos": len(cmds),
        "errores": len(errores),
    }
    if errores:
        salida["primer_error"] = errores[0]
    print(json.dumps(salida, sort_keys=True))
    # Codigo != 0 si se pidio aplicar y algun nft fallo: el cron lo deja en el
    # log y un fallo sistematico se nota, en vez de "aplicado" mintiendo.
    return 1 if errores else 0


if __name__ == "__main__":
    raise SystemExit(main())
