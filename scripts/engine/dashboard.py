#!/usr/bin/env python3
"""Dashboard operativo de solo lectura para el motor de tiempo real en VM02.

Complementario, no reemplaza otras herramientas de monitoreo (journalctl,
SSH directo al helper de enforcement). No ejecuta ninguna accion: solo lee
el log del motor, el estado del set nftables de enforcement (via el mismo
helper root ya autorizado, subcomando "list" de solo lectura) y el estado de
los servicios systemd relevantes. Ver diseno completo, justificacion de
arquitectura y manual de instalacion/usuario en
docs/06-features-modelado/10-diseno-dashboard-motor.md.

Sin dependencias externas a proposito: corre con /usr/bin/python3 del
sistema, no con el venv del motor (que tiene scikit-learn/numpy, innecesario
aqui). VM02 esta aislada de internet; agregar una dependencia nueva (p.ej.
Flask) repetiria el esfuerzo de aprovisionamiento offline ya hecho para el
venv del motor, para una ganancia marginal frente a polling simple.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

HTML = """<!doctype html><meta charset="utf-8"><title>PPI - motor en vivo</title>
<style>
body{font:15px system-ui;margin:2rem;background:#10151c;color:#e8eef5}
h1{color:#7dd3fc;margin-bottom:.2rem}
.sub{color:#94a3b8;margin-top:0}
.grid{display:flex;gap:1rem;flex-wrap:wrap;margin:1rem 0}
.card{background:#1b2633;padding:1rem;border-radius:10px;min-width:170px}
.ok{color:#4ade80}.bad{color:#f87171}
table{border-collapse:collapse;width:100%;margin-top:.5rem}
td,th{padding:.4rem .6rem;border-bottom:1px solid #334155;text-align:left;font-size:.92rem}
code{color:#bae6fd}
.alert{color:#f87171;font-weight:600}
.permit{color:#4ade80}
.heur{color:#94a3b8}
h2{margin-top:2rem;border-bottom:1px solid #334155;padding-bottom:.3rem}
</style>
<h1>Sistema PPI &mdash; motor en vivo</h1>
<p class="sub">Solo lectura, complementario. Se actualiza cada 5s. <span id="stamp"></span></p>

<h2>Salud del sistema</h2>
<div class="grid" id="health"></div>

<h2>Modelo congelado</h2>
<div class="grid" id="model"></div>

<h2>IPs bloqueadas ahora</h2>
<table><thead><tr><th>IP</th><th>Expira en</th></tr></thead><tbody id="blocked"></tbody></table>

<h2>Actividad reciente</h2>
<div class="grid" id="counters"></div>
<table><thead><tr><th>Hora</th><th>IP</th><th>Decision</th><th>Detector</th><th>Score</th><th>Paquetes</th></tr></thead><tbody id="decisions"></tbody></table>

<script>
function card(title, value, cls) {
  return `<div class="card"><b>${title}</b><br><span class="${cls||''}">${value}</span></div>`;
}
function fmtTime(t) {
  return new Date(t * 1000).toLocaleTimeString();
}
async function refresh() {
  try {
    const status = await (await fetch('/api/status')).json();
    stamp.textContent = 'Actualizado: ' + new Date().toLocaleTimeString();

    health.innerHTML = Object.entries(status.services).map(([name, active]) =>
      card(name, active ? 'activo' : 'INACTIVO', active ? 'ok' : 'bad')
    ).join('');

    const m = status.model;
    model.innerHTML = [
      card('Detector', m.detector_name),
      card('Umbral', m.threshold.toFixed(4)),
      card('FPR benigno (test)', (m.test_fpr * 100).toFixed(2) + '%'),
      card('Deteccion global', (m.detection_rate * 100).toFixed(1) + '%'),
      card('Deteccion Kali-real', (m.kali_real_detection_rate * 100).toFixed(1) + '%'),
    ].join('');

    blocked.innerHTML = status.blocked.length
      ? status.blocked.map(b => `<tr><td><code>${b.ip}</code></td><td>${b.expires_seconds != null ? b.expires_seconds + 's' : '?'}</td></tr>`).join('')
      : '<tr><td colspan="2">Ninguna IP bloqueada ahora.</td></tr>';

    const c = status.counters;
    counters.innerHTML = [
      card('Ultima hora, total', c.total),
      card('ALERT (modelo)', c.alert_model, c.alert_model > 0 ? 'alert' : ''),
      card('PERMIT (modelo)', c.permit_model, 'permit'),
      card('PERMIT (ventana vacia)', c.permit_heuristic, 'heur'),
    ].join('');

    const decisions = await (await fetch('/api/decisions?limit=100')).json();
    document.getElementById('decisions').innerHTML = decisions.map(d => {
      const cls = d.decision === 'ALERT' ? 'alert' : (d.detector_name === 'empty_window_heuristic' ? 'heur' : 'permit');
      return `<tr><td>${fmtTime(d.logged_at)}</td><td><code>${d.entity_ip}</code></td>` +
        `<td class="${cls}">${d.decision}</td><td>${d.detector_name}</td>` +
        `<td>${d.score != null ? d.score.toFixed(4) : '&mdash;'}</td><td>${d.packet_count_10s}</td></tr>`;
    }).join('') || '<tr><td colspan="6">Sin decisiones recientes.</td></tr>';
  } catch (e) {
    stamp.textContent = 'Error al actualizar: ' + e;
  }
}
refresh();
setInterval(refresh, 5000);
</script>
"""


def tail_lines(path: Path, max_bytes: int = 1_048_576) -> list[str]:
    if not path.exists():
        return []
    size = path.stat().st_size
    with path.open("rb") as handle:
        handle.seek(max(0, size - max_bytes))
        chunk = handle.read()
    text = chunk.decode("utf-8", errors="replace")
    lines = text.split("\n")
    return [line for line in lines[1:] if line.strip()] if size > max_bytes else [
        line for line in lines if line.strip()
    ]


def read_decisions(log_path: Path, limit: int) -> list[dict]:
    records = []
    for line in tail_lines(log_path):
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            continue
        if event.get("event") == "decision":
            records.append(event)
    records.sort(key=lambda item: item.get("logged_at", 0))
    return records[-limit:][::-1]


def compute_counters(decisions: list[dict], window_seconds: int = 3600) -> dict:
    now = time.time()
    recent = [d for d in decisions if now - d.get("logged_at", 0) <= window_seconds]
    alert_model = sum(1 for d in recent if d["decision"] == "ALERT")
    permit_heuristic = sum(1 for d in recent if d.get("detector_name") == "empty_window_heuristic")
    permit_model = sum(
        1 for d in recent if d["decision"] == "PERMIT" and d.get("detector_name") != "empty_window_heuristic"
    )
    return {
        "total": len(recent),
        "alert_model": alert_model,
        "permit_model": permit_model,
        "permit_heuristic": permit_heuristic,
    }


def service_status(names: list[str]) -> dict[str, bool]:
    try:
        result = subprocess.run(
            ["systemctl", "is-active", *names],
            capture_output=True,
            text=True,
            timeout=5,
            check=False,
        )
    except (subprocess.TimeoutExpired, OSError):
        return {name: False for name in names}
    outputs = result.stdout.strip().split("\n")
    return {name: (outputs[i].strip() == "active" if i < len(outputs) else False) for i, name in enumerate(names)}


def enforcement_list(enforce_command: str) -> list[dict]:
    try:
        result = subprocess.run(
            ["sudo", "-n", enforce_command, "list"],
            capture_output=True,
            text=True,
            timeout=10,
            check=False,
        )
    except (subprocess.TimeoutExpired, OSError):
        return []
    if result.returncode != 0:
        return []
    try:
        return json.loads(result.stdout)
    except json.JSONDecodeError:
        return []


def load_model_summary(manifest_path: Path, detector_name: str) -> dict:
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    detector_eval = manifest["evaluation"][detector_name]
    return {
        "detector_name": detector_name,
        "threshold": float(detector_eval["threshold_used"]),
        "test_fpr": float(detector_eval["test"]["fpr"]),
        "detection_rate": float(detector_eval["anomalies"]["detection_rate"]),
        "kali_real_detection_rate": float(detector_eval["anomalies"]["kali_real_detection_rate"]),
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--log-path",
        type=Path,
        default=Path("/home/useransible/ppi-motor-logs/motor_decision.log"),
    )
    parser.add_argument(
        "--manifest-path",
        type=Path,
        default=Path("/home/useransible/ppi-motor-model/manifest.json"),
    )
    parser.add_argument("--detector-name", default="ocsvm_scaled")
    parser.add_argument("--enforce-command", default="/usr/local/sbin/ppi-enforce")
    parser.add_argument(
        "--services",
        default="ppi-motor.service,ppi-motor-capture.service,suricata.service",
    )
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8788)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    service_names = [name.strip() for name in args.services.split(",") if name.strip()]
    model_summary = load_model_summary(args.manifest_path, args.detector_name)

    class Handler(BaseHTTPRequestHandler):
        def _send_json(self, payload: dict | list) -> None:
            body = json.dumps(payload).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def do_GET(self) -> None:  # noqa: N802
            path, _, query = self.path.partition("?")
            if path == "/":
                body = HTML.encode("utf-8")
                self.send_response(200)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)
                return
            if path == "/api/status":
                decisions = read_decisions(args.log_path, limit=2000)
                self._send_json(
                    {
                        "services": service_status(service_names),
                        "model": model_summary,
                        "blocked": enforcement_list(args.enforce_command),
                        "counters": compute_counters(decisions),
                    }
                )
                return
            if path == "/api/decisions":
                params = dict(pair.split("=") for pair in query.split("&") if "=" in pair)
                limit = int(params.get("limit", "100"))
                self._send_json(read_decisions(args.log_path, limit=limit))
                return
            self.send_error(404)

        def log_message(self, *args_: object) -> None:  # silencioso, evita ruido en journal
            pass

    print(f"Dashboard: http://{args.host}:{args.port}/")
    ThreadingHTTPServer((args.host, args.port), Handler).serve_forever()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
