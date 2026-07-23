#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

from validate_matrix import load_and_validate


REPO = Path(__file__).resolve().parents[2]
DEFAULT_MATRIX = REPO / "configs/campaigns/f1-normal-v2.json"
DEFAULT_FEATURE_SCHEMA = REPO / "configs/features/multilayer-v1.json"
STORAGE_CONTRACT = REPO / "configs/storage/evidence-v1.json"
OFFICIAL_PRE_CAPTURE_QUIET_SECONDS = 70


def git(*args: str) -> str:
    return subprocess.check_output(["git", "-C", str(REPO), *args], text=True).strip()


def write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    temporary = path.with_suffix(".tmp")
    temporary.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    os.chmod(temporary, 0o600)
    temporary.replace(path)


def selected_artifacts_root() -> Path:
    raw = os.environ.get("PPI_ARTIFACTS_ROOT", str(REPO / "artifacts"))
    if not Path(raw).is_absolute():
        raise SystemExit("ERROR: PPI_ARTIFACTS_ROOT debe ser una ruta absoluta")
    return Path(raw).resolve()


def inspect_official_storage(artifacts_root: Path) -> dict:
    contract = json.loads(STORAGE_CONTRACT.read_text(encoding="utf-8"))
    expected_root = Path(contract["artifacts_root"])
    mountpoint = Path(contract["mountpoint"])
    marker_path = mountpoint / contract["marker"]
    marker_valid = False
    if marker_path.is_file():
        try:
            marker = json.loads(marker_path.read_text(encoding="utf-8"))
            marker_valid = (
                marker.get("schema_version") == contract["schema_version"]
                and marker.get("mountpoint") == str(mountpoint)
                and marker.get("artifacts_root") == str(expected_root)
                and marker.get("filesystem") == contract["filesystem"]
            )
        except (OSError, json.JSONDecodeError):
            marker_valid = False
    report = {
        "expected_artifacts_root": str(expected_root),
        "selected_artifacts_root": str(artifacts_root),
        "artifacts_root_match": artifacts_root == expected_root,
        "artifacts_root_is_directory": artifacts_root.is_dir(),
        "mountpoint": str(mountpoint),
        "mountpoint_is_mount": os.path.ismount(mountpoint),
        "marker_path": str(marker_path),
        "marker_valid": marker_valid,
    }
    report["gate_pass"] = all(
        report[field]
        for field in (
            "artifacts_root_match",
            "artifacts_root_is_directory",
            "mountpoint_is_mount",
            "marker_valid",
        )
    )
    return report


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Ejecuta exactamente un perfil versionado de la matriz F1 normal."
    )
    parser.add_argument("--profile", required=True, help="ID exacto del perfil")
    parser.add_argument("--repetition", type=int, required=True, help="Repetición 1..N")
    parser.add_argument("--matrix", type=Path, default=DEFAULT_MATRIX)
    parser.add_argument("--feature-schema", type=Path, default=DEFAULT_FEATURE_SCHEMA)
    parser.add_argument("--pilot", action="store_true", help="Marca propósito calibration y omite el gate global")
    parser.add_argument("--no-cooldown", action="store_true", help="Solo permitido con --pilot")
    parser.add_argument("--dry-run", action="store_true", help="Valida e imprime el plan sin ejecutar")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    artifacts_root = selected_artifacts_root()
    matrix, matrix_report = load_and_validate(args.matrix, args.feature_schema, artifacts_root)
    official_storage = inspect_official_storage(artifacts_root)
    profiles = {profile["id"]: profile for profile in matrix["profiles"]}
    if args.profile not in profiles:
        raise SystemExit(f"ERROR: perfil inexistente: {args.profile}")
    if not 1 <= args.repetition <= matrix["default_repetitions"]:
        raise SystemExit(
            f"ERROR: repetición fuera de rango 1..{matrix['default_repetitions']}"
        )
    if args.no_cooldown and not args.pilot:
        raise SystemExit("ERROR: --no-cooldown solo se permite en un piloto")
    if not args.pilot and (
        args.matrix.resolve() != DEFAULT_MATRIX.resolve()
        or args.feature_schema.resolve() != DEFAULT_FEATURE_SCHEMA.resolve()
    ):
        raise SystemExit("ERROR: una campaña oficial solo admite la matriz y esquema versionados por defecto")

    profile = profiles[args.profile]
    scenario_args_sha256 = hashlib.sha256(
        json.dumps(profile["args"], ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    ).hexdigest()
    prefix = "CAL-G6" if args.pilot else "F1N"
    campaign_id = f"{prefix}-{args.profile}-R{args.repetition:02d}"
    purpose = "calibration" if args.pilot else "experiment"
    partition = "excluded_calibration" if args.pilot else matrix["partition_by_repetition"][str(args.repetition)]
    plan = {
        "campaign_id": campaign_id,
        "purpose": purpose,
        "partition": partition,
        "profile": profile,
        "repetition": args.repetition,
        "matrix_sha256": matrix_report["matrix_sha256"],
        "scenario_args_sha256": scenario_args_sha256,
        "matrix_storage_gate_pass": matrix_report["storage_gate_pass"],
        "artifacts_root": str(artifacts_root),
        "official_storage": official_storage,
        "git_commit": git("rev-parse", "HEAD"),
        "warmup_seconds": matrix["warmup_seconds"],
        "settle_seconds": matrix["settle_seconds"],
        "cooldown_seconds": 0 if args.no_cooldown else matrix["cooldown_seconds"],
        "pre_capture_quiet_seconds": 0 if args.pilot else OFFICIAL_PRE_CAPTURE_QUIET_SECONDS,
    }
    print(json.dumps(plan, indent=2, sort_keys=True), flush=True)
    if args.dry_run:
        return 0

    if git("status", "--porcelain"):
        raise SystemExit("ERROR: el árbol Git debe estar limpio para generar evidencia")
    if not args.pilot and not official_storage["gate_pass"]:
        raise SystemExit(
            "ERROR: una campaña oficial exige el volumen identificado y montado en "
            f"{official_storage['expected_artifacts_root']}"
        )
    if not args.pilot and not matrix_report["storage_gate_pass"]:
        raise SystemExit(
            "ERROR: el almacenamiento no soporta la matriz oficial y su reserva; "
            "amplíe/monte almacenamiento o use --pilot para calibración"
        )

    campaign_dir = artifacts_root / "campaigns" / campaign_id
    feature_dir = artifacts_root / "features" / campaign_id
    ledger_path = artifacts_root / "g6-ledger" / f"{campaign_id}.json"
    if campaign_dir.exists() or feature_dir.exists() or ledger_path.exists():
        raise SystemExit(f"ERROR: el ID ya posee artefactos: {campaign_id}")

    quiet_seconds = plan["pre_capture_quiet_seconds"]
    if quiet_seconds:
        print(
            f"Quietud previa a captura: {quiet_seconds} s para drenar eventos EVE diferidos",
            flush=True,
        )
        time.sleep(quiet_seconds)
        if git("status", "--porcelain"):
            raise SystemExit("ERROR: el árbol Git cambió durante la quietud previa")

    ledger = {
        **plan,
        "schema_version": "f1-run-ledger-v1",
        "status": "running",
        "started_at": datetime.now().astimezone().isoformat(),
    }
    write_json(ledger_path, ledger)

    env = os.environ.copy()
    env.update(
        {
            "PPI_CAMPAIGN_PURPOSE": purpose,
            "PPI_CAMPAIGN_WARMUP_SECONDS": str(matrix["warmup_seconds"]),
            "PPI_CAMPAIGN_SETTLE_SECONDS": str(matrix["settle_seconds"]),
            "PPI_CAMPAIGN_MATRIX_SHA256": matrix_report["matrix_sha256"],
            "PPI_CAMPAIGN_MATRIX_PROFILE": args.profile,
            "PPI_CAMPAIGN_MATRIX_REPETITION": str(args.repetition),
            "PPI_CAMPAIGN_ARGS_SHA256": scenario_args_sha256,
            "PPI_CAMPAIGN_PARTITION": partition,
            "PPI_ARTIFACTS_ROOT": str(artifacts_root),
        }
    )
    run_command = [
        str(REPO / "scripts/campaign/run-f1.sh"),
        campaign_id,
        profile["scenario"],
        *profile["args"],
    ]
    try:
        subprocess.run(run_command, cwd=REPO, env=env, check=True)
        subprocess.run(
            [str(REPO / "scripts/features/extract_campaign.sh"), campaign_id],
            cwd=REPO,
            env=env,
            check=True,
        )
        report_path = feature_dir / "extraction-report.json"
        extraction_report = json.loads(report_path.read_text(encoding="utf-8"))
        if extraction_report.get("rows", 0) < 1:
            raise RuntimeError("el extractor no produjo filas")
        if not args.pilot and extraction_report.get("eligible_training_rows", 0) < 1:
            raise RuntimeError("la campaña oficial no produjo filas elegibles para entrenamiento")
    except (subprocess.CalledProcessError, RuntimeError, KeyboardInterrupt) as exc:
        ledger.update(
            {
                "status": "failed",
                "ended_at": datetime.now().astimezone().isoformat(),
                "error": str(exc),
            }
        )
        write_json(ledger_path, ledger)
        raise SystemExit(f"ERROR: falló {campaign_id}: {exc}") from exc

    ledger.update(
        {
            "status": "completed",
            "ended_at": datetime.now().astimezone().isoformat(),
            "feature_rows": extraction_report["rows"],
            "eligible_training_rows": extraction_report["eligible_training_rows"],
            "output_sha256": extraction_report["output_sha256"],
        }
    )
    write_json(ledger_path, ledger)
    cooldown = plan["cooldown_seconds"]
    if cooldown:
        print(f"Cooldown controlado: {cooldown} s", flush=True)
        time.sleep(cooldown)
    print(f"Perfil completado: {campaign_id}", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
