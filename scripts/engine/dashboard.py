#!/usr/bin/env python3
"""Dashboard operativo de solo lectura para el motor de tiempo real en VM02.

Complementario, no reemplaza otras herramientas de monitoreo (journalctl,
SSH directo al helper de enforcement). No ejecuta ninguna accion: solo lee
el log del motor, el estado del set nftables de enforcement (via el mismo
helper root ya autorizado, subcomando "list" de solo lectura) y el estado de
los servicios systemd relevantes. Ver diseno completo, justificacion de
arquitectura y manual de instalacion/usuario en
docs/fase06-dashboard/01-diseno-dashboard-motor.md.

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

HTML = """<!doctype html>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>PPI &middot; motor en vivo</title>
<style>
  :root {
    --bg: #0a0f1a;
    --surface: #121a2b;
    --surface-2: #1a2338;
    --border: #253150;
    --text: #dbe4f2;
    --text-dim: #7c8bad;
    --accent: #5eead4;
    --ok: #4ade80; --ok-soft: #12271c;
    --amber: #f0b429; --amber-soft: #332508;
    --danger: #f87171; --danger-soft: #351515;
    --mono: ui-monospace, "Cascadia Code", "Roboto Mono", "SF Mono", Menlo, Consolas, monospace;
    --sans: ui-sans-serif, system-ui, "Segoe UI", Helvetica, Arial, sans-serif;
  }
  * { box-sizing: border-box; }
  body {
    margin: 0; background: var(--bg); color: var(--text);
    font-family: var(--sans); font-size: 15px; line-height: 1.5;
  }
  .wrap { max-width: 1080px; margin: 0 auto; padding: 1.6rem 1.4rem 4rem; }
  header { display: flex; justify-content: space-between; align-items: flex-end; flex-wrap: wrap; gap: 0.8rem; margin-bottom: 1.4rem; }
  h1 { font-size: 1.35rem; margin: 0; letter-spacing: -0.01em; }
  h1 small { display: block; font-family: var(--mono); font-size: 0.72rem; color: var(--text-dim); font-weight: 400; margin-top: 0.15rem; letter-spacing: 0.04em; text-transform: uppercase; }
  .stamp { font-family: var(--mono); font-size: 0.78rem; color: var(--text-dim); }

  .healthbar {
    display: flex; align-items: center; gap: 0.7rem;
    padding: 0.85rem 1.1rem; border-radius: 12px; margin-bottom: 1.6rem;
    border: 1px solid var(--border); background: var(--surface);
  }
  .healthbar.ok { border-color: color-mix(in srgb, var(--ok) 45%, var(--border)); }
  .healthbar.warn { border-color: color-mix(in srgb, var(--amber) 45%, var(--border)); }
  .healthbar.bad { border-color: color-mix(in srgb, var(--danger) 45%, var(--border)); }
  .healthbar .dot { width: 10px; height: 10px; border-radius: 50%; flex: none; }
  .healthbar.ok .dot { background: var(--ok); box-shadow: 0 0 8px var(--ok); }
  .healthbar.warn .dot { background: var(--amber); box-shadow: 0 0 8px var(--amber); }
  .healthbar.bad .dot { background: var(--danger); box-shadow: 0 0 8px var(--danger); }
  .healthbar .msg { font-weight: 600; }
  .healthbar .sub { color: var(--text-dim); font-size: 0.86rem; }

  section { margin-bottom: 2.2rem; }
  .sec-head { display: flex; align-items: center; gap: 0.55rem; margin-bottom: 0.8rem; color: var(--text-dim); }
  .sec-head svg { color: var(--accent); flex: none; }
  .sec-head h2 { font-size: 0.82rem; text-transform: uppercase; letter-spacing: 0.08em; font-weight: 600; margin: 0; color: var(--text-dim); }

  .grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(160px, 1fr)); gap: 0.8rem; }
  .card {
    background: var(--surface); border: 1px solid var(--border); border-left: 3px solid var(--border);
    border-radius: 10px; padding: 0.8rem 1rem;
  }
  .card.ok { border-left-color: var(--ok); }
  .card.bad { border-left-color: var(--danger); }
  .card .label { font-size: 0.74rem; color: var(--text-dim); text-transform: uppercase; letter-spacing: 0.04em; }
  .card .value { font-family: var(--mono); font-size: 1.25rem; font-weight: 700; margin-top: 0.15rem; font-variant-numeric: tabular-nums; }
  .card.ok .value { color: var(--ok); }
  .card.bad .value { color: var(--danger); }
  .card.accent .value { color: var(--accent); }
  .card.amber .value { color: var(--amber); }

  .note {
    display: flex; gap: 0.6rem; align-items: flex-start;
    border-left: 3px solid var(--amber); background: var(--amber-soft);
    border-radius: 0 10px 10px 0; padding: 0.7rem 1rem; font-size: 0.86rem; color: var(--text);
  }
  .note svg { color: var(--amber); flex: none; margin-top: 0.1rem; }

  .spark-wrap { background: var(--surface); border: 1px solid var(--border); border-radius: 10px; padding: 0.9rem 1rem; overflow-x: auto; }
  .spark-legend { display: flex; gap: 1.1rem; font-size: 0.76rem; color: var(--text-dim); margin-top: 0.5rem; }
  .spark-legend span { display: inline-flex; align-items: center; gap: 0.35rem; }
  .swatch { width: 9px; height: 9px; border-radius: 2px; display: inline-block; }

  table { border-collapse: collapse; width: 100%; font-size: 0.86rem; }
  .tbl-wrap { background: var(--surface); border: 1px solid var(--border); border-radius: 10px; overflow: hidden; overflow-x: auto; }
  th { text-align: left; padding: 0.6rem 0.9rem; font-size: 0.72rem; text-transform: uppercase; letter-spacing: 0.05em; color: var(--text-dim); border-bottom: 1px solid var(--border); }
  td { padding: 0.5rem 0.9rem; border-bottom: 1px solid var(--border); vertical-align: middle; }
  tr:last-child td { border-bottom: none; }
  tr.row-alert td:first-child { box-shadow: inset 3px 0 0 var(--danger); }
  .ip, .num { font-family: var(--mono); font-variant-numeric: tabular-nums; }
  .empty-row td { color: var(--text-dim); text-align: center; padding: 1.1rem; }

  .badge { display: inline-flex; align-items: center; gap: 0.35rem; font-family: var(--mono); font-size: 0.76rem; padding: 0.18rem 0.55rem; border-radius: 999px; font-weight: 600; }
  .badge.alert { background: var(--danger-soft); color: var(--danger); }
  .badge.permit { background: var(--ok-soft); color: var(--ok); }
  .badge.heur { background: var(--surface-2); color: var(--text-dim); }
  .why { color: var(--text-dim); font-size: 0.82rem; }
</style>

<div class="wrap">
  <header>
    <h1>Sistema PPI<small>Motor en vivo &middot; solo lectura</small></h1>
    <span class="stamp" id="stamp"></span>
  </header>

  <div class="healthbar" id="healthbar"></div>

  <section>
    <div class="sec-head"><svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round"><rect x="3" y="4" width="18" height="6" rx="1.5"/><rect x="3" y="14" width="18" height="6" rx="1.5"/><circle cx="7" cy="7" r="0.9" fill="currentColor" stroke="none"/><circle cx="7" cy="17" r="0.9" fill="currentColor" stroke="none"/></svg><h2>Salud del sistema</h2></div>
    <div class="grid" id="health"></div>
  </section>

  <section>
    <div class="sec-head"><svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round"><rect x="6" y="6" width="12" height="12" rx="1.5"/><line x1="9" y1="2" x2="9" y2="6"/><line x1="15" y1="2" x2="15" y2="6"/><line x1="9" y1="18" x2="9" y2="22"/><line x1="15" y1="18" x2="15" y2="22"/><line x1="2" y1="9" x2="6" y2="9"/><line x1="2" y1="15" x2="6" y2="15"/><line x1="18" y1="9" x2="22" y2="9"/><line x1="18" y1="15" x2="22" y2="15"/></svg><h2>Modelo congelado</h2></div>
    <div class="grid" id="model"></div>
    <div class="note"><svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="M12 3 L22 20 L2 20 Z"/><line x1="12" y1="9" x2="12" y2="13.5"/><circle cx="12" cy="16.5" r="0.7" fill="currentColor" stroke="none"/></svg><span><strong>Punto débil conocido:</strong> este modelo detecta peor la fuerza bruta de contraseñas (50&ndash;55%) que el resto de familias de ataque (&gt;80%). Una decisión PERMIT en ese escenario es menos confiable que en otros.</span></div>
  </section>

  <section>
    <div class="sec-head"><svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><polyline points="2,12 7,12 9,6 13,18 15,12 22,12"/></svg><h2>Actividad &middot; última hora</h2></div>
    <div class="grid" id="counters"></div>
    <div class="spark-wrap">
      <svg id="spark" width="100%" height="46" viewBox="0 0 610 46" preserveAspectRatio="none"></svg>
      <div class="spark-legend">
        <span><i class="swatch" style="background:var(--danger)"></i>minuto con ALERT</span>
        <span><i class="swatch" style="background:var(--accent)"></i>solo PERMIT</span>
        <span><i class="swatch" style="background:var(--border)"></i>sin tráfico</span>
        <span>&larr; hace 60 min&nbsp;&nbsp;&nbsp;ahora &rarr;</span>
      </div>
    </div>
  </section>

  <section>
    <div class="sec-head"><svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><rect x="5" y="11" width="14" height="9" rx="1.5"/><path d="M8 11V7a4 4 0 0 1 8 0v4"/></svg><h2>IPs bloqueadas ahora</h2></div>
    <div class="tbl-wrap">
      <table><thead><tr><th>IP</th><th>Expira en</th></tr></thead><tbody id="blocked"></tbody></table>
    </div>
  </section>

  <section>
    <div class="sec-head"><svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round"><line x1="4" y1="6" x2="20" y2="6"/><line x1="4" y1="12" x2="20" y2="12"/><line x1="4" y1="18" x2="20" y2="18"/></svg><h2>Decisiones recientes</h2></div>
    <div class="tbl-wrap">
      <table>
        <thead><tr><th>Hora</th><th>IP</th><th>Decisión</th><th>Motivo</th><th>Score</th><th>Paquetes</th></tr></thead>
        <tbody id="decisions"></tbody>
      </table>
    </div>
  </section>
</div>

<script>
// Solo los iconos usados dinamicamente en refresh(); los estaticos (encabezados
// de seccion, nota de contexto) ya estan inline en el HTML de arriba.
const ICON = {
  ok: '<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.4" stroke-linecap="round" stroke-linejoin="round"><polyline points="4,12 9,17 20,6"/></svg>',
  bad: '<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.4" stroke-linecap="round"><line x1="5" y1="5" x2="19" y2="19"/><line x1="19" y1="5" x2="5" y2="19"/></svg>',
};

const DETECTOR_LABEL = { empty_window_heuristic: 'sin tráfico (heurístico)', ocsvm_scaled: 'modelo (OCSVM)' };
const SERVICE_LABEL = { 'ppi-motor.service': 'Motor', 'ppi-motor-capture.service': 'Captura', 'suricata.service': 'Suricata' };

function card(label, value, cls) {
  return `<div class="card ${cls||''}"><div class="label">${label}</div><div class="value">${value}</div></div>`;
}
function fmtTime(t) {
  return new Date(t * 1000).toLocaleTimeString();
}

function renderHealthbar(services, counters) {
  const allUp = Object.values(services).every(Boolean);
  const el = document.getElementById('healthbar');
  if (!allUp) {
    el.className = 'healthbar bad';
    el.innerHTML = `<span class="dot"></span><div><div class="msg">Atención: un servicio no está activo</div><div class="sub">Revisar con journalctl -- el motor puede no estar observando tráfico real ahora mismo.</div></div>`;
  } else if (counters.alert_model > 0) {
    el.className = 'healthbar warn';
    el.innerHTML = `<span class="dot"></span><div><div class="msg">Servicios activos &middot; ${counters.alert_model} alerta(s) real(es) en la última hora</div><div class="sub">El sistema está funcionando y respondiendo -- revisar la tabla de decisiones abajo.</div></div>`;
  } else {
    el.className = 'healthbar ok';
    el.innerHTML = `<span class="dot"></span><div><div class="msg">Todo operando con normalidad</div><div class="sub">Servicios activos, sin alertas reales en la última hora.</div></div>`;
  }
}

function renderSparkline(activity) {
  const svg = document.getElementById('spark');
  const n = activity.length;
  const w = 610, h = 46, bw = w / n;
  let bars = '';
  activity.forEach((b, i) => {
    const total = b.alert + b.permit;
    const x = i * bw;
    let color = 'var(--border)';
    let barH = 3;
    if (total > 0) {
      barH = Math.max(4, Math.min(h - 2, 4 + Math.log2(total + 1) * 9));
      color = b.alert > 0 ? 'var(--danger)' : 'var(--accent)';
    }
    bars += `<rect x="${x.toFixed(1)}" y="${(h - barH).toFixed(1)}" width="${Math.max(1, bw - 1.2).toFixed(1)}" height="${barH.toFixed(1)}" rx="1" fill="${color}"/>`;
  });
  svg.innerHTML = bars;
}

async function refresh() {
  try {
    const status = await (await fetch('/api/status')).json();
    stamp.textContent = 'Actualizado ' + new Date().toLocaleTimeString();

    renderHealthbar(status.services, status.counters);

    health.innerHTML = Object.entries(status.services).map(([name, active]) =>
      card(SERVICE_LABEL[name] || name, active ? ICON.ok + ' activo' : ICON.bad + ' inactivo', active ? 'ok' : 'bad')
    ).join('');

    const m = status.model;
    model.innerHTML = [
      card('Detector', 'OCSVM'),
      card('Umbral', m.threshold.toFixed(4), 'accent'),
      card('FPR benigno', (m.test_fpr * 100).toFixed(2) + '%'),
      card('Detección global', (m.detection_rate * 100).toFixed(1) + '%', 'accent'),
      card('Detección Kali-real', (m.kali_real_detection_rate * 100).toFixed(1) + '%', 'accent'),
    ].join('');

    blocked.innerHTML = status.blocked.length
      ? status.blocked.map(b => `<tr><td class="ip">${b.ip}</td><td class="num">${b.expires_seconds != null ? b.expires_seconds + 's' : '?'}</td></tr>`).join('')
      : '<tr class="empty-row"><td colspan="2">Ninguna IP bloqueada ahora mismo.</td></tr>';

    const c = status.counters;
    counters.innerHTML = [
      card('Total', c.total),
      card('ALERT (modelo)', c.alert_model, c.alert_model > 0 ? 'bad' : ''),
      card('PERMIT (modelo)', c.permit_model, 'ok'),
      card('PERMIT (sin tráfico)', c.permit_heuristic),
    ].join('');

    renderSparkline(status.activity);

    const decisions = await (await fetch('/api/decisions?limit=100')).json();
    document.getElementById('decisions').innerHTML = decisions.length ? decisions.map(d => {
      const isAlert = d.decision === 'ALERT';
      const badge = isAlert ? `<span class="badge alert">${ICON.bad} ALERT</span>` : `<span class="badge permit">${ICON.ok} PERMIT</span>`;
      return `<tr class="${isAlert ? 'row-alert' : ''}"><td>${fmtTime(d.logged_at)}</td><td class="ip">${d.entity_ip}</td>` +
        `<td>${badge}</td><td class="why">${DETECTOR_LABEL[d.detector_name] || d.detector_name}</td>` +
        `<td class="num">${d.score != null ? d.score.toFixed(4) : '&mdash;'}</td><td class="num">${d.packet_count_10s}</td></tr>`;
    }).join('') : '<tr class="empty-row"><td colspan="6">Sin decisiones recientes.</td></tr>';
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


def bucket_by_minute(decisions: list[dict], minutes: int = 60) -> list[dict]:
    """Agrega decisiones en cubos de 1 minuto para el sparkline de actividad.

    Cubos vacios (sin ninguna decision en ese minuto) se incluyen con
    ceros -- el frontend los necesita para dibujar una linea de tiempo
    continua, no solo los minutos con actividad.
    """
    now = time.time()
    buckets = [{"offset_min": i, "alert": 0, "permit": 0} for i in range(minutes, -1, -1)]
    index_by_offset = {b["offset_min"]: b for b in buckets}
    for item in decisions:
        age_seconds = now - item.get("logged_at", 0)
        if age_seconds < 0 or age_seconds > minutes * 60:
            continue
        offset_min = int(age_seconds // 60)
        bucket = index_by_offset.get(offset_min)
        if bucket is None:
            continue
        if item["decision"] == "ALERT":
            bucket["alert"] += 1
        else:
            bucket["permit"] += 1
    return buckets


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
                        "activity": bucket_by_minute(decisions),
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
