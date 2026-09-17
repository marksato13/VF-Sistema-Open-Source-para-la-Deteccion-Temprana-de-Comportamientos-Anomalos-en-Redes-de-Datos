#!/usr/bin/env python3
"""Resume una repetición F1 únicamente después de pasar el auditor oficial."""

from __future__ import annotations

import argparse
import importlib.util
import json
import os
import sys
from collections import Counter, defaultdict
from decimal import Decimal
from pathlib import Path
from types import ModuleType
from typing import Any


REPO = Path(__file__).resolve().parents[2]
BUILDER_PATH = REPO / "scripts/dataset/build_f1_dataset.py"


def load_builder(path: Path = BUILDER_PATH) -> ModuleType:
    spec = importlib.util.spec_from_file_location("ppi_f1_dataset_builder", path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"no se puede cargar el ensamblador: {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def as_decimal(value: Any) -> Decimal:
    try:
        return Decimal(str(value))
    except Exception as exc:
        raise ValueError(f"valor numérico inválido: {value!r}") from exc


def rounded(value: Decimal) -> float:
    return float(value.quantize(Decimal("0.00000001")))


def median(values: list[Decimal]) -> Decimal:
    ordered = sorted(values)
    middle = len(ordered) // 2
    if len(ordered) % 2:
        return ordered[middle]
    return (ordered[middle - 1] + ordered[middle]) / 2


def normalized_vector(row: dict[str, Any], feature_names: tuple[str, ...]) -> tuple[str, ...]:
    return tuple(format(as_decimal(row[name]).normalize(), "f") for name in feature_names)


def build_summary(
    repetition: int,
    contract: Any,
    audit_report: dict[str, Any],
    accepted: list[dict[str, Any]],
    observation_counts: dict[str, dict[str, int]],
) -> dict[str, Any]:
    maximum = int(contract.matrix["default_repetitions"])
    if not 1 <= repetition <= maximum:
        raise ValueError(f"repetición fuera de rango 1..{maximum}: {repetition}")

    profiles = {item["id"]: item for item in contract.matrix["profiles"]}
    profile_order = [item["id"] for item in contract.matrix["profiles"]]
    selected_candidates = [
        item for item in accepted if int(item["repetition"]) == repetition
    ]
    selected = {item["profile_id"]: item for item in selected_candidates}
    if len(selected) != len(selected_candidates):
        raise ValueError(f"la repetición {repetition} contiene perfiles duplicados")
    expected_profiles = set(profile_order)
    accepted_profiles = set(selected)
    missing_profiles = [profile for profile in profile_order if profile not in accepted_profiles]
    unexpected_profiles = sorted(accepted_profiles - expected_profiles)

    all_rows: list[tuple[dict[str, Any], dict[str, Any]]] = []
    campaign_rows: list[dict[str, Any]] = []
    scenario_rows: Counter[str] = Counter()
    total_packet_observations = 0
    total_application_observations = 0

    for profile_id in profile_order:
        candidate = selected.get(profile_id)
        if candidate is None:
            continue
        profile = profiles[profile_id]
        rows = candidate["rows"]
        counts = observation_counts[candidate["campaign_id"]]
        for count_name in ("packet_observations", "application_observations"):
            count_value = counts.get(count_name)
            if (
                not isinstance(count_value, int)
                or isinstance(count_value, bool)
                or count_value < 0
            ):
                raise ValueError(
                    f"{candidate['campaign_id']} tiene {count_name} inválido: "
                    f"{count_value!r}"
                )
        total_packet_observations += counts["packet_observations"]
        total_application_observations += counts["application_observations"]
        scenario_rows[profile["scenario"]] += len(rows)
        campaign_rows.append(
            {
                "campaign_id": candidate["campaign_id"],
                "profile_id": profile_id,
                "scenario": profile["scenario"],
                "stratum": profile["stratum"],
                "rows": len(rows),
                "packet_observations": counts["packet_observations"],
                "application_observations": counts["application_observations"],
                "pcap_bytes": candidate["pcap_bytes"],
            }
        )
        all_rows.extend((candidate, row) for row in rows)

    total_rows = len(all_rows)
    if total_rows:
        for item in campaign_rows:
            item["row_share"] = rounded(Decimal(item["rows"]) / Decimal(total_rows))

    feature_definitions = {
        item["name"]: item for item in contract.schema.get("features", [])
    }
    feature_statistics: list[dict[str, Any]] = []
    all_zero_features: list[str] = []
    for feature_name in contract.feature_names:
        values = [as_decimal(row[feature_name]) for _, row in all_rows]
        if not values:
            continue
        nonzero_rows = sum(value != 0 for value in values)
        campaigns_with_nonzero = sorted(
            {
                candidate["campaign_id"]
                for candidate, row in all_rows
                if as_decimal(row[feature_name]) != 0
            }
        )
        definition = feature_definitions[feature_name]
        feature_statistics.append(
            {
                "name": feature_name,
                "layer": definition["layer"],
                "unit": definition["unit"],
                "minimum": rounded(min(values)),
                "maximum": rounded(max(values)),
                "mean": rounded(sum(values) / Decimal(len(values))),
                "median": rounded(median(values)),
                "distinct_values": len(set(values)),
                "zero_rows": len(values) - nonzero_rows,
                "nonzero_rows": nonzero_rows,
                "nonzero_campaigns": len(campaigns_with_nonzero),
                "campaigns_with_nonzero": campaigns_with_nonzero,
            }
        )
        if nonzero_rows == 0:
            all_zero_features.append(feature_name)

    fingerprints: dict[tuple[str, ...], list[dict[str, str]]] = defaultdict(list)
    for candidate, row in all_rows:
        fingerprints[normalized_vector(row, contract.feature_names)].append(
            {
                "campaign_id": candidate["campaign_id"],
                "window_end_utc": str(row["window_end_utc"]),
            }
        )
    repeated_vectors = [
        {"occurrences": len(locations), "locations": locations}
        for locations in fingerprints.values()
        if len(locations) > 1
    ]
    repeated_vectors.sort(
        key=lambda item: (
            -item["occurrences"],
            item["locations"][0]["campaign_id"],
            item["locations"][0]["window_end_utc"],
        )
    )

    rows_per_campaign = [item["rows"] for item in campaign_rows]
    repetition_complete = not missing_profiles and not unexpected_profiles
    repository_invalid = audit_report.get("invalid_campaigns", [])
    repository_warnings = audit_report.get("campaign_warnings", [])
    cross_campaign_duplicates = audit_report.get("duplicate_feature_vectors", [])
    cross_campaign_duplicate_count = int(
        audit_report.get(
            "duplicate_feature_vector_count",
            len(cross_campaign_duplicates),
        )
    )
    cross_partition_duplicate_count = int(
        audit_report.get("cross_partition_duplicate_feature_vector_count", 0)
    )
    current_git_dirty = bool(audit_report.get("current_git_dirty", False))
    gate_pass = (
        repetition_complete
        and total_rows > 0
        and not repository_invalid
        and not repository_warnings
        and not current_git_dirty
    )

    return {
        "schema_version": "f1-repetition-summary-v1",
        "repetition": repetition,
        "partition": contract.matrix["partition_by_repetition"][str(repetition)],
        "matrix_sha256": contract.matrix_sha256,
        "feature_schema_sha256": contract.schema_sha256,
        "expected_profiles": len(expected_profiles),
        "accepted_profiles": len(accepted_profiles & expected_profiles),
        "missing_profiles": missing_profiles,
        "unexpected_profiles": unexpected_profiles,
        "repetition_complete": repetition_complete,
        "gate_pass": gate_pass,
        "repository_audit": {
            "accepted_campaigns": audit_report.get("accepted_campaigns", 0),
            "invalid_campaigns": repository_invalid,
            "campaign_warnings": repository_warnings,
            "cross_campaign_duplicate_vectors": cross_campaign_duplicates,
            "cross_campaign_duplicate_vector_count": cross_campaign_duplicate_count,
            "cross_partition_duplicate_vector_count": cross_partition_duplicate_count,
            "cross_campaign_duplicate_vectors_truncated": int(
                audit_report.get("duplicate_feature_vectors_truncated", 0)
            ),
            "current_git_dirty": current_git_dirty,
            "assembler_git_commit": audit_report.get("assembler_git_commit"),
        },
        "rows": {
            "total": total_rows,
            "eligible": total_rows,
            "campaigns_with_one_row": sum(item["rows"] == 1 for item in campaign_rows),
            "campaigns_with_multiple_rows": sum(item["rows"] > 1 for item in campaign_rows),
            "minimum_per_campaign": min(rows_per_campaign) if rows_per_campaign else 0,
            "maximum_per_campaign": max(rows_per_campaign) if rows_per_campaign else 0,
            "median_per_campaign": rounded(
                median([Decimal(value) for value in rows_per_campaign])
            )
            if rows_per_campaign
            else 0,
        },
        "observations": {
            "packet": total_packet_observations,
            "application": total_application_observations,
        },
        "campaigns": campaign_rows,
        "rows_by_scenario": dict(sorted(scenario_rows.items())),
        "features": feature_statistics,
        "all_zero_features": all_zero_features,
        "exact_repeated_vector_groups": len(repeated_vectors),
        "exact_repeated_vectors": repeated_vectors,
    }


def load_observation_counts(
    builder: ModuleType,
    features_dir: Path,
    accepted: list[dict[str, Any]],
) -> dict[str, dict[str, int]]:
    result: dict[str, dict[str, int]] = {}
    for candidate in accepted:
        campaign_id = candidate["campaign_id"]
        report = builder.load_json(
            features_dir / campaign_id / "extraction-report.json",
            "GATE-RESUMEN",
        )
        packet_observations = report.get("packet_observations")
        application_observations = report.get("application_observations")
        for name, value in (
            ("packet_observations", packet_observations),
            ("application_observations", application_observations),
        ):
            if not isinstance(value, int) or isinstance(value, bool) or value < 0:
                raise ValueError(f"{campaign_id} tiene {name} inválido: {value!r}")
        result[campaign_id] = {
            "packet_observations": packet_observations,
            "application_observations": application_observations,
        }
    return result


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Audita y resume las features de una repetición F1."
    )
    parser.add_argument("--repo", type=Path, default=REPO)
    parser.add_argument("--artifacts-root", type=Path)
    parser.add_argument("--repetition", type=int, required=True)
    parser.add_argument(
        "--require-complete",
        action="store_true",
        help="Retorna código 3 si la repetición o el repositorio no pasan el gate.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    repo = args.repo.resolve()
    builder = load_builder(repo / "scripts/dataset/build_f1_dataset.py")
    raw_root = args.artifacts_root or Path(
        os.environ.get("PPI_ARTIFACTS_ROOT", str(repo / "artifacts"))
    )
    if not raw_root.is_absolute():
        print("ERROR: artifacts-root debe ser absoluto", file=sys.stderr)
        return 2
    artifacts_root = raw_root.resolve()
    campaigns_dir = artifacts_root / "campaigns"
    features_dir = artifacts_root / "features"
    ledgers_dir = artifacts_root / "g6-ledger"
    try:
        contract = builder.load_contract(repo)
        audit_report, accepted = builder.audit_repository(
            contract,
            campaigns_dir,
            features_dir,
            ledgers_dir,
        )
        observation_counts = load_observation_counts(builder, features_dir, accepted)
        summary = build_summary(
            args.repetition,
            contract,
            audit_report,
            accepted,
            observation_counts,
        )
    except (builder.GateError, KeyError, ValueError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2
    print(json.dumps(summary, indent=2, sort_keys=True))
    if args.require_complete and not summary["gate_pass"]:
        return 3
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
