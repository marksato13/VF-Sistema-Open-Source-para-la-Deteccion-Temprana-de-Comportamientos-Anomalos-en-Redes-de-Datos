from __future__ import annotations

import csv
import hashlib
import importlib.util
import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from copy import deepcopy
from pathlib import Path


SOURCE_REPO = Path(__file__).resolve().parents[1]
MODULE_PATH = SOURCE_REPO / "scripts/dataset/build_f1_dataset.py"
SPEC = importlib.util.spec_from_file_location("build_f1_dataset", MODULE_PATH)
assert SPEC and SPEC.loader
builder = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = builder
SPEC.loader.exec_module(builder)


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def rewrite_checksums(directory: Path) -> None:
    lines = []
    for path in sorted(directory.rglob("*")):
        if path.is_file() and path.name != "SHA256SUMS":
            lines.append(f"{sha256(path)}  {path.relative_to(directory)}\n")
    (directory / "SHA256SUMS").write_text("".join(lines), encoding="utf-8")


class DatasetBuilderFixture(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.repo = Path(self.temporary.name)
        (self.repo / "configs/campaigns").mkdir(parents=True)
        (self.repo / "configs/features").mkdir(parents=True)
        shutil.copy2(
            SOURCE_REPO / builder.MATRIX_RELATIVE,
            self.repo / builder.MATRIX_RELATIVE,
        )
        shutil.copy2(
            SOURCE_REPO / builder.SCHEMA_RELATIVE,
            self.repo / builder.SCHEMA_RELATIVE,
        )
        (self.repo / ".gitignore").write_text("artifacts/\n", encoding="utf-8")
        subprocess.run(["git", "init", "-q", str(self.repo)], check=True)
        subprocess.run(["git", "-C", str(self.repo), "config", "user.email", "fixture@example.invalid"], check=True)
        subprocess.run(["git", "-C", str(self.repo), "config", "user.name", "Fixture"], check=True)
        subprocess.run(["git", "-C", str(self.repo), "add", "."], check=True)
        subprocess.run(["git", "-C", str(self.repo), "commit", "-qm", "fixture"], check=True)
        self.commit = subprocess.check_output(
            ["git", "-C", str(self.repo), "rev-parse", "HEAD"], text=True
        ).strip()
        self.contract = builder.load_contract(self.repo)
        self.matrix = self.contract.matrix
        self.profile = deepcopy(self.matrix["profiles"][0])
        self.campaign_id = "F1N-DNS-VALID-10-R01"
        self.campaigns = self.repo / "artifacts/campaigns"
        self.features = self.repo / "artifacts/features"
        self.ledgers = self.repo / "artifacts/g6-ledger"
        self.campaign_dir = self.campaigns / self.campaign_id
        self.feature_dir = self.features / self.campaign_id
        self.ledger_path = self.ledgers / f"{self.campaign_id}.json"
        (self.campaign_dir / "pcap").mkdir(parents=True)
        self.feature_dir.mkdir(parents=True)
        self.ledgers.mkdir(parents=True)
        self._write_valid_fixture()

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def test_rejects_non_sequential_feature_order(self) -> None:
        schema_path = self.repo / builder.SCHEMA_RELATIVE
        schema = json.loads(schema_path.read_text(encoding="utf-8"))
        schema["features"][0]["order"] = 2
        schema_path.write_text(json.dumps(schema), encoding="utf-8")
        with self.assertRaisesRegex(builder.GateError, "exactamente 1..14"):
            builder.load_contract(self.repo)

    def test_duplicate_vector_report_preserves_total_when_truncated(self) -> None:
        row = {name: "0.00000000" for name in self.contract.feature_names}
        accepted = [
            {"campaign_id": "FIRST", "rows": [row]},
            {"campaign_id": "SECOND", "rows": [dict(row), dict(row), dict(row)]},
        ]
        reported, total = builder.find_cross_campaign_duplicate_vectors(
            accepted,
            self.contract.feature_names,
            report_limit=1,
        )
        self.assertEqual(total, 3)
        self.assertEqual(
            reported,
            [{"first_campaign": "FIRST", "duplicate_campaign": "SECOND"}],
        )

    def _write_json(self, path: Path, value: dict) -> None:
        path.write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8")

    def _write_valid_fixture(self) -> None:
        pcap = self.campaign_dir / "pcap/capture.pcap0"
        pcap.write_bytes(b"fixture-pcap")
        eve = self.campaign_dir / "eve-slice.jsonl"
        eve.write_text("", encoding="utf-8")
        manifest = {
            "campaign_id": self.campaign_id,
            "scenario": self.profile["scenario"],
            "purpose": "experiment",
            "partition": "train",
            "status": "completed",
            "git": {"commit": self.commit, "dirty": False},
            "campaign_plan": {
                "matrix_sha256": self.contract.matrix_sha256,
                "profile": self.profile["id"],
                "repetition": 1,
                "scenario_args_sha256": builder.sha256_bytes(
                    json.dumps(
                        self.profile["args"], ensure_ascii=False, separators=(",", ":")
                    ).encode("utf-8")
                ),
            },
            "warmup_seconds": 60,
            "settle_seconds": 9,
            "evidence": {
                "complete": True,
                "sensor_sample_rows": 60,
                "sensor_sampler_stderr_bytes": 0,
                "pcap_file_count": 1,
                "pcap_total_bytes": pcap.stat().st_size,
                "pcap_validation_failures": 0,
                "pcap_captured_packets": 1,
                "pcap_parsed_packets": 1,
                "pcap_kernel_drops": 0,
                "pcap_remote_file_count": 1,
                "pcap_remote_total_bytes": pcap.stat().st_size,
                "pcap_transfer_verified": True,
                "pcap_limit_reached": False,
                "eve_slice_records": 0,
                "expected_eve_records": 0,
            },
        }
        deltas = {
            "counter_reset_detected": False,
            "capture": {"kernel_drops": 0, "kernel_ifdrops": 0},
            "decoder_invalid": 0,
            "alert_queue_overflow": 0,
            "eve": {"slice_matches_checkpoint": True},
        }
        self._write_json(self.campaign_dir / "manifest.json", manifest)
        self._write_json(self.campaign_dir / "deltas.json", deltas)
        rewrite_checksums(self.campaign_dir)

        header = [*builder.METADATA_COLUMNS, *self.contract.feature_names]
        row = {
            "campaign_id": self.campaign_id,
            "entity_ip": "10.20.0.20",
            "window_end_utc": "2026-07-22T00:00:00+00:00",
            "history_coverage_s": "60.00000000",
            "eligible_training": "True",
            "packet_count_10s": "2",
            "flow_attempt_count_30s": "1",
            "syn_count_10s": "0",
            "http_request_count_60s": "0",
            "dns_query_count_60s": "1",
            **{name: "0.00000000" for name in self.contract.feature_names},
        }
        csv_path = self.feature_dir / "multilayer-v1.csv"
        with csv_path.open("w", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(handle, fieldnames=header)
            writer.writeheader()
            writer.writerow(row)
        report = {
            "schema_version": self.contract.schema["schema_version"],
            "campaign_id": self.campaign_id,
            "rows": 1,
            "eligible_training_rows": 1,
            "output_sha256": sha256(csv_path),
            "inputs": {
                "schema": {"sha256": self.contract.schema_sha256},
                "eve": {"sha256": sha256(eve)},
                "pcap": [{"sha256": sha256(pcap)}],
            },
        }
        self._write_json(self.feature_dir / "extraction-report.json", report)
        rewrite_checksums(self.feature_dir)
        ledger = {
            "campaign_id": self.campaign_id,
            "purpose": "experiment",
            "partition": "train",
            "status": "completed",
            "profile": self.profile,
            "repetition": 1,
            "matrix_sha256": self.contract.matrix_sha256,
            "scenario_args_sha256": manifest["campaign_plan"]["scenario_args_sha256"],
            "git_commit": self.commit,
            "feature_rows": 1,
            "eligible_training_rows": 1,
            "output_sha256": sha256(csv_path),
        }
        self._write_json(self.ledger_path, ledger)

    def mutate_json(self, path: Path, callback, bundle: Path | None = None) -> None:
        value = json.loads(path.read_text(encoding="utf-8"))
        callback(value)
        self._write_json(path, value)
        if bundle:
            rewrite_checksums(bundle)

    def assert_gate(self, gate: str) -> None:
        with self.assertRaises(builder.GateError) as context:
            builder.validate_candidate(self.ledger_path, self.campaigns, self.features, self.contract)
        self.assertEqual(context.exception.gate, gate)

    def test_valid_candidate_passes_all_gates(self) -> None:
        result = builder.validate_candidate(self.ledger_path, self.campaigns, self.features, self.contract)
        self.assertEqual(result["cell"], ["DNS-VALID-10", 1])
        self.assertEqual(result["partition"], "train")
        self.assertEqual(len(result["rows"]), 1)

    def test_rejects_calibration_even_if_partition_train(self) -> None:
        self.mutate_json(self.ledger_path, lambda value: value.update(purpose="calibration"))
        self.assert_gate("GATE-ANTICALIBRACION")

    def test_recomputes_partition_from_repetition(self) -> None:
        self.mutate_json(self.ledger_path, lambda value: value.update(repetition=5))
        self.assert_gate("GATE-ANTICALIBRACION")

    def test_rejects_drops_even_when_complete_true(self) -> None:
        self.mutate_json(
            self.campaign_dir / "manifest.json",
            lambda value: value["evidence"].update(pcap_kernel_drops=3),
            self.campaign_dir,
        )
        self.assert_gate("GATE-INTEGRIDAD")

    def test_rejects_csv_modified_after_checksum(self) -> None:
        with (self.feature_dir / "multilayer-v1.csv").open("a", encoding="utf-8") as handle:
            handle.write("tampered\n")
        self.assert_gate("GATE-INTEGRIDAD")

    def test_rejects_dirty_capture_commit(self) -> None:
        self.mutate_json(
            self.campaign_dir / "manifest.json",
            lambda value: value["git"].update(dirty=True),
            self.campaign_dir,
        )
        self.assert_gate("GATE-GIT")

    def test_rejects_matrix_not_present_in_cited_commit(self) -> None:
        matrix_path = self.repo / builder.MATRIX_RELATIVE
        matrix = json.loads(matrix_path.read_text(encoding="utf-8"))
        matrix["cooldown_seconds"] = 31
        matrix_path.write_text(json.dumps(matrix), encoding="utf-8")
        self.contract = builder.load_contract(self.repo)
        new_hash = self.contract.matrix_sha256
        self.mutate_json(self.ledger_path, lambda value: value.update(matrix_sha256=new_hash))
        self.mutate_json(
            self.campaign_dir / "manifest.json",
            lambda value: value["campaign_plan"].update(matrix_sha256=new_hash),
            self.campaign_dir,
        )
        self.assert_gate("GATE-GIT")

    def test_rejects_campaign_id_outside_expected_cell(self) -> None:
        self.mutate_json(self.ledger_path, lambda value: value.update(campaign_id="F1N-FAKE-R01"))
        self.assert_gate("GATE-CRUCE")

    def test_incomplete_matrix_is_reported_not_built(self) -> None:
        report, accepted = builder.audit_repository(
            self.contract, self.campaigns, self.features, self.ledgers
        )
        self.assertEqual(report["accepted_campaigns"], 1)
        self.assertEqual(len(report["missing_cells"]), 144)
        self.assertFalse(report["ready_to_build"])
        with self.assertRaises(builder.GateError):
            builder.build_dataset(self.repo / "dataset", report, accepted, self.contract)

    def test_complete_collection_builds_three_atomic_splits(self) -> None:
        base = builder.validate_candidate(
            self.ledger_path, self.campaigns, self.features, self.contract
        )
        candidates = []
        for profile in self.matrix["profiles"]:
            for repetition in range(1, 6):
                candidate = deepcopy(base)
                campaign_id = f"F1N-{profile['id']}-R{repetition:02d}"
                candidate.update(
                    campaign_id=campaign_id,
                    cell=[profile["id"], repetition],
                    profile_id=profile["id"],
                    repetition=repetition,
                    partition=self.matrix["partition_by_repetition"][str(repetition)],
                    csv_sha256=hashlib.sha256(campaign_id.encode()).hexdigest(),
                )
                candidate["rows"] = [dict(base["rows"][0], campaign_id=campaign_id)]
                candidates.append(candidate)
        report = {
            "ready_to_build": True,
            "matrix_sha256": self.contract.matrix_sha256,
            "feature_schema_sha256": self.contract.schema_sha256,
            "expected_campaigns": 145,
            "accepted_campaigns": 145,
            "excluded_campaigns": [],
            "invalid_campaigns": [],
            "accepted_cells": [],
            "campaign_warnings": [],
            "missing_cells": [],
            "duplicate_feature_vectors": [],
            "current_git_dirty": False,
            "assembler_git_commit": self.commit,
        }
        output = self.repo / "dataset"
        manifest = builder.build_dataset(output, report, candidates, self.contract)
        self.assertEqual(manifest["split_rows"], {"train": 87, "validation": 29, "test": 29})
        self.assertEqual(len(manifest["source_campaigns"]), 145)
        self.assertEqual(
            {path.name for path in output.iterdir()},
            {"train.csv", "validation.csv", "test.csv", "manifest.json", "SHA256SUMS"},
        )
        builder.verify_checksum_bundle(output)

    def test_rejects_output_hash_disagreement(self) -> None:
        self.mutate_json(self.ledger_path, lambda value: value.update(output_sha256="0" * 64))
        self.assert_gate("GATE-CRUCE")

    def test_rejects_eve_checkpoint_disagreement(self) -> None:
        self.mutate_json(
            self.campaign_dir / "manifest.json",
            lambda value: value["evidence"].update(expected_eve_records=1),
            self.campaign_dir,
        )
        self.assert_gate("GATE-INTEGRIDAD")

    def test_rejects_pcap_limit_reached(self) -> None:
        self.mutate_json(
            self.campaign_dir / "manifest.json",
            lambda value: value["evidence"].update(pcap_limit_reached=True),
            self.campaign_dir,
        )
        self.assert_gate("GATE-INTEGRIDAD")

    def test_rejects_manifest_ledger_status_disagreement(self) -> None:
        self.mutate_json(
            self.campaign_dir / "manifest.json",
            lambda value: value.update(status="scenario_failed"),
            self.campaign_dir,
        )
        self.assert_gate("GATE-INTEGRIDAD")

    def test_rejects_duplicate_window_inside_csv(self) -> None:
        csv_path = self.feature_dir / "multilayer-v1.csv"
        lines = csv_path.read_text(encoding="utf-8").splitlines()
        csv_path.write_text("\n".join([*lines, lines[-1]]) + "\n", encoding="utf-8")
        new_hash = sha256(csv_path)
        self.mutate_json(
            self.feature_dir / "extraction-report.json",
            lambda value: value.update(rows=2, eligible_training_rows=2, output_sha256=new_hash),
        )
        rewrite_checksums(self.feature_dir)
        self.mutate_json(
            self.ledger_path,
            lambda value: value.update(
                feature_rows=2, eligible_training_rows=2, output_sha256=new_hash
            ),
        )
        self.assert_gate("GATE-DUPLICADOS")

    def test_rejects_argument_hash_not_matching_matrix(self) -> None:
        self.mutate_json(
            self.campaign_dir / "manifest.json",
            lambda value: value["campaign_plan"].update(scenario_args_sha256="0" * 64),
            self.campaign_dir,
        )
        self.assert_gate("GATE-MATRIZ")


if __name__ == "__main__":
    unittest.main()
