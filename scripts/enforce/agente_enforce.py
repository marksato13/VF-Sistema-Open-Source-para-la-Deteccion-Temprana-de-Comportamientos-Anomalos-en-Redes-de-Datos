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
- **Alcance (opcional, `alcance.json` junto al agente):** `nunca` = redes que el
  host jamás sanciona (infraestructura); `solo` = si no está vacío, el host
  aplica únicamente a esas IPs y el resto queda en sombra (publicado, no aplicado).
- **Liberación humana:** `--liberar IP` retira la IP de los sets y la anota en
  `liberadas.json`; no se reaplica mientras la orden siga siendo la misma. Una
  orden de mayor nivel (reincidencia) vuelve a aplicarse; si la IP sale del feed,
  la liberación se olvida.

Uso:
    agente_enforce.py --feed URL_o_fichero --firma URL_o_fichero \\
        --clave-publica pub.pem [--aplicar]   # sin --aplicar: dry-run
    agente_enforce.py ... --aplicar --sudo --liberar 10.10.20.30
"""
from __future__ import annotations

import argparse
import ipaddress
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
            out[ip] = {"accion": accion, "hasta": int(e["hasta"]), "nivel": int(e.get("nivel") or 0)}
    return out


def _redes(lista) -> list:
    out = []
    for x in lista or []:
        try:
            out.append(ipaddress.ip_network(str(x), strict=False))
        except ValueError:
            continue
    return out


def en_redes(ip: str, redes: list) -> bool:
    try:
        a = ipaddress.ip_address(ip)
    except ValueError:
        return False
    return any(a in r for r in redes)


def filtrar_alcance(vig: dict[str, dict], alcance: dict | None,
                    liberadas: dict[str, dict] | None) -> tuple[dict, dict]:
    """Separa lo que el host aplica de lo que deja en sombra, con el motivo.

    - `nunca`: redes de infraestructura -> nunca se aplican.
    - `solo`: si tiene algo, solo esas IPs/redes se aplican.
    - liberadas: no se reaplica mientras el nivel de la orden no supere el liberado.
    """
    alcance = alcance or {}
    nunca, solo = _redes(alcance.get("nunca")), _redes(alcance.get("solo"))
    liberadas = liberadas or {}
    aplicar, sombra = {}, {}
    for ip, v in vig.items():
        if en_redes(ip, nunca):
            sombra[ip] = "nunca"
        elif solo and not en_redes(ip, solo):
            sombra[ip] = "fuera-de-alcance"
        elif ip in liberadas and misma_orden(v, liberadas[ip]):
            sombra[ip] = "liberada"
        else:
            aplicar[ip] = v
    return aplicar, sombra


MARGEN_RENOVACION = 20   # s: el sensor republica; solo una ofensa NUEVA mueve la caducidad más allá


def misma_orden(v: dict, lib: dict) -> bool:
    """¿Sigue siendo la orden que el humano liberó? No si escaló de nivel o si el
    sensor la renovó por una ofensa nueva (su caducidad avanzó)."""
    if v.get("nivel", 0) > int(lib.get("nivel", 0)):
        return False
    return int(v.get("hasta", 0)) <= int(lib.get("hasta", 0)) + MARGEN_RENOVACION


def depurar_liberadas(liberadas: dict[str, dict], vig: dict[str, dict]) -> dict[str, dict]:
    """Olvida liberaciones de IPs que ya no tienen orden o cuya orden cambió."""
    return {ip: d for ip, d in liberadas.items() if ip in vig and misma_orden(vig[ip], d)}


def plan_liberar(ip: str) -> list[list[str]]:
    """Retira la IP de ambos sets (si no está, nft falla y se ignora)."""
    return [["nft", "delete", "element", "inet", "cyberflow", s, "{", ip, "}"]
            for s in (SET_BLOCK, SET_LIMIT)]


def _leer_json(path: Path) -> dict:
    try:
        d = json.loads(path.read_text(encoding="utf-8"))
        return d if isinstance(d, dict) else {}
    except (OSError, ValueError):
        return {}


def plan_nftables(vig: dict[str, dict], ahora: float,
                  actuales: dict[str, dict[str, float]] | None = None) -> list[list[str]]:
    """Comandos nft para añadir acciones sin acortar su caducidad nativa.

    Los sets no se vacían en cada pasada: si una decisión deja la ventana de
    publicación, nftables conserva la entrada hasta el timeout firmado. `nft add
    element` es idempotente para un elemento existente y mantiene su expiración.
    """
    blocks = {ip: v for ip, v in vig.items() if v["accion"] == "BLOCK"}
    limits = {ip: v for ip, v in vig.items() if v["accion"] == "LIMIT"}
    actuales = actuales or {SET_BLOCK: {}, SET_LIMIT: {}}
    # Tabla PROPIA y AISLADA (`inet cyberflow`): coexiste con el firewall del host
    # sin tocarlo. La cadena tiene `policy accept` -> solo cae lo que esté en los
    # sets; jamás bloquea nada más. Los sets llevan `timeout` nativo (caducidad).
    # Las reglas se recrean cada pasada (flush chain) para no duplicarse. Los sets
    # NO se vacían: su timeout nativo es la autoridad para retirar cada acción.
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


def _plan_elemento(cmds: list[list[str]], ip: str, valor: dict, ahora: float,
                    destino: str, opuesto: str,
                    actuales: dict[str, dict[str, float]]) -> None:
    """Añade o amplía una entrada; nunca acorta un timeout ya aplicado."""
    # Un LIMIT posterior no revoca un BLOCK que aún vive en el kernel. No existe
    # downgrade automático: la sanción fuerte termina por timeout o retiro humano.
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
    """Lee expiraciones absolutas del set; un set aún inexistente equivale a vacío."""
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
    """Renderiza una transacción nft: o se aplica completa o no cambia nada."""
    return "\n".join(" ".join(c[1:]) for c in cmds) + "\n"


def _ejecutar_lote(cmds: list[list[str]], usar_sudo: bool) -> subprocess.CompletedProcess:
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
    aqui = Path(__file__).resolve().parent
    p.add_argument("--alcance", default=str(aqui / "alcance.json"),
                   help="JSON {nunca: [redes], solo: [redes]}; si no existe, se aplica a todo")
    p.add_argument("--liberadas", default=str(aqui / "liberadas.json"),
                   help="registro de liberaciones humanas")
    p.add_argument("--liberar", metavar="IP", help="retira la IP de nftables y no la reaplica "
                                                    "mientras la orden no escale")
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
    ruta_lib = Path(a.liberadas)
    liberadas_prev = _leer_json(ruta_lib)
    liberadas = depurar_liberadas(liberadas_prev, vig)

    if a.liberar:
        ip = a.liberar.strip()
        try:
            ipaddress.ip_address(ip)
        except ValueError:
            print(json.dumps({"estado": "ip-invalida", "ip": ip}))
            return 2
        if a.aplicar:
            for c in plan_liberar(ip):          # uno a uno: si no está en un set, no pasa nada
                subprocess.run((["sudo", "-n"] if a.sudo else []) + c, check=False,
                               capture_output=True, text=True)
            orden = vig.get(ip, {})
            liberadas[ip] = {"nivel": orden.get("nivel", 0), "hasta": orden.get("hasta", 0),
                             "desde": int(ahora)}
            ruta_lib.write_text(json.dumps(liberadas, sort_keys=True), encoding="utf-8")
        print(json.dumps({"estado": "liberada" if a.aplicar else "dry-run", "ip": ip,
                          "orden_vigente": vig.get(ip)}, sort_keys=True))
        return 0

    vig, sombra = filtrar_alcance(vig,_leer_json(Path(a.alcance)), liberadas)
    if a.aplicar and liberadas != liberadas_prev:
        try:
            ruta_lib.write_text(json.dumps(liberadas, sort_keys=True), encoding="utf-8")
        except OSError:
            pass
    actuales = {
        SET_BLOCK: _elementos_actuales(SET_BLOCK, ahora, a.sudo),
        SET_LIMIT: _elementos_actuales(SET_LIMIT, ahora, a.sudo),
    }
    cmds = plan_nftables(vig, ahora, actuales)

    errores: list[str] = []
    if a.aplicar:
        r = _ejecutar_lote(cmds, a.sudo)
        if r.returncode != 0:
            # Un elemento puede caducar entre el snapshot JSON y el commit. Como
            # el primer lote fue atómico, releer y replanificar una vez es seguro.
            ahora = time.time()
            actuales = {
                SET_BLOCK: _elementos_actuales(SET_BLOCK, ahora, a.sudo),
                SET_LIMIT: _elementos_actuales(SET_LIMIT, ahora, a.sudo),
            }
            cmds = plan_nftables(vig, ahora, actuales)
            r = _ejecutar_lote(cmds, a.sudo)
        # El lote es atómico: si algo falla, nftables conserva el estado anterior.
        if r.returncode != 0:
            errores.append((r.stderr or r.stdout or "fallo nft").strip()[:160])
    salida = {
        "estado": "aplicado" if a.aplicar else "dry-run",
        "block": sorted(ip for ip, v in vig.items() if v["accion"] == "BLOCK"),
        "limit": sorted(ip for ip, v in vig.items() if v["accion"] == "LIMIT"),
        "comandos": len(cmds),
        "errores": len(errores),
        "sombra": sombra,
    }
    if errores:
        salida["primer_error"] = errores[0]
    print(json.dumps(salida, sort_keys=True))
    # Codigo != 0 si se pidio aplicar y algun nft fallo: el cron lo deja en el
    # log y un fallo sistematico se nota, en vez de "aplicado" mintiendo.
    return 1 if errores else 0


if __name__ == "__main__":
    raise SystemExit(main())
