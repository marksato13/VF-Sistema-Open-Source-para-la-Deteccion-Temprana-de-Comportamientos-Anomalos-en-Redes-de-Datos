#!/usr/bin/env python3
"""Reproduce métricas binarias y de ranking de los siete modelos de PM-multilayer-v2-v1.

La clase positiva es anomalía. El conjunto negativo son las 276 ventanas normales
de test y el positivo las 179 ventanas de evaluation_only. Los modelos no se
reentrenan: se cargan los joblib originales y se verifican contra manifest.json.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
from pathlib import Path
from typing import Any

import joblib
import numpy as np
from sklearn.metrics import (
    accuracy_score,
    average_precision_score,
    balanced_accuracy_score,
    f1_score,
    matthews_corrcoef,
    precision_score,
    recall_score,
    roc_auc_score,
)


DEFAULT_MODEL_DIR = Path(
    "/srv/ppi-evidence/artifacts/models/pm-multilayer-v2-v1-calibration-7models/models"
)


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read_rows(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def wilson(k: int, n: int, z: float = 1.959963984540054) -> list[float]:
    proportion = k / n
    denominator = 1 + z * z / n
    center = (proportion + z * z / (2 * n)) / denominator
    half = z * math.sqrt(
        (proportion * (1 - proportion) + z * z / (4 * n)) / n
    ) / denominator
    return [center - half, center + half]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo", type=Path, default=Path(__file__).resolve().parents[2])
    parser.add_argument("--model-dir", type=Path, default=DEFAULT_MODEL_DIR)
    parser.add_argument("--output", type=Path)
    return parser.parse_args()


def build_report(repo: Path, model_dir: Path) -> dict[str, Any]:
    manifest_path = repo / "artifacts/model/manifest.json"
    normal_path = repo / "artifacts/dataset/multilayer-v2-normal.csv"
    anomaly_path = repo / "artifacts/dataset/multilayer-v2-anomalies.csv"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))

    if sha256(normal_path) != manifest["normal_csv_sha256"]:
        raise RuntimeError("el SHA-256 del dataset normal no coincide con el manifiesto")
    if sha256(anomaly_path) != manifest["anomaly_csv_sha256"]:
        raise RuntimeError("el SHA-256 del dataset anómalo no coincide con el manifiesto")

    normal_rows = read_rows(normal_path)
    anomaly_rows = read_rows(anomaly_path)
    test_rows = [row for row in normal_rows if row["partition"] == "test"]
    if len(test_rows) != 276 or len(anomaly_rows) != 179:
        raise RuntimeError(
            f"tamaños inesperados: test={len(test_rows)}, anomalías={len(anomaly_rows)}"
        )

    features = manifest["feature_names"]
    x_test = np.asarray(
        [[float(row[name]) for name in features] for row in test_rows], dtype=np.float64
    )
    x_anomaly = np.asarray(
        [[float(row[name]) for name in features] for row in anomaly_rows], dtype=np.float64
    )
    x_all = np.vstack([x_test, x_anomaly])
    y_true = np.asarray([0] * len(x_test) + [1] * len(x_anomaly), dtype=np.int8)

    report: dict[str, Any] = {
        "sources": {
            "manifest": {
                "path": str(manifest_path.relative_to(repo)),
                "sha256": sha256(manifest_path),
            },
            "normal_csv": {
                "path": str(normal_path.relative_to(repo)),
                "sha256": sha256(normal_path),
            },
            "anomaly_csv": {
                "path": str(anomaly_path.relative_to(repo)),
                "sha256": sha256(anomaly_path),
            },
            "model_dir": str(model_dir),
        },
        "evaluation": {
            "negative_class": "276 benign windows from partition=test",
            "positive_class": "179 anomaly windows from evaluation_only",
            "positive_prevalence": float(y_true.mean()),
            "threshold_rule": "score_samples < threshold => anomaly",
        },
        "models": {},
    }

    expected_models = sorted(
        (Path(relative).stem, expected_hash)
        for relative, expected_hash in manifest["model_hashes"].items()
    )
    for name, expected_hash in expected_models:
        model_path = model_dir / f"{name}.joblib"
        actual_hash = sha256(model_path)
        if actual_hash != expected_hash:
            raise RuntimeError(f"SHA-256 incorrecto para {name}: {actual_hash}")

        model = joblib.load(model_path)
        score_samples = np.asarray(model.score_samples(x_all), dtype=np.float64)
        threshold = float(manifest["evaluation"][name]["threshold_used"])
        y_pred = (score_samples < threshold).astype(np.int8)
        anomaly_score = -score_samples

        tn = int(np.sum((y_true == 0) & (y_pred == 0)))
        fp = int(np.sum((y_true == 0) & (y_pred == 1)))
        fn = int(np.sum((y_true == 1) & (y_pred == 0)))
        tp = int(np.sum((y_true == 1) & (y_pred == 1)))
        frozen = manifest["evaluation"][name]
        if fp != frozen["test"]["alerts_strict"]:
            raise RuntimeError(f"{name}: FP reproducido no coincide con el manifiesto")
        if tp != frozen["anomalies"]["detected_strict"]:
            raise RuntimeError(f"{name}: TP reproducido no coincide con el manifiesto")

        precision = float(precision_score(y_true, y_pred, zero_division=0))
        recall = float(recall_score(y_true, y_pred, zero_division=0))
        specificity = tn / (tn + fp)
        fpr = fp / (fp + tn)
        report["models"][name] = {
            "model_sha256": actual_hash,
            "threshold": threshold,
            "tn": tn,
            "fp": fp,
            "fn": fn,
            "tp": tp,
            "precision": precision,
            "precision_wilson_95": wilson(tp, tp + fp),
            "recall": recall,
            "recall_wilson_95": wilson(tp, tp + fn),
            "specificity": specificity,
            "specificity_wilson_95": wilson(tn, tn + fp),
            "fpr": fpr,
            "fpr_wilson_95": wilson(fp, fp + tn),
            "f1": float(f1_score(y_true, y_pred, zero_division=0)),
            "accuracy": float(accuracy_score(y_true, y_pred)),
            "balanced_accuracy": float(balanced_accuracy_score(y_true, y_pred)),
            "mcc": float(matthews_corrcoef(y_true, y_pred)),
            "roc_auc": float(roc_auc_score(y_true, anomaly_score)),
            "average_precision_pr_auc": float(
                average_precision_score(y_true, anomaly_score)
            ),
        }
    return report


def main() -> int:
    args = parse_args()
    report = build_report(args.repo.resolve(), args.model_dir.resolve())
    serialized = json.dumps(report, indent=2, sort_keys=True) + "\n"
    if args.output:
        args.output.write_text(serialized, encoding="utf-8")
    else:
        print(serialized, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
