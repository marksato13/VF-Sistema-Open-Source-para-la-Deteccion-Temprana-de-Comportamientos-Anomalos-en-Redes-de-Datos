from __future__ import annotations

import importlib.util
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace


SOURCE_REPO = Path(__file__).resolve().parents[1]
MODULE_PATH = SOURCE_REPO / "scripts/analysis/summarize_f1_repetition.py"
SPEC = importlib.util.spec_from_file_location("summarize_f1_repetition", MODULE_PATH)
assert SPEC and SPEC.loader
summary_module = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = summary_module
SPEC.loader.exec_module(summary_module)


FEATURES = (
    "packet_rate_10s",
    "byte_rate_10s",
    "mean_ip_len_10s",
    "large_ip_ratio_10s",
    "unique_dst_ip_ratio_30s",
    "icmp_ratio_10s",
    "flow_attempt_rate_10s",
    "syn_rate_10s",
    "syn_completion_ratio_10s",
    "rst_ratio_10s",
    "unique_dst_port_ratio_30s",
    "http_error_ratio_60s",
    "dns_nxdomain_ratio_60s",
    "tls_session_rate_60s",
)


def feature_row(campaign_id: str, window: str, packet_rate: str) -> dict[str, str]:
    row = {name: "0.00000000" for name in FEATURES}
    row.update(
        {
            "campaign_id": campaign_id,
            "window_end_utc": window,
            "packet_rate_10s": packet_rate,
        }
    )
    return row


class RepetitionSummaryTests(unittest.TestCase):
    def setUp(self) -> None:
        profiles = [
            {"id": "PROFILE-A", "scenario": "alpha", "stratum": "light"},
            {"id": "PROFILE-B", "scenario": "beta", "stratum": "burst"},
        ]
        schema_features = [
            {
                "name": name,
                "layer": "L3" if index < 6 else "L4" if index < 11 else "L7",
                "unit": "ratio",
            }
            for index, name in enumerate(FEATURES)
        ]
        self.contract = SimpleNamespace(
            matrix={
                "default_repetitions": 5,
                "partition_by_repetition": {
                    "1": "train",
                    "2": "train",
                    "3": "train",
                    "4": "validation",
                    "5": "test",
                },
                "profiles": profiles,
            },
            schema={"features": schema_features},
            feature_names=FEATURES,
            matrix_sha256="a" * 64,
            schema_sha256="b" * 64,
        )
        self.audit = {
            "accepted_campaigns": 2,
            "invalid_campaigns": [],
            "campaign_warnings": [],
            "duplicate_feature_vectors": [],
            "duplicate_feature_vector_count": 0,
            "cross_partition_duplicate_feature_vector_count": 0,
            "duplicate_feature_vectors_truncated": 0,
            "current_git_dirty": False,
            "assembler_git_commit": "c" * 40,
        }
        self.accepted = [
            {
                "campaign_id": "F1N-PROFILE-A-R01",
                "profile_id": "PROFILE-A",
                "repetition": 1,
                "pcap_bytes": 100,
                "rows": [
                    feature_row("F1N-PROFILE-A-R01", "2026-07-27T00:00:10+00:00", "1"),
                    feature_row("F1N-PROFILE-A-R01", "2026-07-27T00:00:20+00:00", "1"),
                ],
            },
            {
                "campaign_id": "F1N-PROFILE-B-R01",
                "profile_id": "PROFILE-B",
                "repetition": 1,
                "pcap_bytes": 200,
                "rows": [
                    feature_row("F1N-PROFILE-B-R01", "2026-07-27T00:00:30+00:00", "2")
                ],
            },
        ]
        self.counts = {
            "F1N-PROFILE-A-R01": {
                "packet_observations": 10,
                "application_observations": 2,
            },
            "F1N-PROFILE-B-R01": {
                "packet_observations": 20,
                "application_observations": 3,
            },
        }

    def test_complete_repetition_reports_distribution_and_repeated_rows(self) -> None:
        result = summary_module.build_summary(
            1, self.contract, self.audit, self.accepted, self.counts
        )
        self.assertTrue(result["repetition_complete"])
        self.assertTrue(result["gate_pass"])
        self.assertEqual(result["rows"]["total"], 3)
        self.assertEqual(result["rows"]["campaigns_with_multiple_rows"], 1)
        self.assertEqual(result["observations"], {"packet": 30, "application": 5})
        self.assertEqual(result["rows_by_scenario"], {"alpha": 2, "beta": 1})
        packet_rate = next(
            item for item in result["features"] if item["name"] == "packet_rate_10s"
        )
        self.assertEqual(packet_rate["minimum"], 1.0)
        self.assertEqual(packet_rate["maximum"], 2.0)
        self.assertEqual(packet_rate["nonzero_rows"], 3)
        self.assertEqual(result["exact_repeated_vector_groups"], 1)
        self.assertEqual(result["exact_repeated_vectors"][0]["occurrences"], 2)
        self.assertIn("byte_rate_10s", result["all_zero_features"])

    def test_missing_profile_fails_gate_without_discarding_summary(self) -> None:
        result = summary_module.build_summary(
            1, self.contract, self.audit, self.accepted[:1], self.counts
        )
        self.assertFalse(result["repetition_complete"])
        self.assertFalse(result["gate_pass"])
        self.assertEqual(result["missing_profiles"], ["PROFILE-B"])
        self.assertEqual(result["rows"]["total"], 2)

    def test_repository_error_fails_gate(self) -> None:
        audit = {**self.audit, "invalid_campaigns": [{"gate": "fixture"}]}
        result = summary_module.build_summary(
            1, self.contract, audit, self.accepted, self.counts
        )
        self.assertTrue(result["repetition_complete"])
        self.assertFalse(result["gate_pass"])

    def test_complete_profiles_with_empty_rows_fail_gate(self) -> None:
        accepted = [{**candidate, "rows": []} for candidate in self.accepted]
        result = summary_module.build_summary(
            1, self.contract, self.audit, accepted, self.counts
        )
        self.assertTrue(result["repetition_complete"])
        self.assertEqual(result["rows"]["total"], 0)
        self.assertFalse(result["gate_pass"])

    def test_negative_observation_count_is_rejected(self) -> None:
        counts = {
            **self.counts,
            "F1N-PROFILE-A-R01": {
                "packet_observations": -1,
                "application_observations": 2,
            },
        }
        with self.assertRaisesRegex(ValueError, "packet_observations inválido"):
            summary_module.build_summary(
                1, self.contract, self.audit, self.accepted, counts
            )

    def test_dirty_repository_fails_gate(self) -> None:
        audit = {**self.audit, "current_git_dirty": True}
        result = summary_module.build_summary(
            1, self.contract, audit, self.accepted, self.counts
        )
        self.assertTrue(result["repetition_complete"])
        self.assertFalse(result["gate_pass"])

    def test_exact_cross_campaign_vector_is_diagnostic_not_collection_failure(self) -> None:
        audit = {
            **self.audit,
            "duplicate_feature_vectors": [
                {
                    "first_campaign": "A",
                    "first_partition": "train",
                    "duplicate_campaign": "B",
                    "duplicate_partition": "validation",
                    "cross_partition": True,
                }
            ],
            "duplicate_feature_vector_count": 1,
            "cross_partition_duplicate_feature_vector_count": 1,
        }
        result = summary_module.build_summary(
            1, self.contract, audit, self.accepted, self.counts
        )
        self.assertTrue(result["gate_pass"])
        self.assertEqual(
            result["repository_audit"]["cross_partition_duplicate_vector_count"],
            1,
        )

    def test_rejects_repetition_outside_matrix(self) -> None:
        with self.assertRaisesRegex(ValueError, "fuera de rango"):
            summary_module.build_summary(
                6, self.contract, self.audit, self.accepted, self.counts
            )


if __name__ == "__main__":
    unittest.main()
