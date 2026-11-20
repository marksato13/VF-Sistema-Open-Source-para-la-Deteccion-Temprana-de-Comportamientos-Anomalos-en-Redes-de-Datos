#!/usr/bin/env python3
"""Comprobaciones de estado de los verificadores de la Etapa 4 (Sensor1 y bastión). SOLO LECTURA.

VERSION 2026-11-06.1. Corrige los tres FALLO desactualizados publicados en los pendientes de la 4A (docs da4c3a0):
  - v1 retirado: el publicador (Sensor1) y el relé (bastión) v1 deben estar INACTIVOS y NO HABILITADOS, y no debe
    quedar ningún proceso v1 en ejecución;
  - motor_startup: se busca en el registro actual y en los rotados (también .gz) y debe corresponder al PROCESO
    VIGENTE del motor: marca de tiempo frente al inicio real del proceso (/proc), línea de ejecución y configuración
    esperada. Un arranque histórico correcto no basta.

Principio: una lectura fallida NUNCA prueba nada. Cualquier error de systemctl, de /proc, de un registro o del
manifiesto produce «FALLO … (no demostrable: motivo)», nunca OK.

Salida: líneas «OK    …», «FALLO …» o «INFO  …». Código de salida: 0 si todo OK, 1 si hay algún FALLO, 2 uso.

  verif_estado.py v1-retirado --unidad U [--unidad U …] --proceso NOMBRE [--proceso NOMBRE …]
  verif_estado.py motor-arranque --unidad ppi-motor --registro LOG --umbral U --disparo eventos
                                 --procesamiento incremental [--max-retraso-s 60]

Banco (solo con CF_BANCO=1): CF_VERIF_SYSTEMCTL (orden systemctl) y CF_VERIF_PROC (raíz de /proc).
"""
import argparse
import gzip
import json
import os
import re
import shlex
import subprocess
import sys
import zlib

VERSION = "2026-11-06.1"
TOL_ANTES_S = 1.5  # btime de /proc/stat va en segundos enteros: el inicio calculado puede adelantarse hasta 1 s


class NoDemostrable(Exception):
    pass


def entorno():
    sc, proc = ["systemctl"], "/proc"
    if os.environ.get("CF_BANCO") == "1":
        sc = shlex.split(os.environ.get("CF_VERIF_SYSTEMCTL", "systemctl"))
        proc = os.environ.get("CF_VERIF_PROC", "/proc")
    return sc, proc


# ------------------------------------------------------------------ systemd
PROPS = ("LoadState", "ActiveState", "SubState", "UnitFileState", "MainPID")


def unidad(nombre, systemctl):
    cmd = systemctl + ["show", nombre] + [a for p in PROPS for a in ("-p", p)]
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=20)
    except (OSError, subprocess.TimeoutExpired) as e:
        raise NoDemostrable(f"systemctl show {nombre}: {e}")
    if r.returncode != 0:
        raise NoDemostrable(f"systemctl show {nombre} rc={r.returncode}: {r.stderr.strip()[:160]}")
    props = {}
    for linea in r.stdout.splitlines():
        if "=" in linea:
            k, v = linea.split("=", 1)
            props[k] = v
    falta = [k for k in ("LoadState", "ActiveState", "UnitFileState") if k not in props]
    if falta:
        raise NoDemostrable(f"systemctl show {nombre} sin {', '.join(falta)}")
    return props


# ------------------------------------------------------------------ /proc
def ocultacion_proc(proc):
    """None si /proc muestra todos los procesos; si no, el motivo (hidepid)."""
    try:
        with open(os.path.join(proc, "self", "mountinfo"), encoding="utf-8") as f:
            for linea in f:
                partes = linea.split()
                if len(partes) > 4 and partes[4] == "/proc":
                    opciones = " ".join(partes[5:])
                    m = re.search(r"hidepid=(\w+)", opciones)
                    if m and m.group(1) not in ("0", "off"):
                        return f"/proc montado con hidepid={m.group(1)}"
                    return None
    except OSError as e:
        return f"no se puede leer {proc}/self/mountinfo: {e}"
    return f"/proc no aparece en {proc}/self/mountinfo"


def ancestros():
    """PID propio y de sus antecesores (se excluyen: su línea de órdenes lleva los nombres buscados)."""
    pids, p = set(), os.getpid()
    while p > 1 and p not in pids:
        pids.add(p)
        try:
            with open(f"/proc/{p}/stat", encoding="utf-8") as f:
                p = int(f.read().rsplit(")", 1)[1].split()[1])
        except (OSError, ValueError, IndexError):
            break
    return pids


def procesos(proc):
    """[(pid, argv)] de todos los procesos con línea de órdenes. Error de lectura = NoDemostrable."""
    oculto = ocultacion_proc(proc)
    if oculto:
        raise NoDemostrable(oculto)
    try:
        entradas = [e for e in os.listdir(proc) if e.isdigit()]
    except OSError as e:
        raise NoDemostrable(f"no se puede listar {proc}: {e}")
    if not entradas:
        raise NoDemostrable(f"{proc} sin procesos visibles")
    res, ilegibles = [], []
    for e in entradas:
        try:
            with open(os.path.join(proc, e, "cmdline"), "rb") as f:
                b = f.read()
        except (FileNotFoundError, ProcessLookupError):
            continue  # terminó mientras se recorría /proc
        except OSError as ex:
            ilegibles.append(f"{e}: {ex.strerror}")
            continue
        if b:
            res.append((int(e), [a.decode("utf-8", "replace") for a in b.rstrip(b"\0").split(b"\0")]))
    if ilegibles:
        raise NoDemostrable(f"líneas de órdenes ilegibles: {', '.join(ilegibles[:5])}")
    return res


def inicio_proceso(proc, pid):
    """Inicio real del proceso (epoch) = btime + starttime / CLK_TCK."""
    try:
        with open(os.path.join(proc, str(pid), "stat"), encoding="utf-8") as f:
            campos = f.read().rsplit(")", 1)[1].split()
        arranque = int(campos[19])
        with open(os.path.join(proc, "stat"), encoding="utf-8") as f:
            btime = [int(l.split()[1]) for l in f if l.startswith("btime ")]
    except (OSError, ValueError, IndexError) as e:
        raise NoDemostrable(f"inicio del proceso {pid} ilegible: {e}")
    if len(btime) != 1:
        raise NoDemostrable(f"btime ausente en {proc}/stat")
    return btime[0] + arranque / os.sysconf("SC_CLK_TCK")


def cmdline(proc, pid):
    try:
        with open(os.path.join(proc, str(pid), "cmdline"), "rb") as f:
            b = f.read()
    except OSError as e:
        raise NoDemostrable(f"línea de órdenes del PID {pid} ilegible: {e}")
    if not b:
        raise NoDemostrable(f"línea de órdenes del PID {pid} vacía")
    return [a.decode("utf-8", "replace") for a in b.rstrip(b"\0").split(b"\0")]


# ------------------------------------------------------------------ v1 retirado
def v1_retirado(unidades, nombres, systemctl, proc):
    """Lista de (ok, texto). Timers: inactivos y disabled/masked (o sin cargar). Servicios: inactivos y
    disabled/masked, o «static» SOLO si todos los timers indicados están retirados (un static no se habilita: solo
    lo arranca su timer o una orden manual, y lo segundo lo cubre la búsqueda de procesos)."""
    out, timers_ok, estados = [], True, {}
    for u in unidades:
        try:
            estados[u] = unidad(u, systemctl)
        except NoDemostrable as e:
            estados[u] = e
    for u in unidades:
        p = estados[u]
        if isinstance(p, NoDemostrable):
            out.append((False, f"v1 {u} retirado (no demostrable: {p})"))
            timers_ok = timers_ok and not u.endswith(".timer")
            continue
        carga, act, fich = p["LoadState"], p["ActiveState"], p["UnitFileState"]
        desc = f"LoadState={carga} ActiveState={act} UnitFileState={fich or '-'}"
        if carga == "not-found" and act == "inactive":
            out.append((True, f"v1 {u} retirado (unidad no instalada; {desc})"))
            continue
        if carga not in ("loaded", "masked"):
            ok = False
        elif u.endswith(".timer"):
            ok = act == "inactive" and fich in ("disabled", "masked")
            timers_ok = timers_ok and ok
        else:
            ok = act == "inactive" and fich in ("disabled", "masked", "static")
        out.append((ok, f"v1 {u} inactivo y no habilitado ({desc})"))
    hay_timer = any(u.endswith(".timer") for u in unidades)
    for i, (ok, txt) in enumerate(out):
        if ok and "UnitFileState=static" in txt and not (hay_timer and timers_ok):
            out[i] = (False, txt + " — static solo vale con su timer retirado, y no está demostrado")
    try:
        excluir = ancestros()
        vivos = [(pid, a) for pid, a in procesos(proc) if pid not in excluir
                 and any(os.path.basename(x) in nombres for x in a)]
        if vivos:
            out.append((False, "sin procesos v1 en ejecución: " + "; ".join(
                f"PID {pid} «{' '.join(a)[:120]}»" for pid, a in vivos[:5])))
        else:
            out.append((True, f"sin procesos v1 en ejecución ({', '.join(nombres)})"))
    except NoDemostrable as e:
        out.append((False, f"sin procesos v1 en ejecución (no demostrable: {e})"))
    return out


# ------------------------------------------------------------------ motor_startup del proceso vigente
OPCIONES = {  # opción de motor_decision.py -> (clave del evento motor_startup, conversión)
    "--model-path": ("model_path", str),
    "--manifest-path": ("manifest_path", str),
    "--detector-name": ("detector_name", str),
    "--disparo": ("disparo", str),
    "--eve-path": ("eve_path", str),
    "--capture-dir": ("capture_dir", str),
    "--entity-network": ("entity_network", str),
    "--step-seconds": ("step_seconds", float),
    "--history-seconds": ("history_seconds", float),
    "--excluir": ("excluidas", lambda v: sorted(x for x in v.split(",") if x)),
    "--excluir-protocolos": ("protocolos_excluidos", lambda v: sorted(int(x) for x in v.split(",") if x)),
}
OBLIGATORIAS = ("--model-path", "--manifest-path", "--detector-name", "--disparo")


def valores_cmdline(argv):
    v = {}
    for i, a in enumerate(argv):
        if a in OPCIONES and i + 1 < len(argv):
            v[a] = argv[i + 1]
        elif "=" in a and a.split("=", 1)[0] in OPCIONES:
            k, x = a.split("=", 1)
            v[k] = x
    return v


def registros(base):
    """[base, base.1, base.2(.gz), …] existentes, del más nuevo al más viejo. El actual debe existir."""
    if not os.path.isfile(base):
        raise NoDemostrable(f"registro actual ausente: {base}")
    d, n = os.path.dirname(base) or ".", os.path.basename(base)
    try:
        nombres = os.listdir(d)
    except OSError as e:
        raise NoDemostrable(f"no se puede listar {d}: {e}")
    rot = []
    for x in nombres:
        m = re.fullmatch(re.escape(n) + r"\.(\d+)(\.gz)?", x)
        if m:
            rot.append((int(m.group(1)), os.path.join(d, x)))
    return [base] + [p for _, p in sorted(rot)]


def arranques(ruta):
    """Eventos motor_startup de un registro (texto o .gz). Error de lectura o línea de arranque corrupta = NoDemostrable."""
    abrir = gzip.open if ruta.endswith(".gz") else open
    res = []
    try:
        with abrir(ruta, "rt", encoding="utf-8", errors="strict") as f:
            for n, linea in enumerate(f, 1):
                if '"motor_startup"' not in linea:
                    continue
                try:
                    e = json.loads(linea)
                except ValueError:
                    if linea.endswith("\n"):
                        raise NoDemostrable(f"línea de arranque corrupta en {ruta}:{n}")
                    continue  # última línea a medio escribir
                if e.get("event") == "motor_startup":
                    t = e.get("timestamp")
                    if not isinstance(t, (int, float)):
                        raise NoDemostrable(f"arranque sin marca de tiempo numérica en {ruta}:{n}")
                    res.append((float(t), ruta, e))
    except NoDemostrable:
        raise
    except (OSError, EOFError, UnicodeDecodeError, zlib.error, gzip.BadGzipFile) as e:
        raise NoDemostrable(f"no se puede leer {ruta}: {e}")
    return res


def umbral_manifiesto(ruta, detector):
    try:
        with open(ruta, encoding="utf-8") as f:
            m = json.load(f)
        return float(m["detectors"][detector]["calibration"]["threshold"])
    except (OSError, ValueError, KeyError, TypeError) as e:
        raise NoDemostrable(f"umbral del manifiesto {ruta} ilegible para {detector}: {e!r}")


def motor_arranque(unidad_motor, base, umbral, disparo, procesamiento, max_retraso, systemctl, proc):
    """(ok, [líneas]). OK solo si hay exactamente un motor_startup del proceso vigente y su configuración es la
    esperada y la de su línea de ejecución."""
    lineas = []
    try:
        p = unidad(unidad_motor, systemctl)
        if p["ActiveState"] != "active":
            return False, [f"FALLO motor_startup del proceso vigente: {unidad_motor} no está activo "
                           f"({p['ActiveState']})"]
        try:
            pid = int(p.get("MainPID", "0"))
        except ValueError:
            pid = 0
        if pid <= 0:
            raise NoDemostrable(f"{unidad_motor} sin MainPID")
        ini = inicio_proceso(proc, pid)
        argv = cmdline(proc, pid)
        rutas = registros(base)
        try:
            usadas = [r for r in rutas if r == base or os.path.getmtime(r) >= ini - TOL_ANTES_S]
        except OSError as e:
            raise NoDemostrable(f"fecha de un registro rotado ilegible: {e}")
        todos = [a for r in usadas for a in arranques(r)]
        lineas.append(f"INFO  motor PID {pid}, inicio real {ini:.2f}; registros leídos: "
                      f"{', '.join(os.path.basename(r) for r in usadas)} ({len(rutas) - len(usadas)} rotados "
                      f"anteriores al inicio, no pueden contener su arranque)")
        cand = [a for a in todos if ini - TOL_ANTES_S <= a[0] <= ini + max_retraso]
        posteriores = [a for a in todos if a[0] > ini + max_retraso]
        if posteriores:
            raise NoDemostrable(f"hay arranques posteriores al del proceso vigente ({posteriores[-1][0]:.2f}): "
                                f"no corresponden al PID {pid}")
        if not cand:
            prev = max((a[0] for a in todos), default=None)
            if prev is None:
                raise NoDemostrable("no hay ningún motor_startup en los registros que pueden contenerlo")
            raise NoDemostrable(f"solo hay arranques anteriores al proceso vigente (último {prev:.2f}, proceso desde "
                                f"{ini:.2f}): el arranque del proceso vigente no está en los registros")
        if len(cand) > 1:
            raise NoDemostrable(f"{len(cand)} arranques compatibles con el inicio del PID {pid}: ambiguo")
        t, ruta, e = cand[0]
    except NoDemostrable as ex:
        return False, lineas + [f"FALLO motor_startup del proceso vigente (no demostrable: {ex})"]
    errores = []
    v = valores_cmdline(argv)
    for opt in OBLIGATORIAS:
        if opt not in v:
            errores.append(f"la línea de ejecución no lleva {opt}")
    for opt, x in v.items():
        clave, conv = OPCIONES[opt]
        try:
            esperado = conv(x)
            ev = e.get(clave)
            ev = sorted(ev) if isinstance(ev, list) else (float(ev) if conv is float and ev is not None else ev)
        except (ValueError, TypeError) as ex:
            errores.append(f"{opt} no comparable: {ex}")
            continue
        if ev != esperado:
            errores.append(f"{clave}: evento {ev!r} ≠ ejecución {esperado!r}")
    if e.get("disparo") != disparo:
        errores.append(f"disparo {e.get('disparo')!r} ≠ esperado {disparo!r}")
    if e.get("procesamiento") != procesamiento:
        errores.append(f"procesamiento {e.get('procesamiento')!r} ≠ esperado {procesamiento!r}")
    try:  # el umbral esperado sale del manifiesto y del detector de la LÍNEA DE EJECUCIÓN, no del propio evento
        um = umbral_manifiesto(v.get("--manifest-path", ""), v.get("--detector-name", ""))
        if e.get("threshold") != um:
            errores.append(f"threshold del evento {e.get('threshold')!r} ≠ manifiesto {um!r}")
        if um != umbral:
            errores.append(f"umbral del manifiesto {um!r} ≠ congelado {umbral!r}")
    except NoDemostrable as ex:
        return False, lineas + [f"FALLO motor_startup del proceso vigente (no demostrable: {ex})"]
    desc = (f"PID {pid}, inicio {ini:.2f}, evento +{t - ini:.2f} s en {os.path.basename(ruta)}")
    if errores:
        return False, lineas + [f"FALLO motor_startup del proceso vigente con configuración distinta ({desc}): "
                                + "; ".join(errores)]
    return True, lineas + [f"OK    motor_startup del proceso vigente ({desc}; disparo {disparo}, {procesamiento}, "
                           f"umbral {umbral} = manifiesto; {len(v)} opciones de la ejecución coinciden)"]


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="orden", required=True)
    a = sub.add_parser("v1-retirado")
    a.add_argument("--unidad", action="append", required=True)
    a.add_argument("--proceso", action="append", required=True, help="nombre (basename) de un ejecutable o guion v1")
    b = sub.add_parser("motor-arranque")
    b.add_argument("--unidad", required=True)
    b.add_argument("--registro", required=True)
    b.add_argument("--umbral", type=float, required=True)
    b.add_argument("--disparo", required=True)
    b.add_argument("--procesamiento", required=True)
    b.add_argument("--max-retraso-s", type=float, default=60.0)
    x = ap.parse_args(argv)
    sc, proc = entorno()
    if x.orden == "v1-retirado":
        res = v1_retirado(x.unidad, set(x.proceso), sc, proc)
        for ok, txt in res:
            print(("OK    " if ok else "FALLO ") + txt)
        return 0 if all(ok for ok, _ in res) else 1
    ok, lineas = motor_arranque(x.unidad, x.registro, x.umbral, x.disparo, x.procesamiento, x.max_retraso_s, sc, proc)
    print("\n".join(lineas))
    return 0 if ok else 1


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as e:  # cualquier error no previsto es FALLO, nunca OK
        print(f"FALLO verif_estado {VERSION}: error inesperado {e!r}")
        sys.exit(1)
