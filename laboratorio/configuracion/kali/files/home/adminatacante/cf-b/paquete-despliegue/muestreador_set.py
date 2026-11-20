#!/usr/bin/env python3
"""Muestreador de SOLO LECTURA de los sets de nftables de srv-dmz para E2/E5 (serie continua; hoy hay 2 lecturas por episodio). Usa el ayudante con la
operación `listar` (el mismo contrato que `d5_episodio.srv_nft`) y escribe una línea JSONL por muestra: t (epoch), ok, sets {nombre: {ip: valor}}.
Un fallo del ayudante se REGISTRA (`ok: false`), no se oculta. No modifica nada. Uso: muestreador_set.py --salida F.jsonl [--intervalo 2] [--duracion 0]
[--helper "sudo -n /usr/local/sbin/cf-nft-helper"]; se detiene con SIGTERM/SIGINT o al cumplir --duracion."""
import argparse
import json
import shlex
import signal
import subprocess
import sys
import time

PETICION = {"perfil": "dmz", "operaciones": [{"op": "listar"}]}


def listar(orden, correr=subprocess.run):
    try:
        r = correr(list(orden), input=json.dumps(PETICION), capture_output=True, text=True, timeout=10)
        obj = json.loads(r.stdout)
    except (ValueError, OSError, subprocess.TimeoutExpired) as ex:
        return {"ok": False, "error": ex.__class__.__name__}
    if not obj.get("ok"):
        return {"ok": False, "error": str(obj.get("rechazo") or obj.get("error_nft") or "listar falló")[:120]}
    sets = (obj.get("estado") or {}).get("sets") or {}
    return {"ok": True, "sets": {k: (dict(v) if v else {}) for k, v in sets.items()}}


def muestrear(orden, salida, intervalo=2.0, duracion=0.0, ahora=time.time, dormir=time.sleep, parar=lambda: False, correr=subprocess.run):
    t_fin = ahora() + duracion if duracion else None
    n = 0
    with open(salida, "a", encoding="utf-8", buffering=1) as fh:
        while not parar() and (t_fin is None or ahora() < t_fin):
            t = ahora()
            fh.write(json.dumps(dict(listar(orden, correr), t=t), sort_keys=True) + "\n")
            n += 1
            dormir(max(0.0, intervalo - (ahora() - t)))
    return n


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--salida", required=True)
    p.add_argument("--intervalo", type=float, default=2.0)
    p.add_argument("--duracion", type=float, default=0.0)
    p.add_argument("--helper", default="sudo -n /usr/local/sbin/cf-nft-helper")
    a = p.parse_args(argv)
    stop = {"v": False}
    for s in (signal.SIGTERM, signal.SIGINT):
        signal.signal(s, lambda *_: stop.update(v=True))
    muestrear(shlex.split(a.helper), a.salida, a.intervalo, a.duracion, parar=lambda: stop["v"])
    return 0


if __name__ == "__main__":
    sys.exit(main())
