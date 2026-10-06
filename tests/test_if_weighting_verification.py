from __future__ import annotations

import importlib.util
import sys
import unittest
from collections import Counter
from pathlib import Path


SOURCE_REPO = Path(__file__).resolve().parents[1]
MODULE_PATH = SOURCE_REPO / "scripts/analysis/verify_if_weighting.py"
SPEC = importlib.util.spec_from_file_location("verify_if_weighting", MODULE_PATH)
assert SPEC and SPEC.loader
module = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = module
SPEC.loader.exec_module(module)


class IsolationForestWeightingTests(unittest.TestCase):
    def test_campaign_weights_sum_to_one_per_campaign(self) -> None:
        campaign_ids = ["A", "A", "B", "B", "B"]
        weights = module.campaign_weights(campaign_ids)
        self.assertEqual(weights, [0.5, 0.5, 1 / 3, 1 / 3, 1 / 3])
        self.assertAlmostEqual(sum(weights[:2]), 1.0)
        self.assertAlmostEqual(sum(weights[2:]), 1.0)

    def test_episode_expansion_is_deterministic_and_balanced(self) -> None:
        campaign_ids = ["A", "A", "B", "B", "B"]
        indices, common_rows = module.episode_balanced_indices(campaign_ids)
        expanded_campaigns = [campaign_ids[index] for index in indices]
        self.assertEqual(common_rows, 6)
        self.assertEqual(len(indices), 12)
        self.assertEqual(Counter(expanded_campaigns), {"A": 6, "B": 6})
        self.assertEqual(indices, [0, 0, 0, 1, 1, 1, 2, 2, 3, 3, 4, 4])

    def test_lower_tail_uses_windows_and_strict_inequality(self) -> None:
        scores = [float(value) for value in range(20)]
        campaigns = ["A"] * 2 + [f"C{value}" for value in range(18)]
        result = module.lower_tail_diagnostics(scores, campaigns, alpha=0.05)
        self.assertEqual(result["unit"], "windows")
        self.assertEqual(result["n_windows"], 20)
        self.assertEqual(result["k"], 1)
        self.assertEqual(result["threshold"], 1.0)
        self.assertEqual(result["strict_alert_count"], 1)
        self.assertEqual(result["strict_alert_campaign_count"], 1)

    def test_threshold_ties_are_conservative(self) -> None:
        scores = [0.0, 0.0, *[float(value) for value in range(1, 19)]]
        campaigns = [f"C{value}" for value in range(20)]
        result = module.lower_tail_diagnostics(scores, campaigns, alpha=0.05)
        self.assertEqual(result["k"], 1)
        self.assertEqual(result["threshold"], 0.0)
        self.assertEqual(result["strict_alert_count"], 0)
        self.assertEqual(result["threshold_tie_count"], 2)


if __name__ == "__main__":
    unittest.main()
