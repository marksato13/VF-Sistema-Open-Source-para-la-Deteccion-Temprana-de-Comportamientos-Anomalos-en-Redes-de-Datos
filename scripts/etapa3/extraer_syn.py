#!/usr/bin/env python3
"""Etapa 3: tabla de intentos TCP (SYN) por par origen→destino de un archivo PCAP.

Una sola lectura del PCAP. Para cada SYN puro (SYN sin ACK) de un origen de la red de
entidades guarda (t_syn, puerto destino, t_respuesta, tipo de respuesta), con:

- copias del espejo SPAN: misma trama (5-tupla, flags, seq, longitud IP) en < 5 ms -> una
- retransmisiones: mismo (origen, puerto origen, destino, puerto destino, seq) -> un intento
- respuesta: primer SYN-ACK (completado) o RST (rechazado) del destino para ese intento,
  con su instante; el evaluador solo la usa si llegó antes del instante evaluado.

Salida: JSON comprimido {par: [[t_syn, dport, t_resp|null, "SA"|"R"|null], ...]} y las
estadísticas de lectura (tramas, SYN, tiempo de CPU) para el presupuesto de la vía rápida.

Uso: python extraer_syn.py dir-pcap salida.json.gz [--red 10.10.0.0/16] [--desde iso] [--hasta iso]
"""
from __future__ import annotations

import argparse
import datetime as dt
import gzip
import ipaddress
import json
import socket
import struct
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "features"))
import extract_multilayer_v2 as v2  # noqa: E402

SYN, ACK, RST = 0x02, 0x10, 0x04


def tcp_rapido(frame: bytes):
    """(src, dst, sport, dport, flags, seq, iplen) de una trama TCP/IPv4, o None (rápido)."""
    if len(frame) < 34:
        return None
    off = 14
    et = (frame[12] << 8) | frame[13]
    while et in (0x8100, 0x88A8):
        et = (frame[off + 2] << 8) | frame[off + 3]
        off += 4
    if et != 0x0800 or len(frame) < off + 20 or frame[off] >> 4 != 4 or frame[off + 9] != 6:
        return None
    ihl = (frame[off] & 0x0F) * 4
    tr = off + ihl
    if len(frame) < tr + 14:
        return None
    flags = frame[tr + 13]
    if not flags & (SYN | RST):
        return None
    src = socket.inet_ntoa(frame[off + 12:off + 16])
    dst = socket.inet_ntoa(frame[off + 16:off + 20])
    sport, dport = struct.unpack("!HH", frame[tr:tr + 4])
    seq = struct.unpack("!I", frame[tr + 4:tr + 8])[0]
    iplen = (frame[off + 2] << 8) | frame[off + 3]
    return src, dst, sport, dport, flags, seq, iplen


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("pcap_dir", type=Path)
    ap.add_argument("salida", type=Path)
    ap.add_argument("--red", default="10.10.0.0/16")
    ap.add_argument("--desde", default="")
    ap.add_argument("--hasta", default="")
    a = ap.parse_args()
    red = ipaddress.ip_network(a.red)
    en_red: dict[str, bool] = {}

    def dentro(ip: str) -> bool:
        r = en_red.get(ip)
        if r is None:
            r = en_red[ip] = ipaddress.ip_address(ip) in red
        return r

    t_desde = dt.datetime.fromisoformat(a.desde.replace("Z", "+00:00")).timestamp() if a.desde else 0
    t_hasta = dt.datetime.fromisoformat(a.hasta.replace("Z", "+00:00")).timestamp() if a.hasta else 1e12
    intentos: dict[str, list] = {}
    abiertos: dict[tuple, list] = {}       # (src,sport,dst,dport) -> registro del ultimo intento
    vistos_seq: set[tuple] = set()
    ultima_copia: dict[tuple, float] = {}
    n_tramas = n_syn = n_copias = n_retrans = 0
    c0 = time.process_time()
    ficheros = sorted(a.pcap_dir.glob("live-*.pcap"))
    for f in ficheros:
        for t, frame in v2.iter_pcap_frames(f):
            n_tramas += 1
            if t < t_desde or t > t_hasta:
                continue
            x = tcp_rapido(frame)
            if x is None:
                continue
            src, dst, sport, dport, flags, seq, iplen = x
            kc = x
            t0 = ultima_copia.get(kc)
            ultima_copia[kc] = t
            if t0 is not None and t - t0 < 0.005:
                n_copias += 1
                continue
            if flags & SYN and not flags & ACK:
                if not dentro(src):
                    continue
                k = (src, sport, dst, dport, seq)
                if k in vistos_seq:
                    n_retrans += 1
                    continue
                vistos_seq.add(k)
                n_syn += 1
                reg = [round(t, 6), dport, None, None]
                intentos.setdefault(src + ">" + dst, []).append(reg)
                abiertos[(src, sport, dst, dport)] = reg
            else:
                # respuesta del destino al intento (src,sport)->(dst,dport): viene de dst a src
                reg = abiertos.get((dst, dport, src, sport))
                if reg is not None and reg[2] is None and t >= reg[0]:
                    if flags & SYN and flags & ACK:
                        reg[2], reg[3] = round(t, 6), "SA"
                    elif flags & RST:
                        reg[2], reg[3] = round(t, 6), "R"
        # higiene de memoria: copias de más de 1 s ya no pueden coincidir
        if len(ultima_copia) > 2_000_000:
            ultima_copia.clear()
    cpu = time.process_time() - c0
    est = {"ficheros": len(ficheros), "tramas": n_tramas, "syn_intentos": n_syn,
           "copias_span_descartadas": n_copias, "retransmisiones_syn": n_retrans,
           "pares": len(intentos), "cpu_s": round(cpu, 2)}
    with gzip.open(a.salida, "wt", encoding="utf-8") as fh:
        json.dump({"estadisticas": est, "intentos": intentos}, fh)
    print(json.dumps(est))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
