#!/usr/bin/env python3
"""Genera las unidades systemd de los seis perfiles del laboratorio.

Un perfil por alias: el motor puntua por IP, asi que seis direcciones sobre
una sola maquina son seis entidades distintas para el modelo.

    python3 clientes_config.py --comprobar     # valida sin escribir nada
    python3 clientes_config.py --mostrar       # imprime las unidades
    sudo python3 clientes_config.py --escribir # las instala y recarga systemd

Despues:

    sudo systemctl enable --now cyberflow-lab.target   # arranca los seis
    sudo systemctl stop cyberflow-lab.target           # los para todos

El target existe para eso: durante una linea base de 72 h hay que poder
arrancar y parar los seis a la vez, y sin el son seis ordenes que se pueden
quedar a medias sin que nadie lo note.
"""

from __future__ import annotations

import argparse
import ipaddress
import os
import subprocess
import sys
from pathlib import Path

# El orden importa poco, pero el reparto no: cada perfil va atado a UN alias y
# no se mezclan. Si dos perfiles compartieran origen, el modelo veria una sola
# entidad con la suma de los dos comportamientos.
PERFILES = ["ofimatica", "navegacion", "descargas", "aplicacion", "ligero", "erratico"]

CABECERA = """# Generado por scripts/laboratorio/clientes_config.py
# NO editar a mano: cualquier cambio se pierde en la siguiente generacion.
"""

UNIDAD = """{cabecera}
[Unit]
Description=CyberFlow laboratorio - perfil {perfil} desde {origen}
After=network-online.target
Wants=network-online.target
PartOf=cyberflow-lab.target

[Service]
Type=simple
User={usuario}
Group={usuario}
WorkingDirectory={raiz}
ExecStart={python} {raiz}/clientes_lab.py \\
    --perfil {perfil} \\
    --origen {origen} \\
    --servidor {servidor} \\
    --dns {dns}
Restart=always
RestartSec=5
# El generador imprime una linea por accion: a 1,9 acciones/s son ~272.000
# lineas en 72 h, que llenarian el journal sin aportar nada -- lo que de
# verdad hay que analizar sale del espejo, no de aqui. Los errores si se
# conservan: un perfil que muere en silencio durante tres dias es el peor
# fallo posible de esta fase.
StandardOutput=null
StandardError=journal
NoNewPrivileges=true
ProtectSystem=strict
PrivateTmp=true

[Install]
WantedBy=cyberflow-lab.target
"""

TARGET = """{cabecera}
[Unit]
Description=CyberFlow laboratorio - los seis perfiles de trafico
# Wants= explicito, y no solo el WantedBy= de cada servicio. Ese WantedBy solo
# crea el enlace en .wants/ cuando el servicio se habilita, asi que "systemctl
# start cyberflow-lab.target" arrancaba el target con NADA colgando: active,
# los seis perfiles parados y ningun error. Medido asi la primera vez.
#
# Sin Requires= a proposito: que un perfil falle no debe tumbar a los otros
# cinco. La linea base sobrevive perdiendo una entidad; no sobrevive a un
# arranque parcial que nadie mira.
Wants={servicios}

[Install]
WantedBy=multi-user.target
"""


def render(args) -> dict[str, str]:
    base = ipaddress.ip_address(args.base)
    cabecera = CABECERA.rstrip("\n")
    servicios = " ".join("cyberflow-lab-%s.service" % p for p in PERFILES)
    unidades = {"cyberflow-lab.target": TARGET.format(cabecera=cabecera,
                                                      servicios=servicios)}
    for i, perfil in enumerate(PERFILES):
        unidades["cyberflow-lab-%s.service" % perfil] = UNIDAD.format(
            cabecera=cabecera, perfil=perfil, origen=str(base + i),
            usuario=args.usuario, raiz=args.raiz.rstrip("/"),
            python=args.python, servidor=args.servidor, dns=args.dns)
    return unidades


def comprobar(args) -> list[str]:
    """Lo que tiene que ser cierto ANTES de dejar esto tres dias corriendo."""
    fallos = []

    try:
        base = ipaddress.ip_address(args.base)
    except ValueError as e:
        return ["--base no es una direccion IP: %s" % e]

    alias = [str(base + i) for i in range(len(PERFILES))]

    for valor, nombre in ((args.servidor, "--servidor"), (args.dns, "--dns")):
        try:
            ipaddress.ip_address(valor)
        except ValueError:
            fallos.append("%s no es una direccion IP: %r" % (nombre, valor))

    raiz = Path(args.raiz)
    guion = raiz / "clientes_lab.py"
    if not guion.exists():
        fallos.append("no existe %s" % guion)

    if not Path(args.python).exists():
        fallos.append("no existe el interprete %s" % args.python)

    # Solo si se ejecuta en la propia maquina destino: comprobar que los seis
    # alias estan configurados. Sin ellos, cada perfil arrancaria y moriria al
    # intentar hacer bind, y sin esta comprobacion habria que descubrirlo
    # leyendo seis journals distintos.
    if sys.platform.startswith("linux"):
        try:
            salida = subprocess.run(["ip", "-o", "-4", "addr"], capture_output=True,
                                    text=True, timeout=5, check=False).stdout
            faltan = [a for a in alias if (" " + a + "/") not in salida]
            if faltan:
                fallos.append("estos alias no estan en ninguna interfaz: %s"
                              % ", ".join(faltan))
        except (OSError, subprocess.TimeoutExpired):
            pass  # sin 'ip' no se puede comprobar; no es motivo para abortar

    return fallos


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--base", default="10.10.20.21",
                   help="primer alias; los seis perfiles usan este y los cinco siguientes")
    p.add_argument("--servidor", default="10.10.30.10")
    p.add_argument("--dns", default="10.10.10.20")
    p.add_argument("--usuario", default="adminclientes")
    p.add_argument("--raiz", default="/home/adminclientes/laboratorio")
    p.add_argument("--python", default="/usr/bin/python3")
    p.add_argument("--destino", default="/etc/systemd/system")
    modo = p.add_mutually_exclusive_group(required=True)
    modo.add_argument("--comprobar", action="store_true")
    modo.add_argument("--mostrar", action="store_true")
    modo.add_argument("--escribir", action="store_true")
    args = p.parse_args()

    fallos = comprobar(args)
    if fallos:
        for f in fallos:
            print("  - %s" % f, file=sys.stderr)
        if not args.mostrar:
            return 1
        print("(se muestran igual, pero NO se instalarian asi)", file=sys.stderr)
    elif args.comprobar:
        print("configuracion valida: %d perfiles desde %s" % (len(PERFILES), args.base))

    if args.comprobar:
        return 0

    unidades = render(args)

    if args.mostrar:
        for nombre, texto in unidades.items():
            print("=" * 70)
            print("### %s" % nombre)
            print("=" * 70)
            print(texto)
        return 0

    if os.geteuid() != 0:
        print("--escribir necesita root", file=sys.stderr)
        return 1

    destino = Path(args.destino)
    for nombre, texto in unidades.items():
        ruta = destino / nombre
        if ruta.exists():
            ruta.replace(str(ruta) + ".anterior")
        ruta.write_text(texto, encoding="utf-8", newline="\n")
        print("escrito %s" % ruta)

    print("")
    print("Ahora:  sudo systemctl daemon-reload")
    print("        sudo systemctl enable --now cyberflow-lab.target")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
