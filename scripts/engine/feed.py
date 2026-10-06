#!/usr/bin/env python3
"""Feed de enforcement: la lista firmada que el sensor publica y los hosts aplican.

Modelo "un feed / N agentes (pull)": el sensor NO tiene credenciales de los hosts;
publica una lista **firmada** y cada host la trae, verifica y aplica en su propio
kernel. Ver DISENO-ENFORCEMENT.md §2.

Firma: **ed25519 vía openssl** (asimétrico; el sensor firma con la clave privada,
los hosts verifican con la pública). Se usa openssl y no una librería de Python
para no añadir dependencias al entorno congelado del modelo — mismo criterio que el
certificado del panel.

Formato del feed (JSON canónico, `sort_keys`):
    {
      "version": 1,
      "generado": <epoch>,
      "umbrales": "<version de heuristicos>",
      "entradas": [
        {"ip": "...", "accion": "LIMIT|BLOCK", "hasta": <epoch>,
         "alcance": "all"|["host",...], "motivo": "...", "detector": "..."},
        ...
      ]
    }
"""
from __future__ import annotations

import json
import os
import subprocess
import tempfile
import time

VERSION_FEED = 1


def construir(entradas: list[dict], ahora: float | None = None,
              umbrales: str = "") -> dict:
    """Ensambla el feed. Cada entrada ya trae ip/accion/hasta/alcance/motivo."""
    return {
        "version": VERSION_FEED,
        "generado": ahora if ahora is not None else time.time(),
        "umbrales": umbrales,
        "entradas": sorted(entradas, key=lambda e: (e["ip"], e.get("accion", ""))),
    }


def serializar(feed: dict) -> bytes:
    """JSON canónico (determinista) — lo que se firma y lo que se verifica."""
    return (json.dumps(feed, sort_keys=True, separators=(",", ":")) + "\n").encode("utf-8")


# --- Firma asimétrica con openssl (ed25519) --------------------------------

def generar_claves(priv_path: str, pub_path: str) -> None:
    """Crea el par ed25519 (privada 0600 en el sensor, pública para los hosts)."""
    subprocess.run(["openssl", "genpkey", "-algorithm", "ed25519", "-out", priv_path],
                   check=True, capture_output=True)
    os.chmod(priv_path, 0o600)
    subprocess.run(["openssl", "pkey", "-in", priv_path, "-pubout", "-out", pub_path],
                   check=True, capture_output=True)


def firmar(datos: bytes, priv_path: str) -> bytes:
    """Firma los bytes canónicos del feed; devuelve la firma cruda."""
    with tempfile.NamedTemporaryFile(delete=False) as fd:
        fd.write(datos)
        tmp = fd.name
    try:
        r = subprocess.run(
            ["openssl", "pkeyutl", "-sign", "-inkey", priv_path, "-rawin", "-in", tmp],
            check=True, capture_output=True)
        return r.stdout
    finally:
        os.unlink(tmp)


def verificar(datos: bytes, firma: bytes, pub_path: str) -> bool:
    """True si la firma corresponde a los datos bajo la clave pública."""
    with tempfile.NamedTemporaryFile(delete=False) as fdd, \
            tempfile.NamedTemporaryFile(delete=False) as fds:
        fdd.write(datos); dpath = fdd.name
        fds.write(firma); spath = fds.name
    try:
        r = subprocess.run(
            ["openssl", "pkeyutl", "-verify", "-pubin", "-inkey", pub_path,
             "-rawin", "-in", dpath, "-sigfile", spath],
            capture_output=True)
        return r.returncode == 0
    finally:
        os.unlink(dpath)
        os.unlink(spath)
