#!/usr/bin/env python3
"""[SENSOR1 m4rk] Lectura de cada PCAP del anillo en cuanto se cierra (O2/O3, S2/S3 de E-carga). SOLO LECTURA.

VERSION 2026-11-06.2. Sustituye al obs_pcap.py de la observación del 06-nov, que tenía la hora de fin escrita a mano
como epoch y con un comentario distinto (1793945490 = 06:11:30Z, comentado como 05:51:30Z).

Ahora el fin se da DOS veces, en epoch y en ISO UTC, y deben coincidir al segundo; si no, rc 2 y no lee nada.
  obs_pcap.py --dir /var/lib/ppi-motor-capture --salida DIR --hasta-epoch E --hasta-iso 2026-11-09T04:16:00Z
              [--margen 30] [--en-seco]
--en-seco: comprueba los argumentos, imprime el fin calculado (epoch, UTC y Perú) y el tiempo que falta, y sale sin
leer el anillo. Es la comprobación en seco previa exigida por PROTOCOLO-CARGA-v2 §3.5.

Por fichero cerrado (ya existe uno más nuevo): cabecera global, todos los registros completos, primer y último
instante. Una línea JSON por fichero en DIR/pcap.jsonl. Sigue hasta hasta-epoch + margen y hace una pasada final.
"""
import argparse
import datetime as dt
import json
import os
import struct
import sys
import time

VERSION = "2026-11-06.2"
PERU = dt.timezone(dt.timedelta(hours=-5))


def leer(p):
    r = {"fichero": os.path.basename(p)}
    try:
        with open(p, "rb") as f:
            b = f.read()
    except OSError as e:
        r["error"] = f"lectura: {e}"
        return r
    r["bytes"] = len(b)
    if len(b) < 24:
        r["error"] = "cabecera global incompleta"
        return r
    magic = b[:4]
    if magic in (b"\xd4\xc3\xb2\xa1", b"\x4d\x3c\xb2\xa1"):
        e = "<"
    elif magic in (b"\xa1\xb2\xc3\xd4", b"\xa1\xb2\x3c\x4d"):
        e = ">"
    else:
        r["error"] = "magic desconocido"
        return r
    div = 1e9 if magic in (b"\x4d\x3c\xb2\xa1", b"\xa1\xb2\x3c\x4d") else 1e6
    i, n, t0, t1 = 24, 0, None, None
    while i < len(b):
        if i + 16 > len(b):
            r["error"] = f"cabecera de registro incompleta en {i}"
            break
        s, us, incl, _orig = struct.unpack(e + "IIII", b[i:i + 16])
        if i + 16 + incl > len(b):
            r["error"] = f"registro incompleto en {i}"
            break
        t = s + us / div
        t0 = t if t0 is None else t0
        t1 = t
        n += 1
        i += 16 + incl
    r.update(registros=n, primero=t0, ultimo=t1)
    return r


def fin_comprobado(epoch, iso):
    """Epoch del fin si epoch e ISO (UTC, sufijo Z) coinciden al segundo; ValueError si no."""
    if not iso.endswith("Z"):
        raise ValueError(f"--hasta-iso debe ser UTC con sufijo Z: {iso!r}")
    t = dt.datetime.strptime(iso, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=dt.timezone.utc).timestamp()
    if abs(t - epoch) >= 1:
        raise ValueError(f"--hasta-epoch {epoch} = {dt.datetime.fromtimestamp(epoch, dt.timezone.utc):%FT%TZ} "
                         f"no coincide con --hasta-iso {iso}")
    return float(epoch)


def pasada(d, salida, vistos):
    fs = sorted(x for x in os.listdir(d) if x.startswith("live-") and x.endswith(".pcap"))
    nuevos = 0
    with open(salida, "a", encoding="utf-8") as out:
        for x in fs[:-1]:            # el último sigue abierto
            if x in vistos:
                continue
            r = leer(os.path.join(d, x))
            r["leido_en"] = time.time()
            out.write(json.dumps(r) + "\n")
            vistos.add(x)
            nuevos += 1
    return nuevos


def main(argv=None, reloj=time.time, dormir=time.sleep):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--dir", required=True)
    ap.add_argument("--salida", required=True)
    ap.add_argument("--hasta-epoch", type=float, required=True)
    ap.add_argument("--hasta-iso", required=True)
    ap.add_argument("--margen", type=float, default=30.0)
    ap.add_argument("--intervalo", type=float, default=30.0)
    ap.add_argument("--en-seco", action="store_true")
    a = ap.parse_args(argv)
    try:
        fin = fin_comprobado(a.hasta_epoch, a.hasta_iso)
    except ValueError as e:
        print(f"ERROR {e}", file=sys.stderr)
        return 2
    u = dt.datetime.fromtimestamp(fin, dt.timezone.utc)
    info = {"version": VERSION, "fin_epoch": fin, "fin_utc": f"{u:%FT%TZ}",
            "fin_peru": f"{u.astimezone(PERU):%F %T} (UTC-5)", "parada_epoch": fin + a.margen,
            "faltan_s": round(fin - reloj(), 1)}
    if a.en_seco:
        info["en_seco"] = True
        info["dir_existe"] = os.path.isdir(a.dir)
        print(json.dumps(info, ensure_ascii=False))
        return 0 if info["dir_existe"] else 2
    os.makedirs(a.salida, exist_ok=True)
    salida = os.path.join(a.salida, "pcap.jsonl")
    vistos = set()
    if os.path.exists(salida):
        with open(salida, encoding="utf-8") as f:
            vistos = {json.loads(l)["fichero"] for l in f if l.strip()}
    while reloj() <= fin + a.margen:
        pasada(a.dir, salida, vistos)
        dormir(a.intervalo)
    pasada(a.dir, salida, vistos)
    info["terminado_en"] = reloj()
    print(json.dumps(info, ensure_ascii=False), file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
