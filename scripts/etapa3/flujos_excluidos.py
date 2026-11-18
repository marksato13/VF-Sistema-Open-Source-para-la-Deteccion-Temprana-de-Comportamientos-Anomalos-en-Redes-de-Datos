#!/usr/bin/env python3
"""Etapa 3 (punto 6): ¿qué tráfico se pierde cuando los paquetes de E pasan a un excluido?

Para cada caso (entidad E, fin de ventana A), lista los flujos entre E y las IP excluidas
de la evaluación con tramas en (A - 60, A]: protocolo, puertos, paquetes por sentido,
primera trama del flujo en el archivo (si empezó antes del horizonte A - 230 s, la
atribución congelada ya no ve su primer paquete y lo asigna al otro extremo).
Clasifica el puerto de servicio (syslog, SNMP, Zabbix, NTP, DNS, LDAP, SMB, HTTP...).

Uso: python flujos_excluidos.py dir-pcap salida.json "E|HH:MM:SS" [...] --excluidas ip,ip,...
"""
from __future__ import annotations

import argparse
import collections
import datetime as dt
import json
import struct
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "engine"))
from detector_rapido import LectorPcap  # noqa: E402

SERVICIOS = {514: "syslog", 161: "snmp", 162: "snmp-trap", 10050: "zabbix-agente", 10051: "zabbix-servidor",
             123: "ntp", 53: "dns", 389: "ldap", 636: "ldaps", 445: "smb", 135: "rpc", 88: "kerberos",
             80: "http", 443: "https", 22: "ssh", 3268: "gc", 9100: "node-exporter", 1514: "wazuh",
             1515: "wazuh-alta", 55000: "wazuh-api", 3000: "grafana", 9090: "prometheus"}


def ip4(b):
    return ".".join(map(str, b))


def l4(fr):
    off = 14
    et = struct.unpack("!H", fr[12:14])[0]
    while et == 0x8100:
        et = struct.unpack("!H", fr[off + 2:off + 4])[0]
        off += 4
    if et != 0x0800 or len(fr) < off + 20:
        return None
    proto = fr[off + 9]
    ihl = (fr[off] & 15) * 4
    src, dst = ip4(fr[off + 12:off + 16]), ip4(fr[off + 16:off + 20])
    sp = dp = 0
    if proto in (6, 17) and len(fr) >= off + ihl + 4:
        sp, dp = struct.unpack("!HH", fr[off + ihl:off + ihl + 4])
    return proto, src, dst, sp, dp


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("pcap", type=Path)
    ap.add_argument("salida", type=Path)
    ap.add_argument("casos", nargs="+")
    ap.add_argument("--excluidas", required=True)
    ap.add_argument("--fecha", default="2026-11-01")
    a = ap.parse_args()
    exc = set(a.excluidas.split(","))
    casos = []
    for c in a.casos:
        e, h = c.split("|")
        A = dt.datetime.fromisoformat("%sT%s+00:00" % (a.fecha, h)).timestamp()
        casos.append((e, A))
    t_min = min(A for _, A in casos) - 1800
    t_max = max(A for _, A in casos)
    ents = {e for e, _ in casos}
    primero: dict[tuple, float] = {}
    tramas: dict[tuple, list] = collections.defaultdict(list)
    for f in sorted(a.pcap.glob("live-*.pcap")):
        m = dt.datetime.strptime(f.stem[5:], "%Y%m%d%H%M%S").replace(tzinfo=dt.timezone.utc).timestamp()
        if m < t_min - 20 or m > t_max:
            continue
        with f.open("rb") as fh:
            lp = LectorPcap(fh)
            while True:
                x = lp.siguiente()
                if x is None:
                    break
                t, fr = x
                p = l4(fr)
                if not p:
                    continue
                proto, s, d, sp, dp = p
                if not ((s in ents and d in exc) or (d in ents and s in exc)):
                    continue
                e, o = (s, d) if s in ents else (d, s)
                pe, po = (sp, dp) if s in ents else (dp, sp)
                k = (e, o, proto, pe, po)
                primero.setdefault(k, t)
                tramas[k].append((t, s == e))
    res = []
    for e, A in casos:
        flujos = []
        for k, lst in tramas.items():
            if k[0] != e:
                continue
            en = [x for x in lst if A - 60 < x[0] <= A]
            if not en:
                continue
            servicio = SERVICIOS.get(k[4]) or SERVICIOS.get(k[3]) or "otro"
            flujos.append({"otro": k[1], "proto": {6: "tcp", 17: "udp", 1: "icmp"}.get(k[2], k[2]),
                           "puerto_E": k[3], "puerto_otro": k[4], "servicio": servicio,
                           "tramas_60s_E_a_otro": sum(1 for x in en if x[1]),
                           "tramas_60s_otro_a_E": sum(1 for x in en if not x[1]),
                           "primera_trama_flujo_s_antes_de_A": round(A - primero[k], 1),
                           "empezo_antes_del_horizonte_230s": A - primero[k] > 230})
        res.append({"entidad": e, "fin_ventana": dt.datetime.fromtimestamp(A, dt.timezone.utc).isoformat(),
                    "flujos_con_excluidas": sorted(flujos, key=lambda x: -(x["tramas_60s_E_a_otro"] + x["tramas_60s_otro_a_E"]))})
    a.salida.write_text(json.dumps(res, indent=1), encoding="utf-8")
    for r in res:
        print(r["entidad"], r["fin_ventana"][11:19])
        for f in r["flujos_con_excluidas"][:6]:
            print("   ", f["otro"], f["proto"], f["puerto_E"], "->", f["puerto_otro"], f["servicio"],
                  "E>o", f["tramas_60s_E_a_otro"], "o>E", f["tramas_60s_otro_a_E"],
                  "inicio hace", f["primera_trama_flujo_s_antes_de_A"], "s")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
