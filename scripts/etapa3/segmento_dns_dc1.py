#!/usr/bin/env python3
"""Segmento para el banco del LIMIT DNS (Etapa 3): solo las consultas UDP/53 hacia un
resolvedor, sin etiqueta 802.1Q y sin las copias del espejo SPAN.

En el cable del sensor cada consulta aparece dos veces (VLAN de origen y de destino);
el resolvedor real la recibe una sola vez. Se considera copia la trama con la misma
cabecera IP y carga UDP en menos de ``--copia-s`` (5 ms), como en la vista DNS. Los
reintentos (> 5 ms) se conservan.

Escribe el PCAP y, al lado, ``<salida>.json`` con las consultas por origen.

Uso: segmento_dns_dc1.py dir-pcap desde_iso hasta_iso salida.pcap [--resolvedor 10.10.10.20]
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import struct
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "features"))
import extract_multilayer_v2 as v2  # noqa: E402


def ts(s: str) -> float:
    return dt.datetime.fromisoformat(s.replace("Z", "+00:00")).timestamp()


def sin_vlan(fr: bytes) -> bytes | None:
    """Trama Ethernet sin etiquetas 802.1Q; None si no es IPv4."""
    eth = fr[12:14]
    cuerpo = fr[14:]
    cab = fr[:12]
    while eth in (b"\x81\x00", b"\x88\xa8"):
        eth, cuerpo = cuerpo[2:4], cuerpo[4:]
    if eth != b"\x08\x00":
        return None
    return cab + eth + cuerpo


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("dir_pcap", type=Path)
    p.add_argument("desde")
    p.add_argument("hasta")
    p.add_argument("salida", type=Path)
    p.add_argument("--resolvedor", default="10.10.10.20")
    p.add_argument("--copia-s", type=float, default=0.005)
    a = p.parse_args()
    desde, hasta = ts(a.desde), ts(a.hasta)
    dst = bytes(int(x) for x in a.resolvedor.split("."))
    filas = []
    for f in sorted(a.dir_pcap.glob("live-*.pcap")):
        st = dt.datetime.strptime(f.stem[5:], "%Y%m%d%H%M%S").replace(tzinfo=dt.timezone.utc).timestamp()
        if st > hasta or st < desde - 900:
            continue
        for t, fr in v2.iter_pcap_frames(f):
            if not desde <= t <= hasta:
                continue
            e = sin_vlan(fr)
            if e is None:
                continue
            ip = e[14:]
            if len(ip) < 28 or ip[9] != 17 or ip[16:20] != dst:
                continue
            ihl = (ip[0] & 0x0F) * 4
            if struct.unpack("!H", ip[ihl + 2:ihl + 4])[0] != 53:
                continue
            filas.append((t, e, ip))
    filas.sort(key=lambda x: x[0])
    vistas: dict[bytes, float] = {}
    por_origen, copias, n = Counter(), 0, 0
    with a.salida.open("wb") as out:
        out.write(struct.pack("<IHHiIII", 0xA1B2C3D4, 2, 4, 0, 0, 262144, 1))
        for t, e, ip in filas:
            ihl = (ip[0] & 0x0F) * 4
            # clave: IP sin TTL ni checksum (cambian al enrutar entre VLAN) + UDP completo
            clave = ip[:8] + ip[9:10] + ip[12:20] + ip[ihl:]
            t0 = vistas.get(clave)
            if t0 is not None and t - t0 < a.copia_s:
                copias += 1
                continue
            vistas[clave] = t
            s = int(t)
            us = int(round((t - s) * 1e6))
            if us >= 1000000:
                s, us = s + 1, us - 1000000
            out.write(struct.pack("<IIII", s, us, len(e), len(e)) + e)
            por_origen[".".join(str(b) for b in ip[12:16])] += 1
            n += 1
    json.dump({"desde": a.desde, "hasta": a.hasta, "resolvedor": a.resolvedor, "consultas": n,
               "copias_descartadas": copias, "por_origen": dict(por_origen)},
              open(str(a.salida) + ".json", "w"), indent=1)
    print(a.salida.name, n, "consultas;", copias, "copias;", dict(por_origen))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
