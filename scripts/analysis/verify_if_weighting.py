#!/usr/bin/env python3
"""Verifica pesos por campaña y diagnostica la cola inferior de IF sobre train."""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import math
import os
import platform
import subprocess
import sys
from collections import Counter, defaultdict
from pathlib import Path
from types import ModuleType
from typing import Any, Iterable, Sequence


REPO = Path(__file__).resolve().parents[2]
BUILDER_PATH = REPO / "scripts/dataset/build_f1_dataset.py"
DEFAULT_SEEDS = (20260804, 7, 42)
IF_PARAMETERS = {
    "n_estimators": 500,
    "max_samples": "auto",
    "contamination": "auto",
    "max_features": 1.0,
    "bootstrap": False,
    "n_jobs": 1,
    "warm_start": False,
}


def sha256_path(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_builder(path: Path = BUILDER_PATH) -> ModuleType:
    spec = importlib.util.spec_from_file_location("ppi_f1_dataset_builder_weighting", path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"no se puede cargar el ensamblador: {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def campaign_weights(campaign_ids: Sequence[str]) -> list[float]:
    if not campaign_ids:
        raise ValueError("se requiere al menos una fila")
    counts = Counter(campaign_ids)
    return [1.0 / counts[campaign_id] for campaign_id in campaign_ids]


def episode_balanced_indices(campaign_ids: Sequence[str]) -> tuple[list[int], int]:
    """Replica filas hasta que cada campaña aporte el mismo total."""
    if not campaign_ids:
        raise ValueError("se requiere al menos una fila")
    positions: dict[str, list[int]] = defaultdict(list)
    order: list[str] = []
    for index, campaign_id in enumerate(campaign_ids):
        if campaign_id not in positions:
            order.append(campaign_id)
        positions[campaign_id].append(index)
    common_rows = math.lcm(*(len(indices) for indices in positions.values()))
    expanded: list[int] = []
    for campaign_id in order:
        indices = positions[campaign_id]
        repeats = common_rows // len(indices)
        for index in indices:
            expanded.extend([index] * repeats)
    return expanded, common_rows


def lower_tail_diagnostics(
    scores: Sequence[float], campaign_ids: Sequence[str], alpha: float = 0.05
) -> dict[str, Any]:
    """Aplica el cuantil inferior estricto; n siempre significa ventanas."""
    if len(scores) != len(campaign_ids) or not scores:
        raise ValueError("scores y campañas deben tener la misma longitud no vacía")
    if not 0 < alpha < 0.5:
        raise ValueError("alpha debe estar entre 0 y 0.5")
    ordered = sorted(range(len(scores)), key=lambda index: (scores[index], index))
    k = math.floor(alpha * len(scores))
    threshold = float(scores[ordered[k]])
    prefix = ordered[:k]
    alerts = [index for index, score in enumerate(scores) if score < threshold]
    return {
        "unit": "windows",
        "n_windows": len(scores),
        "alpha": alpha,
        "k": k,
        "threshold": threshold,
        "strict_alert_count": len(alerts),
        "strict_alert_campaign_count": len({campaign_ids[index] for index in alerts}),
        "lower_prefix_campaign_count": len(
            {campaign_ids[index] for index in prefix}
        ),
        "threshold_tie_count": sum(score == threshold for score in scores),
    }


def tree_structure_equal(left: Any, right: Any) -> bool:
    import numpy as np

    if len(left.estimators_) != len(right.estimators_):
        return False
    attributes = ("children_left", "children_right", "feature", "threshold")
    return all(
        all(
            np.array_equal(getattr(a.tree_, attribute), getattr(b.tree_, attribute))
            for attribute in attributes
        )
        for a, b in zip(left.estimators_, right.estimators_, strict=True)
    )


def verify_seed(
    matrix: Any,
    weights: Sequence[float],
    campaign_ids: Sequence[str],
    seed: int,
) -> dict[str, Any]:
    import numpy as np
    from sklearn.ensemble import IsolationForest

    parameters = {**IF_PARAMETERS, "random_state": seed}
    uniform = IsolationForest(**parameters).fit(matrix)
    weighted = IsolationForest(**parameters).fit(matrix, sample_weight=weights)
    uniform_scores = uniform.score_samples(matrix)
    weighted_scores = weighted.score_samples(matrix)
    return {
        "seed": seed,
        "score_array_equal": bool(np.array_equal(uniform_scores, weighted_scores)),
        "score_max_abs_delta": float(np.max(np.abs(uniform_scores - weighted_scores))),
        "tree_structure_equal": tree_structure_equal(uniform, weighted),
        "lower_tail_uniform": lower_tail_diagnostics(
            uniform_scores.tolist(), campaign_ids
        ),
    }


def load_train(repo: Path, artifacts_root: Path) -> tuple[Any, list[dict[str, Any]]]:
    builder = load_builder(repo / "scripts/dataset/build_f1_dataset.py")
    contract = builder.load_contract(repo)
    report, accepted = builder.audit_repository(
        contract,
        artifacts_root / "campaigns",
        artifacts_root / "features",
        artifacts_root / "g6-ledger",
    )
    if report["invalid_campaigns"]:
        raise RuntimeError(f"campañas inválidas: {report['invalid_campaigns']}")
    selected = [candidate for candidate in accepted if candidate["partition"] == "train"]
    expected = {
        (profile["id"], repetition)
        for profile in contract.matrix["profiles"]
        for repetition, partition in (
            (int(value), name)
            for value, name in contract.matrix["partition_by_repetition"].items()
        )
        if partition == "train"
    }
    observed = {(candidate["profile_id"], candidate["repetition"]) for candidate in selected}
    if observed != expected or len(selected) != len(expected):
        raise RuntimeError(
            f"train incompleto/incongruente: observado={len(observed)}, esperado={len(expected)}"
        )
    profile_order = {
        profile["id"]: index for index, profile in enumerate(contract.matrix["profiles"])
    }
    selected.sort(
        key=lambda item: (item["repetition"], profile_order[item["profile_id"]])
    )
    return contract, selected


def build_report(
    repo: Path, artifacts_root: Path, seeds: Iterable[int] = DEFAULT_SEEDS
) -> dict[str, Any]:
    import numpy as np
    import sklearn

    contract, selected = load_train(repo, artifacts_root)
    rows: list[dict[str, Any]] = []
    campaign_ids: list[str] = []
    for candidate in selected:
        ordered_rows = sorted(candidate["rows"], key=lambda row: row["window_end_utc"])
        rows.extend(ordered_rows)
        campaign_ids.extend([candidate["campaign_id"]] * len(ordered_rows))
    matrix = np.asarray(
        [[float(row[name]) for name in contract.feature_names] for row in rows],
        dtype=np.float64,
    )
    weights = campaign_weights(campaign_ids)
    expanded, common_rows = episode_balanced_indices(campaign_ids)
    results = [verify_seed(matrix, weights, campaign_ids, seed) for seed in seeds]
    git_commit = subprocess.check_output(
        ["git", "-C", str(repo), "rev-parse", "HEAD"], text=True
    ).strip()
    git_dirty = bool(
        subprocess.check_output(
            ["git", "-C", str(repo), "status", "--porcelain"], text=True
        ).strip()
    )
    return {
        "schema_version": "if-weighting-verification-v1",
        "python": platform.python_version(),
        "numpy": np.__version__,
        "scikit_learn": sklearn.__version__,
        "matrix_sha256": contract.matrix_sha256,
        "feature_schema_sha256": contract.schema_sha256,
        "verifier_sha256": sha256_path(Path(__file__)),
        "requirements_sha256": sha256_path(repo / "requirements-model.txt"),
        "git_commit": git_commit,
        "git_dirty": git_dirty,
        "train_campaigns": len(selected),
        "train_rows": len(rows),
        "row_counts": dict(sorted(Counter(Counter(campaign_ids).values()).items())),
        "episode_expansion": {
            "rows_per_campaign": common_rows,
            "expanded_rows": len(expanded),
        },
        "if_parameters": IF_PARAMETERS,
        "seeds": results,
        "verification_pass": all(
            result["score_array_equal"] and result["tree_structure_equal"]
            for result in results
        ),
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Verifica si sample_weight cambia Isolation Forest en F1 train."
    )
    parser.add_argument("--repo", type=Path, default=REPO)
    parser.add_argument("--artifacts-root", type=Path)
    parser.add_argument("--seeds", type=int, nargs="+", default=list(DEFAULT_SEEDS))
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    raw_root = args.artifacts_root or os.environ.get("PPI_ARTIFACTS_ROOT")
    if raw_root is None:
        print("ERROR: use --artifacts-root o PPI_ARTIFACTS_ROOT", file=sys.stderr)
        return 2
    artifacts_root = Path(raw_root)
    if not artifacts_root.is_absolute():
        print("ERROR: la raíz de artefactos debe ser absoluta", file=sys.stderr)
        return 2
    try:
        report = build_report(args.repo.resolve(), artifacts_root, args.seeds)
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 3
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0 if report["verification_pass"] else 4


if __name__ == "__main__":
    raise SystemExit(main())
