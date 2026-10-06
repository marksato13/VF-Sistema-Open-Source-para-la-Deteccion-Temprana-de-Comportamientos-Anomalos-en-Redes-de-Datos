#!/usr/bin/env python3
"""Preflight y calibración atómica del protocolo congelado PM-F1-v1.

El selector abre únicamente las celdas oficiales R01--R04. R05 no se enumera,
no se valida y no se usa para preparar, ajustar ni calibrar ningún detector.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import importlib.metadata
import importlib.util
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
from types import ModuleType
from typing import Any, Callable, Sequence


REPO = Path(__file__).resolve().parents[2]
BUILDER_RELATIVE = Path("scripts/dataset/build_f1_dataset.py")
REQUIREMENTS_RELATIVE = Path("requirements-model.txt")
PROTOCOL_ID = "PM-F1-v1"
ALPHA = 0.05
PRIMARY_SEED = 20260804
STABILITY_SEEDS = tuple(range(20260804, 20260814))
EXPECTED_PYTHON = "3.14.4"
EXPECTED_ROWS = {"train": 224, "validation": 72}
EXPECTED_CAMPAIGNS = {"train": 87, "validation": 29}
EXPECTED_REPETITIONS = {
    1: "train",
    2: "train",
    3: "train",
    4: "validation",
}
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
class SelectedData:
    contract: Any
    candidates: tuple[dict[str, Any], ...]
    rows: tuple[dict[str, str], ...]
    metadata: tuple[dict[str, Any], ...]
    partitions: tuple[str, ...]


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def sha256_path(path: Path) -> str:
    return sha256_bytes(path.read_bytes())


def load_builder(repo: Path) -> ModuleType:
    path = repo / BUILDER_RELATIVE
    spec = importlib.util.spec_from_file_location("ppi_f1_dataset_builder_calibration", path)
    if spec is None or spec.loader is None:
        raise CalibrationError(f"no se puede cargar el ensamblador: {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def git_state(repo: Path) -> tuple[str, bool]:
    commit = subprocess.check_output(
        ["git", "-C", str(repo), "rev-parse", "HEAD"], text=True
    ).strip()
    dirty = bool(
        subprocess.check_output(
            ["git", "-C", str(repo), "status", "--porcelain"], text=True
        ).strip()
    )
    return commit, dirty


def require_execution_context(repo: Path, expected_commit: str) -> str:
    if len(expected_commit) != 40 or any(character not in "0123456789abcdef" for character in expected_commit):
        raise CalibrationError("--expected-git-commit debe ser un SHA-1 completo en minúsculas")
    commit, dirty = git_state(repo)
    if dirty:
        raise CalibrationError("Git debe estar limpio antes del preflight o la calibración")
    if commit != expected_commit:
        raise CalibrationError(f"commit actual {commit} distinto del esperado {expected_commit}")
    return commit


def parse_frozen_requirements(path: Path) -> dict[str, str]:
    expected: dict[str, str] = {}
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
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
        raise CalibrationError(
            f"CPython {platform.python_version()} no coincide con {EXPECTED_PYTHON}"
        )
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


def expected_ledger_paths(contract: Any, ledgers_dir: Path) -> list[tuple[int, str, Path]]:
    mapping = contract.matrix.get("partition_by_repetition", {})
    for repetition, partition in EXPECTED_REPETITIONS.items():
        if mapping.get(str(repetition)) != partition:
            raise CalibrationError(
                f"la matriz asigna R{repetition:02d} a {mapping.get(str(repetition))!r}, no a {partition!r}"
            )
    paths: list[tuple[int, str, Path]] = []
    for repetition, partition in EXPECTED_REPETITIONS.items():
        for profile in contract.matrix["profiles"]:
            campaign_id = f"F1N-{profile['id']}-R{repetition:02d}"
            paths.append((repetition, partition, ledgers_dir / f"{campaign_id}.json"))
    return paths


def load_selected_data(repo: Path, artifacts_root: Path) -> SelectedData:
    """Valida sólo R01--R04 mediante sus 116 nombres canónicos exactos."""
    builder = load_builder(repo)
    contract = builder.load_contract(repo)
    campaigns_dir = artifacts_root / "campaigns"
    features_dir = artifacts_root / "features"
    ledgers_dir = artifacts_root / "g6-ledger"
    candidates: list[dict[str, Any]] = []
    rows: list[dict[str, str]] = []
    metadata: list[dict[str, Any]] = []
    partitions: list[str] = []
    claimed_cells: set[tuple[str, int]] = set()
    csv_hashes: set[str] = set()

    for repetition, partition, ledger_path in expected_ledger_paths(contract, ledgers_dir):
        if not ledger_path.is_file():
            raise CalibrationError(f"falta ledger oficial: {ledger_path.name}")
        candidate = builder.validate_candidate(
            ledger_path, campaigns_dir, features_dir, contract
        )
        cell = (candidate["profile_id"], candidate["repetition"])
        if cell in claimed_cells:
            raise CalibrationError(f"celda repetida en selección: {cell}")
        if candidate["csv_sha256"] in csv_hashes:
            raise CalibrationError(f"CSV fuente repetido: {candidate['campaign_id']}")
        if candidate["repetition"] != repetition or candidate["partition"] != partition:
            raise CalibrationError(f"split incongruente: {candidate['campaign_id']}")
        if candidate["warnings"]:
            raise CalibrationError(
                f"campaña con advertencias no cerradas: {candidate['campaign_id']} {candidate['warnings']}"
            )
        claimed_cells.add(cell)
        csv_hashes.add(candidate["csv_sha256"])
        candidates.append(candidate)
        for row_index, row in enumerate(
            sorted(candidate["rows"], key=lambda item: item["window_end_utc"])
        ):
            rows.append(row)
            partitions.append(partition)
            metadata.append(
                {
                    "partition": partition,
                    "profile_id": candidate["profile_id"],
                    "repetition": repetition,
                    "campaign_id": candidate["campaign_id"],
                    "row_in_campaign": row_index,
                    "entity_ip": row["entity_ip"],
                    "window_end_utc": row["window_end_utc"],
                }
            )

    partition_rows = Counter(partitions)
    partition_campaigns = Counter(candidate["partition"] for candidate in candidates)
    if dict(partition_rows) != EXPECTED_ROWS:
        raise CalibrationError(f"filas distintas del contrato: {dict(partition_rows)}")
    if dict(partition_campaigns) != EXPECTED_CAMPAIGNS:
        raise CalibrationError(f"campañas distintas del contrato: {dict(partition_campaigns)}")
    return SelectedData(
        contract=contract,
        candidates=tuple(candidates),
        rows=tuple(rows),
        metadata=tuple(metadata),
        partitions=tuple(partitions),
    )


def decimal_vector(row: dict[str, str], feature_names: Sequence[str]) -> tuple[Decimal, ...]:
    return tuple(Decimal(row[name]) for name in feature_names)


def collapsed_train_indices(rows: Sequence[dict[str, str]], feature_names: Sequence[str]) -> list[int]:
    seen: set[tuple[Decimal, ...]] = set()
    selected: list[int] = []
    for index, row in enumerate(rows):
        vector = decimal_vector(row, feature_names)
        if vector not in seen:
            seen.add(vector)
            selected.append(index)
    return selected


def episode_balanced_indices(campaign_ids: Sequence[str]) -> tuple[list[int], int]:
    if not campaign_ids:
        raise CalibrationError("train vacío")
    positions: dict[str, list[int]] = {}
    for index, campaign_id in enumerate(campaign_ids):
        positions.setdefault(campaign_id, []).append(index)
    rows_per_campaign = math.lcm(*(len(indices) for indices in positions.values()))
    expanded: list[int] = []
    for campaign_id in positions:
        indices = positions[campaign_id]
        repeats = rows_per_campaign // len(indices)
        for index in indices:
            expanded.extend([index] * repeats)
    return expanded, rows_per_campaign


def lower_tail(scores: Sequence[float], campaign_ids: Sequence[str], alpha: float = ALPHA) -> dict[str, Any]:
    if not scores or len(scores) != len(campaign_ids):
        raise CalibrationError("scores y campaign_ids deben ser no vacíos y de igual longitud")
    if not 0 < alpha < 0.5:
        raise CalibrationError("alpha debe estar entre 0 y 0.5")
    for score in scores:
        if not math.isfinite(float(score)):
            raise CalibrationError("score no finito")
    ordered = sorted(range(len(scores)), key=lambda index: (float(scores[index]), index))
    k = math.floor(alpha * len(scores))
    threshold = float(scores[ordered[k]])
    prefix = ordered[:k]
    alerts = [index for index, score in enumerate(scores) if float(score) < threshold]
    return {
        "unit": "windows",
        "alpha": alpha,
        "n_windows": len(scores),
        "k": k,
        "threshold": threshold,
        "comparison": "score < threshold",
        "stable_tie_break": "validation_row_index",
        "threshold_tie_count": sum(float(score) == threshold for score in scores),
        "lower_prefix_indices": prefix,
        "lower_prefix_campaigns": sorted({campaign_ids[index] for index in prefix}),
        "lower_prefix_campaign_count": len({campaign_ids[index] for index in prefix}),
        "strict_alert_indices": alerts,
        "strict_alert_campaigns": sorted({campaign_ids[index] for index in alerts}),
        "strict_alert_count": len(alerts),
        "strict_alert_campaign_count": len({campaign_ids[index] for index in alerts}),
    }


def csv_bytes(fieldnames: Sequence[str], rows: Sequence[dict[str, Any]]) -> bytes:
    buffer = io.StringIO(newline="")
    writer = csv.DictWriter(buffer, fieldnames=fieldnames, lineterminator="\n")
    writer.writeheader()
    writer.writerows(rows)
    return buffer.getvalue().encode("utf-8")


def selection_bytes(selected: SelectedData) -> bytes:
    feature_names = list(selected.contract.feature_names)
    fields = [
        "partition",
        "profile_id",
        "repetition",
        "campaign_id",
        "row_in_campaign",
        "entity_ip",
        "window_end_utc",
        *feature_names,
    ]
    output: list[dict[str, Any]] = []
    for row, metadata in zip(selected.rows, selected.metadata, strict=True):
        output.append({**metadata, **{name: row[name] for name in feature_names}})
    return csv_bytes(fields, output)


def matrix_from_rows(rows: Sequence[dict[str, str]], feature_names: Sequence[str]) -> Any:
    import numpy as np

    matrix = np.asarray(
        [[float(row[name]) for name in feature_names] for row in rows], dtype=np.float64
    )
    if matrix.ndim != 2 or matrix.shape[1] != 14 or not np.isfinite(matrix).all():
        raise CalibrationError(f"matriz inválida: shape={matrix.shape}")
    return matrix


def make_if(seed: int, scaled: bool = False) -> Any:
    from sklearn.ensemble import IsolationForest
    from sklearn.pipeline import Pipeline
    from sklearn.preprocessing import StandardScaler

    detector = IsolationForest(**IF_PARAMETERS, random_state=seed)
    return Pipeline([("scaler", StandardScaler()), ("detector", detector)]) if scaled else detector


def primary_detector_factories() -> dict[str, Callable[[], Any]]:
    from sklearn.neighbors import LocalOutlierFactor
    from sklearn.pipeline import Pipeline
    from sklearn.preprocessing import StandardScaler
    from sklearn.svm import OneClassSVM

    return {
        "if_window": lambda: make_if(PRIMARY_SEED),
        "if_scaled": lambda: make_if(PRIMARY_SEED, scaled=True),
        "if_campaign_expanded": lambda: make_if(PRIMARY_SEED),
        "if_exact_collapsed": lambda: make_if(PRIMARY_SEED),
        "lof_scaled": lambda: Pipeline(
            [
                ("scaler", StandardScaler()),
                (
                    "detector",
                    LocalOutlierFactor(
                        n_neighbors=20,
                        novelty=True,
                        contamination="auto",
                        n_jobs=1,
                    ),
                ),
            ]
        ),
        "ocsvm_scaled": lambda: Pipeline(
            [
                ("scaler", StandardScaler()),
                (
                    "detector",
                    OneClassSVM(kernel="rbf", gamma="scale", nu=0.05, cache_size=200),
                ),
            ]
        ),
    }


def fit_and_score(model: Any, train: Any, validation: Any) -> tuple[Any, list[float], dict[str, float]]:
    fit_started = time.perf_counter_ns()
    model.fit(train)
    fit_seconds = (time.perf_counter_ns() - fit_started) / 1_000_000_000
    score_started = time.perf_counter_ns()
    scores = [float(value) for value in model.score_samples(validation)]
    score_seconds = (time.perf_counter_ns() - score_started) / 1_000_000_000
    if not all(math.isfinite(value) for value in scores):
        raise CalibrationError("el detector produjo scores no finitos")
    return model, scores, {
        "fit_seconds": fit_seconds,
        "score_batch_seconds": score_seconds,
        "score_seconds_per_window": score_seconds / len(scores),
        "timing_scope": "descriptive_single_batch_on_vm01_not_production_benchmark",
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


def preflight_report(
    repo: Path,
    artifacts_root: Path,
    output_dir: Path,
    expected_commit: str,
) -> tuple[dict[str, Any], SelectedData]:
    commit = require_execution_context(repo, expected_commit)
    runtime = verify_runtime(repo)
    destination = safe_output_path(artifacts_root, output_dir)
    selected = load_selected_data(repo, artifacts_root)
    payload = selection_bytes(selected)
    train_campaigns = {
        metadata["campaign_id"]
        for metadata in selected.metadata
        if metadata["partition"] == "train"
    }
    validation_campaigns = {
        metadata["campaign_id"]
        for metadata in selected.metadata
        if metadata["partition"] == "validation"
    }
    return {
        "schema_version": "pm-f1-v1-preflight-v1",
        "protocol": PROTOCOL_ID,
        "gate_pass": True,
        "git_commit": commit,
        "git_dirty": False,
        "runtime": runtime,
        "output_dir": str(destination),
        "selection_sha256": sha256_bytes(payload),
        "train": {"campaigns": len(train_campaigns), "rows": selected.partitions.count("train")},
        "validation": {
            "campaigns": len(validation_campaigns),
            "rows": selected.partitions.count("validation"),
        },
        "r05_artifacts_enumerated_or_read": False,
    }, selected


def score_rows_bytes(
    detector_scores: dict[str, list[float]],
    validation_metadata: Sequence[dict[str, Any]],
    validation_seen: Sequence[bool],
) -> bytes:
    fields = [
        "detector",
        "validation_row_index",
        "profile_id",
        "campaign_id",
        "window_end_utc",
        "seen_exact_in_train",
        "score",
    ]
    rows: list[dict[str, Any]] = []
    for detector_name, scores in detector_scores.items():
        for index, (score, metadata, seen) in enumerate(
            zip(scores, validation_metadata, validation_seen, strict=True)
        ):
            rows.append(
                {
                    "detector": detector_name,
                    "validation_row_index": index,
                    "profile_id": metadata["profile_id"],
                    "campaign_id": metadata["campaign_id"],
                    "window_end_utc": metadata["window_end_utc"],
                    "seen_exact_in_train": str(seen),
                    "score": format(score, ".17g"),
                }
            )
    return csv_bytes(fields, rows)


def stability_rows_bytes(
    scores_by_branch_seed: dict[tuple[str, int], list[float]],
    validation_metadata: Sequence[dict[str, Any]],
) -> bytes:
    fields = ["branch", "seed", "validation_row_index", "campaign_id", "score"]
    rows: list[dict[str, Any]] = []
    for (branch, seed), scores in scores_by_branch_seed.items():
        for index, (score, metadata) in enumerate(zip(scores, validation_metadata, strict=True)):
            rows.append(
                {
                    "branch": branch,
                    "seed": seed,
                    "validation_row_index": index,
                    "campaign_id": metadata["campaign_id"],
                    "score": format(score, ".17g"),
                }
            )
    return csv_bytes(fields, rows)


def execute_calibration(
    repo: Path,
    artifacts_root: Path,
    output_dir: Path,
    expected_commit: str,
) -> dict[str, Any]:
    import joblib
    import numpy as np
    import sklearn
    from threadpoolctl import threadpool_info

    preflight, selected = preflight_report(
        repo, artifacts_root, output_dir, expected_commit
    )
    destination = Path(preflight["output_dir"])
    feature_names = tuple(selected.contract.feature_names)
    train_positions = [index for index, value in enumerate(selected.partitions) if value == "train"]
    validation_positions = [
        index for index, value in enumerate(selected.partitions) if value == "validation"
    ]
    train_rows = [selected.rows[index] for index in train_positions]
    validation_rows = [selected.rows[index] for index in validation_positions]
    train_metadata = [selected.metadata[index] for index in train_positions]
    validation_metadata = [selected.metadata[index] for index in validation_positions]
    x_train = matrix_from_rows(train_rows, feature_names)
    x_validation = matrix_from_rows(validation_rows, feature_names)
    train_campaign_ids = [item["campaign_id"] for item in train_metadata]
    validation_campaign_ids = [item["campaign_id"] for item in validation_metadata]
    expanded_indices, rows_per_campaign = episode_balanced_indices(train_campaign_ids)
    collapsed_indices = collapsed_train_indices(train_rows, feature_names)
    if rows_per_campaign != 84 or len(expanded_indices) != 7308:
        raise CalibrationError(
            f"expansión distinta del protocolo: {rows_per_campaign=}, filas={len(expanded_indices)}"
        )
    train_vectors = {decimal_vector(row, feature_names) for row in train_rows}
    validation_seen = [decimal_vector(row, feature_names) in train_vectors for row in validation_rows]

    training_matrices = {
        "if_window": x_train,
        "if_scaled": x_train,
        "if_campaign_expanded": x_train[expanded_indices],
        "if_exact_collapsed": x_train[collapsed_indices],
        "lof_scaled": x_train,
        "ocsvm_scaled": x_train,
    }
    models: dict[str, Any] = {}
    detector_scores: dict[str, list[float]] = {}
    timings: dict[str, dict[str, float]] = {}
    for name, factory in primary_detector_factories().items():
        model, scores, timing = fit_and_score(factory(), training_matrices[name], x_validation)
        models[name] = model
        detector_scores[name] = scores
        timings[name] = timing

    stability_scores: dict[tuple[str, int], list[float]] = {}
    stability_train = {
        "if_window": x_train,
        "if_scaled": x_train,
        "if_campaign_expanded": x_train[expanded_indices],
        "if_exact_collapsed": x_train[collapsed_indices],
    }
    for branch, train_matrix in stability_train.items():
        for seed in STABILITY_SEEDS:
            if seed == PRIMARY_SEED:
                scores = detector_scores[branch]
            else:
                model = make_if(seed, scaled=branch == "if_scaled")
                model.fit(train_matrix)
                scores = [float(value) for value in model.score_samples(x_validation)]
            if not all(math.isfinite(value) for value in scores):
                raise CalibrationError(f"scores de estabilidad no finitos: {branch}/{seed}")
            stability_scores[(branch, seed)] = scores

    # Se sellan representaciones canónicas antes de derivar colas o rankings.
    selection_payload = selection_bytes(selected)
    score_payload = score_rows_bytes(detector_scores, validation_metadata, validation_seen)
    stability_payload = stability_rows_bytes(stability_scores, validation_metadata)
    sealed_hashes = {
        "selection.csv": sha256_bytes(selection_payload),
        "validation-scores.csv": sha256_bytes(score_payload),
        "stability-scores.csv": sha256_bytes(stability_payload),
    }

    detector_reports: dict[str, Any] = {}
    for name, scores in detector_scores.items():
        tail = lower_tail(scores, validation_campaign_ids)
        tail["strict_alert_seen_count"] = sum(
            validation_seen[index] for index in tail["strict_alert_indices"]
        )
        tail["strict_alert_unseen_count"] = sum(
            not validation_seen[index] for index in tail["strict_alert_indices"]
        )
        detector_reports[name] = {
            "role": "primary" if name == "if_window" else "sensitivity_or_comparator",
            "train_rows": len(training_matrices[name]),
            "timing": timings[name],
            "calibration": tail,
        }
    stability_reports: dict[str, list[dict[str, Any]]] = {}
    for branch in stability_train:
        branch_reports = []
        for seed in STABILITY_SEEDS:
            tail = lower_tail(stability_scores[(branch, seed)], validation_campaign_ids)
            branch_reports.append(
                {
                    "seed": seed,
                    "threshold": tail["threshold"],
                    "strict_alert_count": tail["strict_alert_count"],
                    "strict_alert_campaign_count": tail["strict_alert_campaign_count"],
                    "threshold_tie_count": tail["threshold_tie_count"],
                }
            )
        stability_reports[branch] = branch_reports

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
        (temporary / "selection.csv").write_bytes(selection_payload)
        (temporary / "validation-scores.csv").write_bytes(score_payload)
        (temporary / "stability-scores.csv").write_bytes(stability_payload)
        model_hashes: dict[str, str] = {}
        for name, model in models.items():
            model_path = temporary / "models" / f"{name}.joblib"
            joblib.dump(model, model_path, compress=3)
            model_hashes[str(model_path.relative_to(temporary))] = sha256_path(model_path)

        source_campaigns = [
            {
                key: candidate[key]
                for key in (
                    "campaign_id",
                    "profile_id",
                    "repetition",
                    "partition",
                    "git_commit",
                    "csv_sha256",
                    "pcap_bytes",
                )
            }
            for candidate in selected.candidates
        ]
        manifest = {
            "schema_version": "pm-f1-v1-calibration-manifest-v1",
            "protocol": PROTOCOL_ID,
            "created_at": datetime.now().astimezone().isoformat(),
            "git_commit": expected_commit,
            "git_dirty_before_and_after": False,
            "runtime": preflight["runtime"],
            "threadpools": threadpool_info(),
            "numpy": np.__version__,
            "scikit_learn": sklearn.__version__,
            "feature_names": list(feature_names),
            "matrix_sha256": selected.contract.matrix_sha256,
            "feature_schema_sha256": selected.contract.schema_sha256,
            "calibrator_sha256": sha256_path(Path(__file__)),
            "builder_sha256": sha256_path(repo / BUILDER_RELATIVE),
            "sealed_before_tail_diagnostics": True,
            "sealed_file_hashes": sealed_hashes,
            "model_hashes": model_hashes,
            "r05_artifacts_enumerated_or_read": False,
            "selection": {
                "order": "repetition_then_matrix_profile_then_window_end_utc",
                "train_repetitions": [1, 2, 3],
                "validation_repetition": 4,
                "train_campaigns": EXPECTED_CAMPAIGNS["train"],
                "train_rows": EXPECTED_ROWS["train"],
                "validation_campaigns": EXPECTED_CAMPAIGNS["validation"],
                "validation_rows": EXPECTED_ROWS["validation"],
                "validation_seen_rows": sum(validation_seen),
                "validation_unseen_rows": len(validation_seen) - sum(validation_seen),
                "collapsed_train_rows": len(collapsed_indices),
                "expanded_rows_per_campaign": rows_per_campaign,
                "expanded_train_rows": len(expanded_indices),
            },
            "if_parameters": {**IF_PARAMETERS, "random_state": PRIMARY_SEED},
            "stability_seeds": list(STABILITY_SEEDS),
            "secondary_parameters": {
                "lof_scaled": {
                    "n_neighbors": 20,
                    "novelty": True,
                    "contamination": "auto",
                    "n_jobs": 1,
                },
                "ocsvm_scaled": {
                    "kernel": "rbf",
                    "gamma": "scale",
                    "nu": 0.05,
                    "cache_size": 200,
                },
            },
            "scaler_fit_scope": "train_R01_R03_only",
            "missing_value_policy": "reject_non_finite_at_dataset_gate_no_imputation",
            "model_selection_policy": "if_window_remains_primary_comparators_cannot_replace_it_from_R04_or_R05",
            "detectors": detector_reports,
            "stability": stability_reports,
            "source_campaigns": source_campaigns,
        }
        current_commit, current_dirty = git_state(repo)
        if current_commit != expected_commit or current_dirty:
            raise CalibrationError("Git cambió durante la calibración; la salida se descarta")
        (temporary / "manifest.json").write_text(
            json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )
        checksum_lines = []
        for path in sorted(temporary.rglob("*")):
            if path.is_file() and path.name != "SHA256SUMS":
                checksum_lines.append(
                    f"{sha256_path(path)}  {path.relative_to(temporary).as_posix()}\n"
                )
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
    parser = argparse.ArgumentParser(description="Calibración atómica PM-F1-v1")
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
    output_dir = args.output_dir or artifacts_root / "models/pm-f1-v1-calibration"
    try:
        if args.preflight:
            report, _ = preflight_report(
                repo, artifacts_root, output_dir, args.expected_git_commit
            )
        else:
            report = execute_calibration(
                repo, artifacts_root, output_dir, args.expected_git_commit
            )
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 3
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
