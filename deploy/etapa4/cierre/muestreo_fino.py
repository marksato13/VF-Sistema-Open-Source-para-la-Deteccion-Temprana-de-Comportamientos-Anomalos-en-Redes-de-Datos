#!/usr/bin/env python3
"""Muestreo fino (1 s) para el ensayo del anillo de Suricata — cierre 4A, 4-nov-2026. Solo lectura, sin sudo.

Complementa a salud_captura (10 s): sirve para ver ráfagas y recursos ALREDEDOR de cada descarte, que
salud_captura y stats.log (8 s) no resuelven. Cada línea JSONL:
  t; nic ens37 (rx_packets, rx_bytes, rx_dropped, rx_missed_errors, rx_fifo_errors);
  suricata (PID principal re-resuelto cada muestra; ticks utime+stime por hilo W#*, RX*, FM*, FR*, etc.;
  VmRSS kB; nº de hilos); cpu (línea agregada de /proc/stat: user,nice,system,idle,iowait,irq,softirq,steal);
  softnet (suma de dropped y time_squeeze de /proc/net/softnet_stat); disco (/proc/diskstats: lecturas,
  escrituras, ms en E/S y ms ponderados de los discos sd*/vd*/nvme*n*); memoria (MemAvailable kB);
  eve (tamaño de eve.json; los segundos sin crecer se deducen después).
Un dato no legible se escribe null con el motivo en «errores»: nunca 0.
  muestreo_fino.py --salida FICHERO.jsonl [--intervalo 1] [--hasta EPOCH]
"""
from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import time

NIC = "ens37"
EVE = "/var/log/suricata/eve.json"
RE_DISCO = re.compile(r"^(sd[a-z]+|vd[a-z]+|nvme\d+n\d+|xvd[a-z]+)$")


def pid_suricata(err):
    try:
        r = subprocess.run(["systemctl", "show", "-p", "MainPID", "--value", "suricata.service"],
                           capture_output=True, text=True, timeout=5)
        p = int(r.stdout.strip() or 0)
        return p or None
    except Exception as exc:  # noqa: BLE001
        err.append("pid: %s" % exc)
        return None


def nic(err):
    d = "/sys/class/net/%s/statistics/" % NIC
    out = {}
    for k in ("rx_packets", "rx_bytes", "rx_dropped", "rx_missed_errors", "rx_fifo_errors"):
        try:
            out[k] = int(open(d + k).read())
        except OSError as exc:
            out[k] = None; err.append("nic %s: %s" % (k, exc))
    return out


def hilos(pid, err):
    if not pid:
        return None
    res = {"pid": pid, "hilos": {}, "rss_kb": None}
    try:
        for tid in os.listdir("/proc/%d/task" % pid):
            try:
                s = open("/proc/%d/task/%s/stat" % (pid, tid)).read()
                nombre = s[s.index("(") + 1:s.rindex(")")]
                campos = s[s.rindex(")") + 2:].split()
                res["hilos"][nombre + "#" + tid] = int(campos[11]) + int(campos[12])
            except (OSError, ValueError) as exc:
                err.append("hilo %s: %s" % (tid, exc))
        for l in open("/proc/%d/status" % pid):
            if l.startswith("VmRSS:"):
                res["rss_kb"] = int(l.split()[1])
    except OSError as exc:
        err.append("suricata: %s" % exc)
        return None
    return res


def main(argv=None) -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--salida", required=True)
    p.add_argument("--intervalo", type=float, default=1.0)
    p.add_argument("--hasta", type=float, default=None)
    a = p.parse_args(argv)
    pid, ultimo_pid = None, 0.0
    with open(a.salida, "a", encoding="utf-8") as fh:
        while True:
            t0 = time.time()
            if a.hasta and t0 > a.hasta:
                return 0
            err = []
            if pid is None or t0 - ultimo_pid > 5 or not os.path.exists("/proc/%d" % pid):
                pid, ultimo_pid = pid_suricata(err), t0
            m = {"t": round(t0, 3), "nic": nic(err), "suricata": hilos(pid, err)}
            try:
                m["cpu"] = [int(x) for x in open("/proc/stat").readline().split()[1:9]]
            except OSError as exc:
                m["cpu"] = None; err.append("cpu: %s" % exc)
            try:
                dr = sq = 0
                for l in open("/proc/net/softnet_stat"):
                    c = l.split(); dr += int(c[1], 16); sq += int(c[2], 16)
                m["softnet"] = {"dropped": dr, "time_squeeze": sq}
            except (OSError, ValueError, IndexError) as exc:
                m["softnet"] = None; err.append("softnet: %s" % exc)
            try:
                dk = {}
                for l in open("/proc/diskstats"):
                    c = l.split()
                    if RE_DISCO.match(c[2]):
                        dk[c[2]] = [int(c[3]), int(c[7]), int(c[12]), int(c[13])]
                m["disco"] = dk
            except (OSError, ValueError, IndexError) as exc:
                m["disco"] = None; err.append("disco: %s" % exc)
            try:
                m["mem_disponible_kb"] = next(int(l.split()[1]) for l in open("/proc/meminfo") if l.startswith("MemAvailable:"))
            except (OSError, StopIteration) as exc:
                m["mem_disponible_kb"] = None; err.append("mem: %s" % exc)
            try:
                m["eve_bytes"] = os.stat(EVE).st_size
            except OSError as exc:
                m["eve_bytes"] = None; err.append("eve: %s" % exc)
            if err:
                m["errores"] = err
            fh.write(json.dumps(m, separators=(",", ":")) + "\n"); fh.flush()
            time.sleep(max(0.0, a.intervalo - (time.time() - t0)))


if __name__ == "__main__":
    sys.exit(main())
