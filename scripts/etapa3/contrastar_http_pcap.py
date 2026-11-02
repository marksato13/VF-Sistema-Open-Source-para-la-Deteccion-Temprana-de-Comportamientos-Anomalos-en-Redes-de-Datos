#!/usr/bin/env python3
"""Etapa 3: ¿las ráfagas HTTP del EVE tienen paquetes en el cable en ese intervalo?

Para cada ráfaga de http_no_registrado.py, cuenta en el archivo PCAP (rotado, SPAN) los
paquetes TCP del origen al puerto de la ráfaga dentro de [inicio, fin], los SYN y los
segmentos con datos. Si el EVE registra peticiones pero el cable no tiene tráfico, los
eventos son registros tardíos de flujos anteriores (con la marca de otro paquete), no
actividad del origen en ese intervalo.

Uso: python contrastar_http_pcap.py rafagas.json dir-pcap salida.json [--origen 10.10.20.30]
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "engine"))
from detector_rapido import LectorPcap, tcp_de_trama  # noqa: E402


def iso(s):
    return dt.datetime.fromisoformat(s).timestamp()


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("rafagas", type=Path)
    ap.add_argument("pcap", type=Path)
    ap.add_argument("salida", type=Path)
    ap.add_argument("--origen", default="10.10.20.30")
    a = ap.parse_args()
    raf = json.loads(a.rafagas.read_text(encoding="utf-8"))
    ficheros = sorted(a.pcap.glob("live-*.pcap"))
    marcas = [dt.datetime.strptime(f.stem[5:], "%Y%m%d%H%M%S").replace(tzinfo=dt.timezone.utc).timestamp()
              for f in ficheros]
    out = []
    for r in raf:
        t0, t1 = iso(r["inicio"]), iso(r["fin"])
        puerto = r["puerto"][0][0]
        n = syn = datos = 0
        primeros = []
        for f, m in zip(ficheros, marcas):
            if m > t1 or m < t0 - 20:
                continue
            with f.open("rb") as fh:
                lp = LectorPcap(fh)
                while True:
                    x = lp.siguiente()
                    if x is None:
                        break
                    t, fr = x
                    if not t0 <= t <= t1:
                        continue
                    p = tcp_de_trama(fr)
                    if not p or p[0] != a.origen or p[3] != puerto:
                        continue
                    n += 1
                    syn += bool(p[4] & 0x02 and not p[4] & 0x10)
                    datos += p[6] > 52 if len(p) > 6 else 0
                    if len(primeros) < 3:
                        primeros.append(round(t - t0, 3))
        r2 = {"inicio": r["inicio"], "fin": r["fin"], "peticiones_eve": r["peticiones"], "episodios": r["episodios"],
              "puerto": puerto, "paquetes_cable": n, "syn_cable": syn, "primeros_s": primeros}
        out.append(r2)
        print(r["inicio"][11:19], r["fin"][11:19], r["episodios"], "eve", r["peticiones"], "cable", n, "syn", syn)
    a.salida.write_text(json.dumps(out, indent=1), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
