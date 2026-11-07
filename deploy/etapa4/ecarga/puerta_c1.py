#!/usr/bin/env python3
"""Puerta del paso C1 de E-carga v2. SOLO LECTURA. VERSION 2026-11-07.1. La usa arrancar_c1.sh dentro del cerrojo, justo
antes de emitir la orden de arranque. No contiene ninguna condición de parada nueva: las de §3.7 siguen en guardia.py.

  puerta_c1.py DIR_MUESTREO AHORA_EPOCH [--solo-muestreador]  -> JSON {"autoriza", "motivos", "comprobaciones"}

Autoriza solo si se cumplen las tres:
  1. Muestreador vivo: la primera línea de muestreo.pid es de esta versión y modo real; su PID existe, su argv es
     muestreo_bastion.sh con este DIR y modo real; y no consta el final del muestreo.
  2. Ninguna solicitud de parada: ni PARADA-SOLICITADA, ni parada.jsonl con contenido, ni PARADA-NO-CONFIRMADA, ni
     C1-PARADA-NO-CONFIRMADA, ni RESULTADO-PARADA, ni ninguna lectura de la guardia con "parar": true.
  3. Lectura válida y reciente de la guardia: la última línea de guardia.jsonl es un objeto con parar=false, muestras
     >= 1 y t numérico; sin SIN_LECTURA de esa misma muestra; con edad entre 0 y 60 s (el criterio de lecturas <= 60 s
     del protocolo).
rc: 0 autoriza; 1 no autoriza (motivos en el JSON). Cualquier fallo de lectura no autoriza.
"""
import json
import os
import re
import sys
from pathlib import Path

VERSION = "puerta_c1 2026-11-07.1"
VERSION_MUESTREO = "2026-11-07.1"
EDAD_MAX_S = 60
PID_RE = re.compile(r"^(\d+) \S+ inicio muestreo v(\S+) modo=(\S+) fin=(\d+) parada=(\d+) intentos_max=\d+$")


def texto(p):
    try:
        return p.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return None


def muestreador(o, proc):
    t = texto(o / "muestreo.pid")
    if t is None or not t.strip():
        return False, "muestreador: muestreo.pid ausente o vacío"
    lineas = t.splitlines()
    m = PID_RE.match(lineas[0])
    if not m:
        return False, "muestreador: primera línea de muestreo.pid no reconocida"
    pid, version, modo = m.group(1), m.group(2), m.group(3)
    if version != VERSION_MUESTREO:
        return False, f"muestreador: versión {version}, se exige {VERSION_MUESTREO}"
    if modo != "real":
        return False, f"muestreador: modo {modo}, se exige real"
    if any(" fin muestreo;" in x for x in lineas[1:]):
        return False, "muestreador: ya terminó"
    try:
        argv = [a.decode("utf-8", "replace") for a in (proc / pid / "cmdline").read_bytes().split(b"\0") if a]
    except OSError:
        return False, f"muestreador: PID {pid} no está vivo"
    guion = any(os.path.basename(a) == "muestreo_bastion.sh" for a in argv)
    mismo_dir = any(os.path.realpath(a) == os.path.realpath(o) for a in argv)
    if not (guion and mismo_dir and "real" in argv):
        return False, f"muestreador: el PID {pid} no es muestreo_bastion.sh de este DIR en modo real"
    return True, None


def solicitud(o):
    mot = []
    for n in ("PARADA-SOLICITADA", "PARADA-NO-CONFIRMADA", "C1-PARADA-NO-CONFIRMADA", "RESULTADO-PARADA"):
        if (o / n).exists():
            mot.append(f"solicitud de parada: existe {n}")
    t = texto(o / "parada.jsonl")
    if t and t.strip():
        mot.append("solicitud de parada: parada.jsonl con contenido")
    return mot


def guardia(o, ahora):
    t = texto(o / "guardia.jsonl")
    if t is None or not t.strip():
        return ["guardia: sin lecturas"]
    lineas = t.split("\n")
    if lineas[-1] == "":
        lineas.pop()
    mot = []
    for x in lineas:
        try:
            if json.loads(x).get("parar") is True:
                mot.append("solicitud de parada: alguna lectura de la guardia pide parar")
                break
        except (ValueError, AttributeError):
            pass
    try:
        u = json.loads(lineas[-1])
    except ValueError:
        return mot + ["guardia: última lectura inválida (no es JSON)"]
    if not isinstance(u, dict):
        return mot + ["guardia: última lectura inválida (no es un objeto)"]
    if not isinstance(u.get("parar"), bool) or not isinstance(u.get("muestras"), int) or isinstance(u.get("muestras"), bool) \
            or u["muestras"] < 1 or isinstance(u.get("t"), bool) or not isinstance(u.get("t"), (int, float)) \
            or not isinstance(u.get("avisos"), list):
        return mot + ["guardia: última lectura inválida (campos)"]
    ult = f"SIN_LECTURA {u['t']:.0f}"
    falta = [a for a in u["avisos"] if isinstance(a, str) and (a.startswith(ult) or a.startswith("SIN_LECTURA: "))]
    if falta:
        mot.append("guardia: última lectura incompleta: " + "; ".join(falta)[:300])
    edad = ahora - u["t"]
    if edad > EDAD_MAX_S:
        mot.append(f"guardia: lectura desactualizada ({edad:.0f} s > {EDAD_MAX_S} s)")
    elif edad < 0:
        mot.append(f"guardia: lectura con hora futura ({-edad:.0f} s)")
    return mot


def evaluar(o, ahora, proc=Path("/proc"), solo_muestreador=False):
    vivo, m = muestreador(o, proc)
    mot = [m] if m else []
    if not solo_muestreador:
        mot += solicitud(o) + guardia(o, ahora)
    return {"version": VERSION, "ahora": ahora, "autoriza": not mot, "motivos": list(dict.fromkeys(mot)),
            "muestreador_vivo": vivo}


if __name__ == "__main__":
    if len(sys.argv) < 3 or not re.fullmatch(r"\d+", sys.argv[2]):
        print(json.dumps({"version": VERSION, "autoriza": False, "motivos": ["uso"]}))
        sys.exit(1)
    r = evaluar(Path(sys.argv[1]), int(sys.argv[2]), Path(os.environ.get("CF_PROC_BASTION", "/proc")),
                "--solo-muestreador" in sys.argv[3:])
    print(json.dumps(r, ensure_ascii=False))
    sys.exit(0 if r["autoriza"] else 1)
