#!/usr/bin/env python3
"""Genera las figuras y los intervalos de confianza del informe de evaluación crítica.

Solo biblioteca estándar (VM01 no tiene matplotlib): las figuras se emiten como
SVG escrito directamente. Todas las cifras se leen de artefactos reales
(`artifacts/model/manifest.json`, resultados de F6) — ninguna se escribe a mano
en este script, salvo las que se citan textualmente de un documento y se marcan
como tal.

Uso:
    python3 scripts/entregables/generar_figuras_informe.py

Salida:
    docs/entregables/figuras/*.svg   (3 figuras)
    stdout                            (tabla de IC de Wilson usada en el informe)
"""
from __future__ import annotations

import json
import math
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
MANIFEST = REPO / "artifacts" / "model" / "manifest.json"
FIGS = REPO / "docs" / "entregables" / "figuras"

# Paleta (coherente con el resto de artefactos del proyecto)
INK = "#131b2e"
DIM = "#5b6b8c"
LINE = "#c3ccdf"
OK = "#15803d"
DANGER = "#b91c1c"
ACCENT = "#0f8a7d"
AMBER = "#b45309"


# --------------------------------------------------------------------------
# Intervalos de confianza de Wilson (95%)
# --------------------------------------------------------------------------
def wilson(k: int, n: int, z: float = 1.959963984540054) -> tuple[float, float, float]:
    """IC de Wilson para una proporción binomial. Devuelve (p, lo, hi).

    Se elige Wilson sobre el intervalo normal (Wald) porque Wald es inválido
    con n pequeño o p cercano a 0/1 — exactamente el régimen de varias familias
    de ataque de este proyecto (n=6). No requiere dependencias externas.
    """
    if n == 0:
        return (float("nan"),) * 3
    p = k / n
    d = 1 + z * z / n
    centre = (p + z * z / (2 * n)) / d
    margin = (z / d) * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n))
    return p, max(0.0, centre - margin), min(1.0, centre + margin)


def pct(x: float) -> str:
    return f"{100 * x:.1f}%"


# --------------------------------------------------------------------------
# Utilidades SVG
# --------------------------------------------------------------------------
def svg_open(w: int, h: int, title: str) -> list[str]:
    return [
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {w} {h}" '
        f'width="{w}" height="{h}" role="img" aria-label="{title}">',
        f"<title>{title}</title>",
        '<style>'
        'text{font-family:ui-monospace,"Cascadia Code","Roboto Mono",monospace}'
        '.t{font-size:15px;font-weight:700;fill:' + INK + '}'
        '.s{font-size:11px;fill:' + DIM + '}'
        '.l{font-size:11px;fill:' + INK + '}'
        '.v{font-size:11px;font-weight:700}'
        '</style>',
        f'<rect width="{w}" height="{h}" fill="#ffffff"/>',
    ]


def esc(s: str) -> str:
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def write_svg(path: Path, parts: list[str]) -> None:
    parts.append("</svg>")
    path.write_text("\n".join(parts) + "\n", encoding="utf-8")
    print(f"  escrito: {path.relative_to(REPO)}")


# --------------------------------------------------------------------------
# Figura 1 — FPR offline vs operativo
# --------------------------------------------------------------------------
def fig1_fpr(man: dict) -> None:
    fpr_off = man["evaluation"]["ocsvm_scaled"]["test"]["fpr"]
    k_off = man["evaluation"]["ocsvm_scaled"]["test"]["alerts_strict"]
    n_off = man["evaluation"]["ocsvm_scaled"]["test"]["n_windows"]
    # F6: cifras citadas de docs/fase07-validacion-final/02-resultados-f6.md
    series = [
        ("Offline (test del dataset)", fpr_off, f"{k_off}/{n_off} ventanas", OK),
        ("Operativo F6 — pase 2", 17 / 74, "17/74 ventanas", DANGER),
        ("Operativo F6 — pase 1", 16 / 62, "16/62 ventanas", DANGER),
    ]
    w, h = 760, 300
    x0, top, bar_h, gap = 250, 74, 34, 26
    max_v = 0.30
    plot_w = w - x0 - 120

    p = svg_open(w, h, "FPR benigno offline frente al medido en operacion")
    p.append(f'<text x="24" y="30" class="t">Falsos positivos: lo medido offline no se sostiene en operación</text>')
    p.append(f'<text x="24" y="50" class="s">Proporción de ventanas de tráfico legítimo clasificadas como ALERT · barras con IC de Wilson 95%</text>')

    # rejilla
    for frac in (0, 0.05, 0.10, 0.15, 0.20, 0.25, 0.30):
        gx = x0 + plot_w * (frac / max_v)
        p.append(f'<line x1="{gx:.1f}" y1="{top-8}" x2="{gx:.1f}" y2="{top+len(series)*(bar_h+gap)-10}" stroke="{LINE}" stroke-width="1"/>')
        p.append(f'<text x="{gx:.1f}" y="{top+len(series)*(bar_h+gap)+8}" class="s" text-anchor="middle">{int(frac*100)}%</text>')

    for i, (label, value, sub, colour) in enumerate(series):
        y = top + i * (bar_h + gap)
        kk = round(value * (n_off if i == 0 else (74 if i == 1 else 62)))
        nn = n_off if i == 0 else (74 if i == 1 else 62)
        _, lo, hi = wilson(kk, nn)
        bw = plot_w * (value / max_v)
        p.append(f'<text x="{x0-14}" y="{y+bar_h*0.55}" class="l" text-anchor="end">{esc(label)}</text>')
        p.append(f'<text x="{x0-14}" y="{y+bar_h*0.55+14}" class="s" text-anchor="end">{esc(sub)}</text>')
        p.append(f'<rect x="{x0}" y="{y}" width="{bw:.1f}" height="{bar_h}" fill="{colour}" opacity="0.85" rx="3"/>')
        # barra de error (IC)
        xlo, xhi = x0 + plot_w * (lo / max_v), x0 + plot_w * (hi / max_v)
        ym = y + bar_h / 2
        p.append(f'<line x1="{xlo:.1f}" y1="{ym}" x2="{xhi:.1f}" y2="{ym}" stroke="{INK}" stroke-width="1.6"/>')
        for xe in (xlo, xhi):
            p.append(f'<line x1="{xe:.1f}" y1="{ym-6}" x2="{xe:.1f}" y2="{ym+6}" stroke="{INK}" stroke-width="1.6"/>')
        p.append(f'<text x="{max(xhi, bw+x0)+10:.1f}" y="{ym+4}" class="v" fill="{colour}">{pct(value)}</text>')
        p.append(f'<text x="{max(xhi, bw+x0)+10:.1f}" y="{ym+18}" class="s">IC95 {pct(lo)}–{pct(hi)}</text>')

    yb = top + len(series) * (bar_h + gap) + 30
    p.append(f'<text x="24" y="{yb}" class="s">Los intervalos no se solapan: la diferencia entre el FPR offline y el operativo no se explica por azar muestral.</text>')
    p.append(f'<text x="24" y="{yb+16}" class="s">Fuente: artifacts/model/manifest.json · docs/fase07-validacion-final/02-resultados-f6.md</text>')
    write_svg(FIGS / "fig1-fpr-offline-vs-operativo.svg", p)


# --------------------------------------------------------------------------
# Figura 2 — Detección por familia: OCSVM vs Isolation Forest
# --------------------------------------------------------------------------
def fig2_familias(man: dict) -> None:
    ev = man["evaluation"]
    fams = sorted(
        ev["ocsvm_scaled"]["anomalies"]["by_profile"].items(),
        key=lambda kv: -kv[1]["windows"],
    )
    w = 780
    row_h = 30
    top = 96
    h = top + len(fams) * row_h + 78
    x0 = 268
    plot_w = w - x0 - 150

    p = svg_open(w, h, "Deteccion por familia de ataque: OCSVM frente a Isolation Forest")
    p.append('<text x="24" y="30" class="t">Detección por familia: dónde gana OCSVM y dónde pierde</text>')
    p.append('<text x="24" y="50" class="s">Cada familia evaluada una sola vez, con modelo y umbral ya congelados. n = ventanas de esa familia.</text>')
    p.append(f'<rect x="{x0}" y="{top-30}" width="12" height="12" fill="{ACCENT}"/>')
    p.append(f'<text x="{x0+18}" y="{top-20}" class="s">OCSVM (modelo congelado)</text>')
    p.append(f'<rect x="{x0+210}" y="{top-30}" width="12" height="12" fill="{DIM}"/>')
    p.append(f'<text x="{x0+228}" y="{top-20}" class="s">Isolation Forest (if_primary_weighted)</text>')

    for i, (fam, o) in enumerate(fams):
        y = top + i * row_h
        n = o["windows"]
        det_o = o["detected"]
        det_i = ev["if_primary_weighted"]["anomalies"]["by_profile"][fam]["detected"]
        ro, ri = det_o / n, det_i / n
        short = fam.replace("ANOM-KALI-", "").replace("ANOM-", "")
        p.append(f'<text x="{x0-14}" y="{y+13}" class="l" text-anchor="end">{esc(short)}</text>')
        p.append(f'<text x="{x0-14}" y="{y+24}" class="s" text-anchor="end">n={n}</text>')
        # OCSVM
        p.append(f'<rect x="{x0}" y="{y+2}" width="{plot_w*ro:.1f}" height="9" fill="{ACCENT}" rx="2"/>')
        # IF
        p.append(f'<rect x="{x0}" y="{y+14}" width="{plot_w*ri:.1f}" height="9" fill="{DIM}" rx="2"/>')
        col = DANGER if ro < 0.6 else INK
        p.append(f'<text x="{x0+plot_w+12}" y="{y+11}" class="v" fill="{col}">{det_o}/{n}</text>')
        p.append(f'<text x="{x0+plot_w+62}" y="{y+11}" class="s">{pct(ro)}</text>')
        if ri == 0:
            p.append(f'<text x="{x0+plot_w+12}" y="{y+23}" class="s" fill="{DANGER}">{det_i}/{n} punto ciego</text>')
        else:
            p.append(f'<text x="{x0+plot_w+12}" y="{y+23}" class="s">{det_i}/{n}</text>')

    yb = top + len(fams) * row_h + 22
    p.append(f'<text x="24" y="{yb}" class="s">OCSVM resuelve dos puntos ciegos totales de IF (SYN-RATE-50 y UDP-PROBE-50: 0/31 y 0/40) …</text>')
    p.append(f'<text x="24" y="{yb+16}" class="s">… pero paga ese avance en las familias de autenticación (PASSWORD-SPRAY 16/29, AUTH-FAIL 3/6), donde IF era superior.</text>')
    p.append(f'<text x="24" y="{yb+34}" class="s">Fuente: artifacts/model/manifest.json (evaluation.*.anomalies.by_profile)</text>')
    write_svg(FIGS / "fig2-deteccion-por-familia.svg", p)


# --------------------------------------------------------------------------
# Figura 3 — Scores del tráfico legítimo pesado contra el umbral
# --------------------------------------------------------------------------
def fig3_scores(man: dict) -> None:
    thr = man["evaluation"]["ocsvm_scaled"]["threshold_used"]
    # Scores reales de la corrida aislada iperf-tcp 200M, citados de
    # docs/fase07-validacion-final/02-resultados-f6.md
    scores = [1.968, 1.814, 1.689, 1.920]
    lo, hi = 1.60, 2.05
    w, h = 760, 250
    x0, plot_w, axis_y = 60, 640, 130

    p = svg_open(w, h, "Scores de trafico legitimo pesado frente al umbral")
    p.append('<text x="24" y="30" class="t">Tráfico legítimo pesado puntúa en el margen del umbral</text>')
    p.append('<text x="24" y="50" class="s">Descarga legítima iperf-tcp 200 Mbit/s, corrida aislada (cliente en silencio 95 s antes). Cada punto es una ventana de 10 s.</text>')

    def X(v: float) -> float:
        return x0 + plot_w * (v - lo) / (hi - lo)

    p.append(f'<line x1="{x0}" y1="{axis_y}" x2="{x0+plot_w}" y2="{axis_y}" stroke="{LINE}" stroke-width="2"/>')
    for v in [1.6, 1.7, 1.8, 1.9, 2.0]:
        p.append(f'<line x1="{X(v):.1f}" y1="{axis_y-5}" x2="{X(v):.1f}" y2="{axis_y+5}" stroke="{LINE}" stroke-width="1.5"/>')
        p.append(f'<text x="{X(v):.1f}" y="{axis_y+22}" class="s" text-anchor="middle">{v:.1f}</text>')

    xt = X(thr)
    p.append(f'<line x1="{xt:.1f}" y1="{axis_y-58}" x2="{xt:.1f}" y2="{axis_y+34}" stroke="{INK}" stroke-width="2" stroke-dasharray="5 4"/>')
    p.append(f'<text x="{xt:.1f}" y="{axis_y-66}" class="v" fill="{INK}" text-anchor="middle">umbral {thr:.4f}</text>')
    p.append(f'<text x="{X(1.66):.1f}" y="{axis_y+44}" class="s" fill="{DANGER}">← ALERT (bloquea)</text>')
    p.append(f'<text x="{X(1.98):.1f}" y="{axis_y+44}" class="s" fill="{OK}">PERMIT →</text>')

    for s in scores:
        col = DANGER if s < thr else OK
        p.append(f'<circle cx="{X(s):.1f}" cy="{axis_y}" r="8" fill="{col}" stroke="#ffffff" stroke-width="2"/>')
        dy = -20 if s != 1.814 else -36
        p.append(f'<text x="{X(s):.1f}" y="{axis_y+dy}" class="v" fill="{col}" text-anchor="middle">{s:.3f}</text>')

    p.append(f'<text x="24" y="{axis_y+82}" class="s">Los cuatro scores caen en 1.69–1.99: el modelo no separa con margen el tráfico legítimo pesado del anómalo.</text>')
    p.append(f'<text x="24" y="{axis_y+98}" class="s" fill="{DANGER}">La ventana de score 1.689 cruzó el umbral y provocó el bloqueo real de un cliente legítimo durante 120 s.</text>')
    p.append(f'<text x="24" y="{axis_y+116}" class="s">Fuente: docs/fase07-validacion-final/02-resultados-f6.md · umbral leído de artifacts/model/manifest.json</text>')
    write_svg(FIGS / "fig3-scores-trafico-pesado.svg", p)


# --------------------------------------------------------------------------
def tabla_ic(man: dict) -> None:
    ev = man["evaluation"]
    o = ev["ocsvm_scaled"]
    print("\n=== IC de Wilson 95% — proporciones citadas en el informe ===")
    print(f"{'magnitud':44s} {'k/n':>10s} {'punto':>8s}   IC95")
    filas = [
        ("FPR benigno (test)", o["test"]["alerts_strict"], o["test"]["n_windows"]),
        ("Detección global", o["anomalies"]["detected_strict"], o["anomalies"]["n_windows"]),
        ("Detección Kali-real", o["anomalies"]["kali_real_detected"], o["anomalies"]["kali_real_windows"]),
        ("Detección heredada (otra procedencia)", o["anomalies"]["legacy_detected"], o["anomalies"]["legacy_windows"]),
        ("Detección por episodio", o["anomalies"]["detected_episode_count"], o["anomalies"]["total_episode_count"]),
    ]
    for fam, d in sorted(o["anomalies"]["by_profile"].items(), key=lambda kv: -kv[1]["windows"]):
        filas.append((f"  familia {fam}", d["detected"], d["windows"]))
    filas.append(("FPR operativo F6 pase 1", 16, 62))
    filas.append(("FPR operativo F6 pase 2", 17, 74))
    for label, k, n in filas:
        p_, lo_, hi_ = wilson(k, n)
        print(f"{label:44s} {f'{k}/{n}':>10s} {pct(p_):>8s}   [{pct(lo_)} – {pct(hi_)}]  (ancho {pct(hi_-lo_)})")

    print("\n=== Comparación OCSVM vs Isolation Forest (detección global) ===")
    for mo in ("ocsvm_scaled", "if_primary_weighted"):
        a = ev[mo]["anomalies"]
        p_, lo_, hi_ = wilson(a["detected_strict"], a["n_windows"])
        print(f"  {mo:22s} {a['detected_strict']}/{a['n_windows']} = {pct(p_)}  IC95 [{pct(lo_)} – {pct(hi_)}]")


def main() -> int:
    man = json.loads(MANIFEST.read_text(encoding="utf-8"))
    FIGS.mkdir(parents=True, exist_ok=True)
    print("Generando figuras del informe de evaluación crítica…")
    fig1_fpr(man)
    fig2_familias(man)
    fig3_scores(man)
    tabla_ic(man)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
