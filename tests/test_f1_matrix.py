from __future__ import annotations

import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = REPO_ROOT / "scripts/f1/validate_matrix.py"
SPEC = importlib.util.spec_from_file_location("validate_matrix", MODULE_PATH)
assert SPEC and SPEC.loader
validator = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = validator
SPEC.loader.exec_module(validator)


class F1MatrixTests(unittest.TestCase):
    def setUp(self) -> None:
        self.matrix_path = REPO_ROOT / "configs/campaigns/f1-normal-v1.json"
        self.schema_path = REPO_ROOT / "configs/features/multilayer-v1.json"

    def test_official_matrix_contract(self) -> None:
        matrix, report = validator.load_and_validate(self.matrix_path, self.schema_path)
        self.assertEqual(report["profiles"], 27)
        self.assertEqual(report["planned_campaigns"], 135)
        self.assertEqual(report["repetitions_per_profile"], 5)
        self.assertEqual(len(report["feature_coverage"]), 14)
        self.assertEqual(matrix["warmup_seconds"], 60)
        self.assertEqual(matrix["partition_by_repetition"]["5"], "test")
        self.assertGreaterEqual(report["minimum_free_after_plan_bytes"], 20 * 1024**3)

    def test_rejects_unversioned_remote_argument(self) -> None:
        matrix = json.loads(self.matrix_path.read_text(encoding="utf-8"))
        matrix["profiles"][0]["args"] = ["10;uname"]
        with tempfile.TemporaryDirectory() as temporary:
            invalid_path = Path(temporary) / "invalid.json"
            invalid_path.write_text(json.dumps(matrix), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "argumento inseguro"):
                validator.load_and_validate(invalid_path, self.schema_path)

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
                validator.load_and_validate(invalid_path, self.schema_path)


if __name__ == "__main__":
    unittest.main()
