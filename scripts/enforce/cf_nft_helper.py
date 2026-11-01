#!/usr/bin/python3 -I
"""Helper root RESTRINGIDO de nftables para los agentes CyberFlow (Etapa 2, candidato).

Sustituye a ``sudo nft -f -``, que daba al usuario del agente poder para cargar
CUALQUIER regla en el cortafuegos del host. Este helper:

- se instala como root (``/usr/local/sbin/cf-nft-helper``, 0755 root:root) y es lo
  unico que el usuario del agente puede ejecutar con sudo, sin argumentos:
  ``agente ALL=(root) NOPASSWD: /usr/local/sbin/cf-nft-helper ""``;
- lee de stdin UNA peticion JSON con un perfil fijo y una lista de operaciones
  cerradas; valida todo antes de tocar nada (una operacion invalida rechaza la
  peticion entera, sin aplicar nada);
- construye EL MISMO el texto nft, solo sobre su tabla (``inet cyberflow_dmz`` para
  srv-dmz, ``inet cyberflow_dns`` para DC1) y solo con sus sets; nunca acepta texto
  nft, nombres de tabla, de set, cadenas ni expresiones del llamador;
- aplica todo en una transaccion ``nft -f -`` (atomica: o entra entera o nada).

Perfiles:
  dmz -> tabla inet cyberflow_dmz (distinta de la del v1, inet cyberflow), hook input prioridad -10, todo el trafico del origen.
  dns -> tabla inet cyberflow_dns, hook input prioridad -10, SOLO udp/tcp dport 53.
Ambas cadenas tienen policy accept: solo cae lo que este en los sets.

Acciones por origen:
  BLOCK -> set ``bloqueados``: drop.
  LIMIT -> set ``limitados``: drop de lo que exceda ``tasa`` paq/s POR ORIGEN (set
           dinamico ``tasa_origen``; el desplegado compartia un unico cubo).
Cada set lleva ``counter`` por elemento (paquetes/bytes por origen y accion) y cada
regla su ``counter`` (total por accion).

Operaciones (``op``):
  asegurar               crea tabla, sets y cadena si faltan y rehace las reglas
  anadir   set ip timeout   anade un origen con caducidad (1..3720 s)
  quitar   set ip           quita un origen de un set
  listar                 elementos con caducidad restante y contadores (solo lectura)
  retirar_origen ip      quita el origen de los dos sets (limpieza D5)
  desinstalar            borra la tabla del perfil (y nada mas)
"""
from __future__ import annotations

import ipaddress
import json
import subprocess
import sys

TABLAS = {"dmz": "cyberflow_dmz", "dns": "cyberflow_dns"}
SETS = ("bloqueados", "limitados")
TIMEOUT_MAX_S = 3600 + 120
MAX_OPERACIONES = 512
MAX_BYTES_PETICION = 256 * 1024
# Tasa del LIMIT por perfil (paquetes/s por origen). dmz = valor desplegado.
# dns: ver el informe de la Etapa 2 (2,3 consultas/s del escenario): es un valor
# CANDIDATO pendiente de decision, no validado como separador.
TASA = {"dmz": "100/second", "dns": "5/second"}
RAFAGA = {"dmz": 100, "dns": 10}
# Infraestructura que el helper rechaza aunque se lo pidan (defensa en profundidad:
# el agente ya la filtra, pero el helper no confia en el agente).
NUNCA = frozenset({
    "10.10.10.30", "10.10.60.11", "10.10.30.1", "10.10.40.1", "10.10.60.1",
    "10.10.20.1", "10.10.10.20", "10.10.10.21",
})
_OPS = {
    "asegurar": set(),
    "anadir": {"set", "ip", "timeout"},
    "quitar": {"set", "ip"},
    "listar": set(),
    "retirar_origen": {"ip"},
    "desinstalar": set(),
}


class Rechazo(ValueError):
    pass


def _ip(valor) -> str:
    if not isinstance(valor, str) or len(valor) > 15:
        raise Rechazo("ip_invalida")
    try:
        ip = ipaddress.IPv4Address(valor)
    except ValueError:
        raise Rechazo("ip_invalida") from None
    if str(ip) != valor:
        raise Rechazo("ip_no_canonica")
    if (ip.is_loopback or ip.is_multicast or ip.is_unspecified or ip.is_reserved
            or ip.is_link_local or valor == "255.255.255.255"):
        raise Rechazo("ip_especial")
    if valor in NUNCA:
        raise Rechazo("ip_nunca_bloquear")
    return valor


def validar(peticion) -> tuple[str, list[dict]]:
    if not isinstance(peticion, dict) or set(peticion) != {"perfil", "operaciones"}:
        raise Rechazo("peticion_mal_formada")
    perfil = peticion["perfil"]
    if perfil not in TABLAS:
        raise Rechazo("perfil_desconocido")
    ops = peticion["operaciones"]
    if not isinstance(ops, list) or not ops or len(ops) > MAX_OPERACIONES:
        raise Rechazo("operaciones_invalidas")
    limpias = []
    for o in ops:
        if not isinstance(o, dict) or o.get("op") not in _OPS:
            raise Rechazo("op_desconocida")
        campos = set(o) - {"op"}
        if campos != _OPS[o["op"]]:
            raise Rechazo("campos_invalidos:%s" % o["op"])
        x = {"op": o["op"]}
        if "set" in o:
            if o["set"] not in SETS:
                raise Rechazo("set_desconocido")
            x["set"] = o["set"]
        if "ip" in o:
            x["ip"] = _ip(o["ip"])
        if "timeout" in o:
            t = o["timeout"]
            if not isinstance(t, int) or isinstance(t, bool) or not 1 <= t <= TIMEOUT_MAX_S:
                raise Rechazo("timeout_fuera_de_rango")
            x["timeout"] = t
        limpias.append(x)
    especiales = {o["op"] for o in limpias} & {"listar", "desinstalar"}
    if especiales and len(limpias) != 1:
        raise Rechazo("listar_y_desinstalar_van_solos")
    return perfil, limpias


def texto_asegurar(perfil: str) -> list[str]:
    t = TABLAS[perfil]
    filtro = "meta l4proto { udp, tcp } th dport 53 " if perfil == "dns" else ""
    return [
        "add table inet %s" % t,
        "add set inet %s bloqueados { type ipv4_addr; flags timeout; counter; }" % t,
        "add set inet %s limitados { type ipv4_addr; flags timeout; counter; }" % t,
        "add set inet %s tasa_origen { type ipv4_addr; flags dynamic, timeout; timeout 60s; }" % t,
        "add chain inet %s entrada { type filter hook input priority -10; policy accept; }" % t,
        "flush chain inet %s entrada" % t,
        "add rule inet %s entrada %sip saddr @bloqueados counter drop" % (t, filtro),
        ("add rule inet %s entrada %sip saddr @limitados update @tasa_origen "
         "{ ip saddr limit rate over %s burst %d packets } counter drop")
        % (t, filtro, TASA[perfil], RAFAGA[perfil]),
    ]


def texto(perfil: str, ops: list[dict]) -> str:
    t = TABLAS[perfil]
    lineas: list[str] = []
    if ops[0]["op"] == "desinstalar":
        return "destroy table inet %s\n" % t
    if any(o["op"] == "asegurar" for o in ops):
        lineas += texto_asegurar(perfil)
    for o in ops:
        if o["op"] == "anadir":
            lineas.append("add element inet %s %s { %s timeout %ds }" % (t, o["set"], o["ip"], o["timeout"]))
        elif o["op"] == "quitar":
            lineas.append("destroy element inet %s %s { %s }" % (t, o["set"], o["ip"]))
        elif o["op"] == "retirar_origen":
            for s in SETS:
                lineas.append("destroy element inet %s %s { %s }" % (t, s, o["ip"]))
    return "\n".join(lineas) + "\n"


def _listar(perfil: str, nft: str) -> dict:
    t = TABLAS[perfil]
    out = {"sets": {}, "reglas": []}
    for s in SETS:
        r = subprocess.run([nft, "-j", "list", "set", "inet", t, s], capture_output=True, text=True)
        if r.returncode != 0:
            out["sets"][s] = None
            continue
        doc = json.loads(r.stdout)
        elems = {}
        for x in doc.get("nftables", []):
            for e in (x.get("set", {}).get("elem") or []):
                if isinstance(e, dict) and "elem" in e:
                    v = e["elem"]
                    elems[str(v.get("val"))] = {"expira_s": v.get("expires"),
                                                "paquetes": (v.get("counter") or {}).get("packets"),
                                                "bytes": (v.get("counter") or {}).get("bytes")}
                else:
                    elems[str(e)] = {}
        out["sets"][s] = elems
    r = subprocess.run([nft, "-j", "list", "chain", "inet", t, "entrada"], capture_output=True, text=True)
    if r.returncode == 0:
        for x in json.loads(r.stdout).get("nftables", []):
            if "rule" in x:
                cont = [e["counter"] for e in x["rule"].get("expr", []) if isinstance(e, dict) and "counter" in e]
                out["reglas"].append({"handle": x["rule"].get("handle"), "contador": cont[0] if cont else None})
    return out


def ejecutar(peticion, nft: str = "/usr/sbin/nft") -> dict:
    try:
        perfil, ops = validar(peticion)
    except Rechazo as exc:
        return {"ok": False, "rechazo": str(exc)}
    if ops[0]["op"] == "listar":
        return {"ok": True, "perfil": perfil, "estado": _listar(perfil, nft)}
    script = texto(perfil, ops)
    r = subprocess.run([nft, "-f", "-"], input=script, capture_output=True, text=True)
    if r.returncode != 0:
        return {"ok": False, "error_nft": (r.stderr or r.stdout).strip()[:300]}
    return {"ok": True, "perfil": perfil, "operaciones": len(ops)}


def main() -> int:
    if len(sys.argv) != 1:
        print(json.dumps({"ok": False, "rechazo": "sin_argumentos"}))
        return 2
    datos = sys.stdin.buffer.read(MAX_BYTES_PETICION + 1)
    if len(datos) > MAX_BYTES_PETICION:
        print(json.dumps({"ok": False, "rechazo": "peticion_demasiado_grande"}))
        return 2
    try:
        peticion = json.loads(datos)
    except ValueError:
        print(json.dumps({"ok": False, "rechazo": "json_invalido"}))
        return 2
    res = ejecutar(peticion)
    print(json.dumps(res, sort_keys=True))
    return 0 if res.get("ok") else 1


if __name__ == "__main__":
    sys.exit(main())
