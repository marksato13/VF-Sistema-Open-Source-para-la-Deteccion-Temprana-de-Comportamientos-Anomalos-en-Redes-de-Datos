#!/usr/bin/env python3
"""Audita y ensambla F1 sin admitir calibraciones ni evidencia incompleta."""

from __future__ import annotations

import argparse
import csv
import hashlib
import ipaddress
import json
import math
import os
import re
import shutil
import subprocess
import tempfile
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any


REPO = Path(__file__).resolve().parents[2]
MATRIX_RELATIVE = Path("configs/campaigns/f1-normal-v1.json")
SCHEMA_RELATIVE = Path("configs/features/multilayer-v1.json")
CHECKSUM_LINE = re.compile(r"^([a-f0-9]{64}) ([ *])(.+)$")
COMMIT_ID = re.compile(r"^[a-f0-9]{40}$")
ENTITY_NETWORK = ipaddress.ip_network("10.20.0.0/24")

METADATA_COLUMNS = [
    "campaign_id",
    "entity_ip",
    "window_end_utc",
    "history_coverage_s",
    "eligible_training",
    "packet_count_10s",
    "flow_attempt_count_30s",
    "syn_count_10s",
    "http_request_count_60s",
    "dns_query_count_60s",
]


class GateError(ValueError):
    def __init__(self, gate: str, message: str):
        super().__init__(f"{gate}: {message}")
        self.gate = gate
        self.message = message


@dataclass(frozen=True)
class Contract:
    repo: Path
    matrix: dict[str, Any]
    matrix_sha256: str
    schema: dict[str, Any]
    schema_sha256: str
    feature_names: tuple[str, ...]


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def sha256_path(path: Path) -> str:
    return sha256_bytes(path.read_bytes())


def load_json(path: Path, gate: str) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise GateError(gate, f"JSON ilegible {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise GateError(gate, f"se esperaba un objeto JSON en {path}")
    return value


def load_contract(repo: Path) -> Contract:
    matrix_path = repo / MATRIX_RELATIVE
    schema_path = repo / SCHEMA_RELATIVE
    matrix = load_json(matrix_path, "GATE-CONTRATO")
    schema = load_json(schema_path, "GATE-CONTRATO")
    feature_names = tuple(item["name"] for item in schema.get("features", []))
    if len(feature_names) != 14 or len(set(feature_names)) != 14:
        raise GateError("GATE-CONTRATO", "el esquema no contiene 14 features únicas")
    if matrix.get("feature_schema") != schema.get("schema_version"):
        raise GateError("GATE-CONTRATO", "la matriz no referencia el esquema activo")
    return Contract(
        repo=repo,
        matrix=matrix,
        matrix_sha256=sha256_path(matrix_path),
        schema=schema,
        schema_sha256=sha256_path(schema_path),
        feature_names=feature_names,
    )


def verify_checksum_bundle(directory: Path) -> dict[str, str]:
    checksum_path = directory / "SHA256SUMS"
    try:
        lines = checksum_path.read_text(encoding="utf-8").splitlines()
    except OSError as exc:
        raise GateError("GATE-INTEGRIDAD", f"falta SHA256SUMS en {directory}") from exc
    if not lines:
        raise GateError("GATE-INTEGRIDAD", f"SHA256SUMS vacío en {directory}")

    declared: dict[str, str] = {}
    root = directory.resolve()
    for line_number, line in enumerate(lines, start=1):
        match = CHECKSUM_LINE.fullmatch(line)
        if not match:
            raise GateError("GATE-INTEGRIDAD", f"línea SHA inválida {line_number} en {directory}")
        expected, _, raw_name = match.groups()
        relative = Path(raw_name)
        if relative.is_absolute() or ".." in relative.parts:
            raise GateError("GATE-INTEGRIDAD", f"ruta SHA fuera del paquete: {raw_name}")
        normalized = str(relative)
        if normalized in declared:
            raise GateError("GATE-INTEGRIDAD", f"ruta SHA duplicada: {normalized}")
        target = (directory / relative).resolve()
        try:
            target.relative_to(root)
        except ValueError as exc:
            raise GateError("GATE-INTEGRIDAD", f"ruta SHA escapa del paquete: {raw_name}") from exc
        if not target.is_file() or target.is_symlink():
            raise GateError("GATE-INTEGRIDAD", f"archivo declarado ausente/no regular: {raw_name}")
        actual = sha256_path(target)
        if actual != expected:
            raise GateError("GATE-INTEGRIDAD", f"SHA no coincide: {raw_name}")
        declared[normalized] = expected

    actual_files = {
        str(path.relative_to(directory))
        for path in directory.rglob("*")
        if path.is_file() and not path.is_symlink() and path != checksum_path
    }
    if set(declared) != actual_files:
        missing = sorted(actual_files - set(declared))
        stale = sorted(set(declared) - actual_files)
        raise GateError(
            "GATE-INTEGRIDAD",
            f"cobertura SHA no exacta; no declarados={missing}, inexistentes={stale}",
        )
    return declared


def git_blob(repo: Path, commit: str, relative_path: Path) -> bytes:
    if not COMMIT_ID.fullmatch(commit):
        raise GateError("GATE-GIT", f"commit inválido: {commit!r}")
    probe = subprocess.run(
        ["git", "-C", str(repo), "cat-file", "-e", f"{commit}^{{commit}}"],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        check=False,
    )
    if probe.returncode != 0:
        raise GateError("GATE-GIT", f"commit inexistente: {commit}")
    result = subprocess.run(
        ["git", "-C", str(repo), "show", f"{commit}:{relative_path.as_posix()}"],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    if result.returncode != 0:
        raise GateError(
            "GATE-GIT",
            f"{relative_path} no existe en {commit}: {result.stderr.decode(errors='replace').strip()}",
        )
    return result.stdout


def require_equal(left: Any, right: Any, gate: str, description: str) -> None:
    if left != right:
        raise GateError(gate, f"{description}: {left!r} != {right!r}")


def evidence_gate(manifest: dict[str, Any]) -> None:
    require_equal(manifest.get("status"), "completed", "GATE-INTEGRIDAD", "estado manifiesto")
    evidence = manifest.get("evidence")
    if not isinstance(evidence, dict):
        raise GateError("GATE-INTEGRIDAD", "evidence ausente")
    checks = {
        "complete": True,
        "pcap_validation_failures": 0,
        "pcap_kernel_drops": 0,
        "pcap_transfer_verified": True,
        "pcap_limit_reached": False,
    }
    for field, expected in checks.items():
        require_equal(evidence.get(field), expected, "GATE-INTEGRIDAD", f"evidence.{field}")
    require_equal(
        evidence.get("pcap_captured_packets"),
        evidence.get("pcap_parsed_packets"),
        "GATE-INTEGRIDAD",
        "paquetes capturados/parseados",
    )
    require_equal(
        evidence.get("eve_slice_records"),
        evidence.get("expected_eve_records"),
        "GATE-INTEGRIDAD",
        "registros EVE extraídos/esperados",
    )
    if not isinstance(evidence.get("pcap_total_bytes"), int) or evidence["pcap_total_bytes"] <= 0:
        raise GateError("GATE-INTEGRIDAD", "pcap_total_bytes inválido")


def read_feature_rows(
    csv_path: Path,
    campaign_id: str,
    contract: Contract,
) -> list[dict[str, str]]:
    expected_header = [*METADATA_COLUMNS, *contract.feature_names]
    try:
        with csv_path.open(newline="", encoding="utf-8") as handle:
            reader = csv.DictReader(handle)
            if reader.fieldnames != expected_header:
                raise GateError("GATE-CSV", "orden/columnas del CSV no coincide con multilayer-v1")
            rows = list(reader)
    except OSError as exc:
        raise GateError("GATE-CSV", f"CSV ilegible: {csv_path}") from exc
    if not rows:
        raise GateError("GATE-CSV", "CSV sin filas")

    ratio_features = {
        item["name"] for item in contract.schema["features"] if item.get("unit") == "ratio"
    }
    row_keys: set[tuple[str, str]] = set()
    for number, row in enumerate(rows, start=2):
        require_equal(row["campaign_id"], campaign_id, "GATE-CSV", f"campaign_id fila {number}")
        require_equal(row["eligible_training"], "True", "GATE-CSV", f"elegibilidad fila {number}")
        try:
            if ipaddress.ip_address(row["entity_ip"]) not in ENTITY_NETWORK:
                raise GateError("GATE-CSV", f"entity_ip fuera de PPI-LAN en fila {number}")
            coverage = float(row["history_coverage_s"])
            window_end = datetime.fromisoformat(row["window_end_utc"].replace("Z", "+00:00"))
        except (ValueError, TypeError) as exc:
            if isinstance(exc, GateError):
                raise
            raise GateError("GATE-CSV", f"metadata inválida en fila {number}: {exc}") from exc
        if coverage < 60:
            raise GateError("GATE-CSV", f"historia menor de 60 s en fila {number}")
        if window_end.tzinfo is None:
            raise GateError("GATE-CSV", f"timestamp sin zona horaria en fila {number}")
        key = (row["entity_ip"], row["window_end_utc"])
        if key in row_keys:
            raise GateError("GATE-DUPLICADOS", f"ventana duplicada en fila {number}: {key}")
        row_keys.add(key)
        for feature in contract.feature_names:
            try:
                value = float(row[feature])
            except (TypeError, ValueError) as exc:
                raise GateError("GATE-CSV", f"{feature} no numérica en fila {number}") from exc
            if not math.isfinite(value) or value < 0:
                raise GateError("GATE-CSV", f"{feature} fuera de dominio en fila {number}")
            if feature in ratio_features and value > 1:
                raise GateError("GATE-CSV", f"ratio {feature}>1 en fila {number}")
    return rows


def validate_candidate(
    ledger_path: Path,
    campaigns_dir: Path,
    features_dir: Path,
    contract: Contract,
) -> dict[str, Any]:
    ledger = load_json(ledger_path, "GATE-CRUCE")
    campaign_id = ledger.get("campaign_id")
    if not isinstance(campaign_id, str) or ledger_path.stem != campaign_id:
        raise GateError("GATE-CRUCE", "campaign_id no coincide con el nombre del ledger")
    require_equal(ledger.get("purpose"), "experiment", "GATE-ANTICALIBRACION", "purpose ledger")
    require_equal(ledger.get("status"), "completed", "GATE-CRUCE", "estado ledger")

    profile_record = ledger.get("profile")
    if not isinstance(profile_record, dict):
        raise GateError("GATE-MATRIZ", "perfil ausente en ledger")
    profile_id = profile_record.get("id")
    profiles = {item["id"]: item for item in contract.matrix["profiles"]}
    if profile_id not in profiles:
        raise GateError("GATE-MATRIZ", f"perfil desconocido: {profile_id}")
    expected_profile = profiles[profile_id]
    for field in ("id", "scenario", "args", "estimated_pcap_bytes", "stratum", "feature_coverage"):
        require_equal(profile_record.get(field), expected_profile.get(field), "GATE-MATRIZ", f"perfil.{field}")

    repetition = ledger.get("repetition")
    if not isinstance(repetition, int) or not 1 <= repetition <= contract.matrix["default_repetitions"]:
        raise GateError("GATE-MATRIZ", f"repetición inválida: {repetition}")
    expected_partition = contract.matrix["partition_by_repetition"][str(repetition)]
    expected_args_sha256 = sha256_bytes(
        json.dumps(expected_profile["args"], ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    )
    require_equal(ledger.get("partition"), expected_partition, "GATE-ANTICALIBRACION", "partición ledger")
    expected_id = f"F1N-{profile_id}-R{repetition:02d}"
    require_equal(campaign_id, expected_id, "GATE-MATRIZ", "ID oficial")

    campaign_dir = campaigns_dir / campaign_id
    feature_dir = features_dir / campaign_id
    verify_checksum_bundle(campaign_dir)
    verify_checksum_bundle(feature_dir)
    manifest = load_json(campaign_dir / "manifest.json", "GATE-INTEGRIDAD")
    report = load_json(feature_dir / "extraction-report.json", "GATE-INTEGRIDAD")
    deltas = load_json(campaign_dir / "deltas.json", "GATE-INTEGRIDAD")
    evidence_gate(manifest)

    evidence = manifest["evidence"]
    for field, expected in {
        "sensor_sampler_stderr_bytes": 0,
        "pcap_remote_file_count": evidence.get("pcap_file_count"),
        "pcap_remote_total_bytes": evidence.get("pcap_total_bytes"),
    }.items():
        require_equal(evidence.get(field), expected, "GATE-INTEGRIDAD", f"evidence.{field}")
    if not isinstance(evidence.get("sensor_sample_rows"), int) or evidence["sensor_sample_rows"] < 1:
        raise GateError("GATE-INTEGRIDAD", "no existen muestras válidas del Sensor")
    require_equal(deltas.get("counter_reset_detected"), False, "GATE-INTEGRIDAD", "reset de contadores")
    for field in ("kernel_drops", "kernel_ifdrops"):
        require_equal(
            deltas.get("capture", {}).get(field), 0, "GATE-INTEGRIDAD", f"Suricata capture.{field}"
        )
    require_equal(deltas.get("decoder_invalid"), 0, "GATE-INTEGRIDAD", "decoder_invalid")
    require_equal(deltas.get("alert_queue_overflow"), 0, "GATE-INTEGRIDAD", "alert_queue_overflow")
    require_equal(
        deltas.get("eve", {}).get("slice_matches_checkpoint"),
        True,
        "GATE-INTEGRIDAD",
        "checkpoint EVE",
    )

    require_equal(manifest.get("campaign_id"), campaign_id, "GATE-CRUCE", "campaign_id manifiesto")
    require_equal(manifest.get("purpose"), ledger["purpose"], "GATE-CRUCE", "purpose ledger/manifiesto")
    require_equal(manifest.get("partition"), expected_partition, "GATE-ANTICALIBRACION", "partición manifiesto")
    require_equal(manifest.get("scenario"), expected_profile["scenario"], "GATE-MATRIZ", "escenario manifiesto")
    require_equal(manifest.get("warmup_seconds"), contract.matrix["warmup_seconds"], "GATE-MATRIZ", "warm-up")
    require_equal(manifest.get("settle_seconds"), contract.matrix["settle_seconds"], "GATE-MATRIZ", "settle")

    campaign_plan = manifest.get("campaign_plan")
    if not isinstance(campaign_plan, dict):
        raise GateError("GATE-MATRIZ", "campaign_plan ausente")
    require_equal(campaign_plan.get("profile"), profile_id, "GATE-MATRIZ", "perfil manifiesto")
    require_equal(campaign_plan.get("repetition"), repetition, "GATE-MATRIZ", "repetición manifiesto")
    require_equal(
        campaign_plan.get("scenario_args_sha256"),
        expected_args_sha256,
        "GATE-MATRIZ",
        "SHA de argumentos manifiesto",
    )
    require_equal(
        ledger.get("scenario_args_sha256"),
        expected_args_sha256,
        "GATE-MATRIZ",
        "SHA de argumentos ledger",
    )
    require_equal(
        campaign_plan.get("matrix_sha256"), contract.matrix_sha256, "GATE-MATRIZ", "SHA matriz manifiesto"
    )
    require_equal(ledger.get("matrix_sha256"), contract.matrix_sha256, "GATE-MATRIZ", "SHA matriz ledger")

    git_record = manifest.get("git")
    if not isinstance(git_record, dict):
        raise GateError("GATE-GIT", "registro Git ausente")
    require_equal(git_record.get("dirty"), False, "GATE-GIT", "git.dirty")
    commit = git_record.get("commit", "")
    require_equal(ledger.get("git_commit"), commit, "GATE-CRUCE", "commit ledger/manifiesto")
    matrix_at_commit = git_blob(contract.repo, commit, MATRIX_RELATIVE)
    schema_at_commit = git_blob(contract.repo, commit, SCHEMA_RELATIVE)
    require_equal(sha256_bytes(matrix_at_commit), contract.matrix_sha256, "GATE-GIT", "matriz en commit")
    require_equal(sha256_bytes(schema_at_commit), contract.schema_sha256, "GATE-GIT", "esquema en commit")

    require_equal(report.get("campaign_id"), campaign_id, "GATE-CRUCE", "campaign_id reporte")
    require_equal(report.get("schema_version"), contract.schema["schema_version"], "GATE-CSV", "schema reporte")
    if not isinstance(report.get("rows"), int) or report["rows"] < 1:
        raise GateError("GATE-CSV", "reporte sin filas")
    require_equal(
        report.get("eligible_training_rows"), report["rows"], "GATE-CSV", "filas elegibles/totales"
    )
    schema_input = report.get("inputs", {}).get("schema", {})
    require_equal(schema_input.get("sha256"), contract.schema_sha256, "GATE-GIT", "SHA esquema reporte")

    csv_path = feature_dir / "multilayer-v1.csv"
    csv_sha = sha256_path(csv_path)
    require_equal(report.get("output_sha256"), csv_sha, "GATE-INTEGRIDAD", "SHA CSV reporte")
    require_equal(ledger.get("output_sha256"), csv_sha, "GATE-CRUCE", "SHA CSV ledger")
    rows = read_feature_rows(csv_path, campaign_id, contract)
    require_equal(len(rows), report["rows"], "GATE-CSV", "conteo filas CSV/reporte")
    require_equal(ledger.get("feature_rows"), len(rows), "GATE-CRUCE", "conteo filas ledger/CSV")
    require_equal(
        ledger.get("eligible_training_rows"), len(rows), "GATE-CRUCE", "elegibles ledger/CSV"
    )

    eve_path = campaign_dir / "eve-slice.jsonl"
    require_equal(
        report.get("inputs", {}).get("eve", {}).get("sha256"),
        sha256_path(eve_path),
        "GATE-INTEGRIDAD",
        "SHA EVE reporte",
    )
    actual_pcaps = sorted((campaign_dir / "pcap").glob("capture.pcap*"))
    reported_pcaps = report.get("inputs", {}).get("pcap", [])
    actual_pcap_hashes = sorted(sha256_path(path) for path in actual_pcaps)
    report_pcap_hashes = sorted(item.get("sha256") for item in reported_pcaps if isinstance(item, dict))
    require_equal(report_pcap_hashes, actual_pcap_hashes, "GATE-INTEGRIDAD", "SHA PCAP reporte")
    actual_pcap_bytes = sum(path.stat().st_size for path in actual_pcaps)
    require_equal(
        actual_pcap_bytes,
        manifest["evidence"]["pcap_total_bytes"],
        "GATE-INTEGRIDAD",
        "bytes PCAP manifiesto/disco",
    )

    warnings: list[str] = []
    estimated = expected_profile["estimated_pcap_bytes"]
    if actual_pcap_bytes > estimated:
        warnings.append(f"PCAP real supera estimación: {actual_pcap_bytes}>{estimated}")

    return {
        "campaign_id": campaign_id,
        "cell": [profile_id, repetition],
        "profile_id": profile_id,
        "repetition": repetition,
        "partition": expected_partition,
        "git_commit": commit,
        "matrix_sha256": contract.matrix_sha256,
        "csv_sha256": csv_sha,
        "pcap_bytes": actual_pcap_bytes,
        "rows": rows,
        "warnings": warnings,
    }


def expected_cells(contract: Contract) -> set[tuple[str, int]]:
    repetitions = contract.matrix["default_repetitions"]
    return {(profile["id"], repetition) for profile in contract.matrix["profiles"] for repetition in range(1, repetitions + 1)}


def audit_repository(
    contract: Contract,
    campaigns_dir: Path,
    features_dir: Path,
    ledgers_dir: Path,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    accepted: list[dict[str, Any]] = []
    excluded: list[dict[str, str]] = []
    invalid: list[dict[str, str]] = []
    claimed_cells: dict[tuple[str, int], str] = {}
    output_hashes: dict[str, str] = {}

    for ledger_path in sorted(ledgers_dir.glob("*.json")) if ledgers_dir.exists() else []:
        try:
            preview = load_json(ledger_path, "GATE-CRUCE")
            if preview.get("purpose") != "experiment":
                excluded.append({"campaign_id": str(preview.get("campaign_id", ledger_path.stem)), "reason": "not_experiment"})
                continue
            candidate = validate_candidate(ledger_path, campaigns_dir, features_dir, contract)
            cell = tuple(candidate["cell"])
            if cell in claimed_cells:
                raise GateError(
                    "GATE-DUPLICADOS",
                    f"celda {cell} reclamada por {claimed_cells[cell]} y {candidate['campaign_id']}",
                )
            if candidate["csv_sha256"] in output_hashes:
                raise GateError(
                    "GATE-DUPLICADOS",
                    f"CSV repetido entre {output_hashes[candidate['csv_sha256']]} y {candidate['campaign_id']}",
                )
            claimed_cells[cell] = candidate["campaign_id"]
            output_hashes[candidate["csv_sha256"]] = candidate["campaign_id"]
            accepted.append(candidate)
        except GateError as exc:
            invalid.append({"ledger": ledger_path.name, "gate": exc.gate, "reason": exc.message})

    expected = expected_cells(contract)
    accepted_cells = {tuple(candidate["cell"]) for candidate in accepted}
    missing = sorted(expected - accepted_cells)
    current_status = subprocess.check_output(
        ["git", "-C", str(contract.repo), "status", "--porcelain"], text=True
    ).strip()
    current_commit = subprocess.check_output(
        ["git", "-C", str(contract.repo), "rev-parse", "HEAD"], text=True
    ).strip()
    fingerprints: dict[tuple[str, ...], str] = {}
    duplicate_vectors: list[dict[str, str]] = []
    for candidate in accepted:
        for row in candidate["rows"]:
            fingerprint = tuple(row[name] for name in contract.feature_names)
            previous = fingerprints.get(fingerprint)
            if previous and previous != candidate["campaign_id"] and len(duplicate_vectors) < 100:
                duplicate_vectors.append(
                    {"first_campaign": previous, "duplicate_campaign": candidate["campaign_id"]}
                )
            else:
                fingerprints[fingerprint] = candidate["campaign_id"]
    report = {
        "schema_version": "f1-dataset-audit-v1",
        "matrix_sha256": contract.matrix_sha256,
        "feature_schema_sha256": contract.schema_sha256,
        "expected_campaigns": len(expected),
        "accepted_campaigns": len(accepted),
        "excluded_campaigns": excluded,
        "invalid_campaigns": invalid,
        "accepted_cells": [
            {
                "campaign_id": candidate["campaign_id"],
                "profile_id": candidate["profile_id"],
                "repetition": candidate["repetition"],
                "partition": candidate["partition"],
            }
            for candidate in sorted(accepted, key=lambda item: item["campaign_id"])
        ],
        "campaign_warnings": [
            {"campaign_id": candidate["campaign_id"], "warnings": candidate["warnings"]}
            for candidate in accepted
            if candidate["warnings"]
        ],
        "missing_cells": [{"profile_id": profile, "repetition": repetition} for profile, repetition in missing],
        "duplicate_feature_vectors": duplicate_vectors,
        "current_git_dirty": bool(current_status),
        "assembler_git_commit": current_commit,
        "ready_to_build": not invalid and not missing and len(accepted) == len(expected) and not current_status,
    }
    return report, accepted


def build_dataset(
    output_dir: Path,
    report: dict[str, Any],
    accepted: list[dict[str, Any]],
    contract: Contract,
) -> dict[str, Any]:
    if not report["ready_to_build"]:
        raise GateError("GATE-COMPLETITUD", "la auditoría no autoriza construir el dataset")
    if output_dir.exists():
        raise GateError("GATE-SALIDA", f"el destino ya existe: {output_dir}")
    output_dir.parent.mkdir(parents=True, exist_ok=True)
    temporary = Path(tempfile.mkdtemp(prefix=".f1-normal-v1-", dir=output_dir.parent))
    try:
        fieldnames = ["partition", "profile_id", "repetition", *METADATA_COLUMNS]
        feature_names = list(contract.feature_names)
        fieldnames.extend(feature_names)
        split_counts: dict[str, int] = {}
        for partition in ("train", "validation", "test"):
            path = temporary / f"{partition}.csv"
            count = 0
            with path.open("w", newline="", encoding="utf-8") as handle:
                writer = csv.DictWriter(handle, fieldnames=fieldnames)
                writer.writeheader()
                for candidate in sorted(accepted, key=lambda item: item["campaign_id"]):
                    if candidate["partition"] != partition:
                        continue
                    for row in candidate["rows"]:
                        writer.writerow(
                            {
                                "partition": partition,
                                "profile_id": candidate["profile_id"],
                                "repetition": candidate["repetition"],
                                **row,
                            }
                        )
                        count += 1
            split_counts[partition] = count

        manifest = {
            **report,
            "schema_version": "f1-dataset-manifest-v1",
            "created_at": datetime.now().astimezone().isoformat(),
            "split_rows": split_counts,
            "source_campaigns": [
                {key: candidate[key] for key in ("campaign_id", "profile_id", "repetition", "partition", "git_commit", "csv_sha256", "pcap_bytes")}
                for candidate in sorted(accepted, key=lambda item: item["campaign_id"])
            ],
        }
        (temporary / "manifest.json").write_text(
            json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )
        checksum_lines = []
        for path in sorted(temporary.iterdir()):
            if path.name == "SHA256SUMS":
                continue
            checksum_lines.append(f"{sha256_path(path)}  {path.name}\n")
        (temporary / "SHA256SUMS").write_text("".join(checksum_lines), encoding="utf-8")
        temporary.rename(output_dir)
    except Exception:
        shutil.rmtree(temporary, ignore_errors=True)
        raise
    return manifest


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Audita o construye el dataset oficial F1 normal.")
    parser.add_argument("--repo", type=Path, default=REPO)
    parser.add_argument("--campaigns-dir", type=Path)
    parser.add_argument("--features-dir", type=Path)
    parser.add_argument("--ledgers-dir", type=Path)
    parser.add_argument("--output-dir", type=Path)
    parser.add_argument("--audit-only", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    repo = args.repo.resolve()
    contract = load_contract(repo)
    artifacts = repo / "artifacts"
    campaigns_dir = args.campaigns_dir or artifacts / "campaigns"
    features_dir = args.features_dir or artifacts / "features"
    ledgers_dir = args.ledgers_dir or artifacts / "g6-ledger"
    output_dir = args.output_dir or artifacts / "datasets/f1-normal-v1"
    report, accepted = audit_repository(contract, campaigns_dir, features_dir, ledgers_dir)
    if args.audit_only:
        print(json.dumps(report, indent=2, sort_keys=True))
        return 0
    try:
        manifest = build_dataset(output_dir, report, accepted, contract)
    except GateError as exc:
        print(json.dumps(report, indent=2, sort_keys=True))
        print(f"ERROR: {exc}", file=os.sys.stderr)
        return 3
    print(json.dumps(manifest, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
