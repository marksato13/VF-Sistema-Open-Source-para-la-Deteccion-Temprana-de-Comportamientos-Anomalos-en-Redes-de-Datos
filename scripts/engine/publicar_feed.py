#!/usr/bin/env python3
"""Publica el feed de enforcement (firmado) desde las decisiones del motor.

Corre en el SENSOR (no toca hosts). Lee `motor_decision.log`, agrega por IP el
veredicto más severo reciente, le aplica la escalera de caducidad
(`escalada.py`), y escribe un feed firmado (`feed.py`) que los hosts traen y
aplican (modelo un-feed/N-agentes; ver DISENO-ENFORCEMENT.md).

Mapeo veredicto → acción (DISENO §5/§10):
- ALERT del **modelo** (score < umbral)         -> LIMIT (anomalía; degradar)
- ALERT de un **heurístico** (detector `*_heuristic`) -> BLOCK (confirmado)

Nunca actúa sobre la lista de nunca-bloquear (gateways, DNS, sensor, bastión).
"""
from __future__ import annotations

import argparse
import ipaddress
import json
import time
from pathlib import Path

import sys

try:
    from scripts.engine import escalada, feed, heuristicos
except ImportError:  # ejecutado desde scripts/engine/
    import escalada
    import feed
    import heuristicos

# Infra que NUNCA se bloquea, pase lo que pase (coincide con responder_iptables).
NUNCA_BLOQUEAR_POR_DEFECTO = {
    "10.10.10.30",   # bastión
    "10.10.60.11",   # sensor
    "10.10.30.1", "10.10.40.1", "10.10.60.1", "10.10.20.1",  # gateways VLAN
    "10.10.10.20",   # DNS/AD
}

_SEVERIDAD = {"BLOCK": 2, "LIMIT": 1}

# Política del modelo (3-nov). El modelo solo, sin regla que lo confirme, actúa
# cuando la anomalía es CLARA y SOSTENIDA:
#  - clara: score por debajo de umbral - MARGEN_MARGINAL. Las marginales (a menos
#    de 0,05 del umbral) se registran y se ven en el panel, pero no se publican;
#  - sostenida: al menos MIN_VENTANAS_MODELO ventanas claras de la misma IP en el
#    tramo que lee el feed (120 s). Una o dos ventanas sueltas no bastan.
# Medido sobre 30 h del registro (3-nov, 02:25): con 0,05 y 3 ventanas, ninguna IP
# legitima (.21, .24, DNS 10.10.10.20, 50.51/52...) llega a un episodio y la Kali
# .30 conserva sus 6. Con 0,02 y 2 ventanas, .21 tenia 5 y el DNS 29: en la corrida
# 3 de la demo .21 recibio un LIMIT del modelo (margen 0,051, dos ventanas).
# Las reglas (port_scan, http_abuse...) no cambian: actúan desde la 1.a ventana.
MARGEN_MARGINAL = 0.05
MIN_VENTANAS_MODELO = 3


def _modelo_claro(d: dict, margen: float = MARGEN_MARGINAL) -> bool:
    s, u = d.get("score"), d.get("threshold")
    if not isinstance(s, (int, float)) or not isinstance(u, (int, float)):
        return True          # sin score no se puede llamar marginal: se respeta
    return s < u - margen


def _verdicto_de(d: dict) -> tuple[str, str, str] | None:
    """Veredicto (accion, motivo, detector) de una decisión, o None.

    Combina dos señales y se queda con la MÁS severa:
      - Modelo: ALERT del modelo (score < umbral)  -> LIMIT (anomalía).
      - Heurístico: el campo `heuristico` del registro (brute-force, port-scan,
        http-abuse, dns-entropy) -> su acción (BLOCK/LIMIT). También se acepta el
        ALERT de heurístico "legacy" del motor (detector `*_heuristic`) -> BLOCK.
    """
    candidatos: list[tuple[str, str, str]] = []
    if d.get("decision") == "ALERT":
        det = str(d.get("detector_name", ""))
        if det.endswith("_heuristic"):
            candidatos.append(("BLOCK", det, det))
        else:
            candidatos.append(("LIMIT", "modelo:" + det, det))
    h = d.get("heuristico")
    if isinstance(h, dict) and h.get("accion") in _SEVERIDAD:
        candidatos.append((h["accion"],
                           "%s: %s" % (h.get("heuristico", "?"), h.get("motivo", "")),
                           str(h.get("heuristico", "heuristico"))))
    if not candidatos:
        return None
    # A igual severidad gana la regla: dice el motivo y no depende de la política
    # de persistencia del modelo.
    return max(candidatos, key=lambda c: (_SEVERIDAD[c[0]], not c[1].startswith("modelo:")))


def decisiones_a_entradas(decisiones: list[dict], estado: dict, ahora: float,
                          nunca: set[str], alcance="all") -> list[dict]:
    """Núcleo puro: agrega por IP el veredicto más severo, aplica escalera.

    Devuelve la lista de entradas del feed. Muta `estado` (para persistir).
    """
    # Ventanas del modelo claras por IP (para exigir que la anomalía se sostenga).
    claras: dict[str, int] = {}
    for d in decisiones:
        if (d.get("decision") == "ALERT"
                and not str(d.get("detector_name", "")).endswith("_heuristic")
                and _modelo_claro(d)):
            ip = str(d.get("entity_ip", ""))
            claras[ip] = claras.get(ip, 0) + 1

    # Veredicto más severo por IP dentro del lote.
    por_ip: dict[str, dict] = {}
    for d in decisiones:
        ip = str(d.get("entity_ip", ""))
        if not ip or ip in nunca:
            continue
        v = _verdicto_de(d)
        if v is None:
            continue
        accion, motivo, detector = v
        solo_modelo = motivo.startswith("modelo:")
        if solo_modelo and (not _modelo_claro(d)
                            or claras.get(ip, 0) < MIN_VENTANAS_MODELO):
            continue         # marginal o suelta: se registra, no se publica
        evento_ts = float(d.get("logged_at", 0))
        prev = por_ip.get(ip)
        if (prev is None
                or _SEVERIDAD[accion] > _SEVERIDAD[prev["accion"]]
                or (_SEVERIDAD[accion] == _SEVERIDAD[prev["accion"]]
                    and evento_ts > prev["evento_ts"])):
            por_ip[ip] = {"accion": accion, "motivo": motivo,
                          "detector": detector, "evento_ts": evento_ts}

    entradas = []
    for ip, v in sorted(por_ip.items()):
        esc = escalada.procesar(estado, ip, v["accion"], ahora,
                                evento_ts=v["evento_ts"])
        entradas.append({
            "ip": ip,
            "accion": esc["accion"],
            "hasta": round(ahora + esc["timeout_s"]),
            "alcance": alcance,
            "motivo": v["motivo"],
            "detector": v["detector"],
            "nivel": esc["nivel"],
            "revisar_humano": esc["revisar_humano"],
        })
    return entradas


def version_umbrales(declarada: str | None) -> tuple[str, str | None]:
    """Versión de heurísticos con la que se etiqueta el feed, y un aviso si procede.

    La etiqueta describe las reglas que de verdad aplica el código instalado, así
    que sale de `heuristicos.VERSION_UMBRALES`, no del argumento. Antes se tomaba
    tal cual de `--umbrales`, y una unidad que pasaba un valor viejo dejó feeds
    etiquetados `2026-10-06.1` mientras el motor aplicaba `.2`: la traza mentía
    sin que nada fallara. Si el argumento no coincide, se avisa y gana el código.
    """
    vigente = heuristicos.VERSION_UMBRALES
    if declarada and declarada != vigente:
        return vigente, ("--umbrales %r no coincide con la versión del código %r; "
                         "el feed se etiqueta con la del código" % (declarada, vigente))
    return vigente, None


def _leer_decisiones(log_path: Path, desde: float) -> list[dict]:
    out = []
    if not log_path.exists():
        return out
    with log_path.open(encoding="utf-8", errors="ignore") as fh:
        for linea in fh:
            try:
                d = json.loads(linea)
            except ValueError:
                continue
            if d.get("event") == "decision" and float(d.get("logged_at", 0)) >= desde:
                out.append(d)
    return out


LIBERACION_VALIDA_S = 600   # una petición «Preparar demo» viaja en el feed 10 min


def liberaciones_pedidas(ruta: Path | None, ahora: float) -> list[dict]:
    """Petición «Preparar demo» del panel -> [{id, ip, t}] para el feed firmado.

    El panel no toca ningún host: deja la petición; aquí entra en el feed que firma el
    sensor, y el agente de cada host la verifica y la aplica (liberar = quitar reglas)."""
    if ruta is None:
        return []
    try:
        pet = json.loads(Path(ruta).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return []
    if not isinstance(pet, dict):
        return []
    t, ident = pet.get("t"), str(pet.get("id") or "")
    if not isinstance(t, (int, float)) or not ident or not (0 <= ahora - t <= LIBERACION_VALIDA_S):
        return []
    out = []
    for ip in pet.get("ips") or []:
        try:
            ipaddress.ip_address(str(ip))
        except ValueError:
            continue
        out.append({"id": ident, "ip": str(ip), "t": float(t)})
    return out


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--log", type=Path, required=True, help="motor_decision.log")
    p.add_argument("--estado", type=Path, required=True, help="JSON de escalera (persiste)")
    p.add_argument("--clave-privada", type=Path, required=True)
    p.add_argument("--salida-feed", type=Path, required=True)
    p.add_argument("--salida-firma", type=Path, required=True)
    p.add_argument("--ventana-segundos", type=int, default=120,
                   help="solo decisiones de los últimos N s")
    p.add_argument("--peticion", type=Path, default=Path.home() / "feed" / "peticiones" / "preparar.json",
                   help="petición «Preparar demo» del panel (liberar las IP de la demo)")
    p.add_argument("--umbrales", default="",
                   help="obsoleto: la versión se toma de heuristicos.VERSION_UMBRALES; "
                        "si se pasa y no coincide, se avisa")
    a = p.parse_args()

    ahora = time.time()
    try:
        estado = json.loads(a.estado.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        estado = {}

    decisiones = _leer_decisiones(a.log, ahora - a.ventana_segundos)
    entradas = decisiones_a_entradas(decisiones, estado, ahora,
                                     NUNCA_BLOQUEAR_POR_DEFECTO)
    escalada.podar(estado, ahora)

    umbrales, aviso = version_umbrales(a.umbrales)
    if aviso:
        print("AVISO: " + aviso, file=sys.stderr)
    feed_obj = feed.construir(entradas, ahora=ahora, umbrales=umbrales)
    lib = liberaciones_pedidas(a.peticion, ahora)
    if lib:
        feed_obj["liberaciones"] = lib          # va dentro de lo firmado
    datos = feed.serializar(feed_obj)
    firma = feed.firmar(datos, str(a.clave_privada))

    a.salida_feed.write_bytes(datos)
    a.salida_firma.write_bytes(firma)
    a.estado.write_text(json.dumps(estado, sort_keys=True), encoding="utf-8")

    print(json.dumps({"entradas": len(entradas),
                      "block": sum(1 for e in entradas if e["accion"] == "BLOCK"),
                      "limit": sum(1 for e in entradas if e["accion"] == "LIMIT"),
                      "revisar_humano": [e["ip"] for e in entradas if e["revisar_humano"]]},
                     sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
