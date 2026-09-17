from __future__ import annotations

import importlib.util
import ipaddress
import json
import socket
import struct
import sys
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = REPO_ROOT / "scripts/features/extract_multilayer.py"
SPEC = importlib.util.spec_from_file_location("extract_multilayer", MODULE_PATH)
assert SPEC and SPEC.loader
extractor = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = extractor
SPEC.loader.exec_module(extractor)


def ethernet_ipv4(
    src_ip: str,
    dst_ip: str,
    protocol: int,
    transport: bytes,
    payload: bytes = b"",
) -> bytes:
    total_length = 20 + len(transport) + len(payload)
    ip_header = struct.pack(
        "!BBHHHBBH4s4s",
        0x45,
        0,
        total_length,
        1,
        0x4000,
        64,
        protocol,
        0,
        socket.inet_aton(src_ip),
        socket.inet_aton(dst_ip),
    )
    ethernet = bytes.fromhex("00112233445566778899aabb0800")
    return ethernet + ip_header + transport + payload


def tcp_segment(src_port: int, dst_port: int, flags: int, ip_length: int) -> tuple[bytes, bytes]:
    header = struct.pack("!HHIIBBHHH", src_port, dst_port, 0, 0, 5 << 4, flags, 65535, 0, 0)
    return header, bytes(max(0, ip_length - 20 - len(header)))


def udp_segment(src_port: int, dst_port: int, ip_length: int) -> tuple[bytes, bytes]:
    payload = bytes(max(0, ip_length - 28))
    header = struct.pack("!HHHH", src_port, dst_port, 8 + len(payload), 0)
    return header, payload


def icmp_echo(icmp_type: int, identifier: int, ip_length: int) -> tuple[bytes, bytes]:
    header = struct.pack("!BBHHH", icmp_type, 0, 0, identifier, 1)
    return header, bytes(max(0, ip_length - 20 - len(header)))


def write_pcap(path: Path, frames: list[tuple[float, bytes]]) -> None:
    with path.open("wb") as handle:
        handle.write(struct.pack("<IHHIIII", 0xA1B2C3D4, 2, 4, 0, 0, 65535, 1))
        for timestamp, frame in frames:
            seconds = int(timestamp)
            microseconds = round((timestamp - seconds) * 1_000_000)
            handle.write(struct.pack("<IIII", seconds, microseconds, len(frame), len(frame)))
            handle.write(frame)


def iso_timestamp(timestamp: float) -> str:
    return datetime.fromtimestamp(timestamp, timezone.utc).isoformat()


class MultilayerFeatureTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tempdir = tempfile.TemporaryDirectory()
        self.directory = Path(self.tempdir.name)
        self.client = "10.20.0.20"
        self.server = "10.30.0.10"
        frames: list[tuple[float, bytes]] = []

        tcp, payload = tcp_segment(40000, 80, extractor.TCP_SYN, 60)
        frames.append((1001.0, ethernet_ipv4(self.client, self.server, 6, tcp, payload)))
        tcp, payload = tcp_segment(80, 40000, extractor.TCP_SYN | extractor.TCP_ACK, 60)
        frames.append((1001.1, ethernet_ipv4(self.server, self.client, 6, tcp, payload)))
        tcp, payload = tcp_segment(40000, 80, extractor.TCP_ACK, 1000)
        frames.append((1002.0, ethernet_ipv4(self.client, self.server, 6, tcp, payload)))
        tcp, payload = tcp_segment(80, 40000, extractor.TCP_ACK, 1500)
        frames.append((1002.1, ethernet_ipv4(self.server, self.client, 6, tcp, payload)))

        udp, payload = udp_segment(50000, 53, 80)
        frames.append((1003.0, ethernet_ipv4(self.client, self.server, 17, udp, payload)))
        udp, payload = udp_segment(53, 50000, 90)
        frames.append((1003.1, ethernet_ipv4(self.server, self.client, 17, udp, payload)))

        icmp, payload = icmp_echo(8, 77, 84)
        frames.append((1003.2, ethernet_ipv4(self.client, self.server, 1, icmp, payload)))
        icmp, payload = icmp_echo(0, 77, 84)
        frames.append((1003.3, ethernet_ipv4(self.server, self.client, 1, icmp, payload)))

        self.pcap = self.directory / "synthetic.pcap"
        write_pcap(self.pcap, frames)
        events = [
            {
                "timestamp": iso_timestamp(1004.0),
                "event_type": "http",
                "src_ip": self.client,
                "dest_ip": self.server,
                "http": {"status": 404},
            },
            {
                "timestamp": iso_timestamp(1004.1),
                "event_type": "dns",
                "src_ip": self.client,
                "dest_ip": self.server,
                "dns": {"type": "request", "rcode": "NOERROR"},
            },
            {
                "timestamp": iso_timestamp(1004.2),
                "event_type": "dns",
                "src_ip": self.server,
                "dest_ip": self.client,
                "dns": {"type": "response", "rcode": "NXDOMAIN"},
            },
            {
                "timestamp": iso_timestamp(1004.3),
                "event_type": "tls",
                "src_ip": self.client,
                "dest_ip": self.server,
                "tls": {"version": "TLS 1.3"},
            },
            {
                "timestamp": iso_timestamp(1011.0),
                "event_type": "http",
                "src_ip": self.client,
                "dest_ip": self.server,
                "http": {"status": 500},
            },
        ]
        self.eve = self.directory / "eve.jsonl"
        self.eve.write_text("".join(json.dumps(item) + "\n" for item in events), encoding="utf-8")

    def tearDown(self) -> None:
        self.tempdir.cleanup()

    def test_exact_vector_and_causal_boundary(self) -> None:
        network = ipaddress.ip_network("10.20.0.0/24")
        packets = extractor.load_packet_observations([self.pcap], network)
        apps = extractor.load_app_observations(self.eve, network)
        rows = extractor.build_rows("SYNTHETIC", packets, apps)
        first = rows[0]

        self.assertEqual(len(extractor.FEATURE_NAMES), 14)
        self.assertEqual(first["packet_count_10s"], 8)
        self.assertAlmostEqual(first["packet_rate_10s"], 0.8)
        self.assertAlmostEqual(first["byte_rate_10s"], 295.8)
        self.assertAlmostEqual(first["mean_ip_len_10s"], 369.75)
        self.assertAlmostEqual(first["large_ip_ratio_10s"], 0.25)
        self.assertAlmostEqual(first["unique_dst_ip_ratio_30s"], 1 / 3)
        self.assertAlmostEqual(first["icmp_ratio_10s"], 0.25)
        self.assertAlmostEqual(first["flow_attempt_rate_10s"], 0.3)
        self.assertAlmostEqual(first["syn_rate_10s"], 0.1)
        self.assertAlmostEqual(first["syn_completion_ratio_10s"], 1.0)
        self.assertAlmostEqual(first["rst_ratio_10s"], 0.0)
        self.assertAlmostEqual(first["unique_dst_port_ratio_30s"], 1.0)
        self.assertAlmostEqual(first["http_error_ratio_60s"], 1.0)
        self.assertAlmostEqual(first["dns_nxdomain_ratio_60s"], 1.0)
        self.assertAlmostEqual(first["tls_session_rate_60s"], 1 / 60)
        self.assertFalse(first["eligible_training"])

        # El HTTP 500 en t=1011 no puede modificar la fila cuyo cierre es t=1010.
        self.assertEqual(first["window_end_utc"], datetime.fromtimestamp(1010, timezone.utc).isoformat())
        self.assertEqual(first["http_request_count_60s"], 1)

        eligible_rows = extractor.build_rows("SYNTHETIC", packets, apps, capture_start=940.0)
        self.assertTrue(eligible_rows[0]["eligible_training"])

    def test_schema_order_matches_extractor(self) -> None:
        schema_path = REPO_ROOT / "configs/features/multilayer-v1.json"
        extractor.validate_schema(schema_path)
        schema = json.loads(schema_path.read_text(encoding="utf-8"))
        self.assertEqual(len(schema["features"]), 14)


if __name__ == "__main__":
    unittest.main()
