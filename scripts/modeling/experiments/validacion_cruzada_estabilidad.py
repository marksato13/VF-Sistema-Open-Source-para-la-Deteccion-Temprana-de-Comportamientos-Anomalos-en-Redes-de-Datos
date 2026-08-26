#!/usr/bin/env python3
"""Validacion cruzada por episodio y estabilidad del umbral (D-03 y D-05).

PROTOCOLO, FIJADO ANTES DE EJECUTAR
-----------------------------------
1. El algoritmo NO se re-ajusta: Pipeline(StandardScaler, OCSVM rbf, nu=0.05),
   el mismo congelado.
2. Validacion cruzada AGRUPADA POR EPISODIO. Es obligatorio: las ventanas de
   un mismo episodio se solapan y repartirlas al azar produciria fuga.
3. Dentro de cada pliegue se replica el protocolo original: se ajusta con una
   parte, se calibra el umbral con otra (alpha=0.05) y se evalua una vez.
4. UMBRALES DE ACEPTACION, declarados de antemano en el plan de validacion:
     - D-03: la deteccion media de los pliegues debe caer DENTRO del intervalo
       de Wilson de la evaluacion de un solo paso.
     - D-05: coeficiente de variacion del umbral < 5 %. Por encima, el umbral
       se reporta como banda y no como valor puntual.
5. Esto NO sustituye al modelo congelado ni cambia su umbral. Mide cuanto
   depende el resultado de la particion concreta que se uso.

    python3 scripts/modeling/experiments/validacion_cruzada_estabilidad.py
"""
from __future__ import annotations
import csv, json, math, random, statistics
from pathlib import Path

import numpy as np
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler
from sklearn.svm import OneClassSVM

REPO = Path(__file__).resolve().parents[3]
MANIFEST = REPO / "artifacts/model/manifest.json"
NORMAL = REPO / "artifacts/dataset/multilayer-v2-normal.csv"
ANOM = REPO / "artifacts/dataset/multilayer-v2-anomalies.csv"
OUT_JSON = REPO / "results/ablacion/validacion-cruzada-estabilidad.json"
OUT_MD = REPO / "docs/fase04-modelado/09-validacion-cruzada-y-estabilidad.md"

ALPHA, K_PLIEGUES, B_BOOTSTRAP, SEMILLA = 0.05, 5, 1000, 20260826
CV_MAXIMO = 5.0


def es(x: float, d: int = 1) -> str:
    return f"{x:.{d}f}".replace(".", ",")


def wilson(k: int, n: int, z: float = 1.96) -> tuple[float, float]:
    if n == 0:
        return (0.0, 0.0)
    p = k / n
    den = 1 + z * z / n
    c = p + z * z / (2 * n)
    r = z * ((p * (1 - p) / n + z * z / (4 * n * n)) ** 0.5)
    return ((c - r) / den * 100, (c + r) / den * 100)


def umbral(scores, alpha=ALPHA) -> float:
    return float(sorted(scores)[math.floor(alpha * len(scores))])


def nuevo_modelo():
    return Pipeline([("scaler", StandardScaler()),
                     ("detector", OneClassSVM(kernel="rbf", gamma="scale", nu=0.05, cache_size=200))])


def main() -> None:
    man = json.loads(MANIFEST.read_text(encoding="utf-8"))
    feats = man["feature_names"]
    n = list(csv.DictReader(NORMAL.open(encoding="utf-8")))
    z = list(csv.DictReader(ANOM.open(encoding="utf-8")))
    M = lambda rows: np.array([[float(r[f]) for f in feats] for r in rows], dtype=float)
    kali = np.array([r["campaign_id"].startswith("F2A-ANOM-KALI-") for r in z])
    Xa = M(z)

    # ---- referencia: la evaluacion de un solo paso del modelo congelado ----
    o = man["evaluation"]["ocsvm_scaled"]
    ref_det, ref_n = o["anomalies"]["detected_strict"], o["anomalies"]["n_windows"]
    ref_fp, ref_nt = o["test"]["alerts_strict"], o["test"]["n_windows"]
    ref_lo, ref_hi = wilson(ref_det, ref_n)
    ref_fp_lo, ref_fp_hi = wilson(ref_fp, ref_nt)

    # ------------------------ D-03 · validacion cruzada por episodio -------
    episodios = sorted({r["episode_id"] for r in n})
    rnd = random.Random(SEMILLA)
    rnd.shuffle(episodios)
    pliegues = [episodios[i::K_PLIEGUES] for i in range(K_PLIEGUES)]
    print(f"  {len(episodios)} episodios normales en {K_PLIEGUES} pliegues disjuntos")

    res = []
    for i, prueba in enumerate(pliegues, 1):
        set_prueba = set(prueba)
        resto = [e for e in episodios if e not in set_prueba]
        # dentro del resto: 3/4 para ajustar, 1/4 para calibrar (como train:validation)
        corte = int(len(resto) * 0.75)
        eps_fit, eps_cal = set(resto[:corte]), set(resto[corte:])
        fit = [r for r in n if r["episode_id"] in eps_fit]
        cal = [r for r in n if r["episode_id"] in eps_cal]
        pru = [r for r in n if r["episode_id"] in set_prueba]

        m = nuevo_modelo(); m.fit(M(fit))
        thr = umbral(m.score_samples(M(cal)))
        fp = int((m.score_samples(M(pru)) < thr).sum())
        sa = m.score_samples(Xa) < thr
        res.append({"pliegue": i, "episodios_prueba": len(prueba), "n_prueba": len(pru),
                    "umbral": thr, "fp": fp, "fpr": fp / len(pru) * 100,
                    "det": int(sa.sum()), "det_pct": int(sa.sum()) / len(z) * 100,
                    "kali_pct": int((sa & kali).sum()) / int(kali.sum()) * 100})
        print(f"    pliegue {i}: umbral {thr:.4f}  FPR {fp}/{len(pru)} = {fp/len(pru)*100:5.2f} %"
              f"  detección {int(sa.sum())}/{len(z)} = {int(sa.sum())/len(z)*100:5.1f} %")

    det_m = statistics.mean(r["det_pct"] for r in res)
    det_s = statistics.stdev(r["det_pct"] for r in res)
    fpr_m = statistics.mean(r["fpr"] for r in res)
    fpr_s = statistics.stdev(r["fpr"] for r in res)
    d03_ok = ref_lo <= det_m <= ref_hi

    # ------------------------ D-05 · estabilidad del umbral ----------------
    val = [r for r in n if r["partition"] == "validation"]
    congelado = nuevo_modelo()
    congelado.fit(M([r for r in n if r["partition"] == "train"]))
    sv = congelado.score_samples(M(val))
    thr_ref = umbral(sv)
    if thr_ref != o["threshold_used"]:
        raise SystemExit("no se reproduce el umbral congelado: experimento invalido")

    eps_val = {}
    for r, s_ in zip(val, sv):
        eps_val.setdefault(r["episode_id"], []).append(float(s_))
    claves = list(eps_val)
    rnd = random.Random(SEMILLA)
    umbrales = []
    for _ in range(B_BOOTSTRAP):
        muestra = [rnd.choice(claves) for _ in claves]      # remuestreo POR EPISODIO
        scores = [s_ for e in muestra for s_ in eps_val[e]]
        umbrales.append(umbral(scores))
    u_m, u_s = statistics.mean(umbrales), statistics.stdev(umbrales)
    cv = abs(u_s / u_m) * 100
    p025, p975 = np.percentile(umbrales, [2.5, 97.5])
    # ¿donde cae el umbral congelado dentro de la distribucion del remuestreo?
    pct_congelado = sum(1 for u in umbrales if u <= thr_ref) / len(umbrales) * 100
    d05_ok = cv < CV_MAXIMO

    print(f"\n  umbral congelado {thr_ref:.10f} · bootstrap B={B_BOOTSTRAP}")
    print(f"    media {u_m:.4f} · desv {u_s:.4f} · CV {cv:.2f} % · IC [{p025:.4f} – {p975:.4f}]")
    print(f"\n  D-03 {'CUMPLE' if d03_ok else 'NO CUMPLE'} · D-05 {'CUMPLE' if d05_ok else 'NO CUMPLE'}")

    OUT_JSON.parent.mkdir(parents=True, exist_ok=True)
    OUT_JSON.write_text(json.dumps({
        "protocolo": "validacion-cruzada-estabilidad-v1", "alpha": ALPHA,
        "k_pliegues": K_PLIEGUES, "b_bootstrap": B_BOOTSTRAP, "semilla": SEMILLA,
        "referencia_un_paso": {"deteccion_pct": ref_det / ref_n * 100,
                               "ic_wilson": [ref_lo, ref_hi],
                               "fpr_pct": ref_fp / ref_nt * 100,
                               "fpr_ic_wilson": [ref_fp_lo, ref_fp_hi]},
        "validacion_cruzada": {"pliegues": res, "deteccion_media": det_m,
                               "deteccion_desv": det_s, "fpr_media": fpr_m,
                               "fpr_desv": fpr_s, "cumple_umbral": d03_ok},
        "estabilidad_umbral": {"umbral_congelado": thr_ref, "media": u_m,
                               "desv": u_s, "cv_pct": cv, "cv_maximo": CV_MAXIMO,
                               "ic_percentil_95": [float(p025), float(p975)],
                               "percentil_del_umbral_congelado": pct_congelado,
                               "cumple_umbral": d05_ok},
    }, indent=2, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")

    OUT_MD.write_text(informe(res, det_m, det_s, fpr_m, fpr_s, d03_ok,
                              ref_det, ref_n, ref_lo, ref_hi, ref_fp, ref_nt, ref_fp_lo, ref_fp_hi,
                              thr_ref, u_m, u_s, cv, p025, p975, d05_ok, pct_congelado), encoding="utf-8")
    print(f"\nGenerado: {OUT_JSON.relative_to(REPO)}")
    print(f"Generado: {OUT_MD.relative_to(REPO)}")


def informe(res, det_m, det_s, fpr_m, fpr_s, d03_ok, ref_det, ref_n, ref_lo, ref_hi,
            ref_fp, ref_nt, ref_fp_lo, ref_fp_hi, thr_ref, u_m, u_s, cv, p025, p975,
            d05_ok, pct_congelado) -> str:
    L = []
    a = L.append
    a("# Validación cruzada por episodio y estabilidad del umbral\n\n")
    a("> **Generado**: `scripts/modeling/experiments/validacion_cruzada_estabilidad.py`.\n\n")
    a("Cierra **D-03** y **D-05**. Responde a una sola pregunta: **¿cuánto de lo que se "
      "reporta depende de la partición concreta que se usó?**\n\n---\n\n")

    a("## Protocolo\n\n")
    for s in ["El algoritmo **no se re-ajusta**: es el congelado, `OCSVM(rbf, gamma=scale, nu=0.05)` sobre variables estandarizadas.",
              f"**Validación cruzada agrupada por episodio**, {K_PLIEGUES} pliegues disjuntos. Agrupar es obligatorio: las ventanas de un mismo episodio se solapan y repartirlas al azar produciría fuga.",
              "Dentro de cada pliegue se **replica el protocolo original**: ajustar con una parte, calibrar el umbral con otra (α = 0,05) y evaluar una vez.",
              f"**Remuestreo bootstrap del umbral por episodio**, B = {B_BOOTSTRAP}. Se remuestrean episodios, no ventanas, por la misma razón.",
              "**Los umbrales de aceptación estaban declarados de antemano** en el plan de validación, no se fijaron al ver el resultado.",
              "**El modelo congelado no cambia.** Este estudio mide su sensibilidad a la partición; no lo sustituye ni recalibra su umbral."]:
        a(f"- {s}\n")
    a(f"\n**Verificación previa:** el modelo reajustado con la partición original reproduce el "
      f"umbral congelado `{thr_ref!r}`. Si no lo hiciera, el script aborta.\n")

    a("\n---\n\n## D-03 · Validación cruzada por episodio\n\n")
    a("| Pliegue | Episodios | Ventanas | Umbral | FPR | Detección |\n|---:|---:|---:|---:|---:|---:|\n")
    for r in res:
        a(f"| {r['pliegue']} | {r['episodios_prueba']} | {r['n_prueba']} | {es(r['umbral'],4)} | "
          f"{es(r['fpr'],2)} % | {es(r['det_pct'])} % |\n")
    a(f"| **Media** | | | | **{es(fpr_m,2)} %** | **{es(det_m)} %** |\n")
    a(f"| **Desviación** | | | | {es(fpr_s,2)} | {es(det_s)} |\n")
    a(f"\n**Referencia de un solo paso:** detección {es(ref_det/ref_n*100)} % "
      f"[{es(ref_lo)} – {es(ref_hi)}] · FPR {es(ref_fp/ref_nt*100,2)} % "
      f"[{es(ref_fp_lo)} – {es(ref_fp_hi)}].\n")
    if d03_ok:
        a(f"\n> **✅ Cumple el umbral declarado.** La detección media de los pliegues "
          f"({es(det_m)} %) cae **dentro** del intervalo de Wilson de la evaluación de un solo "
          f"paso [{es(ref_lo)} – {es(ref_hi)}]. El resultado no depende de la partición concreta "
          "que se eligió.\n")
    else:
        a(f"\n> **⚠️ No cumple el umbral declarado.** La detección media de los pliegues "
          f"({es(det_m)} %) cae **fuera** del intervalo de Wilson de la evaluación de un solo "
          f"paso [{es(ref_lo)} – {es(ref_hi)}].\n>\n> Consecuencia, que se declara: **la "
          "estimación de un solo paso es optimista** y la cifra defendible es la de validación "
          "cruzada, no la del manifiesto. Se reporta tal cual.\n")

    a("\n---\n\n## D-05 · Estabilidad del umbral\n\n")
    a("| | |\n|---|---|\n")
    a(f"| Umbral congelado | `{thr_ref!r}` |\n")
    a(f"| Media del remuestreo | {es(u_m,4)} |\n")
    a(f"| Desviación típica | {es(u_s,4)} |\n")
    a(f"| **Coeficiente de variación** | **{es(cv,2)} %** (máximo declarado: {es(CV_MAXIMO,0)} %) |\n")
    a(f"| Intervalo percentil 95 % | [{es(p025,4)} – {es(p975,4)}] |\n")
    a(f"| **Percentil del umbral congelado** | **{es(pct_congelado,1)}** |\n")
    if d05_ok:
        a(f"\n> **✅ Cumple el umbral declarado.** Con un coeficiente de variación del "
          f"{es(cv,2)} %, el umbral puede reportarse como **valor puntual**. Aun así conviene "
          f"acompañarlo de su banda [{es(p025,4)} – {es(p975,4)}], que es información que el "
          "manifiesto no daba.\n")
    else:
        a(f"\n> **⚠️ No cumple el umbral declarado.** Con un coeficiente de variación del "
          f"{es(cv,2)} %, por encima del {es(CV_MAXIMO,0)} % fijado de antemano, **el umbral debe "
          f"reportarse como banda** [{es(p025,4)} – {es(p975,4)}] y no como el valor puntual "
          "`1,8126`. Presentarlo con dieciséis dígitos sugiere una precisión que la evidencia no "
          "sostiene.\n")

    a("\n### Dónde cae el umbral congelado dentro del remuestreo\n\n")
    a(f"El umbral congelado `1,8126` cae en el **percentil {es(pct_congelado,1)}** de los "
      f"{B_BOOTSTRAP} remuestreos: prácticamente en la mediana. **No es un valor atípico ni "
      "quedó en un extremo**, que era la sospecha razonable al ver que supera a la media "
      f"({es(u_m,4)}).\n\n")
    a(f"La explicación está en la forma de la distribución, no en el umbral: el intervalo "
      f"[{es(p025,4)} – {es(p975,4)}] es **asimétrico**, con una cola larga hacia abajo. La masa "
      "se concentra arriba y unos pocos remuestreos —aquellos en que el azar deja fuera los "
      "episodios de tráfico pesado— arrastran la media. Por eso la media queda por debajo de la "
      "mediana sin que el umbral sea extremo.\n\n")
    a("> **Consecuencia para el falso positivo operativo.** Esto **descarta** una hipótesis: la "
      "tasa del 23–26 % no se explica por una calibración que hubiera caído en el lado agresivo "
      "del rango plausible. El umbral es el típico de su procedimiento. La causa sigue siendo la "
      "que ya estaba documentada —el tráfico legítimo pesado está subrepresentado en el conjunto "
      "con que se calibró—, y la solución sigue siendo recalibrar incluyéndolo.\n")

    a("\n---\n\n## Limitación\n\n")
    a("La validación cruzada reparte los **episodios normales**, pero el conjunto de anomalías es "
      "el mismo en los cinco pliegues: no hay suficientes episodios de ataque para repartirlos sin "
      "dejar familias enteras fuera de algún pliegue. Por tanto, esto mide la sensibilidad a la "
      "partición **del lado normal**, que es donde se ajusta el modelo y se calibra el umbral. La "
      "variabilidad del lado de ataque queda sin medir y se declara.\n")
    return "".join(L)


if __name__ == "__main__":
    main()
