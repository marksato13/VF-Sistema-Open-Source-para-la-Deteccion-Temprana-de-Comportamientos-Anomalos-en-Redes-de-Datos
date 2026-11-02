#!/usr/bin/env python3
"""Escribe un PCAP con TODAS las tramas de un archivo rotado entre dos instantes (para el banco).

Uso: python segmento_pcap.py dir-pcap desde_iso hasta_iso salida.pcap
"""
from __future__ import annotations

import datetime as dt
import struct
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "features"))
import extract_multilayer_v2 as v2  # noqa: E402


def ts(s: str) -> float:
    return dt.datetime.fromisoformat(s.replace("Z", "+00:00")).timestamp()


def main() -> int:
    d, desde, hasta, salida = Path(sys.argv[1]), ts(sys.argv[2]), ts(sys.argv[3]), Path(sys.argv[4])
    n = 0
    with salida.open("wb") as out:
        out.write(struct.pack("<IHHiIII", 0xA1B2C3D4, 2, 4, 0, 0, 262144, 1))
        filas = []
        for f in sorted(d.glob("live-*.pcap")):
            st = dt.datetime.strptime(f.stem[5:], "%Y%m%d%H%M%S").replace(tzinfo=dt.timezone.utc).timestamp()
            if st > hasta or st < desde - 900:
                continue
            for t, fr in v2.iter_pcap_frames(f):
                if desde <= t <= hasta:
                    filas.append((t, fr))
        filas.sort(key=lambda x: x[0])
        for t, fr in filas:
            s = int(t)
            us = int(round((t - s) * 1e6))
            if us >= 1000000:
                s, us = s + 1, us - 1000000
            out.write(struct.pack("<IIII", s, us, len(fr), len(fr)) + fr)
            n += 1
    print(salida.name, n)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
