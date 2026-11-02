#!/usr/bin/python3 -I
"""Helper root RESTRINGIDO de nftables para los agentes CyberFlow (Etapa 2, candidato).

Sustituye a ``sudo nft -f -``, que daba al usuario del agente poder para cargar
CUALQUIER regla en el cortafuegos del host. Este helper:

- se instala como root (``/usr/local/sbin/cf-nft-helper``, 0755 root:root) y es lo
  unico que el usuario del agente puede ejecutar con sudo, sin argumentos:
  ``agente ALL=(root) NOPASSWD: /usr/local/sbin/cf-nft-helper ""``;
- **el perfil lo fija el HOST, no la peticion**: se lee de
  ``/etc/cyberflow/nft-helper.perfil`` (una palabra: ``dns`` en DC1, ``dmz`` en
  srv-dmz). El fichero y su directorio deben ser de root y no escribibles por grupo
  ni otros; si no, el helper rechaza todo. La peticion debe declarar ese mismo
  perfil (``perfil_no_autorizado`` si no): en DC1 no se puede pedir el perfil dmz.
  La ruta es una constante: no se acepta por argumento ni por variable de entorno;
- lee de stdin UNA peticion JSON con una lista de operaciones cerradas; valida todo
  antes de tocar nada (una operacion invalida rechaza la peticion entera);
- construye EL MISMO el texto nft, solo sobre su tabla (``inet cyberflow_dmz`` en
  srv-dmz, ``inet cyberflow_dns`` en DC1) y solo con sus sets; nunca acepta texto
  nft, nombres de tabla, de set, cadenas ni expresiones del llamador;
- aplica todo en una transaccion ``nft -f -`` (atomica: o entra entera o nada).

Perfiles:
  dmz -> tabla inet cyberflow_dmz (distinta de la del v1, inet cyberflow), hook input prioridad -10, todo el trafico del origen.
  dns -> tabla inet cyberflow_dns, hook input prioridad -10, SOLO udp/tcp dport 53.
Ambas cadenas tienen policy accept: solo cae lo que este en los sets.

Acciones por origen e instrumentacion (Etapa 2, punto 7):
  BLOCK -> set ``bloqueados`` (counter por elemento = paquetes DESCARTADOS del origen).
  LIMIT -> set ``limitados`` (counter por elemento = paquetes que COINCIDEN con la
           regla, pasen o no) + set dinamico ``descartes_limite`` (counter por origen =
           paquetes DESCARTADOS por exceder la tasa). El cubo de tasa es por origen
           (``tasa_origen``).
  Cada elemento de ``bloqueados``/``limitados`` lleva ``comment "id:<id de la entrada
  del feed>"``: los contadores se atribuyen a una accion concreta, tambien tras un
  reinicio del agente. ``anadir`` SUSTITUYE el elemento (destroy + add en la misma
  transaccion): una renovacion abre un intervalo nuevo con contadores a cero; en
  ``limitados`` tambien se pone a cero ``descartes_limite`` de ese origen.

Operaciones (``op``):
  asegurar               crea tabla, sets y cadena si faltan y rehace las reglas
  anadir   set ip timeout id   pone un origen con caducidad (1..3720 s) e id (16 hex)
  quitar   set ip           quita un origen de un set
  listar                 elementos con caducidad, id y contadores (solo lectura)
  retirar_origen ip      quita el origen de los dos sets (limpieza D5)
  desinstalar            borra la tabla del perfil (y nada mas)
"""
from __future__ import annotations

import ipaddress
import json
import os
import re
import stat
import subprocess
import sys

RUTA_PERFIL = "/etc/cyberflow/nft-helper.perfil"
TABLAS = {"dmz": "cyberflow_dmz", "dns": "cyberflow_dns"}
SETS = ("bloqueados", "limitados")
TIMEOUT_MAX_S = 3600 + 120
MAX_OPERACIONES = 512
MAX_BYTES_PETICION = 256 * 1024
# Tasa del LIMIT por perfil (paquetes/s por origen). dmz = valor desplegado.
# dns: 5/s NO recorta el escenario DNS del 3B (2,3 consultas/s): valor PENDIENTE de
# desarrollo y validacion (Etapa 3), no es una respuesta efectiva. Ver el informe.
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
    "anadir": {"set", "ip", "timeout", "id"},
    "quitar": {"set", "ip"},
    "listar": set(),
    "retirar_origen": {"ip"},
    "desinstalar": set(),
}
_ID = re.compile(r"^[0-9a-f]{16}$")


class Rechazo(ValueError):
    pass


def _seguro(st: os.stat_result, es_dir: bool) -> bool:
    tipo_ok = stat.S_ISDIR(st.st_mode) if es_dir else stat.S_ISREG(st.st_mode)
    return tipo_ok and st.st_uid == 0 and not st.st_mode & (stat.S_IWGRP | stat.S_IWOTH)


def leer_perfil_autorizado(ruta: str = RUTA_PERFIL) -> str:
    """Perfil fijado por root en el host. Rechaza enlaces, duenos distintos de root y
    permisos de escritura para grupo u otros en el fichero o en su directorio."""
    try:
        st_f = os.lstat(ruta)
        st_d = os.lstat(os.path.dirname(ruta) or ".")
    except OSError:
        raise Rechazo("perfil_no_configurado") from None
    if not (_seguro(st_f, False) and _seguro(st_d, True)):
        raise Rechazo("configuracion_insegura")
    try:
        with open(ruta, encoding="ascii") as fh:
            valor = fh.read(64).strip()
    except (OSError, UnicodeDecodeError):
        raise Rechazo("perfil_no_configurado") from None
    if valor not in TABLAS:
        raise Rechazo("perfil_no_configurado")
    return valor


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


def validar(peticion, perfil_autorizado: str) -> tuple[str, list[dict]]:
    if perfil_autorizado not in TABLAS:
        raise Rechazo("perfil_no_configurado")
    if not isinstance(peticion, dict) or set(peticion) != {"perfil", "operaciones"}:
        raise Rechazo("peticion_mal_formada")
    perfil = peticion["perfil"]
    if perfil not in TABLAS:
        raise Rechazo("perfil_desconocido")
    if perfil != perfil_autorizado:
        raise Rechazo("perfil_no_autorizado")
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
        if "id" in o:
            if not isinstance(o["id"], str) or not _ID.match(o["id"]):
                raise Rechazo("id_invalido")
            x["id"] = o["id"]
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
        "add set inet %s descartes_limite { type ipv4_addr; flags dynamic, timeout; counter; timeout %ds; }"
        % (t, TIMEOUT_MAX_S),
        "add chain inet %s entrada { type filter hook input priority -10; policy accept; }" % t,
        "flush chain inet %s entrada" % t,
        "add rule inet %s entrada %sip saddr @bloqueados counter drop" % (t, filtro),
        ("add rule inet %s entrada %sip saddr @limitados update @tasa_origen "
         "{ ip saddr limit rate over %s burst %d packets } update @descartes_limite { ip saddr } counter drop")
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
            lineas.append("destroy element inet %s %s { %s }" % (t, o["set"], o["ip"]))
            if o["set"] == "limitados":
                lineas.append("destroy element inet %s descartes_limite { %s }" % (t, o["ip"]))
            lineas.append('add element inet %s %s { %s timeout %ds comment "id:%s" }'
                          % (t, o["set"], o["ip"], o["timeout"], o["id"]))
        elif o["op"] == "quitar":
            lineas.append("destroy element inet %s %s { %s }" % (t, o["set"], o["ip"]))
        elif o["op"] == "retirar_origen":
            for s in SETS:
                lineas.append("destroy element inet %s %s { %s }" % (t, s, o["ip"]))
    return "\n".join(lineas) + "\n"


def _elementos(nft: str, t: str, s: str) -> dict | None:
    r = subprocess.run([nft, "-j", "list", "set", "inet", t, s], capture_output=True, text=True)
    if r.returncode != 0:
        return None
    elems = {}
    for x in json.loads(r.stdout).get("nftables", []):
        for e in (x.get("set", {}).get("elem") or []):
            if isinstance(e, dict) and "elem" in e:
                v = e["elem"]
                com = v.get("comment") or ""
                elems[str(v.get("val"))] = {"expira_s": v.get("expires"),
                                            "id": com[3:] if com.startswith("id:") else None,
                                            "paquetes": (v.get("counter") or {}).get("packets"),
                                            "bytes": (v.get("counter") or {}).get("bytes")}
            else:
                elems[str(e)] = {}
    return elems


def _listar(perfil: str, nft: str) -> dict:
    t = TABLAS[perfil]
    out = {"sets": {s: _elementos(nft, t, s) for s in SETS},
           "descartes_limite": _elementos(nft, t, "descartes_limite"), "reglas": []}
    r = subprocess.run([nft, "-j", "list", "chain", "inet", t, "entrada"], capture_output=True, text=True)
    if r.returncode == 0:
        for x in json.loads(r.stdout).get("nftables", []):
            if "rule" in x:
                cont = [e["counter"] for e in x["rule"].get("expr", []) if isinstance(e, dict) and "counter" in e]
                out["reglas"].append({"handle": x["rule"].get("handle"), "contador": cont[0] if cont else None})
    return out


def ejecutar(peticion, perfil_autorizado: str, nft: str = "/usr/sbin/nft") -> dict:
    try:
        perfil, ops = validar(peticion, perfil_autorizado)
    except Rechazo as exc:
        return {"ok": False, "rechazo": str(exc)}
    if ops[0]["op"] == "listar":
        return {"ok": True, "perfil": perfil, "estado": _listar(perfil, nft)}
    script = texto(perfil, ops)
    r = subprocess.run([nft, "-f", "-"], input=script, capture_output=True, text=True)
    if r.returncode != 0:
        return {"ok": False, "error_nft": (r.stderr or r.stdout).strip()[:300]}
    return {"ok": True, "perfil": perfil, "operaciones": len(ops)}


def main(argv=None, ruta_perfil: str = RUTA_PERFIL) -> int:
    argv = sys.argv if argv is None else argv
    if len(argv) != 1:
        print(json.dumps({"ok": False, "rechazo": "sin_argumentos"}))
        return 2
    try:
        perfil_autorizado = leer_perfil_autorizado(ruta_perfil)
    except Rechazo as exc:
        print(json.dumps({"ok": False, "rechazo": str(exc)}))
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
    res = ejecutar(peticion, perfil_autorizado)
    print(json.dumps(res, sort_keys=True))
    return 0 if res.get("ok") else 1


if __name__ == "__main__":
    sys.exit(main())
