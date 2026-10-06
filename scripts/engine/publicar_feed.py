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
import json
import time
from pathlib import Path

try:
    from scripts.engine import escalada, feed
except ImportError:  # ejecutado desde scripts/engine/
    import escalada
    import feed

# Infra que NUNCA se bloquea, pase lo que pase (coincide con responder_iptables).
NUNCA_BLOQUEAR_POR_DEFECTO = {
    "10.10.10.30",   # bastión
    "10.10.60.11",   # sensor
    "10.10.30.1", "10.10.40.1", "10.10.60.1", "10.10.20.1",  # gateways VLAN
    "10.10.10.20",   # DNS/AD
}

_SEVERIDAD = {"BLOCK": 2, "LIMIT": 1}


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
    return max(candidatos, key=lambda c: _SEVERIDAD[c[0]])


def decisiones_a_entradas(decisiones: list[dict], estado: dict, ahora: float,
                          nunca: set[str], alcance="all") -> list[dict]:
    """Núcleo puro: agrega por IP el veredicto más severo, aplica escalera.

    Devuelve la lista de entradas del feed. Muta `estado` (para persistir).
    """
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
        prev = por_ip.get(ip)
        if prev is None or _SEVERIDAD[accion] > _SEVERIDAD[prev["accion"]]:
            por_ip[ip] = {"accion": accion, "motivo": motivo, "detector": detector}

    entradas = []
    for ip, v in sorted(por_ip.items()):
        esc = escalada.procesar(estado, ip, v["accion"], ahora)
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


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--log", type=Path, required=True, help="motor_decision.log")
    p.add_argument("--estado", type=Path, required=True, help="JSON de escalera (persiste)")
    p.add_argument("--clave-privada", type=Path, required=True)
    p.add_argument("--salida-feed", type=Path, required=True)
    p.add_argument("--salida-firma", type=Path, required=True)
    p.add_argument("--ventana-segundos", type=int, default=120,
                   help="solo decisiones de los últimos N s")
    p.add_argument("--umbrales", default="", help="versión de heurísticos, para trazar")
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

    feed_obj = feed.construir(entradas, ahora=ahora, umbrales=a.umbrales)
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
