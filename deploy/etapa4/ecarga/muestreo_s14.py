#!/usr/bin/env python3
"""[SENSOR1 m4rk] Muestreo para S14 de E-carga v2 (PROTOCOLO-CARGA-v2 r3 §3.6.1). SOLO LECTURA, sin sudo, cada 1 s.

VERSION 2026-11-06.1. Complementa a muestreo_fino.py, que no lee PSI ni el detalle por CPU. Una línea JSON por muestra:
  t        instante (epoch, s)
  psi      totales acumulados (µs) de /proc/pressure: cpu_some, io_some, io_full, mem_some, mem_full
  cpu      /proc/stat: "cpu" (agregado) y "cpu0".."cpuN": user nice system idle iowait irq softirq steal (ticks)
  softnet  /proc/net/softnet_stat: dropped y time_squeeze sumados, y por CPU [procesados, dropped, time_squeeze]
  disco    /proc/diskstats de sd*/vd*/nvme*n*/xvd*: [ms con E/S en curso (io_ticks), ms ponderados]
  mem_disponible_kb, vmstat {pswpin, pswpout, oom_kill}
  suricata {pid, hilos {nombre#tid: ticks utime+stime}}  (PID principal re-resuelto cada 5 s)
  user_hz  ticks por segundo (os.sysconf SC_CLK_TCK)
Un dato no legible se escribe null con el motivo en «errores»: nunca 0. No escribe fuera de --salida.
  muestreo_s14.py --salida FICHERO.jsonl --hasta EPOCH [--intervalo 1] [--raiz /]
"""
import argparse
import json
import os
import re
import subprocess
import sys
import time

VERSION = "2026-11-06.1"
RE_DISCO = re.compile(r"^(sd[a-z]+|vd[a-z]+|nvme\d+n\d+|xvd[a-z]+)$")


def leer(ruta, raiz):
    with open(os.path.join(raiz, ruta.lstrip("/")), encoding="ascii", errors="replace") as f:
        return f.read()


def psi(raiz, err):
    out = {}
    for r in ("cpu", "io", "memory"):
        try:
            for l in leer(f"/proc/pressure/{r}", raiz).splitlines():
                tipo = l.split()[0]
                tot = int(l.rsplit("total=", 1)[1])
                out[f"{'mem' if r == 'memory' else r}_{tipo}"] = tot
        except (OSError, ValueError, IndexError) as e:
            err.append(f"psi {r}: {e}")
    for k in ("cpu_some", "io_some", "io_full", "mem_some", "mem_full"):
        out.setdefault(k, None)
    return out


def cpu(raiz, err):
    try:
        d = {}
        for l in leer("/proc/stat", raiz).splitlines():
            if l.startswith("cpu"):
                c = l.split()
                d[c[0]] = [int(x) for x in c[1:9]]
        return d or None
    except (OSError, ValueError) as e:
        err.append(f"cpu: {e}")
        return None


def softnet(raiz, err):
    try:
        por = []
        for l in leer("/proc/net/softnet_stat", raiz).splitlines():
            c = l.split()
            por.append([int(c[0], 16), int(c[1], 16), int(c[2], 16)])
        return {"dropped": sum(p[1] for p in por), "time_squeeze": sum(p[2] for p in por), "por_cpu": por}
    except (OSError, ValueError, IndexError) as e:
        err.append(f"softnet: {e}")
        return None


def disco(raiz, err):
    try:
        d = {}
        for l in leer("/proc/diskstats", raiz).splitlines():
            c = l.split()
            if len(c) >= 14 and RE_DISCO.match(c[2]):
                d[c[2]] = [int(c[12]), int(c[13])]
        return d or None
    except (OSError, ValueError) as e:
        err.append(f"disco: {e}")
        return None


def mem(raiz, err):
    try:
        return next(int(l.split()[1]) for l in leer("/proc/meminfo", raiz).splitlines() if l.startswith("MemAvailable:"))
    except (OSError, StopIteration, ValueError, IndexError) as e:
        err.append(f"mem: {e}")
        return None


def vmstat(raiz, err):
    try:
        d = {}
        for l in leer("/proc/vmstat", raiz).splitlines():
            k, _, v = l.partition(" ")
            if k in ("pswpin", "pswpout", "oom_kill"):
                d[k] = int(v)
        for k in ("pswpin", "pswpout", "oom_kill"):
            if k not in d:
                err.append(f"vmstat: falta {k}")
                d[k] = None
        return d
    except (OSError, ValueError) as e:
        err.append(f"vmstat: {e}")
        return None


def pid_suricata(err):
    try:
        r = subprocess.run(["systemctl", "show", "-p", "MainPID", "--value", "suricata.service"],
                           capture_output=True, text=True, timeout=5)
        if r.returncode != 0:
            err.append(f"pid: systemctl rc {r.returncode}")
            return None
        return int(r.stdout.strip() or 0) or None
    except Exception as e:  # noqa: BLE001
        err.append(f"pid: {e}")
        return None


def hilos(pid, raiz, err):
    if not pid:
        err.append("suricata: sin PID")
        return None
    res = {"pid": pid, "hilos": {}}
    try:
        base = os.path.join(raiz, "proc", str(pid), "task")
        for tid in os.listdir(base):
            try:
                s = open(os.path.join(base, tid, "stat")).read()
                nombre = s[s.index("(") + 1:s.rindex(")")]
                c = s[s.rindex(")") + 2:].split()
                res["hilos"][f"{nombre}#{tid}"] = int(c[11]) + int(c[12])
            except (OSError, ValueError, IndexError) as e:
                err.append(f"hilo {tid}: {e}")
    except OSError as e:
        err.append(f"suricata: {e}")
        return None
    return res


def muestra(raiz, pid):
    err = []
    m = {"t": round(time.time(), 3), "psi": psi(raiz, err), "cpu": cpu(raiz, err), "softnet": softnet(raiz, err),
         "disco": disco(raiz, err), "mem_disponible_kb": mem(raiz, err), "vmstat": vmstat(raiz, err),
         "suricata": hilos(pid, raiz, err), "user_hz": os.sysconf("SC_CLK_TCK")}
    if err:
        m["errores"] = err
    return m


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--salida", required=True)
    ap.add_argument("--hasta", type=float, required=True)
    ap.add_argument("--intervalo", type=float, default=1.0)
    ap.add_argument("--raiz", default="/")
    a = ap.parse_args(argv)
    if os.path.exists(a.salida):
        print(f"ABORTA: {a.salida} ya existe (no se sobrescribe)", file=sys.stderr)
        return 2
    pid, t_pid = None, 0.0
    with open(a.salida, "x", encoding="utf-8") as fh:
        fh.write(json.dumps({"inicio": time.time(), "version": VERSION, "hasta": a.hasta}) + "\n")
        while time.time() <= a.hasta:
            t0 = time.time()
            if pid is None or t0 - t_pid > 5 or not os.path.exists(f"/proc/{pid}"):
                e = []
                pid, t_pid = pid_suricata(e), t0
            fh.write(json.dumps(muestra(a.raiz, pid), separators=(",", ":")) + "\n")
            fh.flush()
            time.sleep(max(0.0, a.intervalo - (time.time() - t0)))
        fh.write(json.dumps({"fin": time.time()}) + "\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
