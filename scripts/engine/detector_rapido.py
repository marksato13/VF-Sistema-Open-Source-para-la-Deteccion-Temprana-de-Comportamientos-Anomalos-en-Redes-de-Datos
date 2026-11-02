#!/usr/bin/env python3
"""Proceso de la vía rápida de escaneo (Etapa 3, candidato; NO desplegado).

Dos formas de alimentar ``escaneo_temprano.DetectorEscaneoTemprano``:

- ``--ficheros DIR``: capturas cortas (tcpdump -G R). Procesa cada fichero en cuanto
  está CERRADO (existe uno más nuevo). Tras un fichero que termina en la frontera B
  (marca del nombre del siguiente), avanza el reloj del detector a B: ningún paquete
  con marca <= B puede llegar ya, así que resolver los vencimientos hasta B es causal.
- ``--flujo``: lectura continua de un PCAP por la entrada estándar (tcpdump -U -w -).
  Cada paquete se procesa al leerlo; sin paquetes, cada ``--tic`` s avanza el reloj al
  último instante conocido (no al reloj de pared: no se inventa ausencia de paquetes).

Cada disparo se escribe en ``--salida`` (jsonl, con flush) añadiendo:
  disponible_en: reloj de pared cuando el dato que completa la evidencia estuvo en el
                 detector (lectura del paquete o del fichero cerrado)
  emitido_en:    reloj de pared tras escribir la línea
y en ``--resumen`` las cifras de proceso (paquetes, CPU por fichero o por bloque).

Uso:
  detector_rapido.py --ficheros /var/lib/cf-rapido --salida senales_rapidas.jsonl
  tcpdump -i ens19 -U -w - 'tcp' | detector_rapido.py --flujo --salida senales_rapidas.jsonl
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import select
import struct
import sys
import time
from pathlib import Path

try:
    from scripts.engine.escaneo_temprano import DetectorEscaneoTemprano, SYN, RST
except ImportError:
    from escaneo_temprano import DetectorEscaneoTemprano, SYN, RST

EXCLUIDOS_POR_OMISION = ("10.10.60.11,10.10.10.30,10.10.60.2,10.10.60.3,10.10.60.10,10.10.60.20,"
                         "10.10.60.21,10.10.60.30,10.10.60.40,10.10.60.41,10.10.60.50")


def tcp_de_trama(frame: bytes):
    """(src, dst, sport, dport, flags, seq, iplen) de una trama Ethernet/IPv4/TCP con SYN o RST."""
    if len(frame) < 34:
        return None
    off = 14
    et = (frame[12] << 8) | frame[13]
    while et in (0x8100, 0x88A8):
        if len(frame) < off + 4:
            return None
        et = (frame[off + 2] << 8) | frame[off + 3]
        off += 4
    if et != 0x0800 or len(frame) < off + 20 or frame[off] >> 4 != 4 or frame[off + 9] != 6:
        return None
    tr = off + (frame[off] & 0x0F) * 4
    if len(frame) < tr + 14:
        return None
    flags = frame[tr + 13]
    if not flags & (SYN | RST):
        return None
    src = "%d.%d.%d.%d" % tuple(frame[off + 12:off + 16])
    dst = "%d.%d.%d.%d" % tuple(frame[off + 16:off + 20])
    sport, dport, seq = struct.unpack("!HHI", frame[tr:tr + 8])
    return src, dst, sport, dport, flags, seq, (frame[off + 2] << 8) | frame[off + 3]


class LectorPcap:
    """Lector incremental de formato pcap clásico (fichero o flujo)."""

    def __init__(self, fh) -> None:
        self.fh = fh
        cab = self._exacto(24)
        magic = cab[:4]
        if magic in (b"\xd4\xc3\xb2\xa1", b"\x4d\x3c\xb2\xa1"):
            self.e, self.div = "<", (1e6 if magic == b"\xd4\xc3\xb2\xa1" else 1e9)
        elif magic in (b"\xa1\xb2\xc3\xd4", b"\xa1\xb2\x3c\x4d"):
            self.e, self.div = ">", (1e6 if magic == b"\xa1\xb2\xc3\xd4" else 1e9)
        else:
            raise ValueError("no es pcap clasico")

    def _exacto(self, n: int) -> bytes:
        b = b""
        while len(b) < n:
            x = self.fh.read(n - len(b))
            if not x:
                raise EOFError
            b += x
        return b

    def siguiente(self):
        try:
            cab = self._exacto(16)
        except EOFError:
            return None
        s, us, incl, _ = struct.unpack(self.e + "IIII", cab)
        return s + us / self.div, self._exacto(incl)


def _escribir(salida, d: dict, disponible_en: float) -> None:
    d["disponible_en"] = round(disponible_en, 6)
    d["emitido_en"] = round(time.time(), 6)
    salida.write(json.dumps(d, sort_keys=True) + "\n")
    salida.flush()


def marca_de_nombre(p: Path) -> float | None:
    try:
        return dt.datetime.strptime(p.stem.split("-")[-1], "%Y%m%d%H%M%S").replace(
            tzinfo=dt.timezone.utc).timestamp()
    except ValueError:
        return None


def modo_ficheros(det, d: Path, salida, resumen, patron: str, una_vez: bool, sondeo: float,
                  hasta_vacio_s: float) -> None:
    hechos: set[str] = set()
    ultimo_nuevo = time.time()
    while True:
        fs = sorted(d.glob(patron))
        cerrados = fs[:-1] if not una_vez else fs
        nuevos = [f for f in cerrados if f.name not in hechos]
        for i, f in enumerate(nuevos):
            leido_en = time.time()
            c0 = time.process_time()
            n = 0
            with f.open("rb") as fh:
                lp = LectorPcap(fh)
                while True:
                    x = lp.siguiente()
                    if x is None:
                        break
                    t, frame = x
                    tcp = tcp_de_trama(frame)
                    if tcp is None:
                        continue
                    n += 1
                    for disp in det.observar(t, *tcp):
                        _escribir(salida, disp, time.time())
            # frontera: marca del siguiente fichero (si existe); los paquetes <= ella ya están
            sig = fs[fs.index(f) + 1] if fs.index(f) + 1 < len(fs) else None
            frontera = marca_de_nombre(sig) if sig is not None else None
            if frontera is not None:
                for disp in det.avanzar(frontera):
                    _escribir(salida, disp, time.time())
            det.podar(det.t)
            hechos.add(f.name)
            ultimo_nuevo = time.time()
            if resumen is not None:
                resumen.write(json.dumps({"fichero": f.name, "leido_en": round(leido_en, 6),
                                          "fin_en": round(time.time(), 6), "paquetes_tcp": n,
                                          "cpu_s": round(time.process_time() - c0, 6),
                                          "frontera": frontera}) + "\n")
                resumen.flush()
        if una_vez:
            return
        if hasta_vacio_s and time.time() - ultimo_nuevo > hasta_vacio_s:
            return
        time.sleep(sondeo)


def modo_flujo(det, entrada, salida, resumen, tic: float) -> None:
    fd = entrada.fileno()
    lp = LectorPcap(entrada)
    ultimo_tic = time.time()
    c0 = time.process_time()
    n = 0
    while True:
        r, _, _ = select.select([fd], [], [], tic) if hasattr(select, "select") and os.name != "nt" else ([fd], [], [])
        if r:
            x = lp.siguiente()
            if x is None:
                break
            t, frame = x
            tcp = tcp_de_trama(frame)
            if tcp is not None:
                n += 1
                for disp in det.observar(t, *tcp):
                    _escribir(salida, disp, time.time())
        ahora = time.time()
        if ahora - ultimo_tic >= tic:
            # sin datos nuevos: el reloj del detector avanza solo hasta lo visto (det.t)
            for disp in det.avanzar(det.t):
                _escribir(salida, disp, ahora)
            det.podar(det.t)
            ultimo_tic = ahora
            if resumen is not None:
                resumen.write(json.dumps({"bloque_hasta": round(ahora, 6), "paquetes_tcp": n,
                                          "cpu_s": round(time.process_time() - c0, 6)}) + "\n")
                resumen.flush()


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    g = p.add_mutually_exclusive_group(required=True)
    g.add_argument("--ficheros", type=Path)
    g.add_argument("--flujo", action="store_true")
    p.add_argument("--salida", type=Path, required=True)
    p.add_argument("--resumen", type=Path, default=None)
    p.add_argument("--patron", default="*.pcap")
    p.add_argument("--una-vez", action="store_true", help="ficheros: procesar los existentes y salir")
    p.add_argument("--sondeo", type=float, default=0.05)
    p.add_argument("--hasta-vacio", type=float, default=0.0, help="ficheros: salir tras N s sin ficheros nuevos")
    p.add_argument("--tic", type=float, default=0.05)
    p.add_argument("--red", default="10.10.0.0/16")
    p.add_argument("--excluir", default=EXCLUIDOS_POR_OMISION)
    p.add_argument("-K", type=int, default=None)
    p.add_argument("-W", type=float, default=None)
    p.add_argument("-g", type=float, default=None)
    a = p.parse_args(argv)
    det = DetectorEscaneoTemprano(a.red, frozenset(x for x in a.excluir.split(",") if x), a.K, a.W, a.g)
    resumen = a.resumen.open("a", encoding="utf-8") if a.resumen else None
    with a.salida.open("a", encoding="utf-8") as salida:
        if a.ficheros:
            modo_ficheros(det, a.ficheros, salida, resumen, a.patron, a.una_vez, a.sondeo, a.hasta_vacio)
        else:
            modo_flujo(det, sys.stdin.buffer, salida, resumen, a.tic)
    return 0


if __name__ == "__main__":
    sys.exit(main())
