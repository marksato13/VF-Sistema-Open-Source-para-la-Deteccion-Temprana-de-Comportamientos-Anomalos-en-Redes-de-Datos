#!/usr/bin/env python3
"""Genera decisiones de EJEMPLO para el modo demo del panel.

No son mediciones reales: cada línea lleva ``"demo": true`` y sirve solo para
que, en un clon recién hecho, el panel se vea funcionando sin red ni sensor.
Los tiempos se generan relativos a AHORA, así que la actividad de la última hora
siempre aparece poblada, se ejecute el demo cuando se ejecute.

    python3 scripts/demo_datos.py --salida /tmp/cyberflow-demo/motor_decision.log
"""
from __future__ import annotations

import argparse
import json
import random
import time
from datetime import datetime, timezone
from pathlib import Path

# Umbral real del modelo congelado (artifacts/model/manifest.json, ocsvm_scaled).
# La regla del motor: ALERT si score < umbral, PERMIT si score >= umbral.
UMBRAL = 1.8126087939765134

CLIENTES = ["10.10.20.21", "10.10.20.34", "10.10.20.51"]
SERVIDOR = "10.10.30.5"
ATACANTE = "10.10.30.10"


def iso(ts: float) -> str:
    return datetime.fromtimestamp(ts, timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def decision(ts, ip, decision_, detector, score, pkts):
    return {
        "event": "decision",
        "demo": True,
        "logged_at": round(ts, 3),
        "entity_ip": ip,
        "window_end_utc": iso(ts),
        "history_coverage_s": 60,
        "packet_count_10s": pkts,
        "detector_name": detector,
        "score": score,
        "threshold": UMBRAL,
        "decision": decision_,
        # Contadores de alcance de ejemplo (constantes en el demo).
        "excluidas_acumulado": 0,
        "plano_control_descartado": 21000,
        "duplicados_espejo": 288,
        "pcaps_ilegibles": 0,
        "pcaps_ilegibles_motivo": None,
    }


def generar(minutos: int, semilla: int) -> list[dict]:
    rng = random.Random(semilla)
    ahora = time.time()
    filas = []
    for m in range(minutos, -1, -1):
        ts_base = ahora - m * 60
        # Tráfico legítimo de fondo: 2–3 clientes, PERMIT (score por encima del umbral).
        for ip in rng.sample(CLIENTES, k=rng.choice([2, 3])):
            filas.append(decision(ts_base + rng.uniform(0, 55), ip, "PERMIT",
                                  "ocsvm_scaled", round(rng.uniform(1.83, 2.15), 4),
                                  rng.randint(40, 400)))
        # El servidor responde: PERMIT.
        filas.append(decision(ts_base + rng.uniform(0, 55), SERVIDOR, "PERMIT",
                              "ocsvm_scaled", round(rng.uniform(1.84, 2.05), 4),
                              rng.randint(60, 300)))
        # Alguna ventana sin paquetes: heurístico, PERMIT sin score.
        if m % 7 == 0:
            filas.append(decision(ts_base + rng.uniform(0, 55), rng.choice(CLIENTES),
                                  "PERMIT", "empty_window_heuristic", None, 0))
        # Ráfaga de ataque en una ventana reciente: ALERT (score por debajo del umbral).
        if 2 <= m <= 6:
            filas.append(decision(ts_base + rng.uniform(0, 55), ATACANTE, "ALERT",
                                  "ocsvm_scaled", round(rng.uniform(1.45, 1.79), 4),
                                  rng.randint(900, 1900)))
    # Una alerta de fuerza bruta por L7, para mostrar el heurístico.
    filas.append(decision(ahora - 90, ATACANTE, "ALERT", "auth_failure_heuristic",
                          round(rng.uniform(1.6, 1.8), 4), 120))
    filas.sort(key=lambda d: d["logged_at"])
    return filas


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--salida", type=Path, required=True)
    p.add_argument("--minutos", type=int, default=60)
    p.add_argument("--semilla", type=int, default=13)
    a = p.parse_args()
    filas = generar(a.minutos, a.semilla)
    a.salida.parent.mkdir(parents=True, exist_ok=True)
    with a.salida.open("w", encoding="utf-8") as f:
        for d in filas:
            f.write(json.dumps(d, sort_keys=True) + "\n")
    n_alert = sum(1 for d in filas if d["decision"] == "ALERT")
    print("escrito %s · %d decisiones de ejemplo (%d ALERT) · marcadas demo:true"
          % (a.salida, len(filas), n_alert))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
