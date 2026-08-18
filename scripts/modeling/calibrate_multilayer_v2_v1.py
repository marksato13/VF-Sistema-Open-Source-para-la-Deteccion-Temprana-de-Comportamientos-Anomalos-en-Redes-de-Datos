#!/usr/bin/env python3
"""Preflight y calibración atómica del protocolo PM-multilayer-v2-v1.

Adaptación de calibrate_pm_f1_v1.py (protocolo PM-F1-v1, 2026-08-04) al
dataset multilayer-v2 ampliado (28 features, 220 episodios normales, 132
episodios de anomalías reales/heredadas). Ver
docs/fase04-modelado/04-protocolo-modelado-multilayer-v2-y-hoja-de-ruta.md.

Diferencia deliberada respecto a PM-F1-v1, documentada y verificada, no
copiada a ciegas: la rama de sensibilidad "expansión exacta por MCM" del
protocolo original es matemáticamente inviable aquí (episodios van de 1 a 53
filas en vez de 1 a 7; el MCM de todos los valores distintos observados en
train es 15,915,900, produciendo ~2.1 mil millones de filas expandidas). Se
verificó primero, con un chequeo aislado antes de escribir este script, que
sample_weight=1/filas_por_episodio SÍ produce scores distintos en este
dataset (delta máximo absoluto 0.1194 con seed 20260817; en el dataset
anterior esa misma verificación había dado scores idénticos). Dado que 5 de
132 episodios (3.8%) concentran 261 de 824 filas train (31.7%), se declara
el modelo IF ponderado por episodio como principal en vez del IF uniforme
sin ponderar, con justificación empírica explícita -- no es "el comparador
gana una métrica y lo reemplaza", es una corrección de diseño ante un
desbalance de episodio medido antes de tocar validation o test.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import importlib.metadata
import io
import json
import math
import os
import platform
import shutil
import subprocess
import sys
import tempfile
import time
from collections import Counter
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from pathlib import Path
from typing import Any, Callable, Sequence


REPO = Path(__file__).resolve().parents[2]
FEATURE_SCHEMA_RELATIVE = Path("configs/features/multilayer-v2.json")
AUDITOR_RELATIVE = Path("scripts/dataset/audit_multilayer_v2.py")
NORMAL_CSV_RELATIVE = Path("artifacts/dataset/multilayer-v2-normal.csv")
ANOMALY_CSV_RELATIVE = Path("artifacts/dataset/multilayer-v2-anomalies.csv")
REQUIREMENTS_RELATIVE = Path("requirements-model.txt")
PROTOCOL_ID = "PM-multilayer-v2-v1"
ALPHA = 0.05
PRIMARY_SEED = 20260817
STABILITY_SEEDS = tuple(range(20260817, 20260827))
EXPECTED_PYTHON = "3.14.4"
EXPECTED_FEATURE_COUNT = 28
KALI_ENTITY_IP = "10.20.0.100"
EXPECTED_PARTITIONS = {
    "train": {"episodes": 132, "rows": 824},
    "validation": {"episodes": 44, "rows": 273},
    "test": {"episodes": 44, "rows": 276},
}
EXPECTED_ANOMALY = {"episodes": 132, "rows": 179}
IF_PARAMETERS = {
    "n_estimators": 500,
    "max_samples": "auto",
    "contamination": "auto",
    "max_features": 1.0,
    "bootstrap": False,
    "n_jobs": 1,
    "warm_start": False,
}


class CalibrationError(RuntimeError):
    """Fallo de un gate de calibración."""


@dataclass(frozen=True)
class Split:
    rows: tuple[dict[str, str], ...]

    def matrix(self, feature_names: Sequence[str]):
        import numpy as np

        values = [[float(row[name]) for name in feature_names] for row in self.rows]
        matrix = np.asarray(values, dtype=np.float64)
        if matrix.ndim != 2 or matrix.shape[1] != EXPECTED_FEATURE_COUNT or not np.isfinite(matrix).all():
            raise CalibrationError(f"matriz inválida: shape={matrix.shape}")
        return matrix

    def episode_ids(self) -> list[str]:
        return [row["episode_id"] for row in self.rows]


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def sha256_path(path: Path) -> str:
    return sha256_bytes(path.read_bytes())


def git_state(repo: Path) -> tuple[str, bool]:
    commit = subprocess.check_output(["git", "-C", str(repo), "rev-parse", "HEAD"], text=True).strip()
    dirty = bool(subprocess.check_output(["git", "-C", str(repo), "status", "--porcelain"], text=True).strip())
    return commit, dirty


def require_execution_context(repo: Path, expected_commit: str) -> str:
    if len(expected_commit) != 40 or any(c not in "0123456789abcdef" for c in expected_commit):
        raise CalibrationError("--expected-git-commit debe ser un SHA-1 completo en minúsculas")
    commit, dirty = git_state(repo)
    if dirty:
        raise CalibrationError("Git debe estar limpio antes del preflight o la calibración")
    if commit != expected_commit:
        raise CalibrationError(f"commit actual {commit} distinto del esperado {expected_commit}")
    return commit


def parse_frozen_requirements(path: Path) -> dict[str, str]:
    expected: dict[str, str] = {}
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if line.count("==") != 1:
            raise CalibrationError(f"requisito no congelado con ==: {line}")
        name, version = line.split("==", 1)
        expected[name] = version
    if not expected:
        raise CalibrationError("requirements-model.txt no contiene dependencias")
    return expected


def verify_runtime(repo: Path) -> dict[str, Any]:
    if platform.python_version() != EXPECTED_PYTHON:
        raise CalibrationError(f"CPython {platform.python_version()} no coincide con {EXPECTED_PYTHON}")
    requirements_path = repo / REQUIREMENTS_RELATIVE
    expected = parse_frozen_requirements(requirements_path)
    installed: dict[str, str] = {}
    for name, wanted in expected.items():
        try:
            actual = importlib.metadata.version(name)
        except importlib.metadata.PackageNotFoundError as exc:
            raise CalibrationError(f"dependencia ausente: {name}=={wanted}") from exc
        if actual != wanted:
            raise CalibrationError(f"{name} instalado {actual}; se requiere {wanted}")
        installed[name] = actual
    return {
        "python": platform.python_version(),
        "platform": platform.platform(),
        "requirements_sha256": sha256_path(requirements_path),
        "packages": installed,
    }


def run_fresh_audit(repo: Path, normal_csv: Path, anomaly_csv: Path) -> dict[str, Any]:
    """Vuelve a correr el auditor ahora mismo -- no confía en un reporte viejo."""
    output = Path(tempfile.mktemp(suffix=".json"))
    try:
        subprocess.run(
            [
                sys.executable,
                str(repo / AUDITOR_RELATIVE),
                "--normal",
                str(normal_csv),
                "--anomalies",
                str(anomaly_csv),
                "--output",
                str(output),
            ],
            check=True,
            capture_output=True,
            text=True,
        )
        report = json.loads(output.read_text())
    except subprocess.CalledProcessError as exc:
        raise CalibrationError(f"el auditor falló: {exc.stderr}") from exc
    finally:
        output.unlink(missing_ok=True)
    if not report["gates"]["pass"]:
        raise CalibrationError(f"auditoría no pasa: {report['gates']}")
    return report


def load_feature_names(repo: Path) -> tuple[str, ...]:
    schema = json.loads((repo / FEATURE_SCHEMA_RELATIVE).read_text())
    names = tuple(item["name"] for item in sorted(schema["features"], key=lambda x: x["order"]))
    if len(names) != EXPECTED_FEATURE_COUNT:
        raise CalibrationError(f"el esquema declara {len(names)} features, se esperaban {EXPECTED_FEATURE_COUNT}")
    return names


def load_rows(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def build_splits(normal_rows: list[dict[str, str]], anomaly_rows: list[dict[str, str]]) -> dict[str, Split]:
    splits: dict[str, Split] = {}
    for partition, expected in EXPECTED_PARTITIONS.items():
        rows = [r for r in normal_rows if r["partition"] == partition]
        episodes = {r["episode_id"] for r in rows}
        if len(episodes) != expected["episodes"] or len(rows) != expected["rows"]:
            raise CalibrationError(
                f"{partition}: episodios={len(episodes)} filas={len(rows)}, "
                f"se esperaba episodios={expected['episodes']} filas={expected['rows']}"
            )
        splits[partition] = Split(rows=tuple(rows))
    anomaly_episodes = {r["episode_id"] for r in anomaly_rows}
    if len(anomaly_episodes) != EXPECTED_ANOMALY["episodes"] or len(anomaly_rows) != EXPECTED_ANOMALY["rows"]:
        raise CalibrationError(
            f"anomalías: episodios={len(anomaly_episodes)} filas={len(anomaly_rows)}, "
            f"se esperaba episodios={EXPECTED_ANOMALY['episodes']} filas={EXPECTED_ANOMALY['rows']}"
        )
    splits["evaluation_only"] = Split(rows=tuple(anomaly_rows))
    return splits


def decimal_vector(row: dict[str, str], feature_names: Sequence[str]) -> tuple[Decimal, ...]:
    return tuple(Decimal(row[name]) for name in feature_names)


def collapsed_indices(rows: Sequence[dict[str, str]], feature_names: Sequence[str]) -> list[int]:
    seen: set[tuple[Decimal, ...]] = set()
    selected: list[int] = []
    for index, row in enumerate(rows):
        vector = decimal_vector(row, feature_names)
        if vector not in seen:
            seen.add(vector)
            selected.append(index)
    return selected


def episode_weights(episode_ids: Sequence[str]) -> list[float]:
    counts = Counter(episode_ids)
    return [1.0 / counts[episode_id] for episode_id in episode_ids]


def lower_tail(scores: Sequence[float], episode_ids: Sequence[str], alpha: float = ALPHA) -> dict[str, Any]:
    if not scores or len(scores) != len(episode_ids):
        raise CalibrationError("scores y episode_ids deben ser no vacíos y de igual longitud")
    if not 0 < alpha < 0.5:
        raise CalibrationError("alpha debe estar entre 0 y 0.5")
    for score in scores:
        if not math.isfinite(float(score)):
            raise CalibrationError("score no finito")
    ordered = sorted(range(len(scores)), key=lambda i: (float(scores[i]), i))
    k = math.floor(alpha * len(scores))
    threshold = float(scores[ordered[k]])
    prefix = ordered[:k]
    alerts = [i for i, s in enumerate(scores) if float(s) < threshold]
    return {
        "unit": "windows",
        "alpha": alpha,
        "n_windows": len(scores),
        "k": k,
        "threshold": threshold,
        "comparison": "score < threshold",
        "threshold_tie_count": sum(float(s) == threshold for s in scores),
        "lower_prefix_episode_count": len({episode_ids[i] for i in prefix}),
        "strict_alert_indices": alerts,
        "strict_alert_count": len(alerts),
        "strict_alert_episode_count": len({episode_ids[i] for i in alerts}),
    }


def csv_bytes(fieldnames: Sequence[str], rows: Sequence[dict[str, Any]]) -> bytes:
    buffer = io.StringIO(newline="")
    writer = csv.DictWriter(buffer, fieldnames=fieldnames, lineterminator="\n")
    writer.writeheader()
    writer.writerows(rows)
    return buffer.getvalue().encode("utf-8")


def make_if(seed: int, scaled: bool = False) -> Any:
    from sklearn.ensemble import IsolationForest
    from sklearn.pipeline import Pipeline
    from sklearn.preprocessing import StandardScaler

    detector = IsolationForest(**IF_PARAMETERS, random_state=seed)
    return Pipeline([("scaler", StandardScaler()), ("detector", detector)]) if scaled else detector


def detector_factories() -> dict[str, Callable[[], Any]]:
    from sklearn.covariance import EllipticEnvelope
    from sklearn.neighbors import LocalOutlierFactor
    from sklearn.pipeline import Pipeline
    from sklearn.preprocessing import StandardScaler
    from sklearn.svm import OneClassSVM

    return {
        "if_primary_weighted": lambda: make_if(PRIMARY_SEED),
        "if_uniform": lambda: make_if(PRIMARY_SEED),
        "if_scaled_weighted": lambda: make_if(PRIMARY_SEED, scaled=True),
        "if_exact_collapsed": lambda: make_if(PRIMARY_SEED),
        "lof_scaled": lambda: Pipeline(
            [
                ("scaler", StandardScaler()),
                ("detector", LocalOutlierFactor(n_neighbors=20, novelty=True, contamination="auto", n_jobs=1)),
            ]
        ),
        "ocsvm_scaled": lambda: Pipeline(
            [("scaler", StandardScaler()), ("detector", OneClassSVM(kernel="rbf", gamma="scale", nu=0.05, cache_size=200))]
        ),
        # Comparador adicional, familia de algoritmo distinta (covarianza robusta,
        # no árboles/vecindades/margen). Parámetros de fábrica de scikit-learn
        # (contamination=0.1 es el default de la clase, no se ajustó buscando el
        # mejor resultado). Se espera, sin darlo por sentado, que rinda peor: las
        # 28 features son acotadas, discretas y con varias constantes en cero, sin
        # una hipótesis gaussiana demostrada -- el propio ajuste ya advierte
        # "covariance matrix ... not full rank" en este dataset.
        "elliptic_envelope_scaled": lambda: Pipeline(
            [("scaler", StandardScaler()), ("detector", EllipticEnvelope(contamination=0.1, random_state=PRIMARY_SEED))]
        ),
    }


FIT_WEIGHT_BRANCHES = {"if_primary_weighted", "if_scaled_weighted"}


def fit_weighted(model: Any, train_matrix: Any, weights: list[float]) -> None:
    """model.fit(X, sample_weight=w) para un estimador suelto; para un Pipeline
    sklearn exige el prefijo del paso: fit(X, <paso>__sample_weight=w)."""
    if hasattr(model, "named_steps"):
        model.fit(train_matrix, **{"detector__sample_weight": weights})
    else:
        model.fit(train_matrix, sample_weight=weights)


def fit_and_score(name: str, model: Any, train_matrix: Any, weights: list[float] | None, eval_matrix: Any) -> tuple[Any, list[float], dict[str, float]]:
    import warnings

    fit_started = time.perf_counter_ns()
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        if name in FIT_WEIGHT_BRANCHES and weights is not None:
            fit_weighted(model, train_matrix, weights)
        else:
            model.fit(train_matrix)
    sklearn_warnings = [f"{w.category.__name__}: {w.message}" for w in caught]
    fit_seconds = (time.perf_counter_ns() - fit_started) / 1_000_000_000
    score_started = time.perf_counter_ns()
    scores = [float(v) for v in model.score_samples(eval_matrix)]
    score_seconds = (time.perf_counter_ns() - score_started) / 1_000_000_000
    if not all(math.isfinite(v) for v in scores):
        raise CalibrationError(f"{name} produjo scores no finitos")
    return model, scores, {
        "fit_seconds": fit_seconds,
        "score_batch_seconds": score_seconds,
        "score_seconds_per_window": score_seconds / len(scores),
        "timing_scope": "descriptive_single_batch_on_vm01_not_production_benchmark",
        "fit_warnings": sklearn_warnings,
    }


def safe_output_path(artifacts_root: Path, output_dir: Path) -> Path:
    if not artifacts_root.is_absolute() or not output_dir.is_absolute():
        raise CalibrationError("artifacts-root y output-dir deben ser rutas absolutas")
    root = artifacts_root.resolve()
    destination = output_dir.resolve()
    try:
        destination.relative_to(root)
    except ValueError as exc:
        raise CalibrationError("output-dir debe estar dentro de artifacts-root") from exc
    if destination == root:
        raise CalibrationError("output-dir no puede ser la raíz de artefactos")
    if destination.exists():
        raise CalibrationError(f"el destino ya existe y nunca se reemplaza: {destination}")
    return destination


def preflight_report(repo: Path, artifacts_root: Path, output_dir: Path, expected_commit: str) -> tuple[dict[str, Any], dict[str, Split], tuple[str, ...], dict[str, Any]]:
    commit = require_execution_context(repo, expected_commit)
    runtime = verify_runtime(repo)
    destination = safe_output_path(artifacts_root, output_dir)
    normal_csv = repo / NORMAL_CSV_RELATIVE
    anomaly_csv = repo / ANOMALY_CSV_RELATIVE
    audit = run_fresh_audit(repo, normal_csv, anomaly_csv)
    feature_names = load_feature_names(repo)
    normal_rows = load_rows(normal_csv)
    anomaly_rows = load_rows(anomaly_csv)
    splits = build_splits(normal_rows, anomaly_rows)
    return {
        "schema_version": "pm-multilayer-v2-v1-preflight-v1",
        "protocol": PROTOCOL_ID,
        "gate_pass": True,
        "git_commit": commit,
        "git_dirty": False,
        "runtime": runtime,
        "output_dir": str(destination),
        "audit_gates": audit["gates"],
        "normal_csv_sha256": audit["normal_sha256"],
        "anomaly_csv_sha256": audit["anomaly_sha256"],
        "train": {"episodes": EXPECTED_PARTITIONS["train"]["episodes"], "rows": EXPECTED_PARTITIONS["train"]["rows"]},
        "validation": {"episodes": EXPECTED_PARTITIONS["validation"]["episodes"], "rows": EXPECTED_PARTITIONS["validation"]["rows"]},
        "test_and_evaluation_only_enumerated_or_read": True,
        "note": "a diferencia de PM-F1-v1, aqui test y evaluation_only SI se leen en preflight porque ya estan consolidados en el mismo CSV auditado; no se puntuan hasta execute-once, y execute-once puntua todo en un solo paso bloqueado.",
    }, splits, feature_names, audit


def execute_calibration(repo: Path, artifacts_root: Path, output_dir: Path, expected_commit: str) -> dict[str, Any]:
    import joblib
    import numpy as np
    import sklearn
    from threadpoolctl import threadpool_info

    preflight, splits, feature_names, audit = preflight_report(repo, artifacts_root, output_dir, expected_commit)
    destination = Path(preflight["output_dir"])

    train = splits["train"]
    validation = splits["validation"]
    test = splits["test"]
    anomalies = splits["evaluation_only"]

    x_train = train.matrix(feature_names)
    x_validation = validation.matrix(feature_names)
    x_test = test.matrix(feature_names)
    x_anomalies = anomalies.matrix(feature_names)

    train_episode_ids = train.episode_ids()
    validation_episode_ids = validation.episode_ids()
    weights = episode_weights(train_episode_ids)
    collapsed = collapsed_indices(list(train.rows), feature_names)

    training_matrices: dict[str, Any] = {
        "if_primary_weighted": x_train,
        "if_uniform": x_train,
        "if_scaled_weighted": x_train,
        "if_exact_collapsed": x_train[collapsed],
        "lof_scaled": x_train,
        "ocsvm_scaled": x_train,
        "elliptic_envelope_scaled": x_train,
    }
    training_weights: dict[str, list[float] | None] = {
        "if_primary_weighted": weights,
        "if_scaled_weighted": weights,
    }

    models: dict[str, Any] = {}
    validation_scores: dict[str, list[float]] = {}
    timings: dict[str, dict[str, float]] = {}
    for name, factory in detector_factories().items():
        model, scores, timing = fit_and_score(
            name, factory(), training_matrices[name], training_weights.get(name), x_validation
        )
        models[name] = model
        validation_scores[name] = scores
        timings[name] = timing

    # Estabilidad: solo para las ramas Isolation Forest, seeds 20260817..20260826.
    stability_scores: dict[tuple[str, int], list[float]] = {}
    for branch in ("if_primary_weighted", "if_uniform", "if_scaled_weighted", "if_exact_collapsed"):
        for seed in STABILITY_SEEDS:
            if seed == PRIMARY_SEED:
                stability_scores[(branch, seed)] = validation_scores[branch]
                continue
            model = make_if(seed, scaled=branch == "if_scaled_weighted")
            fit_weights = weights if branch in FIT_WEIGHT_BRANCHES else None
            if fit_weights is not None:
                fit_weighted(model, training_matrices[branch], fit_weights)
            else:
                model.fit(training_matrices[branch])
            scores = [float(v) for v in model.score_samples(x_validation)]
            if not all(math.isfinite(v) for v in scores):
                raise CalibrationError(f"scores de estabilidad no finitos: {branch}/{seed}")
            stability_scores[(branch, seed)] = scores

    detector_reports: dict[str, Any] = {}
    for name, scores in validation_scores.items():
        tail = lower_tail(scores, validation_episode_ids)
        detector_reports[name] = {
            "role": "primary" if name == "if_primary_weighted" else "sensitivity_or_comparator",
            "train_rows": len(training_matrices[name]),
            "timing": timings[name],
            "calibration": tail,
        }

    stability_reports: dict[str, list[dict[str, Any]]] = {}
    for branch in ("if_primary_weighted", "if_uniform", "if_scaled_weighted", "if_exact_collapsed"):
        branch_reports = []
        for seed in STABILITY_SEEDS:
            tail = lower_tail(stability_scores[(branch, seed)], validation_episode_ids)
            branch_reports.append(
                {"seed": seed, "threshold": tail["threshold"], "strict_alert_count": tail["strict_alert_count"], "strict_alert_episode_count": tail["strict_alert_episode_count"]}
            )
        stability_reports[branch] = branch_reports

    # Evaluación bloqueada: test (FPR benigno) y anomalías, con el umbral YA fijado arriba, en un solo paso.
    evaluation_reports: dict[str, Any] = {}
    anomaly_episode_ids = anomalies.episode_ids()
    anomaly_entity_ips = [row["entity_ip"] for row in anomalies.rows]
    for name, model in models.items():
        threshold = detector_reports[name]["calibration"]["threshold"]
        test_scores = [float(v) for v in model.score_samples(x_test)]
        anomaly_scores = [float(v) for v in model.score_samples(x_anomalies)]
        test_alerts = sum(1 for s in test_scores if s < threshold)
        anomaly_alerts = [i for i, s in enumerate(anomaly_scores) if s < threshold]
        kali_indices = [i for i, ip in enumerate(anomaly_entity_ips) if ip == KALI_ENTITY_IP]
        legacy_indices = [i for i, ip in enumerate(anomaly_entity_ips) if ip != KALI_ENTITY_IP]
        kali_alerts = [i for i in anomaly_alerts if i in set(kali_indices)]
        legacy_alerts = [i for i in anomaly_alerts if i in set(legacy_indices)]
        by_profile: dict[str, dict[str, int]] = {}
        for i, episode_id in enumerate(anomaly_episode_ids):
            profile = episode_id.split("-E")[0].replace("F2A-", "")
            slot = by_profile.setdefault(profile, {"windows": 0, "detected": 0})
            slot["windows"] += 1
            if i in anomaly_alerts:
                slot["detected"] += 1
        evaluation_reports[name] = {
            "threshold_used": threshold,
            "test": {
                "n_windows": len(test_scores),
                "alerts_strict": test_alerts,
                "fpr": test_alerts / len(test_scores),
            },
            "anomalies": {
                "n_windows": len(anomaly_scores),
                "detected_strict": len(anomaly_alerts),
                "detection_rate": len(anomaly_alerts) / len(anomaly_scores),
                "kali_real_windows": len(kali_indices),
                "kali_real_detected": len(kali_alerts),
                "kali_real_detection_rate": (len(kali_alerts) / len(kali_indices)) if kali_indices else None,
                "legacy_windows": len(legacy_indices),
                "legacy_detected": len(legacy_alerts),
                "legacy_detection_rate": (len(legacy_alerts) / len(legacy_indices)) if legacy_indices else None,
                "by_profile": by_profile,
                "detected_episode_count": len({anomaly_episode_ids[i] for i in anomaly_alerts}),
                "total_episode_count": len(set(anomaly_episode_ids)),
            },
        }

    destination.parent.mkdir(parents=True, exist_ok=True)
    lock_dir = destination.parent / f".{destination.name}.lock"
    try:
        lock_dir.mkdir()
    except FileExistsError as exc:
        raise CalibrationError(f"existe lock de calibración: {lock_dir}") from exc
    temporary: Path | None = None
    try:
        if destination.exists():
            raise CalibrationError(f"el destino apareció durante la ejecución: {destination}")
        temporary = Path(tempfile.mkdtemp(prefix=f".{destination.name}-", dir=destination.parent))
        (temporary / "models").mkdir()
        model_hashes: dict[str, str] = {}
        for name, model in models.items():
            model_path = temporary / "models" / f"{name}.joblib"
            joblib.dump(model, model_path, compress=3)
            model_hashes[str(model_path.relative_to(temporary))] = sha256_path(model_path)

        manifest = {
            "schema_version": "pm-multilayer-v2-v1-calibration-manifest-v1",
            "protocol": PROTOCOL_ID,
            "created_at": datetime.now().astimezone().isoformat(),
            "git_commit": expected_commit,
            "git_dirty_before_and_after": False,
            "runtime": preflight["runtime"],
            "threadpools": threadpool_info(),
            "numpy": np.__version__,
            "scikit_learn": sklearn.__version__,
            "feature_names": list(feature_names),
            "normal_csv_sha256": preflight["normal_csv_sha256"],
            "anomaly_csv_sha256": preflight["anomaly_csv_sha256"],
            "audit_gates": preflight["audit_gates"],
            "calibrator_sha256": sha256_path(Path(__file__)),
            "model_hashes": model_hashes,
            "selection": {
                "train_episodes": EXPECTED_PARTITIONS["train"]["episodes"],
                "train_rows": EXPECTED_PARTITIONS["train"]["rows"],
                "validation_episodes": EXPECTED_PARTITIONS["validation"]["episodes"],
                "validation_rows": EXPECTED_PARTITIONS["validation"]["rows"],
                "test_episodes": EXPECTED_PARTITIONS["test"]["episodes"],
                "test_rows": EXPECTED_PARTITIONS["test"]["rows"],
                "anomaly_episodes": EXPECTED_ANOMALY["episodes"],
                "anomaly_rows": EXPECTED_ANOMALY["rows"],
                "collapsed_train_rows": len(collapsed),
            },
            "deviation_from_pm_f1_v1": {
                "reason": "expansion exacta por MCM es inviable (episodios 1-53 filas, MCM=15,915,900); "
                "verificado antes de fijar este protocolo que sample_weight=1/filas_por_episodio SI cambia "
                "los scores en este dataset (delta maximo absoluto 0.1194, seed 20260817), a diferencia del "
                "dataset anterior donde no cambiaba nada. 5/132 episodios (3.8%) concentran 261/824 filas "
                "train (31.7%).",
                "primary_model_changed_to": "if_primary_weighted (antes if_window sin ponderar)",
            },
            "if_parameters": {**IF_PARAMETERS, "random_state": PRIMARY_SEED},
            "stability_seeds": list(STABILITY_SEEDS),
            "alpha": ALPHA,
            "model_selection_policy": "if_primary_weighted es la conclusion principal; LOF/OCSVM y las demas "
            "ramas IF son comparadores/sensibilidad y no lo reemplazan por ganar una metrica posterior en "
            "test o evaluation_only.",
            "detectors": detector_reports,
            "stability": stability_reports,
            "evaluation": evaluation_reports,
        }
        current_commit, current_dirty = git_state(repo)
        if current_commit != expected_commit or current_dirty:
            raise CalibrationError("Git cambió durante la calibración; la salida se descarta")
        (temporary / "manifest.json").write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        checksum_lines = []
        for path in sorted(temporary.rglob("*")):
            if path.is_file() and path.name != "SHA256SUMS":
                checksum_lines.append(f"{sha256_path(path)}  {path.relative_to(temporary).as_posix()}\n")
        (temporary / "SHA256SUMS").write_text("".join(checksum_lines), encoding="utf-8")
        if destination.exists():
            raise CalibrationError(f"el destino apareció antes del rename: {destination}")
        temporary.rename(destination)
        temporary = None
        return manifest
    finally:
        if temporary is not None:
            shutil.rmtree(temporary, ignore_errors=True)
        lock_dir.rmdir()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Calibración atómica PM-multilayer-v2-v1")
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--preflight", action="store_true")
    mode.add_argument("--execute-once", action="store_true")
    parser.add_argument("--protocol", required=True, choices=[PROTOCOL_ID])
    parser.add_argument("--expected-git-commit", required=True)
    parser.add_argument("--repo", type=Path, default=REPO)
    parser.add_argument("--artifacts-root", type=Path)
    parser.add_argument("--output-dir", type=Path)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    repo = args.repo.resolve()
    raw_root = args.artifacts_root or os.environ.get("PPI_ARTIFACTS_ROOT")
    if raw_root is None:
        print("ERROR: use --artifacts-root o PPI_ARTIFACTS_ROOT", file=sys.stderr)
        return 2
    artifacts_root = Path(raw_root)
    output_dir = args.output_dir or artifacts_root / "models/pm-multilayer-v2-v1-calibration"
    try:
        if args.preflight:
            report, _, _, _ = preflight_report(repo, artifacts_root, output_dir, args.expected_git_commit)
        else:
            report = execute_calibration(repo, artifacts_root, output_dir, args.expected_git_commit)
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 3
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
