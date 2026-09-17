from __future__ import annotations

import importlib.util
import sys
import tempfile
import unittest
from collections import Counter
from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace


SOURCE_REPO = Path(__file__).resolve().parents[1]
MODULE_PATH = SOURCE_REPO / "scripts/modeling/calibrate_pm_f1_v1.py"
SPEC = importlib.util.spec_from_file_location("calibrate_pm_f1_v1", MODULE_PATH)
assert SPEC and SPEC.loader
module = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = module
SPEC.loader.exec_module(module)


FEATURES = tuple(f"f{index}" for index in range(14))


def row(value: str) -> dict[str, str]:
    return {name: value for name in FEATURES}


class PMF1CalibrationTests(unittest.TestCase):
    def test_expected_paths_never_contain_r05(self) -> None:
        contract = SimpleNamespace(
            matrix={
                "partition_by_repetition": {
                    "1": "train",
                    "2": "train",
                    "3": "train",
                    "4": "validation",
                    "5": "test",
                },
                "profiles": [{"id": "A"}, {"id": "B"}],
            }
        )
        paths = module.expected_ledger_paths(contract, Path("/evidence/g6-ledger"))
        self.assertEqual(len(paths), 8)
        self.assertFalse(any("R05" in str(path) for _, _, path in paths))
        self.assertEqual([repetition for repetition, _, _ in paths], [1, 1, 2, 2, 3, 3, 4, 4])

    def test_exact_collapse_preserves_first_decimal_representative(self) -> None:
        rows = [row("1.00000000"), row("1.0"), row("2.00000000"), row("1.00000000")]
        self.assertEqual(module.collapsed_train_indices(rows, FEATURES), [0, 2])
        self.assertEqual(module.decimal_vector(rows[0], FEATURES), (Decimal("1"),) * 14)

    def test_episode_expansion_is_balanced_and_deterministic(self) -> None:
        indices, rows_per_campaign = module.episode_balanced_indices(["A", "A", "B", "B", "B"])
        expanded = [["A", "A", "B", "B", "B"][index] for index in indices]
        self.assertEqual(rows_per_campaign, 6)
        self.assertEqual(Counter(expanded), {"A": 6, "B": 6})
        self.assertEqual(indices, [0, 0, 0, 1, 1, 1, 2, 2, 3, 3, 4, 4])

    def test_lower_tail_is_strict_and_uses_stable_index_for_ties(self) -> None:
        scores = [0.0, 0.0, *[float(value) for value in range(1, 19)]]
        campaigns = [f"C{index}" for index in range(20)]
        result = module.lower_tail(scores, campaigns)
        self.assertEqual(result["n_windows"], 20)
        self.assertEqual(result["k"], 1)
        self.assertEqual(result["threshold"], 0.0)
        self.assertEqual(result["lower_prefix_indices"], [0])
        self.assertEqual(result["strict_alert_count"], 0)
        self.assertEqual(result["threshold_tie_count"], 2)

    def test_lower_tail_rejects_non_finite_scores(self) -> None:
        with self.assertRaisesRegex(module.CalibrationError, "no finito"):
            module.lower_tail([0.0, float("nan")], ["A", "B"])

    def test_selection_bytes_are_deterministic(self) -> None:
        contract = SimpleNamespace(feature_names=FEATURES)
        metadata = ({
            "partition": "train",
            "profile_id": "A",
            "repetition": 1,
            "campaign_id": "F1N-A-R01",
            "row_in_campaign": 0,
            "entity_ip": "10.20.0.20",
            "window_end_utc": "2026-01-01T00:00:00+00:00",
        },)
        selected = module.SelectedData(contract, tuple(), (row("1.00000000"),), metadata, ("train",))
        first = module.selection_bytes(selected)
        second = module.selection_bytes(selected)
        self.assertEqual(first, second)
        self.assertEqual(module.sha256_bytes(first), module.sha256_bytes(second))

    def test_safe_output_must_be_inside_root_and_new(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary).resolve()
            destination = root / "models/pm-f1-v1"
            self.assertEqual(module.safe_output_path(root, destination), destination)
            with self.assertRaisesRegex(module.CalibrationError, "dentro"):
                module.safe_output_path(root, root.parent / "escape")
            destination.mkdir(parents=True)
            with self.assertRaisesRegex(module.CalibrationError, "nunca se reemplaza"):
                module.safe_output_path(root, destination)

    def test_frozen_requirements_require_exact_pins(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "requirements.txt"
            path.write_text("numpy==2.5.1\nscikit-learn>=1.9\n", encoding="utf-8")
            with self.assertRaisesRegex(module.CalibrationError, "no congelado"):
                module.parse_frozen_requirements(path)


if __name__ == "__main__":
    unittest.main()
