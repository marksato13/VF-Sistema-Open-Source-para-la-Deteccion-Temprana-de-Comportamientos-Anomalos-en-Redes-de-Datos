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
MODULE_PATH = REPO_ROOT / "scripts/features/extract_multilayer_v2.py"
SPEC = importlib.util.spec_from_file_location("extract_multilayer_v2", MODULE_PATH)
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
    ttl: int = 64,
) -> bytes:
    total_length = 20 + len(transport) + len(payload)
    ip_header = struct.pack(
        "!BBHHHBBH4s4s",
        0x45,
        0,
        total_length,
        1,
        0x4000,
        ttl,
        protocol,
        0,
        socket.inet_aton(src_ip),
        socket.inet_aton(dst_ip),
    )
    ethernet = bytes.fromhex("00112233445566778899aabb0800")
    return ethernet + ip_header + transport + payload


def ethernet_ipv4_with_flags(
    src_ip: str,
    dst_ip: str,
    protocol: int,
    transport: bytes,
    payload: bytes = b"",
    ttl: int = 64,
    flags_and_fragment_offset: int = 0x4000,
) -> bytes:
    """Igual que ``ethernet_ipv4`` pero permite fijar el campo IP flags/fragment-offset
    explícitamente (por defecto DF=1, sin fragmentar, igual que ``ethernet_ipv4``)."""
    total_length = 20 + len(transport) + len(payload)
    ip_header = struct.pack(
        "!BBHHHBBH4s4s",
        0x45,
        0,
        total_length,
        1,
        flags_and_fragment_offset,
        ttl,
        protocol,
        0,
        socket.inet_aton(src_ip),
        socket.inet_aton(dst_ip),
    )
    ethernet = bytes.fromhex("00112233445566778899aabb0800")
    return ethernet + ip_header + transport + payload


def tcp_segment(src_port: int, dst_port: int, flags: int, ip_length: int, seq: int = 0) -> tuple[bytes, bytes]:
    header = struct.pack("!HHIIBBHHH", src_port, dst_port, seq, 0, 5 << 4, flags, 65535, 0, 0)
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


class MultilayerV2FeatureTests(unittest.TestCase):
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
        tcp, payload = tcp_segment(40000, 80, extractor.TCP_ACK, 1000, seq=1)
        frames.append((1002.0, ethernet_ipv4(self.client, self.server, 6, tcp, payload)))
        tcp, payload = tcp_segment(80, 40000, extractor.TCP_ACK, 1500, seq=1)
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
                "http": {"status": 404, "http_method": "GET"},
            },
            {
                "timestamp": iso_timestamp(1004.1),
                "event_type": "dns",
                "src_ip": self.client,
                "dest_ip": self.server,
                "dns": {"type": "request", "rcode": "NOERROR", "rrname": "server.ppi.lab"},
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
                # Fuera de la ventana causal que cierra en t=1010; no debe alterar la primera fila.
                "timestamp": iso_timestamp(1011.0),
                "event_type": "http",
                "src_ip": self.client,
                "dest_ip": self.server,
                "http": {"status": 500, "http_method": "POST"},
            },
        ]
        self.eve = self.directory / "eve.jsonl"
        self.eve.write_text("".join(json.dumps(item) + "\n" for item in events), encoding="utf-8")

    def tearDown(self) -> None:
        self.tempdir.cleanup()

    def test_schema_has_28_names_and_matches_extractor(self) -> None:
        self.assertEqual(len(extractor.FEATURE_NAMES), 28)
        schema_path = REPO_ROOT / "configs/features/multilayer-v2.json"
        extractor.validate_schema(schema_path)
        schema = json.loads(schema_path.read_text(encoding="utf-8"))
        self.assertEqual(len(schema["features"]), 28)
        schema_names = tuple(
            item["name"] for item in sorted(schema["features"], key=lambda item: item["order"])
        )
        self.assertEqual(schema_names, extractor.FEATURE_NAMES)

    def test_v1_features_preserved_and_causal_boundary_respected(self) -> None:
        network = ipaddress.ip_network("10.20.0.0/24")
        packets = extractor.load_packet_observations([self.pcap], network)
        apps = extractor.load_app_observations(self.eve, network)
        rows = extractor.build_rows("SYNTHETIC", packets, apps)
        first = rows[0]

        # El cierre de la primera ventana es t=1010; el HTTP 500 de t=1011 no puede alterarla.
        self.assertEqual(
            first["window_end_utc"], datetime.fromtimestamp(1010, timezone.utc).isoformat()
        )
        self.assertEqual(first["http_request_count_60s"], 1)

        self.assertAlmostEqual(first["packet_rate_10s"], 0.8)
        self.assertAlmostEqual(first["byte_rate_10s"], 295.8)
        self.assertAlmostEqual(first["large_ip_ratio_10s"], 0.25)
        self.assertAlmostEqual(first["unique_dst_ip_ratio_30s"], 1 / 3)
        self.assertAlmostEqual(first["icmp_ratio_10s"], 0.25)
        self.assertAlmostEqual(first["syn_completion_ratio_10s"], 1.0)
        self.assertAlmostEqual(first["rst_ratio_10s"], 0.0)
        self.assertAlmostEqual(first["unique_dst_port_ratio_30s"], 1.0)
        self.assertAlmostEqual(first["http_error_ratio_60s"], 1.0)
        self.assertAlmostEqual(first["dns_nxdomain_ratio_60s"], 1.0)
        self.assertAlmostEqual(first["tls_session_rate_60s"], 1 / 60)
        self.assertFalse(first["eligible_training"])

    def test_new_v2_features_are_causal_and_conservative(self) -> None:
        network = ipaddress.ip_network("10.20.0.0/24")
        packets = extractor.load_packet_observations([self.pcap], network)
        apps = extractor.load_app_observations(self.eve, network)
        rows = extractor.build_rows("SYNTHETIC", packets, apps)
        first = rows[0]

        # Todas las tramas sintéticas usan TTL=64 y no llevan fragmentación.
        self.assertAlmostEqual(first["ttl_mean_10s"], 64.0)
        self.assertAlmostEqual(first["fragment_ratio_10s"], 0.0)
        self.assertGreater(first["protocol_diversity_30s"], 0.0)
        self.assertLessEqual(first["protocol_diversity_30s"], 1.0)

        # Cada segmento TCP con payload usa una secuencia distinta por dirección: sin retransmisión.
        self.assertAlmostEqual(first["tcp_retransmission_ratio_10s"], 0.0)

        self.assertGreater(first["flow_duration_mean_30s"], 0.0)
        self.assertGreater(first["tx_rx_byte_ratio_30s"], 0.0)
        self.assertLess(first["tx_rx_byte_ratio_30s"], 1.0)

        self.assertAlmostEqual(first["http_request_rate_60s"], 1 / 60)
        self.assertAlmostEqual(first["http_auth_failure_ratio_60s"], 0.0)
        self.assertAlmostEqual(first["http_status_5xx_ratio_60s"], 0.0)
        # Una única solicitud HTTP: entropía de método = 0 bits (sin incertidumbre).
        self.assertAlmostEqual(first["http_method_entropy_60s"], 0.0)

        self.assertAlmostEqual(first["dns_query_rate_60s"], 1 / 60)
        self.assertAlmostEqual(first["unique_dns_name_ratio_60s"], 1.0)

        self.assertAlmostEqual(first["tls_handshake_failure_ratio_60s"], 0.0)
        self.assertAlmostEqual(first["tls_version_ratio_60s"], 1.0)

        # El HTTP 500 de t=1011 queda fuera de la ventana causal de la primera fila.
        second = next(row for row in rows if row["window_end_utc"] > first["window_end_utc"])
        self.assertGreater(second["http_status_5xx_ratio_60s"], 0.0)

    def test_fragment_ratio_10s_reports_intermediate_value(self) -> None:
        # Caso positivo: 1 paquete con IP_FLAG_MF activo entre 4 paquetes totales
        # dentro de la misma ventana de 10s -> ratio = 1/4 = 0.25 (ni 0.0 ni 1.0).
        network = ipaddress.ip_network("10.20.0.0/24")
        frames: list[tuple[float, bytes]] = []

        udp, payload = udp_segment(51000, 9000, 80)
        frames.append(
            (
                2001.0,
                ethernet_ipv4_with_flags(
                    self.client,
                    self.server,
                    17,
                    udp,
                    payload,
                    flags_and_fragment_offset=extractor.IP_FLAG_MF,
                ),
            )
        )
        for offset, port in enumerate((9001, 9002, 9003), start=1):
            udp, payload = udp_segment(51000 + offset, port, 80)
            frames.append(
                (2001.0 + offset, ethernet_ipv4_with_flags(self.client, self.server, 17, udp, payload))
            )

        pcap_path = self.directory / "fragment.pcap"
        write_pcap(pcap_path, frames)

        packets = extractor.load_packet_observations([pcap_path], network)
        rows = extractor.build_rows("FRAG-TEST", packets, [])
        self.assertEqual(len(rows), 1)
        row = rows[0]
        self.assertEqual(row["packet_count_10s"], 4)
        self.assertAlmostEqual(row["fragment_ratio_10s"], 0.25)

    def test_tls_handshake_failure_ratio_60s_reports_intermediate_value(self) -> None:
        # Caso positivo: 1 evento TLS sin "version" (incompleto) entre 3 eventos TLS
        # totales dentro de la misma ventana de 60s -> ratio = 1/3 (ni 0.0 ni 1.0).
        network = ipaddress.ip_network("10.20.0.0/24")
        events = [
            {
                "timestamp": iso_timestamp(5001.0),
                "event_type": "tls",
                "src_ip": self.client,
                "dest_ip": self.server,
                "tls": {},
            },
            {
                "timestamp": iso_timestamp(5001.1),
                "event_type": "tls",
                "src_ip": self.client,
                "dest_ip": self.server,
                "tls": {"version": "TLS 1.2"},
            },
            {
                "timestamp": iso_timestamp(5001.2),
                "event_type": "tls",
                "src_ip": self.client,
                "dest_ip": self.server,
                "tls": {"version": "TLS 1.3"},
            },
        ]
        eve_path = self.directory / "tls_partial.jsonl"
        eve_path.write_text("".join(json.dumps(item) + "\n" for item in events), encoding="utf-8")

        apps = extractor.load_app_observations(eve_path, network)
        rows = extractor.build_rows("TLS-PARTIAL", [], apps)
        self.assertEqual(len(rows), 1)
        row = rows[0]
        self.assertEqual(row["tls_observation_count_60s"], 3)
        self.assertAlmostEqual(row["tls_handshake_failure_ratio_60s"], 1 / 3)

    def test_missing_signals_degrade_to_zero(self) -> None:
        network = ipaddress.ip_network("10.20.0.0/24")
        empty_dir = Path(self.tempdir.name) / "empty"
        empty_dir.mkdir()
        empty_pcap = empty_dir / "empty.pcap"
        write_pcap(empty_pcap, [])
        empty_eve = empty_dir / "empty.jsonl"
        empty_eve.write_text("", encoding="utf-8")

        packets = extractor.load_packet_observations([empty_pcap], network)
        apps = extractor.load_app_observations(empty_eve, network)
        self.assertEqual(packets, [])
        self.assertEqual(apps, [])
        self.assertEqual(extractor.build_rows("EMPTY", packets, apps), [])


if __name__ == "__main__":
    unittest.main()
