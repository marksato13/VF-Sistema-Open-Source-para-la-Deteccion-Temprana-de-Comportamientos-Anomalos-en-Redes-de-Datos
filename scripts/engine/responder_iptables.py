#!/usr/bin/env python3
"""Respuesta: bloquea con iptables las IP en alerta sostenida.

El motor solo OBSERVA (espejo SPAN, fuera del camino), asi que su regla nftables
local no corta nada real. Este responder cierra el lazo llevando la decision a
un punto que SI esta en el camino: el iptables del host que se protege -el
servidor, o mañana pfSense-. Lee el registro del motor, decide, y aplica DROP.

Dos decisiones de diseño que son el corazon de esto:

1. INTERLOCK DE CALIBRACION. No aplica NADA si el modelo no esta calibrado en
   esta red. Medido hoy: con el umbral de otra red el motor alerta el 92 % de
   las ventanas; activar bloqueo con eso seria una denegacion de servicio
   autoinfligida. El bloqueo se gana solo despues de recalibrar. --forzar lo
   salta, a sabiendas.

2. ALERTA SOSTENIDA, no una ventana suelta. Se bloquea una IP con >= --minimo
   alertas del MODELO en los ultimos --ventana s. Una anomalia de una ventana
   es ruido; un ataque llena varias seguidas. Ademas nunca se bloquea la lista
   de seguridad (gateways, DNS, el propio sensor, lo excluido del alcance).

Por omision corre en SECO: imprime lo que HARIA y por que, sin tocar iptables.
Asi se puede ejecutar contra el registro real -incluso en el sensor, que no
puede aplicar- para ver la decision antes de darle poder de corte.

    python3 responder_iptables.py --registro logs/motor_decision.log \\
        --excluir 10.10.60.11/32,10.10.10.30/32 --calibrado false
"""

from __future__ import annotations

import argparse
import ipaddress
import json
import subprocess
import time
from pathlib import Path

CHAIN = "CYBERFLOW"

# Nunca se bloquea esto, pase lo que pase: romper la red que se protege es peor
# que el ataque. Son los .1/.2 de cada VLAN (gateway y su par) y los resolutores
# de DNS conocidos. Se amplia con --excluir (lo mismo que excluye el motor).
def es_infraestructura(ip: ipaddress.IPv4Address) -> bool:
    ultimo = int(ip) & 0xFF
    if ultimo in (1, 2, 254):          # gateway, par HA, VIP
        return True
    if str(ip) in ("10.10.10.20", "10.10.10.21"):   # DNS
        return True
    return False


def parse_registro(ruta: Path, desde: float, detector_modelo: str) -> dict:
    """Cuenta alertas del MODELO por entidad desde 'desde' (epoch)."""
    conteo: dict[str, int] = {}
    ultima: dict[str, float] = {}
    try:
        with ruta.open(encoding="utf-8", errors="replace") as f:
            for linea in f:
                if '"event": "decision"' not in linea and '"event":"decision"' not in linea:
                    continue
                try:
                    d = json.loads(linea)
                except ValueError:
                    continue
                if d.get("event") != "decision" or d.get("decision") != "ALERT":
                    continue
                # Solo el detector del modelo: la heuristica de fuerza bruta y la
                # de ventana vacia no son deteccion no supervisada.
                if detector_modelo and d.get("detector_name") != detector_modelo:
                    continue
                t = float(d.get("logged_at", 0) or 0)
                if t < desde:
                    continue
                ip = str(d.get("entity_ip", ""))
                conteo[ip] = conteo.get(ip, 0) + 1
                ultima[ip] = max(ultima.get(ip, 0), t)
    except OSError:
        pass
    return {"conteo": conteo, "ultima": ultima}


def candidatos(datos: dict, minimo: int, redes_fuera: list) -> list:
    fuera = []
    for ip_s, n in sorted(datos["conteo"].items(), key=lambda kv: -kv[1]):
        if n < minimo:
            continue
        try:
            ip = ipaddress.ip_address(ip_s)
        except ValueError:
            continue
        if es_infraestructura(ip) or any(ip in r for r in redes_fuera):
            continue
        fuera.append({"ip": ip_s, "alertas": n, "ultima": datos["ultima"].get(ip_s, 0)})
    return fuera


def iptables_activas(aplicar: bool) -> set:
    if not aplicar:
        return set()
    try:
        r = subprocess.run(["iptables", "-S", CHAIN], capture_output=True, text=True)
    except (OSError, subprocess.SubprocessError):
        return set()
    ips = set()
    for l in r.stdout.splitlines():
        pt = l.split()
        if "-s" in pt:
            ips.add(pt[pt.index("-s") + 1].split("/")[0])
    return ips


def aplicar_regla(accion: str, ip: str) -> None:
    # -I al principio para ganar a un ACCEPT posterior; chain propia y aditiva.
    subprocess.run(["iptables", accion, CHAIN, "-s", ip, "-j", "DROP"], check=False)


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--registro", type=Path, required=True)
    p.add_argument("--ventana", type=int, default=60, help="segundos hacia atras")
    p.add_argument("--minimo", type=int, default=6,
                   help="alertas del modelo en la ventana para bloquear")
    p.add_argument("--expira", type=int, default=300,
                   help="segundos sin alertas antes de desbloquear")
    p.add_argument("--detector", default="ocsvm_scaled")
    p.add_argument("--excluir", default="")
    p.add_argument("--calibrado", default="false",
                   help="'true' solo si el modelo se calibro en ESTA red")
    p.add_argument("--aplicar", action="store_true",
                   help="ejecuta iptables de verdad (requiere root). Sin esto, seco")
    p.add_argument("--forzar", action="store_true",
                   help="aplica aunque el modelo no este calibrado. Peligroso")
    a = p.parse_args()

    redes_fuera = [ipaddress.ip_network(x.strip(), strict=False)
                   for x in a.excluir.split(",") if x.strip()]
    ahora = time.time()
    datos = parse_registro(a.registro, ahora - a.ventana, a.detector)
    cand = candidatos(datos, a.minimo, redes_fuera)

    calibrado = a.calibrado.strip().lower() == "true"
    bloquear = a.aplicar and (calibrado or a.forzar)

    informe = {
        "modo": "aplicar" if bloquear else "seco",
        "calibrado_en_esta_red": calibrado,
        "ventana_s": a.ventana,
        "minimo_alertas": a.minimo,
        "candidatos": cand,
        "n_candidatos": len(cand),
    }

    if a.aplicar and not calibrado and not a.forzar:
        informe["rechazado"] = ("modelo sin calibrar: no se aplica bloqueo. "
                                "Con el umbral de otra red esto bloquearia trafico "
                                "legitimo en masa. Recalibra, o usa --forzar a "
                                "sabiendas.")

    if bloquear:
        activas = iptables_activas(True)
        quiere = {c["ip"] for c in cand}
        nuevas = quiere - activas
        for ip in nuevas:
            aplicar_regla("-I", ip)
        # Expira: desbloquea lo que ya no alerta hace mas de --expira.
        expiradas = []
        for ip in activas - quiere:
            ult = datos["ultima"].get(ip, 0)
            if ahora - ult > a.expira:
                aplicar_regla("-D", ip)
                expiradas.append(ip)
        informe["bloqueadas_nuevas"] = sorted(nuevas)
        informe["desbloqueadas"] = expiradas
        informe["bloqueadas_total"] = sorted((activas | quiere) - set(expiradas))

    print(json.dumps(informe, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
