from __future__ import annotations

import subprocess
import unittest
from pathlib import Path


REPO = Path(__file__).resolve().parents[1]
SCRIPT = REPO / "scripts/f1/preflight_profile.sh"


class F1PreflightContractTests(unittest.TestCase):
    def setUp(self) -> None:
        self.source = SCRIPT.read_text(encoding="utf-8")

    def test_bash_syntax(self) -> None:
        subprocess.run(["bash", "-n", str(SCRIPT)], check=True)

    def test_only_matrix_dry_run_is_present(self) -> None:
        self.assertIn('run_matrix_profile.py"', self.source)
        self.assertIn('--dry-run', self.source)
        for forbidden in (
            "ppi-pcap-control start",
            "campaign/start.sh",
            "run-f1.sh",
            "--execute-once",
        ):
            self.assertNotIn(forbidden, self.source)

    def test_external_macs_are_frozen(self) -> None:
        for mac in (
            "00:0c:29:f7:15:80",
            "00:0c:29:15:ad:a7",
            "00:0c:29:52:db:60",
            "00:0c:29:c5:ed:66",
        ):
            self.assertIn(mac, self.source)

    def test_gates_have_frozen_order(self) -> None:
        gates = (
            "GIT",
            "CONTRACT_STORAGE",
            "CAPACITY_NTP",
            "IDS_SSH",
            "ISOLATION_BYPASS",
            "ROUTES",
            "SURICATA_CAPTURE",
            "SERVICES_LISTENER",
            "PROBES_GENERATOR",
        )
        positions = [self.source.index(f"run_gate {gate} ") for gate in gates]
        self.assertEqual(positions, sorted(positions))

    def test_official_log_cannot_be_replaced(self) -> None:
        self.assertIn('[[ ! -e "$FINAL_LOG" ]]', self.source)
        self.assertIn("FULL_CONTIGUOUS_PREFLIGHT=PASS", self.source)
        self.assertIn("failed-$(date +%Y%m%dT%H%M%S%N).log", self.source)

    def test_transport_errors_cannot_mean_inactive_or_blocked(self) -> None:
        self.assertIn('[[ "$tcpdump_rc" == 1 ]]', self.source)
        self.assertIn(
            '[[ "$kali_probe_rc" == 1 || "$kali_probe_rc" == 124 ]]',
            self.source,
        )
        self.assertIn("no se pudo verificar tcpdump en Sensor", self.source)
        self.assertIn("no se pudo verificar el bloqueo Kali→iperf3", self.source)

    def test_preflights_use_atomic_lock_and_private_umask(self) -> None:
        self.assertIn("umask 077", self.source)
        self.assertIn('mkdir -m 0700 "$PREFLIGHT_LOCK"', self.source)
        self.assertIn('rmdir "$PREFLIGHT_LOCK"', self.source)


if __name__ == "__main__":
    unittest.main()
