#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
from pathlib import Path


ALLOWED_SCENARIOS = {
    "http", "https", "http-concurrent", "http-multi", "http-missing", "https-sessions",
    "dns-valid", "dns-nxdomain", "dns-mixed", "dns-multi", "api-normal", "api-auth-fail", "ping", "tcp-refused",
    "iperf-tcp", "iperf-udp", "frag-udp", "mixed-light",
}
SAFE_ARGUMENT = re.compile(r"^[A-Za-z0-9._-]+$")
SAFE_ID = re.compile(r"^[A-Z0-9][A-Z0-9-]{2,47}$")
PCAP_REJECTION_BYTES = 1_945_600_000


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_and_validate(
    matrix_path: Path,
    feature_schema_path: Path,
    storage_path: Path | None = None,
) -> tuple[dict, dict]:
    matrix = json.loads(matrix_path.read_text(encoding="utf-8"))
    feature_schema = json.loads(feature_schema_path.read_text(encoding="utf-8"))
    errors: list[str] = []

    if matrix.get("schema_version") != matrix_path.stem:
        errors.append("schema_version de matriz no coincide con el nombre del archivo")
    if matrix.get("feature_schema") != feature_schema.get("schema_version"):
        errors.append("feature_schema no coincide")
    repetitions = matrix.get("default_repetitions")
    if not isinstance(repetitions, int) or isinstance(repetitions, bool) or repetitions != 5:
        errors.append(f"{matrix_path.stem} requiere exactamente 5 repeticiones por perfil")
    expected_partitions = {
        "1": "train", "2": "train", "3": "train",
        "4": "validation", "5": "test",
    }
    if matrix.get("partition_by_repetition") != expected_partitions:
        errors.append("la partición fija debe ser R01-R03 train, R04 validation y R05 test")
    if matrix.get("warmup_seconds", 0) < 60:
        errors.append("warm-up oficial debe ser al menos 60 s")

    feature_names = {item["name"] for item in feature_schema.get("features", [])}
    expected_feature_count = 28 if feature_schema.get("schema_version") == "multilayer-v2" else 14
    if len(feature_names) != expected_feature_count:
        errors.append(f"el esquema debe contener exactamente {expected_feature_count} features y contiene {len(feature_names)}")
    covered: set[str] = set()
    seen_ids: set[str] = set()
    total_bytes = 0
    profiles = matrix.get("profiles", [])
    if not profiles:
        errors.append("la matriz no contiene perfiles")
    for index, profile in enumerate(profiles):
        prefix = f"profiles[{index}]"
        profile_id = profile.get("id", "")
        if not SAFE_ID.fullmatch(profile_id):
            errors.append(f"{prefix}: id inválido")
        if profile_id in seen_ids:
            errors.append(f"{prefix}: id duplicado {profile_id}")
        seen_ids.add(profile_id)
        if profile.get("scenario") not in ALLOWED_SCENARIOS:
            errors.append(f"{prefix}: escenario no permitido")
        if any(not isinstance(arg, str) or not SAFE_ARGUMENT.fullmatch(arg) for arg in profile.get("args", [])):
            errors.append(f"{prefix}: argumento inseguro")
        estimated = profile.get("estimated_pcap_bytes")
        if not isinstance(estimated, int) or estimated <= 0 or estimated >= PCAP_REJECTION_BYTES:
            errors.append(f"{prefix}: estimación PCAP inválida")
        else:
            total_bytes += estimated * repetitions
        coverage = set(profile.get("feature_coverage", []))
        unknown = coverage - feature_names
        if unknown:
            errors.append(f"{prefix}: features desconocidas {sorted(unknown)}")
        covered.update(coverage)

    missing_coverage = sorted(feature_names - covered)
    if missing_coverage:
        errors.append(f"features sin cobertura declarada: {missing_coverage}")
    if errors:
        raise ValueError("\n".join(errors))

    selected_storage = (storage_path or matrix_path).resolve()
    try:
        free_bytes = shutil.disk_usage(selected_storage).free
        storage_path_exists = True
    except FileNotFoundError:
        free_bytes = 0
        storage_path_exists = False
    reserve_value = matrix.get("minimum_free_after_plan_bytes")
    if not isinstance(reserve_value, int) or isinstance(reserve_value, bool) or reserve_value < 20 * 1024**3:
        raise ValueError("la reserva de almacenamiento debe ser al menos 20 GiB")
    reserve = reserve_value
    report = {
        "schema_version": matrix["schema_version"],
        "matrix_sha256": sha256(matrix_path),
        "profiles": len(profiles),
        "repetitions_per_profile": repetitions,
        "partition_by_repetition": matrix["partition_by_repetition"],
        "planned_campaigns": len(profiles) * repetitions,
        "estimated_pcap_bytes": total_bytes,
        "required_with_reserve_bytes": total_bytes + reserve,
        "minimum_free_after_plan_bytes": reserve,
        "estimated_free_after_plan_bytes": free_bytes - total_bytes,
        "local_free_bytes": free_bytes,
        "storage_path": str(selected_storage),
        "storage_path_exists": storage_path_exists,
        "storage_gate_pass": free_bytes >= total_bytes + reserve,
        "feature_coverage": sorted(covered),
        "known_gaps": matrix.get("known_gaps", []),
    }
    return matrix, report


def parse_args() -> argparse.Namespace:
    repo = Path(__file__).resolve().parents[2]
    parser = argparse.ArgumentParser()
    parser.add_argument("--matrix", type=Path, default=repo / "configs/campaigns/f1-normal-v2.json")
    parser.add_argument("--feature-schema", type=Path, default=repo / "configs/features/multilayer-v1.json")
    parser.add_argument(
        "--storage-path",
        type=Path,
        default=Path(os.environ.get("PPI_ARTIFACTS_ROOT", repo / "artifacts")),
    )
    parser.add_argument("--require-storage", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    _, report = load_and_validate(args.matrix, args.feature_schema, args.storage_path)
    print(json.dumps(report, indent=2, sort_keys=True))
    if args.require_storage and not report["storage_gate_pass"]:
        return 3
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
