#!/usr/bin/env python3
"""Simula un ataque de punta a punta en el registro del modo DEMO del panel.

Escribe, ventana a ventana y en tiempo real, las decisiones que el motor
produciria ante el ataque: primero trafico normal, luego la rafaga. Las acciones
y los motivos NO se inventan: cada fila pasa por el mismo motor de reglas que
usa el sensor (``heuristicos.evaluar``). Asi el recorrido completo se ve en el
panel: la alerta flotante, la accion en «Decisiones recientes» y la IP en
«IPs bloqueadas ahora» con su cuenta atras.

    python3 scripts/simular_ataque.py --log /tmp/cyberflow-demo/motor_decision.log --ataque escaneo
    python3 scripts/simular_ataque.py --log ... --ataque todos

Seguridad: se niega a escribir en un registro con decisiones reales. Si lo
hiciera, el publicador del feed las convertiria en un BLOCK real en el host.
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / "engine"))
import heuristicos  # noqa: E402

UMBRAL_POR_OMISION = -0.568892      # umbral score_samples del IF desplegado

# Cada ataque: ip atacante, distancia del score al umbral en la rafaga (negativa
# = por debajo = anomalia) y las variables que mira cada regla. El umbral se lee
# del propio registro, asi el score cae en la escala del modelo del panel.
ATAQUES = {
    "escaneo": {
        "ip": "10.10.20.30", "delta": -0.14, "paquetes": 950,
        "fila": {"flow_attempt_count_30s": 1180, "unique_dst_port_ratio_30s": 0.48,
                 "syn_completion_ratio_10s": 0.02},
    },
    "dns": {
        # El modelo no ve el DNS de alta entropia (0/8 en la nota M): PERMIT del
        # modelo y LIMIT de la regla. Igual que en el sensor.
        "ip": "10.10.20.30", "delta": 0.16, "paquetes": 85,
        "fila": {"dns_query_count_60s": 82, "dns_nxdomain_ratio_60s": 0.62,
                 "unique_dns_name_ratio_60s": 0.50},
    },
    "fuerza-bruta": {
        "ip": "10.10.20.30", "delta": 0.13, "paquetes": 260,
        "fila": {"http_request_count_60s": 240, "http_auth_failure_ratio_60s": 1.0},
    },
    "http": {
        "ip": "10.10.20.34", "delta": -0.09, "paquetes": 1400,
        "fila": {"http_request_count_60s": 410, "http_auth_failure_ratio_60s": 0.02},
    },
    "modelo": {
        # Anomalia sin regla: solo el modelo la ve -> LIMIT.
        "ip": "10.10.20.51", "delta": -0.05, "paquetes": 120, "fila": {},
    },
}


def umbral_del_registro(ruta: Path) -> float:
    """El umbral de la ultima decision del registro (la escala del modelo del panel)."""
    umbral = UMBRAL_POR_OMISION
    if ruta.exists():
        with ruta.open(encoding="utf-8", errors="ignore") as fh:
            for linea in fh:
                if '"threshold"' in linea:
                    try:
                        umbral = float(json.loads(linea)["threshold"])
                    except (ValueError, KeyError, TypeError):
                        pass
    return umbral


def registro_es_demo(ruta: Path) -> bool:
    """Vacio, inexistente o solo con decisiones marcadas demo."""
    if not ruta.exists() or ruta.stat().st_size == 0:
        return True
    with ruta.open(encoding="utf-8", errors="ignore") as fh:
        for linea in fh:
            if '"decision"' not in linea:
                continue
            try:
                if not json.loads(linea).get("demo"):
                    return False
            except ValueError:
                continue
    return True


def decision(ip: str, score: float, umbral: float, paquetes: int, fila: dict,
             detector: str, t: float) -> dict:
    h = heuristicos.evaluar(fila) if fila else None
    return {
        "event": "decision", "demo": True, "simulado": True,
        "logged_at": round(t, 3), "entity_ip": ip,
        "window_end_utc": datetime.fromtimestamp(t, timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "history_coverage_s": 60,
        "decision": "ALERT" if score < umbral else "PERMIT",
        "detector_name": detector, "score": round(score, 6), "threshold": umbral,
        "packet_count_10s": paquetes, "heuristico": h,
    }


def simular(log: Path, nombre: str, detector: str, ventanas: int, intervalo: float) -> list[dict]:
    a = ATAQUES[nombre]
    umbral = umbral_del_registro(log)
    escritas = []
    with log.open("a", encoding="utf-8") as fh:
        for i in range(ventanas):
            t = time.time()
            if i == 0:      # la ventana anterior al ataque: normal
                d = decision(a["ip"], umbral + 0.26, umbral, 40, {}, detector, t)
            else:
                d = decision(a["ip"], umbral + a["delta"], umbral, a["paquetes"], a["fila"], detector, t)
            fh.write(json.dumps(d, ensure_ascii=False) + "\n")
            fh.flush()
            escritas.append(d)
            accion = (d["heuristico"] or {}).get("accion") or ("LIMIT" if d["decision"] == "ALERT" else "PERMIT")
            print("%s  %-12s %-6s %s" % (d["window_end_utc"], d["entity_ip"], accion,
                                         (d["heuristico"] or {}).get("motivo", "")))
            if i < ventanas - 1:
                time.sleep(intervalo)
    return escritas


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--log", type=Path, required=True, help="registro del panel en modo demo")
    p.add_argument("--ataque", choices=sorted(ATAQUES) + ["todos"], default="escaneo")
    p.add_argument("--detector", default="ocsvm_scaled",
                   help="nombre del detector del modelo (el del manifiesto del panel)")
    p.add_argument("--ventanas", type=int, default=5)
    p.add_argument("--intervalo", type=float, default=3.0, help="segundos reales entre ventanas")
    a = p.parse_args(argv)

    if not registro_es_demo(a.log):
        print("Este registro tiene decisiones reales: no se simula aqui. El publicador del "
              "feed convertiria lo simulado en un BLOCK real en el host. Use el registro "
              "del modo demo.", file=sys.stderr)
        return 2
    a.log.parent.mkdir(parents=True, exist_ok=True)
    nombres = sorted(ATAQUES) if a.ataque == "todos" else [a.ataque]
    for n in nombres:
        print("== %s" % n)
        simular(a.log, n, a.detector, a.ventanas, a.intervalo)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
