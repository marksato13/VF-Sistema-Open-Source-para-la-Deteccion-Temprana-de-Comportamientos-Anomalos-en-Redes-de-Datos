"""Acuse de aplicacion: lo que el host protegido tiene REALMENTE en su firewall.

Se ejecuta en el host (srv-dmz) y escribe un JSON por la salida estandar. El
relay del bastion lo trae cada 10 s y lo deja en el sensor, en
~/feed/acuses/<host>.json, para que el panel muestre el paso 5 («Aplicacion en
el host») con datos del propio host y no con una suposicion.

Solo lectura: lista la tabla `inet cyberflow` con el ayudante
/usr/local/sbin/cf-nft-mostrar (sudo -n, ya instalado para el agente), lee
~/enforce/liberadas.json y la ultima pasada del agente en el journal. Guarda
~/enforce/acuse-historial.json para registrar las transiciones (aplicada,
cambiada, retirada) con la hora en que el host las vio por primera vez.

El acuse no va firmado: es un informe del host, no una orden. El panel lo
presenta como tal («según el host»).
"""
from __future__ import annotations

import json
import os
import socket
import subprocess
import sys
import time
from pathlib import Path

ENFORCE = Path.home() / "enforce"
HISTORIAL = ENFORCE / "acuse-historial.json"
MAX_EVENTOS = 300
SETS = {"cyberflow_bloqueados": "BLOCK", "cyberflow_limitados": "LIMIT"}


def leer_nft(cmd=("sudo", "-n", "/usr/local/sbin/cf-nft-mostrar")) -> tuple[dict, str | None]:
    """{ip: {"accion", "expira_en"}} de los sets de la tabla cyberflow."""
    try:
        r = subprocess.run(list(cmd), capture_output=True, text=True, timeout=10)
        doc = json.loads(r.stdout or "{}").get("nftables", [])
    except (OSError, ValueError, subprocess.TimeoutExpired) as e:
        return {}, "nft: %s" % type(e).__name__
    return reglas_de_nft(doc), None


def reglas_de_nft(doc: list) -> dict:
    out = {}
    for x in doc:
        s = x.get("set") if isinstance(x, dict) else None
        if not s or s.get("name") not in SETS:
            continue
        for el in s.get("elem", []):
            v = el.get("elem", el) if isinstance(el, dict) else {"val": el}
            ip = v.get("val")
            if not isinstance(ip, str):
                continue
            accion = SETS[s["name"]]
            if ip in out and out[ip]["accion"] == "BLOCK":
                continue
            out[ip] = {"accion": accion, "expira_en": v.get("expires")}
    return out


def ultima_pasada() -> dict | None:
    try:
        r = subprocess.run(["journalctl", "-u", "ppi-enforce-agent", "-n", "40", "--no-pager", "-o", "json"],
                           capture_output=True, text=True, timeout=10)
    except (OSError, subprocess.TimeoutExpired):
        return None
    for linea in reversed(r.stdout.splitlines()):
        try:
            j = json.loads(linea)
            msg = j.get("MESSAGE")
            if isinstance(msg, str) and msg.startswith("{"):
                d = json.loads(msg)
                return {"hora": int(j.get("__REALTIME_TIMESTAMP", "0")) / 1e6, "estado": d.get("estado"),
                        "errores": d.get("errores"), "block": d.get("block", []), "limit": d.get("limit", []),
                        "sombra": d.get("sombra", {})}
        except ValueError:
            continue
    return None


def estado_timer() -> str:
    try:
        return subprocess.run(["systemctl", "is-active", "ppi-enforce-agent.timer"], capture_output=True,
                              text=True, timeout=5).stdout.strip() or "desconocido"
    except (OSError, subprocess.TimeoutExpired):
        return "desconocido"


def transiciones(antes: dict, ahora: dict, t: float) -> list[dict]:
    """Eventos entre dos fotos del firewall: aplicada, cambiada o retirada."""
    ev = []
    for ip, r in ahora.items():
        a = antes.get(ip)
        if a is None:
            ev.append({"t": t, "ip": ip, "evento": "aplicada", "accion": r["accion"]})
        elif a.get("accion") != r["accion"]:
            ev.append({"t": t, "ip": ip, "evento": "cambiada", "accion": r["accion"], "antes": a.get("accion")})
    for ip, a in antes.items():
        if ip not in ahora:
            ev.append({"t": t, "ip": ip, "evento": "retirada", "accion": a.get("accion")})
    return ev


def acuse(reglas: dict, error: str | None, liberadas: dict, pasada: dict | None, agente: str,
          historial: dict, ahora: float, host: str) -> tuple[dict, dict]:
    eventos = list(historial.get("eventos", []))
    if error is None:
        eventos += transiciones(historial.get("reglas", {}), reglas, ahora)
        # una liberacion humana nueva tambien es un evento del host
        vistas = historial.get("liberadas", {})
        for ip, l in liberadas.items():
            if isinstance(l, dict) and l.get("desde") and l.get("desde") != vistas.get(ip):
                eventos.append({"t": l["desde"], "ip": ip, "evento": "liberada", "accion": ""})
        historial = {"reglas": reglas, "eventos": eventos[-MAX_EVENTOS:],
                     "liberadas": {ip: l.get("desde") for ip, l in liberadas.items() if isinstance(l, dict)}}
    lib = {}
    for ip, l in liberadas.items():
        if isinstance(l, dict):
            lib[ip] = {"desde": l.get("desde"), "gracia_hasta": (l.get("desde") or 0) + (l.get("gracia") or 0)}
    doc = {"host": host, "generado": ahora, "agente": agente, "error": error,
           "reglas": {ip: {"accion": r["accion"],
                           "expira": None if r.get("expira_en") is None else ahora + r["expira_en"]}
                      for ip, r in reglas.items()},
           "liberadas": lib, "ultima_pasada": pasada, "eventos": historial.get("eventos", [])[-60:]}
    return doc, historial


def main(argv=None) -> int:
    ahora = time.time()
    reglas, error = leer_nft()
    try:
        liberadas = json.loads((ENFORCE / "liberadas.json").read_text(encoding="utf-8"))
        if not isinstance(liberadas, dict):
            liberadas = {}
    except (OSError, ValueError):
        liberadas = {}
    try:
        historial = json.loads(HISTORIAL.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        historial = {}
    host = os.environ.get("CF_HOST_NOMBRE") or socket.gethostname()
    doc, historial = acuse(reglas, error, liberadas, ultima_pasada(), estado_timer(), historial, ahora, host)
    try:
        tmp = HISTORIAL.with_suffix(".tmp")
        tmp.write_text(json.dumps(historial), encoding="utf-8")
        tmp.replace(HISTORIAL)
    except OSError:
        pass
    json.dump(doc, sys.stdout, ensure_ascii=False)
    return 0


if __name__ == "__main__":
    sys.exit(main())
