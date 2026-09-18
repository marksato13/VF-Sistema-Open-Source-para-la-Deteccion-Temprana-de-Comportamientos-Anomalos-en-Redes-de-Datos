#!/usr/bin/env python3
"""Genera las unidades de systemd de CyberFlow desde configs/cyberflow.toml.

Por que existe. Las unidades publicadas en configs/sensor/ traian cableados la
interfaz (ens35), un filtro BPF con las redes del laboratorio (10.20.0.0/24 y
10.30.0.0/24), el usuario useransible y rutas absolutas bajo /home/useransible.
En el primer despliegue sobre una red distinta no funciono ninguna de las dos y
hubo que reescribirlas a mano. Este script convierte ese trabajo manual en un
fichero de configuracion y una plantilla.

Solo biblioteca estandar: tomllib entra en Python 3.11. El resto del proyecto
sigue el mismo criterio -el extractor parsea PCAP con struct y el panel usa
http.server- y no tiene sentido introducir una dependencia para esto.

Uso:
    python3 scripts/setup/cyberflow_config.py --mostrar
    sudo python3 scripts/setup/cyberflow_config.py --escribir
    python3 scripts/setup/cyberflow_config.py --comprobar
"""
from __future__ import annotations

import argparse
import ipaddress
import os
import shutil
import sys
import tomllib
from pathlib import Path

RAIZ_REPO = Path(__file__).resolve().parents[2]
CONFIG_POR_OMISION = RAIZ_REPO / "configs" / "cyberflow.toml"
DESTINO_SYSTEMD = Path("/etc/systemd/system")

CABECERA = """# Generado por scripts/setup/cyberflow_config.py desde {origen}
# NO editar a mano: cualquier cambio se pierde en la siguiente generacion.
# Para cambiar algo, edita el .toml y vuelve a ejecutar el generador.
"""

NIC = """{cabecera}
[Unit]
Description=CyberFlow - prepara {interfaz} para captura pasiva
After=network-online.target
Wants=network-online.target
Before=suricata.service

[Service]
Type=oneshot
RemainAfterExit=yes
# Sin promiscuo la vNIC filtra el espejo: ninguna trama va dirigida a su MAC.
ExecStart=/usr/sbin/ip link set {interfaz} up promisc on
# GRO/LRO/TSO/GSO recomponen segmentos y falsearian tamano de trama y tasas.
ExecStart=-/usr/sbin/ethtool -K {interfaz} gro off lro off tso off gso off
# Una sonda pasiva no debe emitir.
ExecStart=-/usr/sbin/sysctl -qw net.ipv6.conf.{interfaz}.disable_ipv6=1
ExecStop=-/usr/sbin/ip link set {interfaz} promisc off

[Install]
WantedBy=multi-user.target
"""

CAPTURA = """{cabecera}
[Unit]
Description=CyberFlow - buffer en anillo de PCAP para el motor
After=network-online.target suricata.service cyberflow-capture-nic.service
Wants=network-online.target
Requires=cyberflow-capture-nic.service

[Service]
Type=simple
# Arranca como root y suelta privilegios con -Z justo tras abrir el socket.
ExecStartPre=/usr/bin/install -d -o tcpdump -g {usuario} -m 2750 {directorio}
ExecStart=/usr/bin/tcpdump -i {interfaz} -n -s 0 -U -B 65536 \\
    -Z tcpdump -w {directorio}/live-%%Y%%m%%d%%H%%M%%S.pcap \\
    -G {anillo_segundos} -W {anillo_archivos}{filtro}
UMask=0027
Restart=always
RestartSec=2

[Install]
WantedBy=multi-user.target
"""

MOTOR = """{cabecera}
[Unit]
Description=CyberFlow - motor de decision (OCSVM), modo {modo}
After=network-online.target suricata.service ppi-motor-capture.service
Wants=network-online.target
Requires=ppi-motor-capture.service

[Service]
Type=simple
User={usuario}
Group={usuario}
WorkingDirectory={raiz}
ExecStart={python} \\
    {raiz}/scripts/engine/motor_decision.py \\
    --eve-path {eve} \\
    --capture-dir {directorio} \\
    --model-path {raiz}/{modelo} \\
    --manifest-path {raiz}/{manifiesto} \\
    --schema {raiz}/{esquema} \\
    --entity-network {red_entidades} \\{exclusiones}
    --log-path {raiz}/{registro} \\
    --step-seconds {paso_segundos} \\
    --history-seconds {historia_segundos}{enforce}
Restart=always
RestartSec=5
{endurecido}
[Install]
WantedBy=multi-user.target
"""

ENDURECIDO_OBS = """# Modo observacion: el motor no necesita escalar privilegios nunca.
NoNewPrivileges=true
ProtectSystem=strict
PrivateDevices=true
ReadWritePaths={raiz}/logs
ReadOnlyPaths={directorio} {eve_dir}
"""

ENDURECIDO_BLOQ = """# Modo bloqueo: NoNewPrivileges debe ser false o sudo no puede
# escalar al helper ppi-enforce, sin importar la politica de sudoers.
NoNewPrivileges=false
ProtectSystem=strict
ReadWritePaths={raiz}/logs
ReadOnlyPaths={directorio} {eve_dir}
"""

PANEL = """{cabecera}
[Unit]
Description=CyberFlow - panel web de solo lectura
After=ppi-motor.service
Wants=ppi-motor.service{acceso}

[Service]
Type=simple
User={usuario}
Group={usuario}
WorkingDirectory={raiz}
ExecStart={python} {raiz}/scripts/engine/dashboard.py \\
    --log-path {raiz}/{registro} \\
    --manifest-path {raiz}/{manifiesto} \\
    --services ppi-motor.service,ppi-motor-capture.service,suricata.service \\{calibrado}
    --host {direccion} --port {puerto}
Restart=always
RestartSec=5
NoNewPrivileges=true
ProtectSystem=strict

[Install]
WantedBy=multi-user.target
"""


ACCESO = """{cabecera}
[Unit]
Description=CyberFlow - acceso al panel: solo {resumen}
# El panel no tiene autenticacion. Si esta unidad falla, ppi-dashboard no
# arranca (la requiere con Requires=): nunca queda expuesto sin filtro.
Before=ppi-dashboard.service

[Service]
Type=oneshot
RemainAfterExit=yes
ExecStartPre=-/usr/sbin/nft delete table inet cyberflow_panel
ExecStart=/usr/sbin/nft -f {reglas}
ExecStop=-/usr/sbin/nft delete table inet cyberflow_panel

[Install]
WantedBy=multi-user.target
"""

REGLAS = """# Generado por scripts/setup/cyberflow_config.py. NO editar a mano.
# Tabla propia y aislada: solo decide sobre el puerto del panel y deja pasar
# todo lo demas (policy accept), asi que no puede cortar el SSH de gestion.
table inet cyberflow_panel {{
    chain entrada {{
        type filter hook input priority 0; policy accept;
{permitidos}        tcp dport {puerto} drop
    }}
}}
"""

RUTA_REGLAS = "/etc/cyberflow/panel-acceso.nft"
RUTA_ROTACION = "/etc/logrotate.d/cyberflow"

LIMPIEZA = """{cabecera}
[Unit]
Description=CyberFlow - poda el anillo de PCAP
# tcpdump -G rota por tiempo, pero con un nombre con fecha NO reutiliza
# nombres: -W no borra nada y el "anillo" crece para siempre. Medido en el
# sensor de referencia: 6707 ficheros y 403 MB en un dia. El motor ya ignora
# los ficheros viejos por su mtime, asi que esto no cambia lo que analiza:
# solo impide que el disco se llene.

[Service]
Type=oneshot
ExecStart=/usr/bin/find {directorio} -maxdepth 1 -name '{glob}' -mmin +{retener} -delete
"""

LIMPIEZA_TIMER = """{cabecera}
[Unit]
Description=CyberFlow - poda periodica del anillo de PCAP

[Timer]
OnBootSec=5min
OnUnitActiveSec=5min
Persistent=true

[Install]
WantedBy=timers.target
"""

ROTACION = """# Generado por scripts/setup/cyberflow_config.py. NO editar a mano.
# El motor escribe una linea JSON por decision y puede producir cientos por
# minuto. Sin tope, este fichero llena la raiz, y un / lleno tumba la maquina
# entera, incluido el SSH de gestion.
#
# Sin copytruncate a proposito: el motor abre el fichero en modo append en
# cada escritura y lo cierra, asi que tras renombrarlo escribe en el nuevo sin
# necesidad de senales ni de reiniciar el servicio.
{registro} {{
    daily
    maxsize 200M
    rotate 14
    missingok
    notifempty
    compress
    delaycompress
    create 0640 {usuario} {usuario}
}}
"""


def panel_expuesto(panel: dict) -> bool:
    try:
        return bool(panel.get("activo")) and \
            not ipaddress.ip_address(panel.get("direccion", "127.0.0.1")).is_loopback
    except ValueError:
        return True


def cargar(ruta: Path) -> dict:
    with ruta.open("rb") as fh:
        return tomllib.load(fh)


def comprobar(cfg: dict) -> list[str]:
    """Valida lo que se puede validar sin tocar la maquina. Devuelve los fallos."""
    fallos: list[str] = []
    cap, red, mot, rut = cfg["captura"], cfg["red"], cfg["motor"], cfg["rutas"]

    try:
        ipaddress.ip_network(red["red_entidades"], strict=False)
    except ValueError as e:
        fallos.append("red.red_entidades no es una red valida: %s" % e)

    for r in red.get("excluir", []):
        try:
            ipaddress.ip_network(r, strict=False)
        except ValueError as e:
            fallos.append("red.excluir contiene %r invalido: %s" % (r, e))

    if mot["modo"] not in ("observacion", "bloqueo"):
        fallos.append("motor.modo debe ser 'observacion' o 'bloqueo', no %r" % mot["modo"])

    anillo = cap["anillo_archivos"] * cap["anillo_segundos"]
    if mot["historia_segundos"] >= anillo:
        fallos.append(
            "motor.historia_segundos (%d) debe ser menor que el anillo (%d x %d = %d s), "
            "o el motor pedira historia que ya roto fuera del buffer"
            % (mot["historia_segundos"], cap["anillo_archivos"],
               cap["anillo_segundos"], anillo))

    # Podar antes de que el motor deje de necesitarlos le quitaria historia.
    anillo_minutos = cap["anillo_archivos"] * cap["anillo_segundos"] / 60.0
    if cap.get("retener_minutos", 0) <= anillo_minutos:
        fallos.append(
            "captura.retener_minutos (%s) debe ser mayor que la duracion del "
            "anillo (%.1f min): la poda borraria capturas que el motor todavia "
            "necesita" % (cap.get("retener_minutos"), anillo_minutos))

    filtro = cap.get("filtro_bpf", "").strip()
    if filtro and "vlan" not in filtro:
        fallos.append(
            "captura.filtro_bpf no menciona 'vlan'. Si el espejo conserva la etiqueta "
            "802.1Q -y aqui la conserva- un filtro de capa 3 sin 'vlan' no casa con "
            "nada y el anillo queda vacio sin dar ningun error")

    panel = cfg.get("panel", {})
    if panel.get("activo"):
        try:
            ipaddress.ip_address(panel.get("direccion", ""))
        except ValueError:
            fallos.append("panel.direccion no es una direccion IP: %r" % panel.get("direccion"))
        if panel_expuesto(panel):
            permitir = panel.get("permitir", [])
            if not permitir:
                fallos.append(
                    "panel.direccion %s expone el panel en la red y el panel NO tiene "
                    "autenticacion: panel.permitir debe listar los origenes autorizados"
                    % panel.get("direccion"))
            for r in permitir:
                try:
                    n = ipaddress.ip_network(r, strict=False)
                except ValueError as e:
                    fallos.append("panel.permitir contiene %r invalido: %s" % (r, e))
                    continue
                if n.prefixlen == 0:
                    fallos.append("panel.permitir contiene %s: equivale a no filtrar nada" % r)

    raiz = Path(rut["raiz"])
    for clave in ("modelo", "manifiesto", "esquema"):
        # Solo se comprueba si el generador corre en la propia maquina destino.
        destino = raiz / rut[clave]
        if raiz.exists() and not destino.exists():
            fallos.append("rutas.%s no existe: %s" % (clave, destino))

    return fallos


def exclusiones(red: dict) -> str:
    """Lo que queda fuera del calculo, tal como lo recibe el motor."""
    partes = []
    if red.get("excluir"):
        partes.append("\n    --excluir %s \\" % ",".join(red["excluir"]))
    if red.get("excluir_protocolos"):
        partes.append("\n    --excluir-protocolos %s \\"
                      % ",".join(str(p) for p in red["excluir_protocolos"]))
    return "".join(partes)


def render(cfg: dict) -> dict[str, str]:
    cap, red, mot, rut = cfg["captura"], cfg["red"], cfg["motor"], cfg["rutas"]
    panel = cfg.get("panel", {})
    raiz = rut["raiz"].rstrip("/")
    python = "%s/%s/bin/python" % (raiz, rut["entorno"].strip("/"))
    cabecera = CABECERA.format(origen="configs/cyberflow.toml")

    filtro = cap.get("filtro_bpf", "").strip()
    filtro_linea = " \\\n    %s" % filtro if filtro else ""

    if mot["modo"] == "bloqueo":
        enforce = " \\\n    --enforce --block-timeout-seconds %d" % mot["bloqueo_segundos"]
        endurecido = ENDURECIDO_BLOQ
    else:
        enforce = ""
        endurecido = ENDURECIDO_OBS

    comun = dict(
        cabecera=cabecera, interfaz=cap["interfaz"], usuario=rut["usuario"],
        directorio=cap["directorio"].rstrip("/"), raiz=raiz, python=python,
        # rsplit y no Path().parent: el generador puede correr en Windows y
        # Path convertiria las barras a "\", produciendo una unidad invalida.
        eve=rut["eve"], eve_dir=rut["eve"].rsplit("/", 1)[0] or "/",
        modelo=rut["modelo"], manifiesto=rut["manifiesto"], esquema=rut["esquema"],
        registro=rut["registro"], red_entidades=red["red_entidades"],
        paso_segundos=mot["paso_segundos"], historia_segundos=mot["historia_segundos"],
        modo=mot["modo"], anillo_segundos=cap["anillo_segundos"],
        anillo_archivos=cap["anillo_archivos"], filtro=filtro_linea, enforce=enforce,
        exclusiones=exclusiones(red),
    )

    unidades = {
        "cyberflow-limpieza.service": LIMPIEZA.format(
            cabecera=cabecera, directorio=cap["directorio"].rstrip("/"),
            glob=cap.get("anillo_glob", "live-*.pcap"),
            retener=cap["retener_minutos"]),
        "cyberflow-limpieza.timer": LIMPIEZA_TIMER.format(cabecera=cabecera),
        RUTA_ROTACION: ROTACION.format(registro="%s/%s" % (raiz, rut["registro"]),
                                       usuario=rut["usuario"]),
        "cyberflow-capture-nic.service": NIC.format(**comun),
        "ppi-motor-capture.service": CAPTURA.format(**comun),
        "ppi-motor.service": MOTOR.format(
            endurecido=endurecido.format(**comun), **comun),
    }
    if panel.get("activo"):
        acceso = ""
        if panel_expuesto(panel):
            redes = [ipaddress.ip_network(r, strict=False) for r in panel["permitir"]]
            v4 = [str(n) for n in redes if n.version == 4]
            v6 = [str(n) for n in redes if n.version == 6]
            lineas = ""
            if v4:
                lineas += "        tcp dport %d ip saddr { %s } accept\n" % (panel["puerto"], ", ".join(v4))
            if v6:
                lineas += "        tcp dport %d ip6 saddr { %s } accept\n" % (panel["puerto"], ", ".join(v6))
            unidades[RUTA_REGLAS] = REGLAS.format(permitidos=lineas, puerto=panel["puerto"])
            unidades["cyberflow-panel-acceso.service"] = ACCESO.format(
                cabecera=cabecera, resumen=", ".join(v4 + v6), reglas=RUTA_REGLAS)
            acceso = ("\nRequires=cyberflow-panel-acceso.service"
                      "\nAfter=cyberflow-panel-acceso.service")
        calibrado = ("\n    --calibrado-en-esta-red \\"
                     if cfg["motor"].get("calibrado_en_esta_red") else "")
        unidades["ppi-dashboard.service"] = PANEL.format(
            direccion=panel["direccion"], puerto=panel["puerto"], acceso=acceso,
            calibrado=calibrado, **comun)
    return unidades


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--config", type=Path, default=CONFIG_POR_OMISION)
    p.add_argument("--destino", type=Path, default=DESTINO_SYSTEMD)
    g = p.add_mutually_exclusive_group(required=True)
    g.add_argument("--mostrar", action="store_true", help="imprime las unidades")
    g.add_argument("--escribir", action="store_true", help="las instala en systemd")
    g.add_argument("--comprobar", action="store_true", help="solo valida el .toml")
    args = p.parse_args()

    if not args.config.exists():
        print("no existe la configuracion: %s" % args.config, file=sys.stderr)
        return 2
    cfg = cargar(args.config)

    fallos = comprobar(cfg)
    if fallos:
        print("La configuracion tiene %d problema(s):\n" % len(fallos), file=sys.stderr)
        for f in fallos:
            print("  - %s" % f, file=sys.stderr)
        if not args.comprobar:
            return 1
        return 1
    if args.comprobar:
        print("configuracion valida: %s" % args.config)
        return 0

    unidades = render(cfg)

    if args.mostrar:
        for nombre, texto in unidades.items():
            print("=" * 70)
            print("### %s" % nombre)
            print("=" * 70)
            print(texto)
        return 0

    if os.geteuid() != 0:
        print("--escribir necesita root para escribir en %s" % args.destino,
              file=sys.stderr)
        return 2

    args.destino.mkdir(parents=True, exist_ok=True)
    for nombre, texto in unidades.items():
        # Las reglas de cortafuegos van a su ruta absoluta; las unidades, a
        # --destino.
        ruta = Path(nombre) if nombre.startswith("/") else args.destino / nombre
        ruta.parent.mkdir(parents=True, exist_ok=True)
        if ruta.exists():
            copia = ruta.with_suffix(ruta.suffix + ".anterior")
            shutil.copy2(ruta, copia)
        ruta.write_text(texto, encoding="utf-8")
        print("escrito %s" % ruta)
    print("\nAhora:  sudo systemctl daemon-reload")
    servicios = [n for n in unidades if n.endswith(".service")]
    print("        sudo systemctl enable --now %s" % " ".join(servicios))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
