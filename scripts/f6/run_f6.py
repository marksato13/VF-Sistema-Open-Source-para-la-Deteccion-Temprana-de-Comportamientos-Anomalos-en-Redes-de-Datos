#!/usr/bin/env python3
"""Orquestador de la validación final F6 (motor + enforcement ACTIVOS).

Corre en VM01. Para cada corrida: marca la posición del log del motor en VM02,
dispara el escenario real (benigno desde VM05, ataque desde Kali VM04), espera a
que el motor procese, y extrae del propio motor_decision.log las decisiones de la
IP iniciadora en esa ventana. Mide, por corrida, cuántas ventanas alertaron, el
primer ALERT y el primer bloqueo (para lead-time), y la latencia de decisión.

No captura dataset ni toca los CSV congelados: solo lee el log del motor y
genera tráfico de laboratorio ya calibrado (ppi-run-benign / ppi-run-anomaly).
Idempotente por corrida: limpia el bloqueo de la IP objetivo al terminar cada
una para que la siguiente arranque en estado limpio.

Salida: results/f6/f6_resultados.jsonl (una línea por corrida) + un resumen.
"""
from __future__ import annotations

import json
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

SENSOR = "useransible@10.10.10.20"
CLIENT = "useransible@10.10.10.50"   # VM05, tráfico legítimo -> entity 10.20.0.20
KALI = "useransible@10.10.10.40"     # VM04, ataques          -> entity 10.20.0.100
LOG = "/home/useransible/ppi-motor-logs/motor_decision.log"
ENFORCE = "/usr/local/sbin/ppi-enforce"
SERVICES = ["ppi-motor.service", "ppi-motor-capture.service", "ppi-dashboard.service"]

CLIENT_IP = "10.20.0.20"
KALI_IP = "10.20.0.100"

SSH = ["ssh", "-o", "ConnectTimeout=8", "-o", "BatchMode=yes"]

OUT_DIR = Path(__file__).resolve().parents[2] / "results" / "f6"


def ssh(host: str, command: str, timeout: int = 120) -> tuple[int, str, str]:
    proc = subprocess.run(
        SSH + [host, command], capture_output=True, text=True, timeout=timeout
    )
    return proc.returncode, proc.stdout, proc.stderr


def sensor_now() -> float:
    """Reloj de VM02 (epoch), para alinear con logged_at del motor."""
    _, out, _ = ssh(SENSOR, "date +%s.%N")
    return float(out.strip())


def log_line_count() -> int:
    _, out, _ = ssh(SENSOR, f"wc -l < {LOG}")
    return int(out.strip() or "0")


def new_decisions(baseline: int, entity_ip: str) -> list[dict]:
    """Decisiones de una IP desde la línea `baseline` del log."""
    code, out, err = ssh(SENSOR, f"tail -n +{baseline + 1} {LOG}")
    rows = []
    for line in out.splitlines():
        try:
            e = json.loads(line)
        except json.JSONDecodeError:
            continue
        if e.get("event") != "decision" or e.get("entity_ip") != entity_ip:
            continue
        rows.append(e)
    return rows


def services_active() -> dict[str, bool]:
    _, out, _ = ssh(SENSOR, "systemctl is-active " + " ".join(SERVICES))
    states = out.split()
    return {svc: (states[i] == "active" if i < len(states) else False)
            for i, svc in enumerate(SERVICES)}


def unblock(ip: str) -> None:
    ssh(SENSOR, f"sudo -n {ENFORCE} list 2>/dev/null | grep -q {ip} && "
                f"sudo -n {ENFORCE} unblock {ip} || true")


def parse_eve_ts(ts: str) -> float:
    # window_end_utc formato "2026-08-18T15:03:00+00:00"
    return datetime.fromisoformat(ts).timestamp()


def latest_window_end_epoch() -> float | None:
    """Epoch del window_end más reciente que el motor ya emitió (su 'reloj de
    procesamiento'). Si el motor va atrasado, esto queda por detrás del reloj
    de pared; cuando alcanza, se acerca al presente."""
    code, out, _ = ssh(
        SENSOR,
        "grep '\"event\": \"decision\"' " + LOG + " | tail -1",
    )
    line = out.strip()
    if not line:
        return None
    try:
        return parse_eve_ts(json.loads(line)["window_end_utc"])
    except Exception:
        return None


def wait_for_catchup(until_epoch: float, cap_seconds: int, poll: int = 5,
                     idle_polls: int = 3) -> float:
    """Espera a que el motor procese ventanas cuyo window_end alcance
    `until_epoch` (ya digirió el tráfico hasta ese instante), o hasta
    `cap_seconds`. Devuelve el atraso final (wall - último window_end).

    Robustez ante red muda: si el motor NO emite ventanas nuevas durante
    `idle_polls` sondeos seguidos (log sin crecer), se asume que no hay tráfico
    pendiente que procesar -> está al día, y se retorna sin agotar el cap. Sin
    esto, entre corridas (red en silencio) el motor no emite nada y la espera
    agotaría el cap completo.
    """
    deadline = time.time() + cap_seconds
    lag = None
    last_lines = log_line_count()
    stable = 0
    while time.time() < deadline:
        wenb = latest_window_end_epoch()
        now = sensor_now()
        if wenb is not None:
            lag = now - wenb
            if wenb >= until_epoch:
                return lag
        lines = log_line_count()
        if lines == last_lines:
            stable += 1
            if stable >= idle_polls:  # log sin crecer -> motor al día (red muda)
                return lag if lag is not None else 0.0
        else:
            stable = 0
            last_lines = lines
        time.sleep(poll)
    return lag if lag is not None else float("nan")


def analyze_run(rows: list[dict], t_start: float) -> dict:
    n = len(rows)
    alerts = [r for r in rows if r.get("decision") == "ALERT"]
    permits = [r for r in rows if r.get("decision") == "PERMIT"]
    detectors: dict[str, int] = {}
    for r in rows:
        detectors[r.get("detector_name", "?")] = detectors.get(r.get("detector_name", "?"), 0) + 1
    first_alert = min(alerts, key=lambda r: r.get("logged_at", 0)) if alerts else None
    blocks = [r for r in alerts
              if isinstance(r.get("enforcement"), dict) and r["enforcement"].get("applied")]
    first_block = min(blocks, key=lambda r: r.get("logged_at", 0)) if blocks else None
    # latencia de decisión = logged_at - window_end (cuánto tras cerrar la ventana)
    latencies = []
    for r in rows:
        try:
            latencies.append(r["logged_at"] - parse_eve_ts(r["window_end_utc"]))
        except Exception:
            pass
    return {
        "windows_total": n,
        "windows_alert": len(alerts),
        "windows_permit": len(permits),
        "detectors": detectors,
        "detected": bool(alerts),
        "blocked": bool(blocks),
        "lead_time_s": (first_alert["logged_at"] - t_start) if first_alert else None,
        "block_latency_s": (first_block["logged_at"] - t_start) if first_block else None,
        "block_detector": first_block["detector_name"] if first_block else None,
        "decision_latency_p50_s": (sorted(latencies)[len(latencies) // 2]
                                   if latencies else None),
        "decision_latency_max_s": (max(latencies) if latencies else None),
    }


def run_one(run: dict, catchup_cap: int = 200) -> dict:
    label, kind = run["id"], run["kind"]
    host = CLIENT if run["source"] == "client" else KALI
    entity = CLIENT_IP if run["source"] == "client" else KALI_IP
    print(f"\n=== {label} [{kind}] {run['cmd']} (entity {entity}) ===", flush=True)

    # 1. Sondeo del atraso al empezar (el catchup-after de la corrida anterior
    #    ya dejó el motor al día; aquí solo se registra, no se espera).
    wend = latest_window_end_epoch()
    lag_before = (sensor_now() - wend) if wend is not None else 0.0

    svc_before = services_active()
    baseline = log_line_count()
    t_start = sensor_now()

    code, out, err = ssh(host, run["cmd"], timeout=run.get("timeout", 180))
    t_fired = sensor_now()
    scenario_ok = (code == 0)
    print(f"  escenario rc={code} (dur {t_fired - t_start:.1f}s, lag_prev="
          f"{lag_before:.0f}s)"
          + ("" if scenario_ok else f"  STDERR: {err.strip()[:200]}"), flush=True)

    # 2. Esperar a que el motor procese TODO el tráfico de esta corrida
    #    (window_end alcanza t_fired + margen), no un settle fijo. Así se
    #    capturan las detecciones tardías cuando el motor va atrasado.
    lag_after = wait_for_catchup(t_fired + 12, cap_seconds=catchup_cap)
    time.sleep(3)  # margen para que la última línea se escriba

    rows = new_decisions(baseline, entity)
    metrics = analyze_run(rows, t_start)
    svc_after = services_active()

    unblock(entity)  # dejar limpio para la siguiente corrida

    result = {
        "id": label, "kind": kind, "source": run["source"], "entity": entity,
        "cmd": run["cmd"], "scenario_rc": code, "scenario_ok": scenario_ok,
        "scenario_duration_s": round(t_fired - t_start, 2),
        "t_start_epoch": t_start,
        "lag_before_s": round(lag_before, 1) if lag_before == lag_before else None,
        "lag_after_s": round(lag_after, 1) if lag_after == lag_after else None,
        "services_before": svc_before, "services_after": svc_after,
        "services_stable": svc_before == svc_after and all(svc_after.values()),
        **metrics,
        "ts_utc": datetime.now(timezone.utc).isoformat(),
    }
    ld = metrics["lead_time_s"]
    print(f"  -> ventanas={metrics['windows_total']} alert={metrics['windows_alert']}"
          f" detectado={metrics['detected']} bloqueado={metrics['blocked']}"
          f" lead={('%.1fs' % ld) if ld is not None else '-'}"
          f" lag_after={lag_after:.0f}s detectores={metrics['detectors']}", flush=True)
    return result


# --- Matriz de corridas F6 completa ---------------------------------------
BENIGN = [
    {"id": "B01", "cmd": "/home/useransible/bin/ppi-run-benign http 100MB 10M", "timeout": 120},
    {"id": "B02", "cmd": "/home/useransible/bin/ppi-run-benign http 500MB 20M", "timeout": 180},
    {"id": "B03", "cmd": "/home/useransible/bin/ppi-run-benign https 100MB 10M", "timeout": 120},
    {"id": "B04", "cmd": "/home/useransible/bin/ppi-run-benign http-concurrent 4 100MB 5M", "timeout": 180},
    {"id": "B05", "cmd": "/home/useransible/bin/ppi-run-benign dns-valid 100", "timeout": 90},
    {"id": "B06", "cmd": "/home/useransible/bin/ppi-run-benign dns-mixed 50 50", "timeout": 90},
    {"id": "B07", "cmd": "/home/useransible/bin/ppi-run-benign api-normal 50", "timeout": 90},
    {"id": "B08", "cmd": "/home/useransible/bin/ppi-run-benign https-sessions 50", "timeout": 90},
    {"id": "B09", "cmd": "/home/useransible/bin/ppi-run-benign ping 100 0.5", "timeout": 90},
    {"id": "B10", "cmd": "/home/useransible/bin/ppi-run-benign mixed-light", "timeout": 220},
    {"id": "B11", "cmd": "/home/useransible/bin/ppi-run-benign http-multi 5", "timeout": 60},
    {"id": "B12", "cmd": "/home/useransible/bin/ppi-run-benign iperf-tcp 200M 30", "timeout": 90},
]
# Frontera del heurístico de fuerza bruta: un cliente legítimo que falla logins.
# count=4 (<5) NO debe disparar; count=10 (>=5) SÍ -> FP declarado del heurístico.
HEURISTIC_BOUNDARY = [
    {"id": "H01-authfail-4", "cmd": "/home/useransible/bin/ppi-run-benign api-auth-fail 4", "timeout": 60},
    {"id": "H02-authfail-10", "cmd": "/home/useransible/bin/ppi-run-benign api-auth-fail 10", "timeout": 60},
]
ATTACK = []
for fam, cmd in [
    ("syn-rate", "tcp-syn-rate 50"),
    ("port-scan", "port-scan-wide 1-1000"),
    ("udp-probe", "udp-probe 50"),
    ("password-spray", "password-spray 50"),
    ("dns-entropy", "dns-entropy 50"),
]:
    for rep in (1, 2, 3):
        ATTACK.append({"id": f"A-{fam}-{rep}",
                       "cmd": f"/home/useransible/bin/ppi-run-anomaly {cmd}",
                       "timeout": 120})


def build_matrix() -> list[dict]:
    runs = []
    for r in BENIGN + HEURISTIC_BOUNDARY:
        runs.append({**r, "kind": "benign", "source": "client"})
    for r in ATTACK:
        runs.append({**r, "kind": "attack", "source": "kali"})
    return runs


def main() -> int:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    results_path = OUT_DIR / "f6_resultados.jsonl"
    runs = build_matrix()
    only = sys.argv[1] if len(sys.argv) > 1 else None
    if only:
        runs = [r for r in runs if r["id"].startswith(only) or r["kind"] == only]

    print(f"F6: {len(runs)} corridas. Salida -> {results_path}", flush=True)
    # limpiar estado inicial
    unblock(CLIENT_IP)
    unblock(KALI_IP)

    with results_path.open("a", encoding="utf-8") as fh:
        for run in runs:
            try:
                res = run_one(run)
            except subprocess.TimeoutExpired as exc:
                res = {"id": run["id"], "kind": run["kind"], "error": f"timeout: {exc}"}
                print(f"  !! TIMEOUT en {run['id']}", flush=True)
            fh.write(json.dumps(res, sort_keys=True) + "\n")
            fh.flush()

    print("\nF6 completo. Analiza con scripts/f6/analyze_f6.py", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
