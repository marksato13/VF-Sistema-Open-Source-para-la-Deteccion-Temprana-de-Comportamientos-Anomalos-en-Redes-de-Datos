#!/usr/bin/env python3
"""Genera INVENTARIO.md (especificaciones y red de cada equipo) a partir de una extraccion saneada.

Uso:  python inventario.py <carpeta_extraccion>   -> escribe <carpeta_extraccion>/INVENTARIO.md
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

ROLES = {
    "bastion": "Bastión de gestión (VM-GESTION): punto de entrada SSH a todo el laboratorio",
    "sensor1": "Sensor principal: Suricata (solo EVE) + motor CyberFlow + panel + publicador del feed",
    "sensor2": "Sensor secundario (réplica del sensor)",
    "srvdmz": "Servidor DMZ atacado: web/servicios + agente de enforcement v2 (nftables)",
    "kali": "Atacante (Kali) para las campañas y la demo",
    "clientes": "Clientes legítimos (7 IPs en una VM) que generan tráfico normal",
    "suricata": "IDS comparador: Suricata con reglas ET Open (replay de PCAP)",
}


def leer(p: Path) -> str:
    try:
        return p.read_text(encoding="utf-8", errors="replace").strip()
    except OSError:
        return ""


def campo(texto: str, clave: str) -> str:
    m = re.search(r"^\s*" + re.escape(clave) + r"\s*:\s*(.+)$", texto, re.M)
    return m.group(1).strip() if m else "?"


def linux(d: Path) -> list[str]:
    os_ = re.search(r'PRETTY_NAME="([^"]+)"', leer(d / "sistema/os-release.txt"))
    cpu = leer(d / "sistema/cpu.txt")
    mem = re.search(r"^Mem:\s+(\S+)", leer(d / "sistema/memoria.txt"), re.M)
    host = campo(leer(d / "sistema/hostnamectl.txt"), "Static hostname")
    ips = [l for l in leer(d / "red/ip-addr.txt").splitlines() if l and not l.startswith("lo")]
    svc = [l.split()[0] for l in leer(d / "servicios/activos.txt").splitlines() if l.strip()]
    propios = [s for s in svc if re.match(r"(ppi-|cf-|cyberflow|suricata|zeek|nginx|apache2|bind9|named|chrony|zabbix|wazuh|smbd|samba|docker)", s)]
    disco = [l for l in leer(d / "sistema/df.txt").splitlines()[1:] if l.strip()]
    out = [
        f"- **Hostname:** `{host}` · **SO:** {os_.group(1) if os_ else '?'} · **Virtualización:** {leer(d / 'sistema/virtualizacion.txt') or '?'}",
        f"- **CPU:** {campo(cpu, 'CPU(s)')} vCPU ({campo(cpu, 'Model name')}) · **RAM:** {mem.group(1) if mem else '?'}",
        "- **Discos:** " + "; ".join(" ".join(l.split()[i] for i in (0, 2, 6) if i < len(l.split())) for l in disco[:4]),
        "- **Red:**",
        *[f"  - `{l}`" for l in ips],
        "- **Servicios relevantes activos:** " + (", ".join(f"`{s}`" for s in propios) or "ninguno de la lista"),
        f"- **Paquetes instalados:** {len(leer(d / 'paquetes/dpkg.txt').splitlines())} (lista en `paquetes/dpkg.txt`)",
    ]
    if "[sin sudo -n]" in leer(d / "red/nft-ruleset.txt"):
        out.append("- **Firewall del host:** no leído (requiere sudo con contraseña; ver la sección «Lo que falta»)")
    return out


def switch(d: Path) -> list[str]:
    ver = leer(d / "version.txt")
    m = re.search(r"Version ([^,\s]+)", ver)
    mod = re.search(r"^Model [Nn]umber\s*:\s*(\S+)", ver, re.M) or re.search(r"cisco (\S+) .*processor", ver)
    vl = [l.split()[0] + " " + l.split()[1] for l in leer(d / "vlan-brief.txt").splitlines()
          if re.match(r"^\d+\s+\S+", l)]
    return [f"- **IOS:** {m.group(1) if m else '?'} · **Modelo:** {mod.group(1) if mod else '?'}",
            "- **VLANs:** " + ", ".join(f"`{v}`" for v in vl[:30]),
            "- Troncales, SPAN hacia los sensores (`monitor-session-all.txt`) y etherchannel; la running-config completa queda fuera del repo público"]


def esxi(d: Path) -> list[str]:
    vms = [l for l in (leer(d / "vms-cyberflow.txt") or leer(d / "vms.txt")).splitlines()[1:] if l.strip()]
    nombres = sorted(p.stem for p in (d / "vmx").glob("*.vmx")) or [l.split()[1] for l in vms if len(l.split()) > 1]
    return [f"- **Versión:** {leer(d / 'version.txt').splitlines()[0] if leer(d / 'version.txt') else '?'}",
            "- **VMs:** " + ", ".join(f"`{n}`" for n in nombres),
            f"- `.vmx` de cada VM en `vmx/` (CPU, RAM, discos, NIC y portgroup) y red/almacén del host en `host.txt`"]


def main() -> int:
    raiz = Path(sys.argv[1])
    l = ["# Inventario del laboratorio CyberFlow", "",
         f"Generado de la extracción `{raiz.name}` (`_registro.txt` = hora y resultado por equipo).", ""]
    for d in sorted(p for p in raiz.iterdir() if p.is_dir()):
        n = d.name
        l.append(f"## {n}")
        if n in ROLES:
            l.append(f"*{ROLES[n]}*")
        l.append("")
        if (d / "_sin-acceso.txt").exists() or not any(d.iterdir()):
            l += [f"- **No extraído:** sin acceso en el momento de la extracción ({leer(d / '_sin-acceso.txt')[:150]})", ""]
            continue
        if (d / "sistema").is_dir():
            l += linux(d)
        elif n.startswith("sw-"):
            l += switch(d)
        elif n.startswith("esxi-"):
            l += esxi(d)
        l.append("")
    (raiz / "INVENTARIO.md").write_text("\n".join(l) + "\n", encoding="utf-8", newline="\n")
    print("INVENTARIO.md:", len(l), "lineas")
    return 0


if __name__ == "__main__":
    sys.exit(main())
