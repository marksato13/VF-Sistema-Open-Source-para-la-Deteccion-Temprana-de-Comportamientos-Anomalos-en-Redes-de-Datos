#!/usr/bin/env python3
"""Crea las cuentas del panel, la clave de sesion y el certificado TLS.

Tres piezas que el panel necesita y que NO pueden vivir en el repositorio:

  usuarios.json    usuario -> {rol, hash}. El hash es scrypt con sal por
                   cuenta, asi que dos personas con la misma contrasena no
                   comparten hash.
  clave-sesion     32 bytes aleatorios que firman la cookie. Cambiarla
                   invalida todas las sesiones abiertas, que es justo lo que
                   se quiere si se sospecha de una.
  cert/key         certificado autofirmado. Sin TLS la contrasena viaja en
                   claro por el troncal espejado y acaba en el propio anillo
                   de PCAP de CyberFlow: el sistema capturaria su credencial.

**La contrasena nunca se pasa por argumento.** Se pide por terminal con
getpass, porque argv es visible en `ps` para cualquier usuario de la maquina y
queda en el historial del shell.

Uso:
    sudo python3 cyberflow_usuarios.py --crear admin  --rol admin
    sudo python3 cyberflow_usuarios.py --crear lector --rol lector
    sudo python3 cyberflow_usuarios.py --clave-sesion
    sudo python3 cyberflow_usuarios.py --certificado --nombre 10.10.60.11
    sudo python3 cyberflow_usuarios.py --comprobar
"""

from __future__ import annotations

import argparse
import getpass
import importlib.util
import json
import os
import secrets
import stat
import subprocess
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "dashboard", RAIZ / "engine/dashboard.py")
assert SPEC and SPEC.loader
_dash = importlib.util.module_from_spec(SPEC)
sys.modules["dashboard"] = _dash
SPEC.loader.exec_module(_dash)

DIR = Path("/etc/cyberflow")
USUARIOS = DIR / "usuarios.json"
CLAVE = DIR / "clave-sesion"
CERT = DIR / "panel.crt"
LLAVE = DIR / "panel.key"

# Minimo razonable. No se piden mayusculas ni simbolos: son reglas que empujan
# a la gente a "Verano2026!" y no anaden entropia real.
MINIMO = 12


def _escribir_privado(ruta: Path, contenido: bytes, duenno: str | None) -> None:
    """Escribe con 0600 desde el principio, no despues.

    Crear el fichero y luego hacer chmod deja una ventana en la que cualquiera
    puede leerlo. O_CREAT|O_EXCL con el modo puesto cierra esa ventana.
    """
    ruta.parent.mkdir(parents=True, exist_ok=True)
    tmp = ruta.with_suffix(ruta.suffix + ".nuevo")
    fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    try:
        os.write(fd, contenido)
    finally:
        os.close(fd)
    if duenno:
        import shutil
        shutil.chown(tmp, user=duenno, group=duenno)
    os.replace(tmp, ruta)


def crear_usuario(nombre: str, rol: str, duenno: str | None) -> int:
    if rol not in _dash.ROLES:
        print("rol invalido: %s (validos: %s)" % (rol, ", ".join(_dash.ROLES)))
        return 2
    if not sys.stdin.isatty():
        print("hace falta una terminal: la contrasena se pide por getpass y "
              "nunca por argumento.")
        return 2

    contrasena = getpass.getpass("Contraseña para %s (%s): " % (nombre, rol))
    if len(contrasena) < MINIMO:
        print("demasiado corta: minimo %d caracteres." % MINIMO)
        return 2
    if contrasena != getpass.getpass("Repítela: "):
        print("no coinciden.")
        return 2

    try:
        datos = json.loads(USUARIOS.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        datos = {}
    datos[nombre] = {"rol": rol, "hash": _dash.hash_contrasena(contrasena)}
    _escribir_privado(USUARIOS,
                      (json.dumps(datos, indent=2, sort_keys=True) + "\n").encode(),
                      duenno)
    print("%s (%s) guardado en %s" % (nombre, rol, USUARIOS))
    return 0


def crear_clave(duenno: str | None) -> int:
    if CLAVE.exists():
        print("ya existe %s. Borrala a mano si de verdad quieres rotarla: "
              "hacerlo cierra todas las sesiones abiertas." % CLAVE)
        return 1
    _escribir_privado(CLAVE, secrets.token_hex(32).encode(), duenno)
    print("clave de sesion creada en %s" % CLAVE)
    return 0


def crear_certificado(nombre: str, dias: int, duenno: str | None) -> int:
    """Autofirmado con openssl, que ya esta en el sensor.

    No se genera en tiempo de ejecucion: un certificado distinto en cada
    arranque haria imposible comprobar la huella, que es la unica validacion
    disponible cuando no hay una CA.
    """
    if CERT.exists() or LLAVE.exists():
        print("ya existe el certificado. Borra %s y %s para rehacerlo."
              % (CERT, LLAVE))
        return 1
    DIR.mkdir(parents=True, exist_ok=True)
    # El SAN importa: los navegadores modernos ignoran el CN y sin SAN el
    # certificado se rechaza incluso aceptando el riesgo a mano.
    san = ("subjectAltName=IP:%s" if _es_ip(nombre) else "subjectAltName=DNS:%s") % nombre
    orden = [
        "openssl", "req", "-x509", "-newkey", "rsa:3072", "-nodes",
        "-days", str(dias), "-subj", "/CN=%s" % nombre,
        "-addext", san,
        "-keyout", str(LLAVE), "-out", str(CERT),
    ]
    r = subprocess.run(orden, capture_output=True, text=True)
    if r.returncode != 0:
        print("openssl fallo:\n%s" % r.stderr.strip())
        return 1
    os.chmod(LLAVE, 0o600)
    os.chmod(CERT, 0o644)
    if duenno:
        import shutil
        shutil.chown(LLAVE, user=duenno, group=duenno)
    huella = subprocess.run(
        ["openssl", "x509", "-in", str(CERT), "-noout", "-fingerprint", "-sha256"],
        capture_output=True, text=True).stdout.strip()
    print("certificado creado para %s, %d dias" % (nombre, dias))
    print(huella)
    print("Apunta esa huella: es lo unico que puedes comprobar en el navegador.")
    return 0


def _es_ip(valor: str) -> bool:
    import ipaddress
    try:
        ipaddress.ip_address(valor)
    except ValueError:
        return False
    return True


def comprobar() -> int:
    """Lo que tiene que ser cierto antes de arrancar el panel con login."""
    fallos = []
    for ruta, modo_max in ((USUARIOS, 0o600), (CLAVE, 0o600), (LLAVE, 0o600)):
        if not ruta.exists():
            fallos.append("falta %s" % ruta)
            continue
        modo = stat.S_IMODE(ruta.stat().st_mode)
        if modo & 0o077:
            fallos.append("%s tiene modo %o: lo puede leer alguien mas" % (ruta, modo))
    if not CERT.exists():
        fallos.append("falta %s" % CERT)

    if USUARIOS.exists():
        cuentas = _dash.cargar_usuarios(USUARIOS)
        if not cuentas:
            fallos.append("%s no tiene ninguna cuenta valida" % USUARIOS)
        elif not any(d["rol"] == "admin" for d in cuentas.values()):
            fallos.append("no hay ninguna cuenta con rol admin")
        else:
            print("cuentas: " + ", ".join("%s(%s)" % (u, d["rol"])
                                          for u, d in sorted(cuentas.items())))
    if CLAVE.exists() and len(CLAVE.read_bytes().strip()) < 32:
        fallos.append("la clave de sesion es demasiado corta")

    for f in fallos:
        print("FALLA: %s" % f)
    if not fallos:
        print("todo listo.")
    return 1 if fallos else 0


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--duenno", default="m4rk",
                   help="usuario que corre el panel y debe poder leer los ficheros")
    g = p.add_mutually_exclusive_group(required=True)
    g.add_argument("--crear", metavar="USUARIO")
    g.add_argument("--clave-sesion", action="store_true")
    g.add_argument("--certificado", action="store_true")
    g.add_argument("--comprobar", action="store_true")
    p.add_argument("--rol", choices=_dash.ROLES)
    p.add_argument("--nombre", default="10.10.60.11",
                   help="CN y SAN del certificado: la IP o el nombre por el que "
                        "se abre el panel")
    p.add_argument("--dias", type=int, default=825)
    args = p.parse_args()

    if args.crear:
        if not args.rol:
            print("--crear necesita --rol")
            return 2
        return crear_usuario(args.crear, args.rol, args.duenno)
    if args.clave_sesion:
        return crear_clave(args.duenno)
    if args.certificado:
        return crear_certificado(args.nombre, args.dias, args.duenno)
    return comprobar()


if __name__ == "__main__":
    raise SystemExit(main())
