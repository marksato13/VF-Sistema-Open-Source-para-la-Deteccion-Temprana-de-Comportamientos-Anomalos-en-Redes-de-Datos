#!/usr/bin/env python3
"""Extrae el vector multicapa-v1 desde PCAP Ethernet/IPv4 y Suricata EVE.

No consume etiquetas ni eventos futuros. Las filas se atribuyen a la IP que
inició cada conversación y se emiten en límites de 10 segundos.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import ipaddress
import json
import math
import socket
import struct
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable, Iterator


FEATURE_NAMES = (
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

METADATA_COLUMNS = (
    "campaign_id",
    "entity_ip",
    "window_end_utc",
    "history_coverage_s",
    "eligible_training",
    "packet_count_10s",
    "flow_attempt_count_30s",
    "syn_count_10s",
    "http_request_count_60s",
    "dns_query_count_60s",
)

TCP_FIN = 0x01
TCP_SYN = 0x02
TCP_RST = 0x04
TCP_ACK = 0x10


@dataclass(frozen=True)
class ParsedPacket:
    timestamp: float
    src_ip: str
    dst_ip: str
    ip_length: int
    protocol: int
    src_port: int = 0
    dst_port: int = 0
    tcp_flags: int = 0
    icmp_type: int = -1
    icmp_id: int = 0


@dataclass(frozen=True)
class PacketObservation:
    timestamp: float
    entity_ip: str
    peer_ip: str
    ip_length: int
    protocol: int
    target_port: int
    flow_attempt: bool
    outbound: bool
    syn: bool
    syn_ack: bool
    rst: bool


@dataclass(frozen=True)
class AppObservation:
    timestamp: float
    entity_ip: str
    kind: str
    error: bool = False
    event_key: str = ""


def parse_eve_timestamp(value: str) -> float:
    normalized = value.replace("Z", "+00:00")
    return datetime.fromisoformat(normalized).timestamp()


def _pcap_format(magic: bytes) -> tuple[str, float]:
    formats = {
        b"\xd4\xc3\xb2\xa1": ("<", 1_000_000.0),
        b"\xa1\xb2\xc3\xd4": (">", 1_000_000.0),
        b"\x4d\x3c\xb2\xa1": ("<", 1_000_000_000.0),
        b"\xa1\xb2\x3c\x4d": (">", 1_000_000_000.0),
    }
    if magic not in formats:
        raise ValueError(f"magic PCAP no soportado: {magic.hex()}")
    return formats[magic]


def iter_pcap_frames(path: Path) -> Iterator[tuple[float, bytes]]:
    with path.open("rb") as handle:
        magic = handle.read(4)
        endian, fraction_divisor = _pcap_format(magic)
        global_rest = handle.read(20)
        if len(global_rest) != 20:
            raise ValueError(f"cabecera PCAP truncada: {path}")
        _, _, _, _, _, linktype = struct.unpack(f"{endian}HHIIII", global_rest)
        if linktype != 1:
            raise ValueError(f"solo Ethernet LINKTYPE 1 está soportado; {path} usa {linktype}")

        record_format = struct.Struct(f"{endian}IIII")
        while True:
            record_header = handle.read(record_format.size)
            if not record_header:
                break
            if len(record_header) != record_format.size:
                raise ValueError(f"registro PCAP truncado: {path}")
            seconds, fraction, captured_length, _ = record_format.unpack(record_header)
            frame = handle.read(captured_length)
            if len(frame) != captured_length:
                raise ValueError(f"paquete PCAP truncado: {path}")
            yield seconds + fraction / fraction_divisor, frame


def parse_ethernet_ipv4(timestamp: float, frame: bytes) -> ParsedPacket | None:
    if len(frame) < 14:
        return None
    offset = 14
    ether_type = struct.unpack("!H", frame[12:14])[0]
    while ether_type in (0x8100, 0x88A8):
        if len(frame) < offset + 4:
            return None
        ether_type = struct.unpack("!H", frame[offset + 2 : offset + 4])[0]
        offset += 4
    if ether_type != 0x0800 or len(frame) < offset + 20:
        return None

    version_ihl = frame[offset]
    if version_ihl >> 4 != 4:
        return None
    ip_header_length = (version_ihl & 0x0F) * 4
    if ip_header_length < 20 or len(frame) < offset + ip_header_length:
        return None
    total_length = struct.unpack("!H", frame[offset + 2 : offset + 4])[0]
    protocol = frame[offset + 9]
    src_ip = socket.inet_ntoa(frame[offset + 12 : offset + 16])
    dst_ip = socket.inet_ntoa(frame[offset + 16 : offset + 20])
    transport = offset + ip_header_length

    src_port = dst_port = tcp_flags = icmp_id = 0
    icmp_type = -1
    if protocol == 6 and len(frame) >= transport + 14:
        src_port, dst_port = struct.unpack("!HH", frame[transport : transport + 4])
        tcp_flags = frame[transport + 13]
    elif protocol == 17 and len(frame) >= transport + 8:
        src_port, dst_port = struct.unpack("!HH", frame[transport : transport + 4])
    elif protocol == 1 and len(frame) >= transport + 8:
        icmp_type = frame[transport]
        icmp_id = struct.unpack("!H", frame[transport + 4 : transport + 6])[0]

    return ParsedPacket(
        timestamp=timestamp,
        src_ip=src_ip,
        dst_ip=dst_ip,
        ip_length=total_length,
        protocol=protocol,
        src_port=src_port,
        dst_port=dst_port,
        tcp_flags=tcp_flags,
        icmp_type=icmp_type,
        icmp_id=icmp_id,
    )


def canonical_flow_key(packet: ParsedPacket) -> tuple:
    if packet.protocol in (6, 17):
        endpoints = sorted(((packet.src_ip, packet.src_port), (packet.dst_ip, packet.dst_port)))
        return packet.protocol, endpoints[0], endpoints[1]
    endpoints = sorted((packet.src_ip, packet.dst_ip))
    return packet.protocol, endpoints[0], endpoints[1], packet.icmp_id


def attribute_packets(
    packets: Iterable[ParsedPacket], entity_network: ipaddress.IPv4Network
) -> list[PacketObservation]:
    flow_owners: dict[tuple, tuple[str, str, int]] = {}
    observations: list[PacketObservation] = []

    for packet in sorted(packets, key=lambda item: item.timestamp):
        key = canonical_flow_key(packet)
        is_new = key not in flow_owners
        if is_new:
            entity_ip = packet.src_ip
            peer_ip = packet.dst_ip
            target_port = packet.dst_port
            if packet.protocol == 6 and packet.tcp_flags & TCP_SYN and packet.tcp_flags & TCP_ACK:
                entity_ip, peer_ip, target_port = packet.dst_ip, packet.src_ip, packet.src_port
            elif packet.protocol == 1 and packet.icmp_type == 0:
                entity_ip, peer_ip = packet.dst_ip, packet.src_ip
            flow_owners[key] = (entity_ip, peer_ip, target_port)

        entity_ip, peer_ip, target_port = flow_owners[key]
        try:
            entity_is_in_scope = ipaddress.ip_address(entity_ip) in entity_network
        except ValueError:
            entity_is_in_scope = False
        if not entity_is_in_scope:
            continue

        outbound = packet.src_ip == entity_ip
        syn = bool(
            packet.protocol == 6
            and outbound
            and packet.tcp_flags & TCP_SYN
            and not packet.tcp_flags & TCP_ACK
        )
        syn_ack = bool(
            packet.protocol == 6
            and not outbound
            and packet.tcp_flags & TCP_SYN
            and packet.tcp_flags & TCP_ACK
        )
        observations.append(
            PacketObservation(
                timestamp=packet.timestamp,
                entity_ip=entity_ip,
                peer_ip=peer_ip,
                ip_length=packet.ip_length,
                protocol=packet.protocol,
                target_port=target_port,
                flow_attempt=is_new,
                outbound=outbound,
                syn=syn,
                syn_ack=syn_ack,
                rst=bool(packet.protocol == 6 and packet.tcp_flags & TCP_RST),
            )
        )
    return observations


def load_packet_observations(
    pcap_paths: Iterable[Path], entity_network: ipaddress.IPv4Network
) -> list[PacketObservation]:
    packets: list[ParsedPacket] = []
    for path in pcap_paths:
        for timestamp, frame in iter_pcap_frames(path):
            parsed = parse_ethernet_ipv4(timestamp, frame)
            if parsed is not None:
                packets.append(parsed)
    return attribute_packets(packets, entity_network)


def load_app_observations(
    eve_path: Path, entity_network: ipaddress.IPv4Network
) -> list[AppObservation]:
    observations: list[AppObservation] = []
    with eve_path.open("r", encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            try:
                event = json.loads(line)
            except json.JSONDecodeError as exc:
                raise ValueError(f"EVE inválido en línea {line_number}: {exc}") from exc
            event_type = event.get("event_type")
            if event_type not in {"http", "dns", "tls"}:
                continue
            timestamp_value = event.get("timestamp")
            if not timestamp_value:
                continue
            timestamp = parse_eve_timestamp(timestamp_value)

            if event_type == "http":
                entity_ip = event.get("src_ip", "")
                if _in_scope(entity_ip, entity_network):
                    status = int(event.get("http", {}).get("status", 0) or 0)
                    observations.append(AppObservation(timestamp, entity_ip, "http", status >= 400))
            elif event_type == "dns":
                dns = event.get("dns", {})
                dns_type = dns.get("type")
                if dns_type == "request":
                    entity_ip = event.get("src_ip", "")
                    if _in_scope(entity_ip, entity_network):
                        observations.append(AppObservation(timestamp, entity_ip, "dns_query"))
                elif dns_type == "response":
                    entity_ip = event.get("dest_ip", "")
                    if _in_scope(entity_ip, entity_network) and dns.get("rcode") == "NXDOMAIN":
                        observations.append(AppObservation(timestamp, entity_ip, "dns_nxdomain", True))
            elif event_type == "tls":
                entity_ip = event.get("src_ip", "")
                if not _in_scope(entity_ip, entity_network):
                    entity_ip = event.get("dest_ip", "")
                if _in_scope(entity_ip, entity_network):
                    event_key = str(event.get("flow_id") or event.get("community_id") or timestamp)
                    observations.append(AppObservation(timestamp, entity_ip, "tls", False, event_key))
    return observations


def _in_scope(value: str, network: ipaddress.IPv4Network) -> bool:
    try:
        return ipaddress.ip_address(value) in network
    except ValueError:
        return False


def in_window(timestamp: float, window_end: float, seconds: int) -> bool:
    return window_end - seconds < timestamp <= window_end


def safe_ratio(numerator: float, denominator: float) -> float:
    return numerator / denominator if denominator else 0.0


def build_rows(
    campaign_id: str,
    packets: list[PacketObservation],
    apps: list[AppObservation],
    step_seconds: int = 10,
    capture_start: float | None = None,
) -> list[dict[str, object]]:
    timestamps = [item.timestamp for item in packets] + [item.timestamp for item in apps]
    if not timestamps:
        return []
    first_observation = min(timestamps)
    if capture_start is None:
        capture_start = first_observation
    if capture_start > first_observation:
        raise ValueError("el inicio de captura no puede ser posterior a la primera observación")
    entities = sorted({item.entity_ip for item in packets} | {item.entity_ip for item in apps})
    rows: list[dict[str, object]] = []

    for entity_ip in entities:
        entity_timestamps = [item.timestamp for item in packets if item.entity_ip == entity_ip]
        entity_timestamps += [item.timestamp for item in apps if item.entity_ip == entity_ip]
        first_anchor = (math.floor(min(entity_timestamps) / step_seconds) + 1) * step_seconds
        last_anchor = math.ceil(max(entity_timestamps) / step_seconds) * step_seconds
        anchor = first_anchor
        while anchor <= last_anchor:
            p10 = [item for item in packets if item.entity_ip == entity_ip and in_window(item.timestamp, anchor, 10)]
            attempts10 = [item for item in p10 if item.flow_attempt]
            attempts30 = [
                item
                for item in packets
                if item.entity_ip == entity_ip and item.flow_attempt and in_window(item.timestamp, anchor, 30)
            ]
            transport_attempts30 = [item for item in attempts30 if item.target_port > 0]
            tcp10 = [item for item in p10 if item.protocol == 6]
            syn_count = sum(item.syn for item in p10)
            syn_ack_count = sum(item.syn_ack for item in p10)
            http60 = [item for item in apps if item.entity_ip == entity_ip and item.kind == "http" and in_window(item.timestamp, anchor, 60)]
            dns_queries60 = [item for item in apps if item.entity_ip == entity_ip and item.kind == "dns_query" and in_window(item.timestamp, anchor, 60)]
            dns_nxdomain60 = [item for item in apps if item.entity_ip == entity_ip and item.kind == "dns_nxdomain" and in_window(item.timestamp, anchor, 60)]
            tls60 = [item for item in apps if item.entity_ip == entity_ip and item.kind == "tls" and in_window(item.timestamp, anchor, 60)]
            tls_session_count = len({item.event_key for item in tls60})

            packet_count = len(p10)
            total_bytes = sum(item.ip_length for item in p10)
            history_coverage = max(0.0, min(60.0, anchor - capture_start))
            row: dict[str, object] = {
                "campaign_id": campaign_id,
                "entity_ip": entity_ip,
                "window_end_utc": datetime.fromtimestamp(anchor, timezone.utc).isoformat(),
                "history_coverage_s": round(history_coverage, 6),
                "eligible_training": history_coverage >= 60.0,
                "packet_count_10s": packet_count,
                "flow_attempt_count_30s": len(attempts30),
                "syn_count_10s": syn_count,
                "http_request_count_60s": len(http60),
                "dns_query_count_60s": len(dns_queries60),
                "packet_rate_10s": packet_count / 10.0,
                "byte_rate_10s": total_bytes / 10.0,
                "mean_ip_len_10s": safe_ratio(total_bytes, packet_count),
                "large_ip_ratio_10s": safe_ratio(
                    sum(500 <= item.ip_length <= 1500 for item in p10), packet_count
                ),
                "unique_dst_ip_ratio_30s": safe_ratio(
                    len({item.peer_ip for item in attempts30}), len(attempts30)
                ),
                "icmp_ratio_10s": safe_ratio(sum(item.protocol == 1 for item in p10), packet_count),
                "flow_attempt_rate_10s": len(attempts10) / 10.0,
                "syn_rate_10s": syn_count / 10.0,
                "syn_completion_ratio_10s": safe_ratio(min(syn_count, syn_ack_count), syn_count),
                "rst_ratio_10s": safe_ratio(sum(item.rst for item in tcp10), len(tcp10)),
                "unique_dst_port_ratio_30s": safe_ratio(
                    len({item.target_port for item in transport_attempts30}), len(transport_attempts30)
                ),
                "http_error_ratio_60s": safe_ratio(sum(item.error for item in http60), len(http60)),
                "dns_nxdomain_ratio_60s": safe_ratio(len(dns_nxdomain60), len(dns_queries60)),
                "tls_session_rate_60s": tls_session_count / 60.0,
            }
            rows.append(row)
            anchor += step_seconds
    return rows


def validate_schema(schema_path: Path) -> None:
    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    names = tuple(item["name"] for item in sorted(schema["features"], key=lambda item: item["order"]))
    if names != FEATURE_NAMES:
        raise ValueError("el orden del esquema no coincide con el extractor")


def write_csv(rows: list[dict[str, object]], output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=METADATA_COLUMNS + FEATURE_NAMES)
        writer.writeheader()
        for row in rows:
            normalized = {
                key: f"{value:.8f}" if isinstance(value, float) else value
                for key, value in row.items()
            }
            writer.writerow(normalized)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def parse_args() -> argparse.Namespace:
    repo_root = Path(__file__).resolve().parents[2]
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pcap", type=Path, nargs="+", required=True)
    parser.add_argument("--eve", type=Path, required=True)
    parser.add_argument("--campaign-id", required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument(
        "--schema",
        type=Path,
        default=repo_root / "configs/features/multilayer-v1.json",
    )
    parser.add_argument("--entity-network", default="10.20.0.0/24")
    capture_start = parser.add_mutually_exclusive_group()
    capture_start.add_argument(
        "--pcap-start-json",
        type=Path,
        help="JSON de ppi-pcap-control con verified_at",
    )
    capture_start.add_argument(
        "--capture-start",
        help="límite inferior ISO-8601 verificado de la historia disponible",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    validate_schema(args.schema)
    entity_network = ipaddress.ip_network(args.entity_network)
    packets = load_packet_observations(args.pcap, entity_network)
    apps = load_app_observations(args.eve, entity_network)
    capture_start = None
    if args.pcap_start_json:
        start_record = json.loads(args.pcap_start_json.read_text(encoding="utf-8"))
        if "verified_at" not in start_record:
            raise ValueError("pcap-start.json no contiene verified_at")
        capture_start = parse_eve_timestamp(start_record["verified_at"])
    elif args.capture_start:
        capture_start = parse_eve_timestamp(args.capture_start)
    rows = build_rows(args.campaign_id, packets, apps, capture_start=capture_start)
    write_csv(rows, args.output)
    print(
        json.dumps(
            {
                "schema_version": "multilayer-v1",
                "campaign_id": args.campaign_id,
                "packet_observations": len(packets),
                "application_observations": len(apps),
                "rows": len(rows),
                "eligible_training_rows": sum(bool(row["eligible_training"]) for row in rows),
                "inputs": {
                    "pcap": [
                        {"path": str(path), "sha256": sha256_file(path)} for path in args.pcap
                    ],
                    "eve": {"path": str(args.eve), "sha256": sha256_file(args.eve)},
                    "schema": {"path": str(args.schema), "sha256": sha256_file(args.schema)},
                },
                "output": str(args.output),
                "output_sha256": sha256_file(args.output),
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
