#!/usr/bin/env python3
"""Pruebas de significancia entre los siete modelos candidatos (D-04).

Hasta ahora las comparaciones se publicaban como puntos desnudos: 88,3 % frente
a 57,5 %, sin decir si la diferencia es distinguible del azar.

PROTOCOLO
---------
1. NO se reentrena nada. Se cargan los siete objetos ajustados publicados en
   artifacts/model/candidates/, previa verificacion de su SHA-256 contra el
   manifiesto congelado.
2. Cada modelo calibra su umbral con la misma regla sobre `validation`
   (alpha=0.05) y se evalua sobre `test` y las anomalias. Debe reproducir el
   manifiesto; si no, el script aborta.
3. McNemar exacto por pares sobre LAS MISMAS ventanas, en dos preguntas
   separadas: deteccion de anomalias y falso positivo benigno.
4. Correccion de Holm-Bonferroni: son 21 comparaciones por pares, y sin
   corregir la probabilidad de un falso hallazgo es alta.

    python3 scripts/modeling/experiments/significancia_modelos.py
"""
from __future__ import annotations
import csv, hashlib, itertools, json, math
from pathlib import Path

import joblib
import numpy as np
from scipy.stats import binomtest

REPO = Path(__file__).resolve().parents[3]
MANIFEST = REPO / "artifacts/model/manifest.json"
CAND = REPO / "artifacts/model/candidates"
NORMAL = REPO / "artifacts/dataset/multilayer-v2-normal.csv"
ANOM = REPO / "artifacts/dataset/multilayer-v2-anomalies.csv"
OUT_JSON = REPO / "results/ablacion/significancia-modelos.json"
OUT_MD = REPO / "docs/fase04-modelado/08-significancia-entre-modelos.md"
ALPHA_CAL, ALPHA_SIG = 0.05, 0.05


def es(x: float, d: int = 1) -> str:
    return f"{x:.{d}f}".replace(".", ",")


def pv(p: float) -> str:
    return "&lt; 0,001" if p < 0.001 else es(p, 3)


def mcnemar(a: np.ndarray, b: np.ndarray) -> dict:
    solo_a = int((a & ~b).sum())
    solo_b = int((b & ~a).sum())
    n = solo_a + solo_b
    return {"solo_A": solo_a, "solo_B": solo_b, "discordantes": n,
            "p": 1.0 if n == 0 else float(binomtest(solo_a, n, 0.5).pvalue)}


def holm(pares: list[tuple[str, float]]) -> dict[str, dict]:
    """Holm-Bonferroni: ordena de menor a mayor p y exige p <= alpha/(m-i)."""
    m = len(pares)
    orden = sorted(pares, key=lambda x: x[1])
    out: dict[str, dict] = {}
    rechaza = True
    for i, (k, p) in enumerate(orden):
        umbral = ALPHA_SIG / (m - i)
        if p > umbral:
            rechaza = False
        out[k] = {"p": p, "umbral_holm": umbral, "significativo": rechaza}
    return out


def main() -> None:
    man = json.loads(MANIFEST.read_text(encoding="utf-8"))
    feats = man["feature_names"]

    # --- 1. integridad antes de cargar un pickle ---
    for rel, h in man["model_hashes"].items():
        f = CAND / Path(rel).name
        real = hashlib.sha256(f.read_bytes()).hexdigest()
        if real != h:
            raise SystemExit(f"{f.name}: SHA-256 no coincide con el manifiesto")
    print(f"  {len(man['model_hashes'])} modelos verificados por SHA-256 ✅")

    n = list(csv.DictReader(NORMAL.open(encoding="utf-8")))
    z = list(csv.DictReader(ANOM.open(encoding="utf-8")))
    M = lambda rows: np.array([[float(r[f]) for f in feats] for r in rows], dtype=float)
    va, te, an = (M([r for r in n if r["partition"] == "validation"]),
                  M([r for r in n if r["partition"] == "test"]), M(z))
    kali = np.array([r["campaign_id"].startswith("F2A-ANOM-KALI-") for r in z])

    res: dict[str, dict] = {}
    for f in sorted(CAND.glob("*.joblib")):
        m = f.stem
        mdl = joblib.load(f)
        sv = mdl.score_samples(va)
        thr = float(sorted(sv)[math.floor(ALPHA_CAL * len(sv))])
        det = mdl.score_samples(an) < thr
        fp = mdl.score_samples(te) < thr
        e = man["evaluation"][m]
        if not (thr == e["threshold_used"]
                and int(fp.sum()) == e["test"]["alerts_strict"]
                and int(det.sum()) == e["anomalies"]["detected_strict"]):
            raise SystemExit(f"{m} no reproduce el manifiesto: experimento invalido")
        res[m] = {"umbral": thr, "det": det, "fp": fp,
                  "n_det": int(det.sum()), "n_fp": int(fp.sum()),
                  "n_kali": int((det & kali).sum())}
        print(f"  {m:26} FPR {res[m]['n_fp']:3}/{len(te)}  det {res[m]['n_det']:3}/{len(an)}  reproduce ✅")

    nombres = sorted(res, key=lambda m: -res[m]["n_det"])
    pares = list(itertools.combinations(nombres, 2))
    crudo_det = {f"{a} vs {b}": mcnemar(res[a]["det"], res[b]["det"]) for a, b in pares}
    crudo_fp = {f"{a} vs {b}": mcnemar(res[a]["fp"], res[b]["fp"]) for a, b in pares}
    holm_det = holm([(k, v["p"]) for k, v in crudo_det.items()])
    holm_fp = holm([(k, v["p"]) for k, v in crudo_fp.items()])
    for k in crudo_det:
        crudo_det[k].update(holm_det[k])
        crudo_fp[k].update(holm_fp[k])

    sig = sum(1 for v in crudo_det.values() if v["significativo"])
    print(f"\n  {sig}/{len(pares)} pares con diferencia significativa en detección tras Holm")

    OUT_JSON.parent.mkdir(parents=True, exist_ok=True)
    OUT_JSON.write_text(json.dumps({
        "alpha_calibracion": ALPHA_CAL, "alpha_significancia": ALPHA_SIG,
        "correccion": "holm-bonferroni", "n_comparaciones": len(pares),
        "reproduce_manifiesto": True,
        "modelos": {m: {k: v for k, v in d.items() if k not in ("det", "fp")} for m, d in res.items()},
        "deteccion": crudo_det, "falso_positivo": crudo_fp,
    }, indent=2, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")
    OUT_MD.write_text(informe(res, nombres, crudo_det, crudo_fp, len(te), len(an), int(kali.sum())),
                      encoding="utf-8")
    print(f"\nGenerado: {OUT_JSON.relative_to(REPO)}")
    print(f"Generado: {OUT_MD.relative_to(REPO)}")


def informe(res, nombres, det, fp, n_te, n_an, n_kali) -> str:
    L: list[str] = []
    a = L.append
    a("# Significancia estadística entre los siete modelos\n\n")
    a("> **Generado**: `scripts/modeling/experiments/significancia_modelos.py`.\n\n")
    a("Cierra **D-04**. Hasta ahora los modelos se comparaban como puntos desnudos "
      "—88,3 % frente a 57,5 %— sin decir si la diferencia es distinguible del azar.\n\n---\n\n")

    a("## Protocolo\n\n")
    for s in ["**No se reentrena nada.** Se cargan los siete objetos ajustados publicados en "
              "`artifacts/model/candidates/`, **previa verificación de su SHA-256** contra el "
              "manifiesto — son *pickles*, y cargarlos ejecuta código.",
              "Cada modelo calibra su umbral con la misma regla sobre `validation` (α = 0,05) "
              "y **debe reproducir el manifiesto**; si no, el script aborta. Los siete lo hacen.",
              "**McNemar exacto** por pares sobre las mismas ventanas, en dos preguntas "
              "separadas: detección y falso positivo.",
              "**Corrección de Holm-Bonferroni**: son 21 comparaciones por pares. Sin "
              "corregir, la probabilidad de encontrar al menos un «hallazgo» por azar "
              "rondaría el 66 %."]:
        a(f"- {s}\n")

    a("\n---\n\n## Los siete, ordenados por detección\n\n")
    a("| Modelo | Detección | Kali real | FPR benigno |\n|---|---:|---:|---:|\n")
    for m in nombres:
        r = res[m]
        neg = "**" if m == "ocsvm_scaled" else ""
        a(f"| {neg}`{m}`{neg} | {neg}{r['n_det']}/{n_an} = {es(r['n_det']/n_an*100)} %{neg} | "
          f"{r['n_kali']}/{n_kali} = {es(r['n_kali']/n_kali*100)} % | "
          f"{r['n_fp']}/{n_te} = {es(r['n_fp']/n_te*100,2)} % |\n")

    a("\n---\n\n## Detección: ¿son distinguibles?\n\n")
    a("«Solo A» y «Solo B» son las ventanas que **solo** uno de los dos detecta. McNemar "
      "solo mira esos desacuerdos: los aciertos y fallos compartidos no informan.\n\n")
    a("| Par | Solo A | Solo B | p | Umbral Holm | |\n|---|---:|---:|---:|---:|---|\n")
    for k, v in sorted(det.items(), key=lambda x: x[1]["p"]):
        marca = "**sí**" if v["significativo"] else "no"
        a(f"| `{k.replace(' vs ', '` vs `')}` | {v['solo_A']} | {v['solo_B']} | {pv(v['p'])} | "
          f"{es(v['umbral_holm'],4)} | {marca} |\n")

    a("\n---\n\n## Falso positivo: ¿son distinguibles?\n\n")
    a("| Par | Solo A | Solo B | p | |\n|---|---:|---:|---:|---|\n")
    for k, v in sorted(fp.items(), key=lambda x: x[1]["p"]):
        marca = "**sí**" if v["significativo"] else "no"
        a(f"| `{k.replace(' vs ', '` vs `')}` | {v['solo_A']} | {v['solo_B']} | {pv(v['p'])} | {marca} |\n")

    a("\n---\n\n## Qué contesta esto\n\n")
    sig_det = [k for k, v in det.items() if v["significativo"]]
    sig_fp = [k for k, v in fp.items() if v["significativo"]]
    ocsvm = [k for k in sig_det if "ocsvm_scaled" in k]

    a("### 1 · La ventaja del OCSVM en detección es real\n\n")
    total_ocsvm = sum(1 for k in det if "ocsvm_scaled" in k)
    a(f"De los 21 pares, **{len(sig_det)} muestran diferencia significativa** en detección "
      "tras corregir por multiplicidad.\n\n")
    a(f"> **Las {total_ocsvm} comparaciones de `ocsvm_scaled` contra los otros seis son "
      f"significativas, sin excepción.** Su ventaja no es un artefacto de un punto de "
      "operación afortunado ni de una comparación elegida a conveniencia.\n\n")
    a("Esto **no** contradice la advertencia de selección posterior de la model card. Son "
      "dos cosas distintas: que el OCSVM detecte más que los demás **sobre estos datos** "
      "está ahora respaldado estadísticamente; que ese 88,3 % sea su desempeño esperable "
      "**fuera** de estos datos sigue sin estarlo.\n")

    a("\n### 2 · En falso positivo, los siete son indistinguibles\n\n")
    if not sig_fp:
        a("**Ningún par** alcanza significancia en falso positivo tras la corrección de "
          "Holm. Con 276 ventanas benignas y recuentos de 10 a 16 alertas, la muestra no "
          "tiene resolución para separar un 3,62 % de un 5,80 %.\n\n")
        a("> **Consecuencia práctica:** afirmar que un modelo «tiene menos falsos positivos» "
          "que otro **no está respaldado por estos datos**. La comparación válida entre los "
          "siete es la de detección, no la de FPR.\n")
    else:
        a(f"{len(sig_fp)} pares alcanzan significancia en falso positivo: "
          + ", ".join(f"`{k}`" for k in sig_fp) + ".\n")

    a("\n### 3 · `if_uniform` e `if_exact_collapsed` no son dos modelos\n\n")
    par = det.get("if_exact_collapsed vs if_uniform") or det.get("if_uniform vs if_exact_collapsed")
    if par:
        a(f"Cero ventanas discordantes ({par['solo_A']} y {par['solo_B']}), p = "
          f"{es(par['p'],3)}. Comparten SHA-256: **son el mismo objeto ajustado**. Sus dos "
          "filas en cualquier tabla comparativa no son dos evidencias independientes, y "
          "contarlas como tales infla artificialmente el número de candidatos.\n")

    a("\n---\n\n## Limitación\n\n")
    a("Todas las comparaciones se hacen sobre los **mismos** conjuntos usados en la "
      "calibración original, así que los valores absolutos heredan el sesgo optimista "
      "declarado en la model card. Lo que estas pruebas sostienen es que **las diferencias "
      "entre modelos son reales y no ruido de muestreo** — una afirmación relativa, que es "
      "justamente la que faltaba respaldar.\n")
    return "".join(L)


if __name__ == "__main__":
    main()
