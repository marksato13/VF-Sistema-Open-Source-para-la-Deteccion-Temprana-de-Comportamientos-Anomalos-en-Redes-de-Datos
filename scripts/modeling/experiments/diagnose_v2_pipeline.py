#!/usr/bin/env python3
"""Diagnóstico experimental (solo lectura) del pipeline Isolation Forest multilayer-v2.

Este script NO es el modelo oficial ni lo reemplaza. No modifica
``scripts/modeling/train_multilayer_v2.py``, ni el dataset congelado, ni ningún
reporte oficial ya publicado. Solo lee los CSV/esquema existentes, entrena
variantes experimentales de Isolation Forest en memoria y reporta métricas para
apoyar la investigación de por qué el modelo oficial (ROC-AUC≈0.60 con el
protocolo por ventana) tiene bajo desempeño. No genera tráfico de red ni toca
ninguna VM.

Preguntas que responde, en este orden:
  1. Efecto del escalado (StandardScaler) sobre train/validation/test/anomalías.
  2. Efecto de ``max_samples`` de IsolationForest, con y sin escalado.
  3. Redundancia (correlación de Pearson) entre las features con separación
     univariante notable (Cohen's d > 0.5 entre train+validation normal y las
     anomalías de evaluation_only), calculada SOLO sobre train+validation
     (nunca sobre test).
  4. Efecto de seleccionar solo las top-N features por Cohen's d.
  5. Dilución por episodio: cuántas ventanas anómalas individualmente
     detectadas se "pierden" al promediar features por episodio (igual que
     ``episode_mean()`` en ``train_multilayer_v2.py``).

Uso:
    python3 scripts/modeling/experiments/diagnose_v2_pipeline.py \\
        --normal artifacts/dataset/multilayer-v2-normal.csv \\
        --anomalies artifacts/dataset/multilayer-v2-anomalies.csv \\
        --schema configs/features/multilayer-v2.json \\
        --output artifacts/dataset/multilayer-v2-pipeline-diagnosis.json
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

try:
    import numpy as np
    import sklearn
    from sklearn.ensemble import IsolationForest
    from sklearn.metrics import average_precision_score, roc_auc_score
    from sklearn.preprocessing import StandardScaler
except ImportError as exc:  # pragma: no cover - reportado tal cual, no simulado.
    print(
        f"ERROR: dependencia faltante ({exc}). Instala scikit-learn/numpy en el "
        "entorno virtual del proyecto (por ejemplo: .venv/bin/python -m pip install "
        "-r requirements-model.txt) antes de ejecutar este diagnóstico.",
        file=sys.stderr,
    )
    raise SystemExit(1)

BASE_PARAMS = {
    "n_estimators": 500,
    "contamination": "auto",
    "max_features": 1.0,
    "random_state": 20260813,
    "n_jobs": 1,
}
VALIDATION_QUANTILE = 0.05


def read_csv(path: Path) -> list[dict]:
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def load_schema_feature_names(schema_path: Path) -> list[str]:
    contract = json.loads(schema_path.read_text(encoding="utf-8"))
    features = contract["features"]
    if len(features) != 28:
        raise ValueError(f"el esquema debe tener 28 features, tiene {len(features)}")
    return [item["name"] for item in sorted(features, key=lambda item: item["order"])]


def to_matrix(rows: list[dict], names: list[str]) -> "np.ndarray":
    return np.asarray([[float(r[k]) for k in names] for r in rows], dtype=float)


def episode_mean(rows: list[dict], names: list[str]) -> list[dict]:
    """Reproduce la agregación por episodio de ``train_multilayer_v2.py``:
    promedia el VALOR CRUDO de cada feature dentro de un episodio (no el score),
    produciendo una fila sintética por episodio."""
    grouped: dict[str, list[dict]] = {}
    for r in rows:
        grouped.setdefault(r["episode_id"], []).append(r)
    out = []
    for episode_id, items in grouped.items():
        row = {"episode_id": episode_id}
        for k in names:
            row[k] = sum(float(x[k]) for x in items) / len(items)
        out.append(row)
    return out


def fit_and_score(xtrain, xval, xtest, xanom, scale: bool, max_samples) -> dict:
    if scale:
        scaler = StandardScaler().fit(xtrain)
        ztrain = scaler.transform(xtrain)
        zval = scaler.transform(xval)
        ztest = scaler.transform(xtest)
        zanom = scaler.transform(xanom)
    else:
        scaler = None
        ztrain, zval, ztest, zanom = xtrain, xval, xtest, xanom

    params = dict(BASE_PARAMS)
    params["max_samples"] = max_samples
    model = IsolationForest(**params).fit(ztrain)

    val_scores = model.decision_function(zval)
    threshold = float(np.quantile(val_scores, VALIDATION_QUANTILE))
    test_scores = model.decision_function(ztest)
    anom_scores = model.decision_function(zanom)

    y = np.r_[np.zeros(len(test_scores)), np.ones(len(anom_scores))]
    s = np.r_[-test_scores, -anom_scores]
    roc_auc = float(roc_auc_score(y, s)) if len(set(y.tolist())) > 1 else None
    average_precision = float(average_precision_score(y, s))

    return {
        "scaled": scale,
        "max_samples": max_samples,
        "roc_auc": roc_auc,
        "average_precision": average_precision,
        "threshold_decision_function": threshold,
        "validation_rows": int(len(xval)),
        "test_rows": int(len(xtest)),
        "anomaly_rows": int(len(xanom)),
        "model": model,
        "scaler": scaler,
        "val_scores": val_scores,
        "test_scores": test_scores,
        "anom_scores": anom_scores,
    }


def strip_internal(result: dict) -> dict:
    return {k: v for k, v in result.items() if k not in ("model", "scaler", "val_scores", "test_scores", "anom_scores")}


def cohens_d_pooled(normal_values: "np.ndarray", anomaly_values: "np.ndarray") -> float:
    n1, n2 = len(normal_values), len(anomaly_values)
    if n1 == 0 or n2 == 0:
        return 0.0
    mean_n, mean_a = float(normal_values.mean()), float(anomaly_values.mean())
    var_n = float(normal_values.var(ddof=1)) if n1 > 1 else 0.0
    var_a = float(anomaly_values.var(ddof=1)) if n2 > 1 else 0.0
    denom = n1 + n2 - 2
    if denom <= 0:
        return 0.0
    pooled_var = ((n1 - 1) * var_n + (n2 - 1) * var_a) / denom
    pooled_sd = pooled_var ** 0.5
    if pooled_sd == 0.0:
        return 0.0
    return (mean_a - mean_n) / pooled_sd


def union_find_clusters(nodes: list[str], edges: list[tuple[str, str]]) -> list[list[str]]:
    parent = {n: n for n in nodes}

    def find(x: str) -> str:
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    def union(a: str, b: str) -> None:
        ra, rb = find(a), find(b)
        if ra != rb:
            parent[ra] = rb

    for a, b in edges:
        union(a, b)

    groups: dict[str, list[str]] = {}
    for n in nodes:
        groups.setdefault(find(n), []).append(n)
    return [sorted(v) for v in groups.values() if len(v) >= 2]


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--normal", type=Path, required=True)
    ap.add_argument("--anomalies", type=Path, required=True)
    ap.add_argument("--schema", type=Path, required=True)
    ap.add_argument("--output", type=Path, required=True)
    args = ap.parse_args()

    names = load_schema_feature_names(args.schema)
    normal_rows = read_csv(args.normal)
    anomaly_rows_all = read_csv(args.anomalies)
    anomaly_rows = [r for r in anomaly_rows_all if r.get("partition") == "evaluation_only"]

    if not normal_rows:
        raise SystemExit("ERROR: el CSV normal está vacío.")
    if not anomaly_rows:
        raise SystemExit("ERROR: no hay filas con partition=='evaluation_only' en el CSV de anomalías.")
    missing_cols = [n for n in names if n not in normal_rows[0]]
    if missing_cols:
        raise SystemExit(f"ERROR: faltan columnas del contrato de 28 features en el CSV normal: {missing_cols}")
    if "episode_id" not in anomaly_rows[0]:
        raise SystemExit("ERROR: el CSV de anomalías no tiene columna episode_id.")

    train = [r for r in normal_rows if r["partition"] == "train"]
    val = [r for r in normal_rows if r["partition"] == "validation"]
    test = [r for r in normal_rows if r["partition"] == "test"]
    if not train or not val or not test:
        raise SystemExit(
            f"ERROR: particiones normales insuficientes (train={len(train)}, validation={len(val)}, test={len(test)})."
        )

    xtrain_full = to_matrix(train, names)
    xval_full = to_matrix(val, names)
    xtest_full = to_matrix(test, names)
    xanom_full = to_matrix(anomaly_rows, names)

    report: dict = {
        "schema_version": "multilayer-v2-pipeline-diagnosis",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "purpose": "Diagnóstico experimental de sensibilidad; NO reemplaza al modelo oficial train_multilayer_v2.py.",
        "sklearn_version": sklearn.__version__,
        "numpy_version": np.__version__,
        "features_schema": names,
        "feature_count": len(names),
        "train_rows": len(train),
        "validation_rows": len(val),
        "test_rows": len(test),
        "anomaly_rows_evaluation_only": len(anomaly_rows),
        "anomaly_episodes_evaluation_only": len({r["episode_id"] for r in anomaly_rows}),
        "base_model_parameters": BASE_PARAMS,
        "validation_quantile_for_threshold": VALIDATION_QUANTILE,
        "normal_csv_sha256": hashlib.sha256(args.normal.read_bytes()).hexdigest(),
        "anomaly_csv_sha256": hashlib.sha256(args.anomalies.read_bytes()).hexdigest(),
    }

    # --- 1. Efecto del escalado (max_samples='auto', 28 features) --------------------
    scaling_results = {}
    for scale in (False, True):
        r = fit_and_score(xtrain_full, xval_full, xtest_full, xanom_full, scale, "auto")
        scaling_results[str(scale)] = strip_internal(r)
    report["1_scaling_effect"] = scaling_results

    # --- 2. Efecto de max_samples, con y sin escalado (28 features) ------------------
    max_samples_values = ["auto", 32, 20]
    max_samples_results = {}
    all_combo_results: dict[str, dict] = {}
    for scale in (False, True):
        for ms in max_samples_values:
            key = f"scaled={scale}|max_samples={ms}"
            r = fit_and_score(xtrain_full, xval_full, xtest_full, xanom_full, scale, ms)
            max_samples_results[key] = strip_internal(r)
            all_combo_results[key] = r
    report["2_max_samples_effect"] = max_samples_results

    def combo_rank(item: tuple[str, dict]):
        _, r = item
        roc = r["roc_auc"] if r["roc_auc"] is not None else -1.0
        return (roc, r["average_precision"])

    best_combo_key, best_combo = max(all_combo_results.items(), key=combo_rank)
    report["2_best_scaling_max_samples_combo"] = {
        "key": best_combo_key,
        "scaled": best_combo["scaled"],
        "max_samples": best_combo["max_samples"],
        "roc_auc": best_combo["roc_auc"],
        "average_precision": best_combo["average_precision"],
    }
    best_scale_flag = best_combo["scaled"]
    best_max_samples = best_combo["max_samples"]

    # --- 3. Redundancia entre features con separación univariante notable ------------
    normal_train_val = train + val
    x_normal_tv = to_matrix(normal_train_val, names)
    cohens_d = {}
    for i, name in enumerate(names):
        cohens_d[name] = cohens_d_pooled(x_normal_tv[:, i], xanom_full[:, i])
    report["3_cohens_d_train_validation_vs_evaluation_only"] = cohens_d

    separable = sorted([n for n in names if abs(cohens_d[n]) > 0.5], key=lambda n: -abs(cohens_d[n]))
    report["3_separable_features_abs_d_gt_0_5"] = separable
    report["3_separable_feature_count"] = len(separable)

    redundant_pairs = []
    if len(separable) >= 2:
        idx_sep = [names.index(n) for n in separable]
        x_corr_source = x_normal_tv[:, idx_sep]  # SOLO train+validation, nunca test.
        corr = np.corrcoef(x_corr_source, rowvar=False)
        for i in range(len(separable)):
            for j in range(i + 1, len(separable)):
                c = float(corr[i, j])
                if abs(c) > 0.8:
                    redundant_pairs.append({"feature_a": separable[i], "feature_b": separable[j], "pearson_r": c})
    report["3_redundant_pairs_abs_corr_gt_0_8"] = redundant_pairs
    report["3_redundant_pair_count"] = len(redundant_pairs)

    clusters = union_find_clusters(separable, [(p["feature_a"], p["feature_b"]) for p in redundant_pairs])
    report["3_correlated_clusters_size_ge_2"] = clusters
    report["3_correlated_clusters_count"] = len(clusters)
    report["3_correlation_computed_on"] = "train+validation only (never test)"

    # --- 4. Selección top-N features por Cohen's d, con la mejor combinación 1-2 -----
    ranked_by_d = sorted(names, key=lambda n: -abs(cohens_d[n]))
    topn_results = {}
    topn_models: dict[int, dict] = {}
    for n_top in (5, 10, 15, 28):
        subset = ranked_by_d[:n_top]
        idx = [names.index(x) for x in subset]
        xt = xtrain_full[:, idx]
        xv = xval_full[:, idx]
        xte = xtest_full[:, idx]
        xa = xanom_full[:, idx]
        r = fit_and_score(xt, xv, xte, xa, best_scale_flag, best_max_samples)
        topn_results[str(n_top)] = {
            "features": subset,
            "roc_auc": r["roc_auc"],
            "average_precision": r["average_precision"],
            "threshold_decision_function": r["threshold_decision_function"],
        }
        topn_models[n_top] = r
    report["4_topn_feature_selection"] = topn_results
    report["4_scaling_max_samples_used"] = {"scaled": best_scale_flag, "max_samples": best_max_samples}
    report["4_WARNING_selection_bias"] = (
        "Estos ROC-AUC/AP NO son una estimacion valida de generalizacion: el ranking "
        "por Cohen's d (variable 'ranked_by_d') se calculo usando las mismas 18 ventanas "
        "evaluation_only que despues se usan aqui para medir ROC-AUC/AP. Es fuga por "
        "seleccion de features (las anomalias 'de prueba' ya influyeron que features se "
        "conservan). No citar estos numeros como mejora real sobre el 0.6007 oficial. "
        "Ver '4b_topn_leave_one_episode_out_cv' para la medicion honesta, sin fuga."
    )

    def topn_rank(item: tuple[str, dict]):
        _, r = item
        roc = r["roc_auc"] if r["roc_auc"] is not None else -1.0
        return (roc, r["average_precision"])

    best_topn_key, best_topn_report = max(topn_results.items(), key=topn_rank)
    report["4_best_topn"] = best_topn_key
    best_n = int(best_topn_key)

    # --- 4b. Top-N con leave-one-episode-out CV: selección de features y evaluación
    # separadas por episodio anómalo, para eliminar la fuga de la sección 4. Es la
    # única cifra de esta sección que debe citarse como comparable con el 0.6007 oficial.
    anomaly_episode_ids = sorted({r["episode_id"] for r in anomaly_rows})
    loeo_results: dict[str, dict] = {}
    for n_top in (5, 10, 15, 28):
        pooled_y: list[int] = []
        pooled_s: list[float] = []
        per_fold: list[dict] = []
        for held_out_episode in anomaly_episode_ids:
            fold_fit_anom_rows = [r for r in anomaly_rows if r["episode_id"] != held_out_episode]
            held_out_rows = [r for r in anomaly_rows if r["episode_id"] == held_out_episode]
            if not fold_fit_anom_rows or not held_out_rows:
                continue
            x_fold_anom = to_matrix(fold_fit_anom_rows, names)
            fold_d = {name: cohens_d_pooled(x_normal_tv[:, idx], x_fold_anom[:, idx]) for idx, name in enumerate(names)}
            fold_subset = sorted(names, key=lambda n: -abs(fold_d[n]))[:n_top]
            idx = [names.index(x) for x in fold_subset]
            xt, xv, xte = xtrain_full[:, idx], xval_full[:, idx], xtest_full[:, idx]
            x_held = to_matrix(held_out_rows, names)[:, idx]
            r = fit_and_score(xt, xv, xte, x_held, best_scale_flag, best_max_samples)
            pooled_y.extend([0] * len(xte))
            pooled_y.extend([1] * len(x_held))
            pooled_s.extend((-r["test_scores"]).tolist())
            pooled_s.extend((-r["anom_scores"]).tolist())
            per_fold.append(
                {
                    "held_out_episode": held_out_episode,
                    "held_out_windows": len(held_out_rows),
                    "features_selected_this_fold": fold_subset,
                }
            )
        y_arr = np.asarray(pooled_y)
        s_arr = np.asarray(pooled_s)
        roc = float(roc_auc_score(y_arr, s_arr)) if len(set(y_arr.tolist())) > 1 else None
        ap = float(average_precision_score(y_arr, s_arr)) if len(y_arr) else None
        loeo_results[str(n_top)] = {
            "roc_auc": roc,
            "average_precision": ap,
            "folds_evaluated": len(per_fold),
            "pooled_normal_rows": int(sum(pooled_y_i == 0 for pooled_y_i in pooled_y)),
            "pooled_anomaly_rows": int(sum(pooled_y_i == 1 for pooled_y_i in pooled_y)),
            "per_fold_detail": per_fold,
        }
    report["4b_topn_leave_one_episode_out_cv"] = loeo_results
    report["4b_note"] = (
        "Para cada uno de los 12 episodios anomalos, se selecciona el top-N por Cohen's d "
        "usando SOLO los otros 11 episodios, se reutiliza train/validation ya congelados "
        "para ajustar Isolation Forest con ese subconjunto de features, y se evalua "
        "unicamente contra el episodio retenido + el test normal completo. Los scores de "
        "las 12 particiones se agrupan (pooled) para un unico ROC-AUC/AP por N. Esta es la "
        "cifra honesta, sin fuga de seleccion de features, comparable con el 0.6007 oficial."
    )

    def loeo_rank(item: tuple[str, dict]):
        _, r = item
        roc = r["roc_auc"] if r["roc_auc"] is not None else -1.0
        return (roc, r["average_precision"] or 0.0)

    best_loeo_key, best_loeo_report = max(loeo_results.items(), key=loeo_rank)
    report["4b_best_topn_honest"] = best_loeo_key

    # --- 5. Dilución por episodio, usando el modelo de la sección 4 (con fuga) -------
    # Nota: esta sección reutiliza intencionalmente el modelo de la sección 4 (no el 4b)
    # porque necesita UN solo modelo fijo para clasificar las 18 ventanas individualmente
    # Y agregadas por episodio con las MISMAS features en ambos casos; el objetivo aquí es
    # aislar el efecto de la agregación por episodio, no medir generalización. El
    # "individually_detected_window_count" hereda el mismo sesgo optimista de la sección 4
    # y no debe citarse como tasa de detección real; solo la PROPORCIÓN de ventanas
    # perdidas al agregar (lost/individually_detected) es informativa sobre el mecanismo
    # de dilución en sí, no sobre el desempeño absoluto del modelo.
    best_overall = topn_models[best_n]
    best_subset = ranked_by_d[:best_n]
    model = best_overall["model"]
    scaler = best_overall["scaler"]
    threshold = best_overall["threshold_decision_function"]
    anom_decision = best_overall["anom_scores"]  # alineado 1:1 con anomaly_rows (mismo orden de filas).

    individual_scores = -anom_decision
    individual_detected = anom_decision <= threshold  # decision_function baja => más anómalo => detectado.

    episode_agg_rows = episode_mean(anomaly_rows, best_subset)
    x_ep = np.asarray([[row[k] for k in best_subset] for row in episode_agg_rows], dtype=float)
    x_ep_final = scaler.transform(x_ep) if scaler is not None else x_ep
    ep_decision = model.decision_function(x_ep_final)
    ep_decision_by_episode = {row["episode_id"]: float(dec) for row, dec in zip(episode_agg_rows, ep_decision)}
    ep_detected_by_episode = {eid: (dec <= threshold) for eid, dec in ep_decision_by_episode.items()}

    lost_windows = []
    for i, row in enumerate(anomaly_rows):
        eid = row["episode_id"]
        if bool(individual_detected[i]) and not ep_detected_by_episode.get(eid, False):
            lost_windows.append(
                {
                    "episode_id": eid,
                    "window_end_utc": row.get("window_end_utc"),
                    "individual_score": float(individual_scores[i]),
                    "individual_decision_function": float(anom_decision[i]),
                    "episode_mean_decision_function": ep_decision_by_episode.get(eid),
                    "threshold_decision_function": threshold,
                }
            )

    report["5_dilution_by_episode"] = {
        "model_used": {
            "top_n_features": best_n,
            "features": best_subset,
            "scaled": best_scale_flag,
            "max_samples": best_max_samples,
            "threshold_decision_function": threshold,
            "roc_auc": best_overall["roc_auc"],
            "average_precision": best_overall["average_precision"],
        },
        "total_anomaly_windows": len(anomaly_rows),
        "total_anomaly_episodes": len({r["episode_id"] for r in anomaly_rows}),
        "individually_detected_window_count": int(sum(bool(v) for v in individual_detected)),
        "episode_aggregated_detected_episode_count": int(sum(1 for v in ep_detected_by_episode.values() if v)),
        "windows_lost_by_episode_aggregation_count": len(lost_windows),
        "windows_lost_by_episode_aggregation_details": lost_windows,
        "_bias_warning": (
            "model_used y individually_detected_window_count heredan la fuga por seleccion "
            "de features de la seccion 4 (ver '4_WARNING_selection_bias'). No citar la tasa "
            "absoluta de deteccion aqui. Solo la proporcion windows_lost/individually_detected "
            "es informativa sobre el MECANISMO de dilucion por episodio, no sobre desempeno real."
        ),
    }

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    print("=== Diagnóstico pipeline multilayer-v2 (experimental, solo lectura) ===")
    print(f"1) Escalado -> sin escalar: ROC-AUC={scaling_results['False']['roc_auc']}, AP={scaling_results['False']['average_precision']} | "
          f"con StandardScaler: ROC-AUC={scaling_results['True']['roc_auc']}, AP={scaling_results['True']['average_precision']}")
    print(f"2) Mejor combinación escalado/max_samples: {best_combo_key} -> ROC-AUC={best_combo['roc_auc']}, AP={best_combo['average_precision']}")
    print(f"3) Features separables (|d|>0.5): {len(separable)}/{len(names)} -> {separable}")
    print(f"   Pares redundantes (|r|>0.8): {len(redundant_pairs)} | Clusters (>=2 features): {len(clusters)}")
    print(f"4) [CON FUGA, NO CITAR] Mejor top-N: {best_topn_key} -> ROC-AUC={best_topn_report['roc_auc']}, AP={best_topn_report['average_precision']}")
    for n_top in (5, 10, 15, 28):
        r = topn_results[str(n_top)]
        print(f"   N={n_top}: ROC-AUC={r['roc_auc']}, AP={r['average_precision']}")
    print(f"4b) [HONESTO, leave-one-episode-out] Mejor top-N: {best_loeo_key} -> ROC-AUC={best_loeo_report['roc_auc']}, AP={best_loeo_report['average_precision']}")
    for n_top in (5, 10, 15, 28):
        r = loeo_results[str(n_top)]
        print(f"   N={n_top}: ROC-AUC={r['roc_auc']}, AP={r['average_precision']} ({r['folds_evaluated']} episodios evaluados)")
    dilution = report["5_dilution_by_episode"]
    print(
        f"5) Dilución por episodio (modelo: top-{best_n}, scaled={best_scale_flag}, max_samples={best_max_samples}): "
        f"{dilution['individually_detected_window_count']}/{dilution['total_anomaly_windows']} ventanas detectadas individualmente; "
        f"{dilution['windows_lost_by_episode_aggregation_count']} se pierden al promediar por episodio."
    )
    print(f"Reporte completo escrito en: {args.output}")


if __name__ == "__main__":
    main()
