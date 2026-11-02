#!/usr/bin/env python3
"""Alternativa B de la vía rápida (Etapa 3, SOLO banco/ensayo): alertas de Suricata -> senal_rapida.

Sigue un eve.json y convierte cada alerta de las firmas de escaneo temprano de CyberFlow
(sid 9100001-9100099) en una línea ``senal_rapida`` con el mismo formato que
``detector_rapido.py``, para que el publicador la trate igual. NO se activa en Sensor1.

  t_evidencia:   marca del paquete que dispara la alerta (campo timestamp del EVE)
  disponible_en: reloj de pared al leer la línea del EVE
  emitido_en:    reloj de pared tras escribir la señal

Uso: suricata_a_senal.py --eve eve.json --salida senales_rapidas.jsonl [--hasta-vacio N]
"""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import sys
import time
from pathlib import Path

SID_MIN, SID_MAX = 9100001, 9100099


def _t(s: str) -> float:
    return dt.datetime.strptime(s[:26] + s[-5:], "%Y-%m-%dT%H:%M:%S.%f%z").timestamp() \
        if len(s) > 26 else dt.datetime.fromisoformat(s).timestamp()


def convertir(ev: dict) -> dict | None:
    if ev.get("event_type") != "alert":
        return None
    sid = int((ev.get("alert") or {}).get("signature_id") or 0)
    if not SID_MIN <= sid <= SID_MAX:
        return None
    t = _t(ev["timestamp"])
    src, dst = ev.get("src_ip"), ev.get("dest_ip")
    return {"event": "senal_rapida", "regla": "port_scan_temprano", "via": "suricata",
            "version": "suricata-sid-%d" % sid,
            "id": hashlib.sha256(("%s>%s|%.6f|%d" % (src, dst, t, sid)).encode()).hexdigest()[:16],
            "origen": src, "destino": dst, "t_evidencia": round(t, 6), "primer_intento_ventana": None,
            "puertos_fallidos": None, "muestra_puertos": [ev.get("dest_port")],
            "firma": (ev.get("alert") or {}).get("signature"), "parametros": {"sid": sid}}


def main(argv=None) -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--eve", type=Path, required=True)
    p.add_argument("--salida", type=Path, required=True)
    p.add_argument("--sondeo", type=float, default=0.02)
    p.add_argument("--hasta-vacio", type=float, default=0.0)
    a = p.parse_args(argv)
    off, resto, ultimo = 0, b"", time.time()
    with a.salida.open("a", encoding="utf-8") as out:
        while True:
            try:
                with a.eve.open("rb") as fh:
                    fh.seek(off)
                    datos = fh.read()
            except FileNotFoundError:
                datos = b""
            if datos:
                off += len(datos)
                ultimo = time.time()
                lineas = (resto + datos).split(b"\n")
                resto = lineas.pop()
                leido = time.time()
                for l in lineas:
                    try:
                        s = convertir(json.loads(l))
                    except ValueError:
                        continue
                    if s:
                        s["disponible_en"] = round(leido, 6)
                        s["emitido_en"] = round(time.time(), 6)
                        out.write(json.dumps(s, sort_keys=True) + "\n")
                        out.flush()
            elif a.hasta_vacio and time.time() - ultimo > a.hasta_vacio:
                return 0
            time.sleep(a.sondeo)


if __name__ == "__main__":
    sys.exit(main())
