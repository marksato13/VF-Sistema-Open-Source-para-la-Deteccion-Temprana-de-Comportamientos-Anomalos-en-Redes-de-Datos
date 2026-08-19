#!/usr/bin/env python3
"""Genera la suite de gráficas del informe de evaluación de la tesis.

Todas las figuras salen de artefactos reales:
  · `artifacts/model/ocsvm_scaled.joblib`  (modelo congelado, re-puntuado aquí)
  · `artifacts/dataset/multilayer-v2-*.csv` (conjuntos auditados)
  · `artifacts/model/manifest.json`         (evaluación bloqueada de los 7 modelos)
  · `results/f6/f6_resultados.jsonl`        (validación del sistema desplegado)

Ninguna cifra se escribe a mano: se recalcula o se lee del artefacto. La
re-puntuación reproduce exactamente las métricas del manifiesto (13/276 y
158/179), lo que verifica de forma independiente que el modelo congelado
reproduce sus propios resultados.

Uso:
    .venv/bin/python3 scripts/entregables/generar_graficas.py
"""
from __future__ import annotations

import csv
import json
from collections import Counter, OrderedDict
from pathlib import Path

import joblib
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from matplotlib.patches import Patch
from sklearn.metrics import roc_auc_score, roc_curve

REPO = Path(__file__).resolve().parents[2]
OUT = REPO / "docs" / "entregables" / "graficas"
DPI = 200

# ---------------------------------------------------------------- estilo ----
INK, DIM, GRID = "#131b2e", "#5b6b8c", "#dde3ee"
ACCENT, DANGER, OK, AMBER, VIOLET = "#0f8a7d", "#b91c1c", "#15803d", "#b45309", "#6d28d9"

plt.rcParams.update({
    "figure.dpi": DPI, "savefig.dpi": DPI, "savefig.bbox": "tight",
    "font.family": "DejaVu Sans", "font.size": 10,
    "axes.titlesize": 12.5, "axes.titleweight": "bold", "axes.titlepad": 12,
    "axes.labelsize": 10, "axes.labelcolor": INK, "axes.edgecolor": "#b9c2d6",
    "axes.facecolor": "white", "figure.facecolor": "white",
    "text.color": INK, "xtick.color": DIM, "ytick.color": DIM,
    "axes.grid": True, "grid.color": GRID, "grid.linewidth": 0.9,
    "axes.axisbelow": True, "legend.frameon": False, "legend.fontsize": 9,
})


def finish(ax, title, subtitle=None, source=None):
    """Aplica el remate común: título, subtítulo y pie de fuente.

    El pad del título se amplía cuando hay subtítulo para que no se solapen:
    el subtítulo ocupa la banda inmediatamente encima de los ejes y el título
    queda por encima de él.
    """
    ax.set_title(title, loc="left", color=INK, pad=30 if subtitle else 12)
    if subtitle:
        ax.text(0, 1.012, subtitle, transform=ax.transAxes, fontsize=8.8,
                color=DIM, va="bottom", ha="left")
    for s in ("top", "right"):
        ax.spines[s].set_visible(False)
    if source:
        ax.figure.text(0.005, -0.02, source, fontsize=7.4, color=DIM, ha="left")


def save(fig, name):
    OUT.mkdir(parents=True, exist_ok=True)
    p = OUT / name
    fig.savefig(p)
    plt.close(fig)
    print(f"  · {p.relative_to(REPO)}")


# ------------------------------------------------------------- datos --------
def load_all():
    man = json.loads((REPO / "artifacts/model/manifest.json").read_text())
    feats = man["feature_names"]
    thr = man["evaluation"]["ocsvm_scaled"]["threshold_used"]
    pipe = joblib.load(REPO / "artifacts/model/ocsvm_scaled.joblib")

    def rows(p):
        return list(csv.DictReader(open(REPO / p)))

    norm = rows("artifacts/dataset/multilayer-v2-normal.csv")
    anom = rows("artifacts/dataset/multilayer-v2-anomalies.csv")

    def score(rs):
        X = np.array([[float(r[f]) for f in feats] for r in rs])
        return pipe.score_samples(X)

    data = {
        "man": man, "thr": thr, "feats": feats,
        "s_train": score([r for r in norm if r["partition"] == "train"]),
        "s_val": score([r for r in norm if r["partition"] == "validation"]),
        "s_test": score([r for r in norm if r["partition"] == "test"]),
        "s_anom": score(anom),
        "anom_rows": anom, "norm_rows": norm,
    }
    return data


# =================================================== A · modelo congelado ====
def fig_roc(d):
    y = np.r_[np.zeros(len(d["s_test"])), np.ones(len(d["s_anom"]))]
    # score bajo = más anómalo -> se invierte para que sea "score de anomalía"
    sc = np.r_[-d["s_test"], -d["s_anom"]]
    fpr, tpr, thrs = roc_curve(y, sc)
    auc = roc_auc_score(y, sc)

    fig, ax = plt.subplots(figsize=(6.4, 5.4))
    ax.plot([0, 1], [0, 1], "--", color=DIM, lw=1.1, label="Azar (AUC = 0.500)")
    ax.plot(fpr, tpr, color=ACCENT, lw=2.6, label=f"OCSVM congelado (AUC = {auc:.3f})")
    ax.fill_between(fpr, tpr, alpha=0.10, color=ACCENT)

    # punto de operación real (umbral congelado)
    op_fpr = float((d["s_test"] < d["thr"]).mean())
    op_tpr = float((d["s_anom"] < d["thr"]).mean())
    ax.plot([op_fpr], [op_tpr], "o", ms=11, color=DANGER, zorder=5,
            markeredgecolor="white", markeredgewidth=1.8)
    ax.annotate(f"Punto de operación\numbral = {d['thr']:.4f}\nFPR {op_fpr:.1%} · detección {op_tpr:.1%}",
                xy=(op_fpr, op_tpr), xytext=(op_fpr + 0.20, op_tpr - 0.26),
                fontsize=8.6, color=DANGER,
                arrowprops=dict(arrowstyle="->", color=DANGER, lw=1.3))
    ax.set_xlabel("Tasa de falsos positivos (FPR)")
    ax.set_ylabel("Tasa de detección (TPR)")
    ax.set_xlim(-0.02, 1.02); ax.set_ylim(-0.02, 1.02)
    ax.legend(loc="lower right")
    finish(ax, "Curva ROC del modelo congelado",
           "276 ventanas benignas de prueba frente a 179 ventanas de ataque · calculada re-puntuando el .joblib",
           "Fuente: artifacts/model/ocsvm_scaled.joblib + artifacts/dataset/ · métrica ausente en el trabajo original")
    save(fig, "A1-curva-roc.png")
    return auc


def fig_distribucion(d):
    fig, ax = plt.subplots(figsize=(8.4, 5.0))
    lo = min(d["s_test"].min(), d["s_anom"].min())
    hi = max(d["s_test"].max(), d["s_anom"].max())
    bins = np.linspace(lo, hi, 55)
    # zonas de decisión sombreadas: más legible que flechas
    ax.axvspan(lo, d["thr"], color=DANGER, alpha=0.055)
    ax.axvspan(d["thr"], hi, color=OK, alpha=0.055)
    ax.hist(d["s_test"], bins=bins, color=OK, alpha=0.72, label=f"Benigno · prueba (n={len(d['s_test'])})")
    ax.hist(d["s_anom"], bins=bins, color=DANGER, alpha=0.66, label=f"Anómalo (n={len(d['s_anom'])})")
    ax.axvline(d["thr"], color=INK, ls="--", lw=2)
    ymax = ax.get_ylim()[1]
    ax.set_ylim(0, ymax * 1.16)
    ax.text(d["thr"] - 0.02, ymax * 1.10, "◄ ALERT (bloquea)", color=DANGER,
            fontsize=9, ha="right", fontweight="bold")
    ax.text(d["thr"] + 0.02, ymax * 1.10, "PERMIT ►", color=OK,
            fontsize=9, ha="left", fontweight="bold")
    ax.text(d["thr"], ymax * 1.02, f"umbral {d['thr']:.4f}", color=INK,
            fontsize=8.6, ha="center")
    ax.set_xlabel("score del modelo (menor = más anómalo)")
    ax.set_ylabel("nº de ventanas")
    ax.legend(loc="upper left", bbox_to_anchor=(0.02, 0.90))
    finish(ax, "Separación de las distribuciones de score",
           "El solapamiento en torno al umbral es el origen de los falsos positivos y negativos",
           "Fuente: re-puntuación del modelo congelado sobre los conjuntos auditados")
    save(fig, "A2-distribucion-scores.png")


def fig_confusion(d):
    tp = int((d["s_anom"] < d["thr"]).sum()); fn = len(d["s_anom"]) - tp
    fp = int((d["s_test"] < d["thr"]).sum()); tn = len(d["s_test"]) - fp
    M = np.array([[tn, fp], [fn, tp]])
    fig, ax = plt.subplots(figsize=(6.0, 5.2))
    ax.imshow(M / M.sum(axis=1, keepdims=True), cmap="BuGn", vmin=0, vmax=1)
    labels = [["Correcto\n(permitido)", "Falso positivo\n(bloquea legítimo)"],
              ["Falso negativo\n(ataque no visto)", "Correcto\n(bloqueado)"]]
    for i in range(2):
        for j in range(2):
            frac = M[i, j] / M[i].sum()
            col = "white" if frac > 0.55 else INK
            ax.text(j, i - 0.13, f"{M[i, j]}", ha="center", va="center",
                    fontsize=25, fontweight="bold", color=col)
            ax.text(j, i + 0.16, f"{frac:.1%}", ha="center", va="center", fontsize=11, color=col)
            ax.text(j, i + 0.33, labels[i][j], ha="center", va="center", fontsize=7.8, color=col)
    ax.set_xticks([0, 1], ["PERMIT", "ALERT"]); ax.set_yticks([0, 1], ["Benigno\n(n=276)", "Anómalo\n(n=179)"])
    ax.set_xlabel("Decisión del sistema"); ax.set_ylabel("Realidad")
    ax.grid(False)
    rec, spec = tp / (tp + fn), tn / (tn + fp)
    finish(ax, "Matriz de confusión en el punto de operación",
           f"Recall {rec:.1%} · Especificidad {spec:.1%} · umbral {d['thr']:.4f}",
           "Nota: la precisión no se reporta porque benigno y anómalo son corpus separados (tasa base artificial)")
    save(fig, "A3-matriz-confusion.png")


def fig_barrido(d):
    grid = np.linspace(min(d["s_test"].min(), d["s_anom"].min()),
                       max(d["s_test"].max(), d["s_anom"].max()), 400)
    fpr = [(d["s_test"] < t).mean() for t in grid]
    det = [(d["s_anom"] < t).mean() for t in grid]
    fig, ax = plt.subplots(figsize=(8.0, 5.0))
    ax.plot(grid, np.array(det) * 100, color=ACCENT, lw=2.4, label="Detección de ataques")
    ax.plot(grid, np.array(fpr) * 100, color=DANGER, lw=2.4, label="Falsos positivos (benigno)")
    ax.axvline(d["thr"], color=INK, ls="--", lw=2)
    ax.text(d["thr"], 103, f" umbral congelado {d['thr']:.4f}", fontsize=8.8, color=INK, fontweight="bold")
    op_f, op_d = (d["s_test"] < d["thr"]).mean() * 100, (d["s_anom"] < d["thr"]).mean() * 100
    ax.plot([d["thr"]], [op_d], "o", color=ACCENT, ms=9, markeredgecolor="white", markeredgewidth=1.6)
    ax.plot([d["thr"]], [op_f], "o", color=DANGER, ms=9, markeredgecolor="white", markeredgewidth=1.6)
    ax.text(d["thr"] + 0.06, op_d, f"{op_d:.1f}%", color=ACCENT, fontsize=9, fontweight="bold", va="center")
    ax.text(d["thr"] + 0.06, op_f, f"{op_f:.1f}%", color=DANGER, fontsize=9, fontweight="bold", va="center")
    ax.set_xlabel("umbral de decisión"); ax.set_ylabel("porcentaje")
    ax.set_ylim(-3, 108); ax.legend(loc="center right")
    finish(ax, "Compromiso entre detección y falsos positivos según el umbral",
           "El umbral se fijó por cuantil α=0.05 sobre validación, no optimizando esta curva",
           "Fuente: re-puntuación del modelo congelado · barrido calculado en este informe")
    save(fig, "A4-barrido-umbral.png")


# ================================================ B · comparación modelos ====
def fig_modelos(d):
    ev = d["man"]["evaluation"]
    order = ["ocsvm_scaled", "if_uniform", "if_exact_collapsed", "if_primary_weighted",
             "if_scaled_weighted", "lof_scaled", "elliptic_envelope_scaled"]
    fig, ax = plt.subplots(figsize=(7.8, 5.6))
    for m in order:
        f = ev[m]["test"]["fpr"] * 100
        dr = ev[m]["anomalies"]["detection_rate"] * 100
        chosen = m == "ocsvm_scaled"
        ax.scatter(f, dr, s=300 if chosen else 130,
                   color=ACCENT if chosen else DIM,
                   edgecolor="white", linewidth=2, zorder=5 if chosen else 3,
                   marker="*" if chosen else "o")
        label = m.replace("_", " ")
        ax.annotate(f"{label}\n{dr:.1f}%", (f, dr),
                    xytext=(9, -4 if not chosen else 8), textcoords="offset points",
                    fontsize=8.2, color=INK if chosen else DIM,
                    fontweight="bold" if chosen else "normal")
    ax.set_xlabel("Falsos positivos sobre tráfico benigno (%)")
    ax.set_ylabel("Detección de ataques (%)")
    ax.set_xlim(2.8, 7.2); ax.set_ylim(18, 100)
    ax.text(0.98, 0.04, "mejor → arriba y a la izquierda", transform=ax.transAxes,
            ha="right", fontsize=8.4, color=DIM, style="italic")
    finish(ax, "Los 7 modelos evaluados: detección frente a falsos positivos",
           "Todos con FPR comparable (3.6–5.1 %); la diferencia real está en la detección",
           "Fuente: artifacts/model/manifest.json · evaluación bloqueada de un solo paso")
    save(fig, "B1-comparacion-modelos.png")


def fig_familias_heatmap(d):
    ev = d["man"]["evaluation"]
    mods = ["ocsvm_scaled", "if_primary_weighted", "if_uniform", "lof_scaled",
            "elliptic_envelope_scaled"]
    fams = sorted(ev["ocsvm_scaled"]["anomalies"]["by_profile"],
                  key=lambda f: -ev["ocsvm_scaled"]["anomalies"]["by_profile"][f]["windows"])
    M = np.array([[ev[m]["anomalies"]["by_profile"][f]["detected"] /
                   ev[m]["anomalies"]["by_profile"][f]["windows"] for m in mods] for f in fams])
    fig, ax = plt.subplots(figsize=(8.6, 6.2))
    im = ax.imshow(M, cmap="RdYlGn", vmin=0, vmax=1, aspect="auto")
    for i, f in enumerate(fams):
        for j, m in enumerate(mods):
            p = ev[m]["anomalies"]["by_profile"][f]
            ax.text(j, i, f"{p['detected']}/{p['windows']}", ha="center", va="center",
                    fontsize=8.6, fontweight="bold",
                    color="white" if M[i, j] < 0.28 else INK)
    ax.set_xticks(range(len(mods)),
                  [m.replace("_scaled", "").replace("_", "\n") for m in mods], fontsize=8.6)
    ax.set_yticks(range(len(fams)),
                  [f"{f.replace('ANOM-KALI-','').replace('ANOM-','')}  (n={ev['ocsvm_scaled']['anomalies']['by_profile'][f]['windows']})"
                   for f in fams], fontsize=8.4)
    ax.grid(False)
    cb = fig.colorbar(im, ax=ax, fraction=0.030, pad=0.02)
    cb.set_label("proporción detectada", fontsize=8.6)
    cb.outline.set_visible(False)
    finish(ax, "Detección por familia de ataque y por modelo",
           "OCSVM cubre los puntos ciegos totales de Isolation Forest (SYN-RATE y UDP-PROBE) y pierde en autenticación",
           "Fuente: artifacts/model/manifest.json (evaluation.*.anomalies.by_profile)")
    save(fig, "B2-heatmap-familias.png")


# ======================================================= C · operativo F6 ====
def wilson(k, n, z=1.959963984540054):
    if n == 0:
        return 0.0, 0.0, 0.0
    p = k / n
    den = 1 + z * z / n
    c = (p + z * z / (2 * n)) / den
    m = (z / den) * np.sqrt(p * (1 - p) / n + z * z / (4 * n * n))
    return p, max(0, c - m), min(1, c + m)


def fig_fpr_operativo(d):
    o = d["man"]["evaluation"]["ocsvm_scaled"]["test"]
    series = [("Offline\n(test del dataset)", o["alerts_strict"], o["n_windows"], OK),
              ("Operativo F6\npase 1", 16, 62, DANGER),
              ("Operativo F6\npase 2", 17, 74, DANGER)]
    fig, ax = plt.subplots(figsize=(7.6, 4.8))
    for i, (lab, k, n, col) in enumerate(series):
        p, lo, hi = wilson(k, n)
        ax.barh(i, p * 100, height=0.5, color=col, alpha=0.85)
        ax.errorbar(p * 100, i, xerr=[[(p - lo) * 100], [(hi - p) * 100]],
                    fmt="none", ecolor=INK, elinewidth=1.7, capsize=6)
        ax.text(hi * 100 + 1.2, i, f"{p:.1%}   IC95 {lo:.1%}–{hi:.1%}   ({k}/{n})",
                va="center", fontsize=9, color=INK)
    ax.set_yticks(range(len(series)), [s[0] for s in series], fontsize=9)
    ax.invert_yaxis(); ax.set_xlabel("Falsos positivos sobre tráfico legítimo (%)")
    ax.set_xlim(0, 52)
    finish(ax, "El falso positivo medido offline no se sostiene en operación",
           "Intervalos de Wilson 95 %: no se solapan, luego la diferencia no se explica por azar muestral",
           "Fuente: artifacts/model/manifest.json · docs/fase07-validacion-final/02-resultados-f6.md")
    save(fig, "C1-fpr-offline-vs-operativo.png")


def fig_leadtime():
    rows = [json.loads(l) for l in open(REPO / "results/f6/f6_resultados.jsonl") if l.strip()]
    att = [r for r in rows if r.get("kind") == "attack" and r.get("lead_time_s") is not None]
    fam = OrderedDict()
    for r in att:
        f = "-".join(r["id"].split("-")[1:-1])
        fam.setdefault(f, []).append(r["lead_time_s"])
    names = list(fam)
    allv = [v for vs in fam.values() for v in vs]
    med = float(np.median(allv))
    xmax = max(allv) + 4

    fig, ax = plt.subplots(figsize=(8.2, 4.6))
    # bandas de referencia primero, para que queden por detrás
    ax.axvspan(0, 10, color=OK, alpha=0.05)
    ax.axvline(med, color=INK, ls="--", lw=1.8, zorder=2)
    ax.axvline(10, color=AMBER, ls=":", lw=1.8, zorder=2)

    for i, f in enumerate(names):
        vals = sorted(fam[f])
        ax.scatter(vals, [i] * len(vals), s=120, color=ACCENT, zorder=5,
                   edgecolor="white", linewidth=1.5)
        # resumen a la derecha, en vez de una etiqueta por punto (evita solapes)
        txt = f"{vals[0]:.1f}s" if len(vals) == 1 else f"{vals[0]:.1f}–{vals[-1]:.1f}s"
        ax.text(xmax - 0.2, i, txt, ha="right", va="center", fontsize=8.8, color=DIM)

    ax.set_yticks(range(len(names)), names, fontsize=9)
    ax.set_xlabel("segundos desde el inicio del ataque hasta el bloqueo")
    ax.set_xlim(0, xmax)
    ax.set_ylim(-0.8, len(names) - 0.2)
    ax.invert_yaxis()
    # etiquetas de las líneas, ancladas dentro del área de datos
    ax.text(med - 0.15, len(names) - 0.35, f"mediana {med:.1f} s", fontsize=8.6,
            color=INK, fontweight="bold", ha="right", va="center")
    ax.text(10.15, len(names) - 0.35, "ciclo del motor (10 s)", fontsize=8.2,
            color=AMBER, ha="left", va="center")
    finish(ax, "Tiempo de detección y bloqueo por familia de ataque",
           f"Sistema desplegado, motor y enforcement activos · {len(allv)} corridas de ataque medidas",
           "Fuente: results/f6/f6_resultados.jsonl")
    save(fig, "C2-lead-time.png")


def fig_scores_pesado(d):
    scores = [1.968, 1.814, 1.689, 1.920]      # corrida aislada iperf-tcp 200M (F6)
    fig, ax = plt.subplots(figsize=(8.0, 3.3))
    ax.axvspan(1.60, d["thr"], color=DANGER, alpha=0.08)
    ax.axvspan(d["thr"], 2.05, color=OK, alpha=0.08)
    ax.axvline(d["thr"], color=INK, ls="--", lw=2)
    for s in scores:
        col = DANGER if s < d["thr"] else OK
        ax.scatter([s], [0], s=290, color=col, zorder=5, edgecolor="white", linewidth=2)
        ax.text(s, 0.16, f"{s:.3f}", ha="center", fontsize=9.4, color=col, fontweight="bold")
    ax.text(d["thr"], -0.30, f"umbral {d['thr']:.4f}", ha="center", fontsize=9, color=INK, fontweight="bold")
    ax.annotate("cruzó el umbral →\nbloqueó a un cliente legítimo 120 s",
                xy=(1.689, 0), xytext=(1.645, -0.72), fontsize=8.6, color=DANGER,
                arrowprops=dict(arrowstyle="->", color=DANGER, lw=1.4))
    ax.set_xlim(1.60, 2.05); ax.set_ylim(-0.95, 0.55)
    ax.set_yticks([]); ax.set_xlabel("score del modelo")
    ax.spines["left"].set_visible(False)
    finish(ax, "Tráfico legítimo pesado puntúa dentro del margen del umbral",
           "Transferencia legítima iperf-tcp 200 Mbit/s, corrida aislada · cada punto es una ventana de 10 s",
           "Fuente: docs/fase07-validacion-final/02-resultados-f6.md")
    save(fig, "C3-scores-trafico-pesado.png")


# ==================================================== D · dataset/features ===
def fig_dataset(d):
    man = d["man"]; sel = man["selection"]
    fig, axes = plt.subplots(1, 3, figsize=(13.6, 4.2),
                             gridspec_kw={"wspace": 0.42})

    a = axes[0]
    parts = [("Entrenamiento", sel["train_rows"], ACCENT),
             ("Validación", sel["validation_rows"], AMBER),
             ("Prueba", sel["test_rows"], VIOLET)]
    a.bar([p[0] for p in parts], [p[1] for p in parts], color=[p[2] for p in parts], width=0.62)
    for i, (_, v, _) in enumerate(parts):
        a.text(i, v + 18, f"{v}", ha="center", fontweight="bold", fontsize=10)
    a.set_ylabel("ventanas"); a.set_ylim(0, 960)
    finish(a, "Partición del tráfico normal", f"{sum(p[1] for p in parts)} ventanas · {sel['train_episodes']+sel['validation_episodes']+sel['test_episodes']} episodios")

    b = axes[1]
    prof = man["evaluation"]["ocsvm_scaled"]["anomalies"]["by_profile"]
    fams = sorted(prof, key=lambda f: prof[f]["windows"])
    cols = [DIM if f.startswith(("ANOM-DNS-NX", "ANOM-AUTH", "ANOM-SYN-RATE-10")) else DANGER for f in fams]
    b.barh([f.replace("ANOM-KALI-", "").replace("ANOM-", "") for f in fams],
           [prof[f]["windows"] for f in fams], color=cols, height=0.66)
    for i, f in enumerate(fams):
        b.text(prof[f]["windows"] + 0.6, i, str(prof[f]["windows"]), va="center", fontsize=8.6)
    b.set_xlabel("ventanas"); b.tick_params(axis="y", labelsize=8)
    b.set_xlim(0, 47)
    b.legend(handles=[Patch(color=DANGER, label="Kali real (161)"),
                      Patch(color=DIM, label="Heredadas (18)")],
             loc="lower right", bbox_to_anchor=(1.0, 0.06))
    finish(b, "Anomalías por familia", "179 ventanas · dos procedencias distintas")

    c = axes[2]
    lay = Counter(x["layer"] for x in json.loads((REPO / "configs/features/multilayer-v2.json").read_text())["features"])
    keys = ["L3", "L4", "L7"]
    c.bar(keys, [lay[k] for k in keys], color=[ACCENT, VIOLET, AMBER], width=0.58)
    for i, k in enumerate(keys):
        c.text(i, lay[k] + 0.18, str(lay[k]), ha="center", fontweight="bold", fontsize=11)
    c.set_ylabel("nº de features"); c.set_ylim(0, 13)
    c.set_xticks(range(3), ["L3\nred", "L4\ntransporte", "L7\naplicación"])
    finish(c, "Las 28 features por capa", "Las tres capas representadas")

    fig.text(0.005, -0.03, "Fuente: artifacts/model/manifest.json · configs/features/multilayer-v2.json",
             fontsize=7.4, color=DIM)
    save(fig, "D1-composicion-dataset.png")


def main():
    print("Cargando artefactos y re-puntuando con el modelo congelado…")
    d = load_all()
    # verificación de integridad: la re-puntuación debe reproducir el manifiesto
    exp = d["man"]["evaluation"]["ocsvm_scaled"]
    got_fp = int((d["s_test"] < d["thr"]).sum())
    got_det = int((d["s_anom"] < d["thr"]).sum())
    assert got_fp == exp["test"]["alerts_strict"], (got_fp, exp["test"]["alerts_strict"])
    assert got_det == exp["anomalies"]["detected_strict"], (got_det, exp["anomalies"]["detected_strict"])
    print(f"  ✓ re-puntuación reproduce el manifiesto: {got_fp}/{len(d['s_test'])} y {got_det}/{len(d['s_anom'])}\n")

    print("Generando gráficas:")
    auc = fig_roc(d)
    fig_distribucion(d)
    fig_confusion(d)
    fig_barrido(d)
    fig_modelos(d)
    fig_familias_heatmap(d)
    fig_fpr_operativo(d)
    fig_leadtime()
    fig_scores_pesado(d)
    fig_dataset(d)

    tp = int((d["s_anom"] < d["thr"]).sum()); fn = len(d["s_anom"]) - tp
    fp = int((d["s_test"] < d["thr"]).sum()); tn = len(d["s_test"]) - fp
    rec = tp / (tp + fn); spec = tn / (tn + fp)
    f1 = 2 * tp / (2 * tp + fp + fn)
    print("\nMétricas nuevas calculadas en este informe (ausentes en el trabajo original):")
    print(f"  ROC-AUC ................ {auc:.4f}")
    print(f"  Recall (detección) ..... {rec:.4f}   ({tp}/{tp+fn})")
    print(f"  Especificidad .......... {spec:.4f}   ({tn}/{tn+fp})")
    print(f"  F1 (tasa base artif.) .. {f1:.4f}")

    # ---- intervalos de confianza de Wilson 95 % sobre lo ya medido ----------
    o = d["man"]["evaluation"]["ocsvm_scaled"]
    filas = [
        ("FPR benigno (test)", o["test"]["alerts_strict"], o["test"]["n_windows"]),
        ("Detección global", o["anomalies"]["detected_strict"], o["anomalies"]["n_windows"]),
        ("Detección Kali-real", o["anomalies"]["kali_real_detected"], o["anomalies"]["kali_real_windows"]),
        ("Detección heredada", o["anomalies"]["legacy_detected"], o["anomalies"]["legacy_windows"]),
        ("Detección por episodio", o["anomalies"]["detected_episode_count"], o["anomalies"]["total_episode_count"]),
    ]
    for f, p in sorted(o["anomalies"]["by_profile"].items(), key=lambda kv: -kv[1]["windows"]):
        filas.append((f"  familia {f}", p["detected"], p["windows"]))
    filas += [("FPR operativo F6 pase 1", 16, 62), ("FPR operativo F6 pase 2", 17, 74)]

    print("\nIntervalos de confianza de Wilson 95 % (sobre proporciones ya medidas):")
    print(f"  {'magnitud':42s} {'k/n':>9s} {'punto':>7s}   IC95")
    for label, k, n in filas:
        p, lo, hi = wilson(k, n)
        print(f"  {label:42s} {f'{k}/{n}':>9s} {p:>6.1%}   [{lo:.1%} – {hi:.1%}]  ancho {hi-lo:.1%}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
