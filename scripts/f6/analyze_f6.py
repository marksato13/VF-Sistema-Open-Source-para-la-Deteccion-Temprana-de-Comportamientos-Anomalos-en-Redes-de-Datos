#!/usr/bin/env python3
"""Agrega f6_resultados.jsonl en las métricas de la validación final F6.

Métricas producidas (todas derivadas del log real del motor, sin inventar):
- FPR operativo: fracción de ventanas benignas que el motor marcó ALERT.
- Tasa de detección por familia de ataque: fracción de corridas con >=1 ALERT.
- Lead-time de detección: tiempo desde el inicio del ataque al primer ALERT
  (y al primer bloqueo), por familia.
- Latencia de decisión: logged_at - window_end (cuánto tras cerrar la ventana).
- Disponibilidad: fracción de corridas con los 3 servicios activos antes y después.
- Frontera del heurístico de fuerza bruta (corridas H*).
"""
from __future__ import annotations

import json
import statistics
from collections import defaultdict
from pathlib import Path

RESULTS = Path(__file__).resolve().parents[2] / "results" / "f6" / "f6_resultados.jsonl"


def load() -> list[dict]:
    rows = []
    for line in RESULTS.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line:
            rows.append(json.loads(line))
    return rows


def family_of(run_id: str) -> str:
    # A-<familia>-<rep>
    parts = run_id.split("-")
    return "-".join(parts[1:-1]) if run_id.startswith("A-") else run_id


def pct(x: float) -> str:
    return f"{100 * x:.2f}%"


def main() -> int:
    rows = [r for r in load() if "error" not in r]
    benign = [r for r in rows if r["kind"] == "benign" and not r["id"].startswith("H")]
    heuristic = [r for r in rows if r["id"].startswith("H")]
    attack = [r for r in rows if r["kind"] == "attack"]

    print("=" * 70)
    print("VALIDACIÓN FINAL F6 — RESUMEN")
    print("=" * 70)

    # --- FPR operativo (solo benignos puros; el heurístico se reporta aparte) ---
    tot_win = sum(r["windows_total"] for r in benign)
    tot_alert = sum(r["windows_alert"] for r in benign)
    runs_with_fp = [r for r in benign if r["windows_alert"] > 0]
    print(f"\n[FPR OPERATIVO]  ventanas benignas: {tot_win} | ALERT: {tot_alert}"
          f" | FPR = {pct(tot_alert / tot_win) if tot_win else 'n/a'}")
    print(f"  corridas benignas con al menos un FP: {len(runs_with_fp)}/{len(benign)}")
    for r in benign:
        flag = "  <-- FP" if r["windows_alert"] > 0 else ""
        print(f"    {r['id']:20s} win={r['windows_total']:3d} alert={r['windows_alert']:2d}"
              f" detectores={r['detectors']}{flag}")

    # --- Detección por familia ---
    print("\n[DETECCIÓN POR FAMILIA DE ATAQUE]")
    by_fam = defaultdict(list)
    for r in attack:
        by_fam[family_of(r["id"])].append(r)
    for fam, runs in sorted(by_fam.items()):
        detected = sum(1 for r in runs if r["detected"])
        blocked = sum(1 for r in runs if r["blocked"])
        leads = [r["lead_time_s"] for r in runs if r["lead_time_s"] is not None]
        dets = defaultdict(int)
        for r in runs:
            for d, c in r["detectors"].items():
                if d not in ("empty_window_heuristic", "no_live_packets_heuristic"):
                    dets[d] += c
        lead_str = (f"lead med={statistics.median(leads):.1f}s "
                    f"[{min(leads):.1f}-{max(leads):.1f}]" if leads else "lead=-")
        print(f"  {fam:16s} detectado {detected}/{len(runs)} | bloqueado {blocked}/{len(runs)}"
              f" | {lead_str} | detectores={dict(dets)}")

    # --- Lead-time global ---
    all_leads = [r["lead_time_s"] for r in attack if r["lead_time_s"] is not None]
    all_blocks = [r["block_latency_s"] for r in attack if r["block_latency_s"] is not None]
    if all_leads:
        print(f"\n[LEAD-TIME GLOBAL]  primer ALERT: med={statistics.median(all_leads):.1f}s"
              f" p95={sorted(all_leads)[int(0.95 * len(all_leads)) - 1]:.1f}s"
              f" rango [{min(all_leads):.1f}-{max(all_leads):.1f}]")
    if all_blocks:
        print(f"[LEAD-TIME BLOQUEO] primer bloqueo: med={statistics.median(all_blocks):.1f}s"
              f" rango [{min(all_blocks):.1f}-{max(all_blocks):.1f}]")

    # --- Latencia de decisión (todas las corridas) ---
    lat_p50 = [r["decision_latency_p50_s"] for r in rows if r.get("decision_latency_p50_s") is not None]
    lat_max = [r["decision_latency_max_s"] for r in rows if r.get("decision_latency_max_s") is not None]
    if lat_p50:
        print(f"\n[LATENCIA DE DECISIÓN]  p50 típico={statistics.median(lat_p50):.1f}s"
              f" | máx observado={max(lat_max):.1f}s (logged_at - window_end)")

    # --- Disponibilidad ---
    stable = sum(1 for r in rows if r.get("services_stable"))
    print(f"\n[DISPONIBILIDAD]  corridas con 3 servicios activos y estables:"
          f" {stable}/{len(rows)} = {pct(stable / len(rows)) if rows else 'n/a'}")

    # --- Frontera del heurístico ---
    print("\n[FRONTERA DEL HEURÍSTICO DE FUERZA BRUTA] (cliente legítimo con 401)")
    for r in heuristic:
        fired = any(d == "auth_failure_heuristic" for d in r["detectors"])
        print(f"  {r['id']:20s} alert={r['windows_alert']} bloqueado={r['blocked']}"
              f" heuristico={'SÍ' if fired else 'no'} detectores={r['detectors']}")

    print("\n" + "=" * 70)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
