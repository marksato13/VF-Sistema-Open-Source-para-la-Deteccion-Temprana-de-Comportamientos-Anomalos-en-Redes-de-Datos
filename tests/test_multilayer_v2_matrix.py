from __future__ import annotations

import importlib.util
import json
import re
import sys
import tempfile
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = REPO_ROOT / "scripts/f1/validate_matrix.py"
SPEC = importlib.util.spec_from_file_location("validate_matrix_v2", MODULE_PATH)
assert SPEC and SPEC.loader
validator = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = validator
SPEC.loader.exec_module(validator)


class MultilayerV2NormalMatrixTests(unittest.TestCase):
    def setUp(self) -> None:
        self.matrix_path = REPO_ROOT / "configs/campaigns/multilayer-v2-normal.json"
        self.schema_path = REPO_ROOT / "configs/features/multilayer-v2.json"

    def test_matrix_passes_against_v2_schema(self) -> None:
        matrix, report = validator.load_and_validate(self.matrix_path, self.schema_path, storage_path=Path("/tmp"))
        self.assertEqual(matrix["schema_version"], "multilayer-v2-normal")
        self.assertEqual(matrix["feature_schema"], "multilayer-v2")
        self.assertEqual(report["repetitions_per_profile"], 5)
        self.assertEqual(report["planned_campaigns"], report["profiles"] * 5)
        self.assertEqual(matrix["partition_by_repetition"], {"1": "train", "2": "train", "3": "train", "4": "validation", "5": "test"})

    def test_every_v2_feature_has_real_coverage(self) -> None:
        _, report = validator.load_and_validate(self.matrix_path, self.schema_path, storage_path=Path("/tmp"))
        schema = json.loads(self.schema_path.read_text(encoding="utf-8"))
        feature_names = {item["name"] for item in schema["features"]}
        self.assertEqual(feature_names, set(report["feature_coverage"]))
        self.assertEqual(len(feature_names), 28)

    def test_mixed_v2_no_longer_claims_structurally_impossible_features(self) -> None:
        # Regresión: mixed-light (HTTP plano + iperf TCP + dns-valid) nunca
        # produce ICMP, TLS, llamadas a /api/* ni NXDOMAIN; ver hallazgo de
        # revisión documentado en known_gaps de la matriz.
        matrix = json.loads(self.matrix_path.read_text(encoding="utf-8"))
        mixed = next(p for p in matrix["profiles"] if p["id"] == "MIXED-V2")
        forbidden = {
            "icmp_ratio_10s",
            "tls_session_rate_60s",
            "http_auth_failure_ratio_60s",
            "http_method_entropy_60s",
            "http_status_5xx_ratio_60s",
            "http_error_ratio_60s",
            "dns_nxdomain_ratio_60s",
            "rst_ratio_10s",
        }
        self.assertFalse(forbidden & set(mixed["feature_coverage"]))

    def test_tls_session_rate_declared_on_tls_producing_profile(self) -> None:
        matrix = json.loads(self.matrix_path.read_text(encoding="utf-8"))
        https_sessions = next(p for p in matrix["profiles"] if p["id"] == "HTTPS-SESSIONS-V2")
        self.assertIn("tls_session_rate_60s", https_sessions["feature_coverage"])

    def test_rejects_unversioned_remote_argument(self) -> None:
        matrix = json.loads(self.matrix_path.read_text(encoding="utf-8"))
        matrix["profiles"][0]["args"] = ["10;uname"]
        with tempfile.TemporaryDirectory() as temporary:
            invalid_path = Path(temporary) / "invalid.json"
            invalid_path.write_text(json.dumps(matrix), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "argumento inseguro"):
                validator.load_and_validate(invalid_path, self.schema_path, storage_path=Path("/tmp"))

    def test_rejects_missing_feature_coverage(self) -> None:
        matrix = json.loads(self.matrix_path.read_text(encoding="utf-8"))
        for profile in matrix["profiles"]:
            profile["feature_coverage"] = [
                name for name in profile["feature_coverage"] if name != "rst_ratio_10s"
            ]
        with tempfile.TemporaryDirectory() as temporary:
            invalid_path = Path(temporary) / "invalid.json"
            invalid_path.write_text(json.dumps(matrix), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "features sin cobertura declarada"):
                validator.load_and_validate(invalid_path, self.schema_path, storage_path=Path("/tmp"))


class MultilayerV2AnomaliesMatrixTests(unittest.TestCase):
    """La matriz de anomalías no comparte forma con las matrices normales
    (sin default_repetitions/partition/estimated_pcap_bytes), por lo que no
    pasa por validate_matrix.load_and_validate. Se valida su propio contrato
    estructural mínimo aquí."""

    def setUp(self) -> None:
        path = REPO_ROOT / "configs/campaigns/multilayer-v2-anomalies.json"
        self.matrix = json.loads(path.read_text(encoding="utf-8"))
        schema_path = REPO_ROOT / "configs/features/multilayer-v2.json"
        schema = json.loads(schema_path.read_text(encoding="utf-8"))
        self.feature_names = {item["name"] for item in schema["features"]}

    def test_execution_policy_is_evaluation_only(self) -> None:
        self.assertEqual(self.matrix["execution_policy"], "evaluation_only")
        self.assertEqual(self.matrix["feature_schema"], "multilayer-v2")
        self.assertEqual(self.matrix["label"], "anomaly")

    def test_profile_ids_scenarios_and_arguments_are_safe(self) -> None:
        seen_ids: set[str] = set()
        for profile in self.matrix["profiles"]:
            self.assertRegex(profile["id"], validator.SAFE_ID.pattern)
            self.assertNotIn(profile["id"], seen_ids, f"id duplicado {profile['id']}")
            seen_ids.add(profile["id"])
            self.assertIn(profile["scenario"], validator.ALLOWED_SCENARIOS)
            for argument in profile["args"]:
                self.assertRegex(argument, validator.SAFE_ARGUMENT.pattern)

    def test_expected_signals_are_known_v2_features(self) -> None:
        for profile in self.matrix["profiles"]:
            unknown = set(profile["expected_signals"]) - self.feature_names
            self.assertFalse(unknown, f"{profile['id']}: señales desconocidas {unknown}")

    def test_profile_id_numeric_suffix_matches_its_own_argument(self) -> None:
        # Regresión del hallazgo: ANOM-SYN-RATE-50 declaraba args=["10"], una
        # inconsistencia de nombres entre el id y el conteo real ejecutado.
        # Cada id termina en el mismo número que aparece en sus args.
        suffix_pattern = re.compile(r"-(\d+)$")
        for profile in self.matrix["profiles"]:
            match = suffix_pattern.search(profile["id"])
            self.assertIsNotNone(match, f"{profile['id']} no termina en un conteo numérico")
            self.assertIn(
                match.group(1),
                profile["args"],
                f"{profile['id']}: el sufijo numérico del id no aparece en args={profile['args']}",
            )

    def test_kali_profiles_are_separate_and_offensive(self) -> None:
        # Los perfiles de Kali no comparten contrato con los heredados: no
        # llevan sufijo numerico obligatorio (tcp-port-scan no tiene conteo) y
        # usan la lista de escenarios ofensivos, no la benigna.
        seen = {p["id"] for p in self.matrix["profiles"]}
        for profile in self.matrix["kali_profiles"]:
            self.assertRegex(profile["id"], validator.SAFE_ID.pattern)
            self.assertNotIn(profile["id"], seen, f"id duplicado {profile['id']}")
            seen.add(profile["id"])
            self.assertIn(profile["scenario"], validator.ALLOWED_KALI_SCENARIOS)
            self.assertNotIn(
                profile["scenario"],
                validator.ALLOWED_SCENARIOS,
                "un escenario ofensivo no debe ser ejecutable por la ruta benigna",
            )
            self.assertEqual(profile["traffic_class"], "offensive")
            for argument in profile["args"]:
                self.assertRegex(argument, validator.SAFE_ARGUMENT.pattern)
            unknown = set(profile["expected_signals"]) - self.feature_names
            self.assertFalse(unknown, f"{profile['id']}: señales desconocidas {unknown}")

    def test_kali_scenario_allowlist_matches_runner(self) -> None:
        # Guarda contra deriva: la constante y el `case` de run-f1-kali.sh
        # deben declarar exactamente los mismos escenarios.
        runner = (REPO_ROOT / "scripts/campaign/run-f1-kali.sh").read_text(encoding="utf-8")
        declared = set()
        for line in runner.splitlines():
            stripped = line.strip()
            if stripped.endswith(") ;;") and "|" in stripped:
                declared = set(stripped.split(")")[0].split("|"))
                break
        self.assertEqual(declared, validator.ALLOWED_KALI_SCENARIOS)

    def test_dataset_snapshot_matches_declared_profiles(self) -> None:
        snapshot = self.matrix["dataset_snapshot"]
        self.assertEqual(snapshot["legacy_relabeled"]["families"], len(self.matrix["profiles"]))
        self.assertEqual(snapshot["kali_real"]["families"], len(self.matrix["kali_profiles"]))
        self.assertEqual(snapshot["families_total"], len(self.matrix["profiles"]) + len(self.matrix["kali_profiles"]))
        self.assertEqual(
            snapshot["windows_total"],
            snapshot["kali_real"]["windows"] + snapshot["legacy_relabeled"]["windows"],
        )
        for group in ("profiles", "kali_profiles"):
            key = "legacy_relabeled" if group == "profiles" else "kali_real"
            self.assertEqual(
                sum(p["observed_windows"] for p in self.matrix[group]),
                snapshot[key]["windows"],
            )

    def test_tcp_refused_count_is_within_run_benign_limits(self) -> None:
        profile = next(p for p in self.matrix["profiles"] if p["scenario"] == "tcp-refused")
        # scripts/f1/run-benign.sh caso tcp-refused solo acepta 3, 5 o 10.
        self.assertIn(profile["args"][0], ("3", "5", "10"))


if __name__ == "__main__":
    unittest.main()
