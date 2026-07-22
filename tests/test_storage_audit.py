from __future__ import annotations

import importlib.util
import sys
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = REPO_ROOT / "scripts/storage/audit_evidence_disk.py"
SPEC = importlib.util.spec_from_file_location("audit_evidence_disk", MODULE_PATH)
assert SPEC and SPEC.loader
audit = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = audit
SPEC.loader.exec_module(audit)


class EvidenceDiskAuditTests(unittest.TestCase):
    def assess(self, **overrides):
        record = {
            "path": "/dev/sdb",
            "type": "disk",
            "size": 150 * audit.GIB,
            "fstype": None,
            "mountpoints": [None],
        }
        record.update(overrides.pop("record", {}))
        return audit.assess_device(
            record,
            requested=overrides.pop("requested", "/dev/disk/by-id/scsi-new-evidence"),
            resolved=overrides.pop("resolved", "/dev/sdb"),
            root_disk=overrides.pop("root_disk", "/dev/sda"),
            minimum_bytes=100 * audit.GIB,
            signatures=overrides.pop("signatures", []),
        )

    def test_accepts_only_a_blank_large_non_root_disk(self) -> None:
        report = self.assess()
        self.assertTrue(report["eligible_new_disk"])
        self.assertTrue(all(report["checks"].values()))

    def test_rejects_root_disk_even_if_blank(self) -> None:
        report = self.assess(resolved="/dev/sda", root_disk="/dev/sda")
        self.assertFalse(report["eligible_new_disk"])
        self.assertFalse(report["checks"]["is_not_root_disk"])

    def test_rejects_small_partitioned_or_formatted_disk(self) -> None:
        report = self.assess(
            record={
                "size": 80 * audit.GIB,
                "fstype": "ext4",
                "children": [{"path": "/dev/sdb1", "type": "part"}],
                "mountpoints": ["/mnt/old"],
            },
            signatures=["gpt", "ext4"],
        )
        self.assertFalse(report["eligible_new_disk"])
        self.assertGreaterEqual(len(report["errors"]), 5)

    def test_rejects_unstable_device_name(self) -> None:
        report = self.assess(requested="/dev/sdb")
        self.assertFalse(report["checks"]["stable_device_path"])

    def test_accepts_vmware_scsi_by_path_for_whole_disk(self) -> None:
        report = self.assess(requested="/dev/disk/by-path/pci-0000:02:00.0-scsi-0:0:1:0")
        self.assertTrue(report["checks"]["stable_device_path"])

    def test_rejects_stable_path_to_partition(self) -> None:
        report = self.assess(
            requested="/dev/disk/by-path/pci-0000:02:00.0-scsi-0:0:1:0-part1"
        )
        self.assertFalse(report["checks"]["stable_device_path"])

    def test_finds_physical_disk_through_nested_block_layers(self) -> None:
        topology = [
            {
                "path": "/dev/mapper/root",
                "type": "lvm",
                "children": [
                    {
                        "path": "/dev/sda2",
                        "type": "part",
                        "children": [{"path": "/dev/sda", "type": "disk"}],
                    }
                ],
            }
        ]
        self.assertEqual(audit.disk_paths(topology), {"/dev/sda"})


if __name__ == "__main__":
    unittest.main()
