#!/usr/bin/env python3
"""Auditoría estrictamente de solo lectura para un disco nuevo de evidencias."""

from __future__ import annotations

import argparse
import json
import os
import stat
import subprocess
from pathlib import Path
from typing import Any


GIB = 1024**3


def populated_mountpoints(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        return [value] if value else []
    if isinstance(value, list):
        return [item for item in value if isinstance(item, str) and item]
    return [str(value)]


def assess_device(
    record: dict[str, Any],
    *,
    requested: str,
    resolved: str,
    root_disk: str,
    minimum_bytes: int,
    signatures: list[str] | None = None,
) -> dict[str, Any]:
    children = record.get("children") or []
    mounts = populated_mountpoints(record.get("mountpoints"))
    signature_list = signatures or []
    size = record.get("size")
    checks = {
        "stable_device_path": (
            requested.startswith("/dev/disk/by-id/")
            or requested.startswith("/dev/disk/by-path/")
        ) and "-part" not in Path(requested).name,
        "is_whole_disk": record.get("type") == "disk",
        "is_not_root_disk": os.path.realpath(resolved) != os.path.realpath(root_disk),
        "minimum_size": isinstance(size, int) and not isinstance(size, bool) and size >= minimum_bytes,
        "has_no_partitions": isinstance(children, list) and len(children) == 0,
        "has_no_filesystem": not bool(record.get("fstype")),
        "is_not_mounted": len(mounts) == 0,
        "has_no_signatures": len(signature_list) == 0,
    }
    labels = {
        "stable_device_path": "la ruta no es by-id/by-path o identifica una partición",
        "is_whole_disk": "el destino no es un disco completo",
        "is_not_root_disk": "el destino corresponde al disco raíz",
        "minimum_size": f"el disco es menor que {minimum_bytes} bytes",
        "has_no_partitions": "el disco ya contiene particiones",
        "has_no_filesystem": "el disco ya contiene un sistema de archivos",
        "is_not_mounted": "el disco está montado",
        "has_no_signatures": "wipefs detectó firmas existentes",
    }
    errors = [labels[name] for name, passed in checks.items() if not passed]
    return {
        "schema_version": "evidence-disk-audit-v1",
        "eligible_new_disk": not errors,
        "device_requested": requested,
        "device_resolved": resolved,
        "root_disk_resolved": root_disk,
        "size_bytes": size,
        "minimum_bytes": minimum_bytes,
        "filesystem": record.get("fstype"),
        "mountpoints": mounts,
        "signatures": signature_list,
        "checks": checks,
        "errors": errors,
    }


def run(*argv: str) -> str:
    return subprocess.check_output(argv, text=True, stderr=subprocess.STDOUT).strip()


def disk_paths(nodes: list[dict[str, Any]]) -> set[str]:
    disks: set[str] = set()
    for node in nodes:
        if node.get("type") == "disk" and isinstance(node.get("path"), str):
            disks.add(os.path.realpath(node["path"]))
        children = node.get("children") or []
        if isinstance(children, list):
            disks.update(disk_paths(children))
    return disks


def root_backing_disk() -> str:
    source = run("findmnt", "--noheadings", "--output", "SOURCE", "--target", "/")
    topology = json.loads(
        run(
            "lsblk", "--json", "--tree", "--inverse", "--paths",
            "--output", "PATH,TYPE", source,
        )
    )
    disks = disk_paths(topology.get("blockdevices", []))
    if len(disks) != 1:
        raise ValueError(
            f"la raíz debe resolver a exactamente un disco físico; encontrados={sorted(disks)}"
        )
    return disks.pop()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Comprueba sin escribir si un dispositivo es apto como disco nuevo de evidencias."
    )
    parser.add_argument(
        "--device",
        required=True,
        help="Ruta estable de disco completo /dev/disk/by-id/... o /dev/disk/by-path/...",
    )
    parser.add_argument("--minimum-gib", type=int, default=100)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    requested = args.device
    if args.minimum_gib < 100:
        raise SystemExit("ERROR: --minimum-gib no puede ser menor que 100")

    preliminary: dict[str, Any] = {
        "schema_version": "evidence-disk-audit-v1",
        "eligible_new_disk": False,
        "device_requested": requested,
        "errors": [],
    }
    path = Path(requested)
    stable_prefix = requested.startswith("/dev/disk/by-id/") or requested.startswith(
        "/dev/disk/by-path/"
    )
    if not stable_prefix or "-part" in path.name:
        preliminary["errors"].append(
            "se exige una ruta de disco completo /dev/disk/by-id/... o /dev/disk/by-path/..."
        )
        print(json.dumps(preliminary, indent=2, sort_keys=True))
        return 3
    if not path.is_symlink():
        preliminary["errors"].append("la ruta estable no existe o no es un enlace simbólico")
        print(json.dumps(preliminary, indent=2, sort_keys=True))
        return 3

    resolved = os.path.realpath(requested)
    try:
        mode = os.stat(resolved).st_mode
    except OSError as exc:
        preliminary["errors"].append(f"no se puede inspeccionar el dispositivo: {exc}")
        print(json.dumps(preliminary, indent=2, sort_keys=True))
        return 3
    if not stat.S_ISBLK(mode):
        preliminary["errors"].append("el enlace no resuelve a un dispositivo de bloque")
        print(json.dumps(preliminary, indent=2, sort_keys=True))
        return 3

    try:
        lsblk = json.loads(
            run(
                "lsblk", "--json", "--tree", "--bytes", "--paths",
                "--output", "PATH,TYPE,SIZE,FSTYPE,MOUNTPOINTS", resolved,
            )
        )
        devices = lsblk.get("blockdevices", [])
        if len(devices) != 1:
            raise ValueError("lsblk no devolvió un único dispositivo raíz")
        signature_output = run("wipefs", "--noheadings", "--output", "TYPE", resolved)
        signatures = [line.strip() for line in signature_output.splitlines() if line.strip()]
        report = assess_device(
            devices[0],
            requested=requested,
            resolved=resolved,
            root_disk=root_backing_disk(),
            minimum_bytes=args.minimum_gib * GIB,
            signatures=signatures,
        )
    except (OSError, subprocess.CalledProcessError, json.JSONDecodeError, ValueError) as exc:
        preliminary["errors"].append(f"falló la auditoría de lectura: {exc}")
        print(json.dumps(preliminary, indent=2, sort_keys=True))
        return 3

    print(json.dumps(report, indent=2, sort_keys=True))
    return 0 if report["eligible_new_disk"] else 3


if __name__ == "__main__":
    raise SystemExit(main())
