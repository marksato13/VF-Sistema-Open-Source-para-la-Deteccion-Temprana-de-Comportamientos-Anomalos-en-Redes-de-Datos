#!/usr/bin/env python3
"""cf-4b-rotacion · aplazar la ejecución diaria de logrotate durante la 4B y reanudarla solo si la corrida se cerró bien.

PROPUESTA (2026-11-08), no instalada en ningún host. Solo biblioteca estándar. Subcomandos:

  armar --tope EPOCH [--fase 4b]   (root) 1) guarda la línea base; 2) ARMA la recuperación (temporizador absoluto de tope y vigía);
                                   3) VERIFICA que ambos están armados; 4) solo entonces para logrotate.timer y verifica que paró.
                                   Si algo falla, revierte: logrotate.timer nunca queda parado sin recuperación armada.
  comprobar                        (solo lectura) compara con la línea base si algún fichero protegido se ha rotado o reescrito.
  cierre [--fase 4b]               (solo lectura) ¿la corrida se cerró bien y sus copias verifican? (ver abajo)
  vigilar --tope EPOCH             (lo lanza armar) reanuda logrotate.timer cuando cierre Y comprobar dan OK, o en el tope.
  reanudar-tope                    (lo lanza el temporizador absoluto) arranca logrotate.timer si sigue parado.
  desarmar                         (root) revierte a mano: arranca logrotate.timer y retira las unidades de recuperación.

Qué se comprueba para decir que NO hubo rotación (no basta el inodo): el fichero existe, mismo inodo, tamaño no menor que
el de la línea base, hash de sus primeros N bytes igual al de la línea base (copytruncate o reescritura lo cambian), ningún
fichero rotado nuevo ni modificado (eve.json.*, stats.log.*, motor_decision.log.*, feed-v2/*.jsonl.*, …) y, en systemd,
que logrotate.service no se ha ejecutado desde la línea base (InvocationID y marca de arranque) ni logrotate.timer disparado.

Qué es «cierre exitoso» (necesario para la reanudación normal): replay con rc=0; s40 empezó (cierre.t); archivador rc=0 y
ESTADO OK; ningún FALLO/PERDIDO en archivar.log; copias/SHA256SUMS existe, VERIFICA y contiene los ficheros imprescindibles;
la copia del motor no es menor que la línea base y existe el segmento EVE. El resultado del cierre NO decide si la 4B fue válida:
solo si ya es seguro dejar rotar.
"""
from __future__ import annotations

import argparse
import datetime as dt
import glob
import hashlib
import json
import os
import subprocess
import sys
import time

VERSION = "2026-11-08.2"
HOME = os.environ.get("CF_HOME", "/home/m4rk")
ESTADO = os.environ.get("CF_ESTADO", "/var/lib/cf-4b-rotacion")
SYSTEMCTL = os.environ.get("CF_SYSTEMCTL", "systemctl")
SYSTEMD_RUN = os.environ.get("CF_SYSTEMD_RUN", "systemd-run")
SELF = os.environ.get("CF_SELF", "/usr/local/sbin/cf-4b-rotacion")
SURICATA = os.environ.get("CF_SURICATA", "/var/log/suricata")
TIMER = os.environ.get("CF_TIMER", "logrotate.timer")        # solo se cambia en las pruebas con una unidad de prueba
SERVICIO = os.environ.get("CF_SERVICIO", "logrotate.service")
UNIT_TOPE, UNIT_VIGIA = "cf-4b-tope", "cf-4b-vigia"
PREFIJO_MAX = 16 << 20
IMPRESCINDIBLES = ("motor_decision.log", "ciclos.jsonl", "eve-segmento.json", "stats-fin.log", "muestras.jsonl", "archivar.log",
                   "archivador-ESTADO.txt", "servicios-fin.txt", "sha256-feed-final.txt", "feed-v2/feed.json",
                   "feed-v2/via-rapida-resumen.jsonl", "feed-v2/traza.jsonl")


def ahora() -> float:
    return time.time()


def log(msg: str) -> None:
    linea = f"{dt.datetime.fromtimestamp(ahora(), dt.timezone.utc).strftime('%FT%TZ')} {msg}"
    print(linea, flush=True)
    try:
        os.makedirs(ESTADO, exist_ok=True)
        with open(os.path.join(ESTADO, "log.txt"), "a", encoding="utf-8") as fh:
            fh.write(linea + "\n")
    except OSError:
        pass


def run(cmd: list[str], timeout: float = 30.0) -> tuple[int, str]:
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
        return r.returncode, (r.stdout or "") + (r.stderr or "")
    except (OSError, subprocess.TimeoutExpired) as e:
        return 127, f"{e.__class__.__name__}: {e}"


def activo(unit: str) -> str:
    lineas = run([SYSTEMCTL, "is-active", unit])[1].strip().splitlines()
    return lineas[0] if lineas else ""


def props(unit: str, *p: str) -> dict:
    rc, out = run([SYSTEMCTL, "show", unit] + [f"-p{x}" for x in p])
    return dict(l.split("=", 1) for l in out.splitlines() if "=" in l) if rc == 0 else {}


# ------------------------------------------------------------------------------------------------ línea base y comprobación
def protegidos() -> list[str]:
    return [f"{SURICATA}/eve.json", f"{SURICATA}/stats.log", f"{HOME}/cyberflow/logs/motor_decision.log",
            f"{HOME}/cyberflow/logs/_state-e4/ciclos.jsonl", f"{HOME}/feed-v2/via-rapida-resumen.jsonl", f"{HOME}/feed-v2/traza.jsonl",
            f"{HOME}/feed-v2/senales-if.jsonl", f"{HOME}/feed-v2/senales-rapidas.jsonl"]


def hermanos() -> list[list]:
    pats = [f"{SURICATA}/eve.json.*", f"{SURICATA}/stats.log.*", f"{SURICATA}/suricata.log.*", f"{SURICATA}/fast.log.*",
            f"{HOME}/cyberflow/logs/motor_decision.log.*", f"{HOME}/feed-v2/*.jsonl.*"]
    out = []
    for p in pats:
        for f in sorted(glob.glob(p)):
            try:
                s = os.stat(f)
                out.append([f, s.st_size, s.st_mtime_ns])
            except OSError:
                out.append([f, None, None])
    return out


def prefijo_sha(path: str, n: int) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        resto = n
        while resto > 0:
            b = fh.read(min(1 << 20, resto))
            if not b:
                break
            h.update(b)
            resto -= len(b)
    return h.hexdigest()


def foto(path: str) -> dict | None:
    try:
        s = os.stat(path)
        n = min(s.st_size, PREFIJO_MAX)
        return {"inodo": s.st_ino, "tam": s.st_size, "prefijo_bytes": n, "prefijo_sha256": prefijo_sha(path, n)}
    except OSError:
        return None


def sistema() -> dict:
    return {"logrotate.service": props(SERVICIO, "InvocationID", "ExecMainStartTimestampMonotonic", "ActiveEnterTimestampMonotonic"),
            "logrotate.timer": props(TIMER, "LastTriggerUSec")}


def sistema_igual(unidad: str, antes: dict, ahora_: dict) -> bool:
    """Un timer PARADO informa LastTriggerUSec vacío (verificado en systemd 255): solo se compara si ambos lados lo traen.
    Los disparos con el timer parado son imposibles; los de antes del stop los cubre la comparación de ficheros."""
    if unidad == "logrotate.timer":
        a, b = antes.get("LastTriggerUSec", ""), ahora_.get("LastTriggerUSec", "")
        return not a or not b or a == b
    return antes == ahora_


def linea_base(tope: float | None = None, fase: str = "4b") -> dict:
    return {"version": VERSION, "tomada_en": ahora(), "fase": fase, "tope_epoch": tope,
            "ficheros": {p: foto(p) for p in protegidos()}, "hermanos": hermanos(), "sistema": sistema()}


def leer_base() -> dict:
    with open(os.path.join(ESTADO, "base.json"), encoding="utf-8") as fh:
        return json.load(fh)


def comprobar(base: dict) -> tuple[bool, list[str]]:
    lin, ok = [], True

    def f(cond: bool, texto: str) -> None:
        nonlocal ok
        lin.append(("OK    " if cond else "FALLO ") + texto)
        ok = ok and cond
    for p, b in base["ficheros"].items():
        if b is None:
            continue                                    # no existía al tomar la base: no se exige
        a = foto(p)
        if a is None:
            f(False, f"{p}: ya no existe en su ruta (renombrado o borrado)")
            continue
        f(a["inodo"] == b["inodo"], f"{p}: inodo {b['inodo']} -> {a['inodo']}")
        f(a["tam"] >= b["tam"], f"{p}: tamaño {b['tam']} -> {a['tam']} (no debe decrecer)")
        igual = a["tam"] >= b["prefijo_bytes"] and prefijo_sha(p, b["prefijo_bytes"]) == b["prefijo_sha256"]
        f(igual, f"{p}: los primeros {b['prefijo_bytes']} bytes {'iguales' if igual else 'CAMBIARON (reescrito o truncado)'}")
    h_now = hermanos()
    f(h_now == base["hermanos"], f"ficheros rotados: {len(base['hermanos'])} -> {len(h_now)}" +
      ("" if h_now == base["hermanos"] else " (aparece o cambia alguno)"))
    s_now = sistema()
    for u in ("logrotate.service", "logrotate.timer"):
        igual = sistema_igual(u, base["sistema"][u], s_now[u])
        f(igual, f"{u}: {'sin ejecuciones desde la línea base' if igual else 'HA CAMBIADO ' + str(s_now[u])}")
    return ok, lin


# ------------------------------------------------------------------------------------------------ cierre de la corrida
def sumas_ok(carpeta: str) -> tuple[bool, str, set]:
    p = os.path.join(carpeta, "SHA256SUMS")
    try:
        txt = open(p, encoding="utf-8").read().splitlines()
    except OSError:
        return False, "no existe copias/SHA256SUMS", set()
    if not txt:
        return False, "copias/SHA256SUMS vacío", set()
    nombres = set()
    for l in txt:
        try:
            h, n = l.split(None, 1)
        except ValueError:
            return False, f"línea ilegible: {l[:40]}", nombres
        n = n.strip().lstrip("*").removeprefix("./")
        f = os.path.join(carpeta, n)
        try:
            if prefijo_sha(f, os.path.getsize(f)) != h:
                return False, f"hash distinto: {n}", nombres
        except OSError:
            return False, f"falta {n}", nombres
        nombres.add(n)
    return True, f"{len(nombres)} ficheros verifican", nombres


CRECEN = ("motor_decision.log", "ciclos.jsonl", "stats-fin.log")        # crecen siempre durante una corrida de 8 h


def leer_fuentes(ruta: str) -> dict:
    """FUENTES-al-copiar.tsv: «nombre<TAB>tamaño» por línea, escrito por s40 v2 justo antes de cada cp. Ilegible o incompleto -> {}."""
    out = {}
    try:
        for l in open(ruta, encoding="utf-8").read().splitlines():
            n, t = l.split("\t")[:2]
            out[n] = int(t)
    except (OSError, ValueError):
        return {}
    return out


def cierre(fase: str, base: dict) -> tuple[bool, list[str]]:
    B = f"{HOME}/cf-e4/{fase}"
    C, D = f"{B}/copias", f"{B}/archivo-pcap"
    lin, ok = [], True

    def f(cond: bool, texto: str) -> None:
        nonlocal ok
        lin.append(("OK    " if cond else "FALLO ") + texto)
        ok = ok and cond

    def leer(p: str) -> str:
        try:
            return open(p, encoding="utf-8", errors="replace").read()
        except OSError:
            return ""
    f(leer(f"{B}/replay/rc.txt").startswith("rc=0"), "replay terminó con rc=0")
    f(os.path.exists(f"{B}/cierre.t"), "s40 empezó (cierre.t)")
    f(leer(f"{D}.rc").strip() == "0", "archivador terminó con rc=0")
    f(leer(f"{C}/archivador-ESTADO.txt").strip().startswith("OK"), "ESTADO del archivador: OK")
    arch = leer(f"{C}/archivar.log").splitlines()
    f(bool(arch) and not any(" FALLO " in l or "PERDIDO" in l for l in arch), "archivar.log sin FALLO ni PERDIDO")
    v, motivo, nombres = sumas_ok(C)
    f(v, f"copias/SHA256SUMS: {motivo}")
    falta = [n for n in IMPRESCINDIBLES if n not in nombres]
    f(not falta, "copias imprescindibles incluidas en SHA256SUMS" + (f" (faltan {falta})" if falta else ""))
    # Un manifiesto que verifica NO prueba que la copia sea fiel: s40 lo genera a partir de lo que haya quedado, también de una copia truncada.
    # Cada copia debe: no ser menor que su fuente en la línea base, empezar por los mismos bytes que ella y terminar en salto de línea.
    pares = [("motor_decision.log", f"{HOME}/cyberflow/logs/motor_decision.log"), ("ciclos.jsonl", f"{HOME}/cyberflow/logs/_state-e4/ciclos.jsonl"),
             ("stats-fin.log", f"{SURICATA}/stats.log"), ("feed-v2/via-rapida-resumen.jsonl", f"{HOME}/feed-v2/via-rapida-resumen.jsonl"),
             ("feed-v2/traza.jsonl", f"{HOME}/feed-v2/traza.jsonl"), ("feed-v2/senales-if.jsonl", f"{HOME}/feed-v2/senales-if.jsonl"),
             ("feed-v2/senales-rapidas.jsonl", f"{HOME}/feed-v2/senales-rapidas.jsonl")]
    # Una copia idéntica a la línea base o cortada en una línea válida PASA los controles anteriores aunque la fuente ya tenga registros de la
    # corrida. Por eso s40 (v2) declara «copias completas» solo si todos los cp tuvieron éxito (COPIAS-COMPLETAS.ok) y anota el tamaño de cada
    # fuente justo antes de copiarla (FUENTES-al-copiar.tsv); la copia debe cubrir ese tamaño. Si la fuente ya creció respecto a la línea base,
    # una copia que no supera la línea base no cubre la corrida (motor, ciclos y stats crecen siempre durante ella).
    marca = leer(f"{C}/COPIAS-COMPLETAS.ok").strip()
    f(marca.startswith("ok"), "s40 declaró las copias completas (todas las operaciones de copia con éxito)" if marca.startswith("ok")
      else "s40 NO declaró copias completas (falta COPIAS-COMPLETAS.ok o hubo copias fallidas)")
    fuentes = leer_fuentes(f"{C}/FUENTES-al-copiar.tsv")
    f(bool(fuentes), "tamaños de las fuentes anotados por s40 (FUENTES-al-copiar.tsv)" if fuentes else "faltan los tamaños de las fuentes (FUENTES-al-copiar.tsv)")
    for nombre, fuente in pares:
        b0 = base["ficheros"].get(fuente)
        if not b0:
            continue
        ruta = f"{C}/{nombre}"
        try:
            tam = os.path.getsize(ruta)
            pref = tam >= b0["prefijo_bytes"] and prefijo_sha(ruta, b0["prefijo_bytes"]) == b0["prefijo_sha256"]
            with open(ruta, "rb") as fh:
                if tam:
                    fh.seek(-1, 2)
                fin = (not tam) or fh.read(1) == b"\n"
            ini = fuentes.get(nombre)
            try:
                actual = os.path.getsize(fuente)
            except OSError:
                actual = None
            cubre = ini is not None and ini >= b0["tam"] and tam >= ini
            creció = actual is not None and actual > b0["tam"]
            if nombre in CRECEN and creció:
                cubre = cubre and ini > b0["tam"] and tam > b0["tam"]
            fiel = tam >= b0["tam"] and pref and fin and cubre
            motivo = (f"{tam} B (línea base {b0['tam']} B; s40 anotó {ini if ini is not None else 'nada'} B; fuente ahora {actual} B)"
                      + ("" if pref else ", NO empieza por los bytes de la fuente") + ("" if fin else ", termina a mitad de línea")
                      + ("" if cubre else ", NO cubre la corrida"))
        except OSError:
            fiel, motivo = False, "no se puede leer"
        f(fiel, f"copia fiel de {nombre}: {motivo}")
    try:
        f(os.path.getsize(f"{C}/eve-segmento.json") > 0, "segmento EVE copiado y no vacío")
    except OSError:
        f(False, "falta el segmento EVE")
    return ok, lin


# ------------------------------------------------------------------------------------------------ reanudar
def reanudar(motivo: str) -> bool:
    for _ in range(3):
        run([SYSTEMCTL, "start", TIMER])
        time.sleep(0.2 if os.environ.get("CF_PRUEBA") else 2)
        if activo(TIMER) == "active":
            run([SYSTEMCTL, "stop", f"{UNIT_TOPE}.timer"])
            log(f"{motivo}: logrotate.timer activo")
            return True
    log(f"{motivo}: NO SE PUDO arrancar logrotate.timer (hay que hacerlo a mano)")
    return False


def vigilar(a) -> int:
    base = leer_base()
    avisada = False
    log(f"vigía {VERSION} en marcha: tope {dt.datetime.fromtimestamp(a.tope, dt.timezone.utc).strftime('%FT%TZ')}")
    # El vigía se arma ANTES de parar el timer: hasta que armar escribe parado.json, «timer activo» es lo normal, no una reanudación.
    while not os.path.exists(os.path.join(ESTADO, "parado.json")):
        if ahora() >= a.tope:
            log("vigía: el timer no llegó a pararse antes del tope; termina")
            return 0
        time.sleep(a.intervalo)
    while True:
        if activo(TIMER) == "active":
            log("vigía: logrotate.timer ya estaba activo (reanudado por otro medio); termina")
            return 0
        if ahora() >= a.tope:
            return 0 if reanudar("REANUDADO_POR_TOPE_SIN_CIERRE_VERIFICADO") else 1
        c_ok, _ = cierre(a.fase, base)
        r_ok, rl = comprobar(base)
        if c_ok and r_ok:
            return 0 if reanudar("REANUDADO_NORMAL (cierre y copias verificados, sin rotación)") else 1
        if not r_ok and not avisada:
            avisada = True
            log("ROTACION_DETECTADA o fichero reescrito: " + "; ".join(l for l in rl if l.startswith("FALLO"))[:400])
        time.sleep(a.intervalo)


def reanudar_tope(_a) -> int:
    if activo(TIMER) == "active":
        log("tope: logrotate.timer ya estaba activo; nada que hacer")
        return 0
    return 0 if reanudar("REANUDADO_POR_TOPE_SIN_CIERRE_VERIFICADO") else 1


# ------------------------------------------------------------------------------------------------ armar / desarmar
def siguiente_elapse(unit: str) -> float | None:
    v = props(unit, "NextElapseUSecRealtime").get("NextElapseUSecRealtime", "").strip()
    for fmt in ("%a %Y-%m-%d %H:%M:%S UTC", "%a %Y-%m-%d %H:%M:%S.%f UTC"):
        try:
            return dt.datetime.strptime(v, fmt).replace(tzinfo=dt.timezone.utc).timestamp()
        except ValueError:
            continue
    return None


def desarmar(_a=None) -> int:
    """Arranca logrotate.timer y SOLO cuando está activo retira el vigía y el tope. Si no arranca, deja la recuperación en pie
    (y la marca parado.json para que el vigía siga intentándolo y el tope actúe) y devuelve 1."""
    for _ in range(3):
        run([SYSTEMCTL, "start", TIMER])
        time.sleep(0.2 if os.environ.get("CF_PRUEBA") else 2)
        if activo(TIMER) == "active":
            break
    else:
        try:
            os.makedirs(ESTADO, exist_ok=True)
            if not os.path.exists(os.path.join(ESTADO, "parado.json")):
                with open(os.path.join(ESTADO, "parado.json"), "w", encoding="utf-8") as fh:
                    json.dump({"parado_en": ahora(), "tope_epoch": None, "origen": "desarmar fallido"}, fh)
        except OSError:
            pass
        log(f"DESARMAR FALLÓ: no se pudo arrancar logrotate.timer ({activo(TIMER)}); el vigía y el tope SIGUEN armados. Arránquelo a mano: sudo systemctl start logrotate.timer")
        print("DESARMAR FALLÓ: logrotate.timer no arrancó; la recuperación sigue armada", file=sys.stderr)
        return 1
    try:
        os.remove(os.path.join(ESTADO, "parado.json"))
    except OSError:
        pass
    for u in (f"{UNIT_VIGIA}.service", f"{UNIT_TOPE}.timer", f"{UNIT_TOPE}.service"):
        run([SYSTEMCTL, "stop", u])
    log(f"desarmado: logrotate.timer {activo(TIMER)}; unidades de recuperación retiradas")
    return 0


def armar(a) -> int:
    if os.geteuid() != 0 and not os.environ.get("CF_PRUEBA"):
        print("armar necesita root"); return 2
    if a.tope <= ahora() + 3600 and not os.environ.get("CF_PRUEBA"):
        print("el tope debe estar al menos 1 h en el futuro"); return 2
    if activo(TIMER) != "active":
        print(f"logrotate.timer no está activo ({activo(TIMER)}): no hay nada que aplazar"); return 2
    def fallo(paso: str) -> int:
        log(f"ARMAR FALLÓ en «{paso}»: se revierte (logrotate.timer: {activo(TIMER)})")
        desarmar()
        return 3
    os.makedirs(ESTADO, exist_ok=True)
    try:
        os.remove(os.path.join(ESTADO, "parado.json"))        # una marca de una corrida anterior no vale
    except OSError:
        pass
    base = linea_base(a.tope, a.fase)
    with open(os.path.join(ESTADO, "base.json"), "w", encoding="utf-8") as fh:
        json.dump(base, fh, indent=1, sort_keys=True)
    log(f"línea base: {sum(1 for v in base['ficheros'].values() if v)} ficheros protegidos, {len(base['hermanos'])} rotados existentes")
    iso = dt.datetime.fromtimestamp(a.tope, dt.timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
    # 1) ARMAR la recuperación antes de tocar el temporizador
    rc, out = run([SYSTEMD_RUN, f"--unit={UNIT_TOPE}", f"--on-calendar={iso}", "--timer-property=AccuracySec=1s",
                   "--description=4B: reanuda logrotate.timer en el tope absoluto", SELF, "reanudar-tope"])
    if rc != 0:
        return fallo("temporizador de tope: " + out.strip()[:120])
    rc, out = run([SYSTEMD_RUN, f"--unit={UNIT_VIGIA}", "--property=Restart=on-failure", "--property=RestartSec=30",
                   "--description=4B: reanuda logrotate.timer al cerrar la corrida", SELF, "vigilar", "--tope", str(int(a.tope)),
                   "--fase", a.fase])
    if rc != 0:
        return fallo("vigía: " + out.strip()[:120])
    # 2) VERIFICAR que está armada
    time.sleep(0.5 if os.environ.get("CF_PRUEBA") else 3)
    if activo(f"{UNIT_TOPE}.timer") != "active":
        return fallo(f"{UNIT_TOPE}.timer no está activo")
    sig = siguiente_elapse(f"{UNIT_TOPE}.timer")
    if sig is None or abs(sig - a.tope) > 5:
        return fallo(f"el tope armado ({sig}) no coincide con el pedido ({a.tope})")
    if activo(f"{UNIT_VIGIA}.service") != "active":
        return fallo(f"{UNIT_VIGIA}.service no está activo")
    if activo(TIMER) != "active":
        return fallo("logrotate.timer dejó de estar activo antes de parar")
    log(f"recuperación ARMADA y verificada: tope {iso}, vigía activo")
    # 3) solo ahora, parar el temporizador
    run([SYSTEMCTL, "stop", TIMER])
    if activo(TIMER) == "active":
        return fallo("logrotate.timer sigue activo tras stop")
    if not comprobar(base)[0]:                       # ficheros (inodo, tamaño, prefijo, hermanos) + servicio; el timer parado no informa
        return fallo("logrotate.timer disparó mientras se paraba")
    with open(os.path.join(ESTADO, "parado.json"), "w", encoding="utf-8") as fh:
        json.dump({"parado_en": ahora(), "tope_epoch": a.tope}, fh)
    log("logrotate.timer PARADO; reanudación: normal (cierre y copias verificados) o tope absoluto " + iso)
    return 0


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    for n in ("armar", "vigilar"):
        p = sub.add_parser(n); p.add_argument("--tope", type=float, required=True); p.add_argument("--fase", default="4b")
        if n == "vigilar":
            p.add_argument("--intervalo", type=float, default=30.0)
    sub.add_parser("comprobar")
    c = sub.add_parser("cierre"); c.add_argument("--fase", default="4b")
    sub.add_parser("reanudar-tope")
    sub.add_parser("desarmar")
    a = ap.parse_args(argv)
    if a.cmd == "armar":
        return armar(a)
    if a.cmd == "vigilar":
        return vigilar(a)
    if a.cmd == "reanudar-tope":
        return reanudar_tope(a)
    if a.cmd == "desarmar":
        return desarmar(a)
    base = leer_base()
    ok, lin = comprobar(base) if a.cmd == "comprobar" else cierre(a.fase, base)
    print("\n".join(lin))
    print(f"RESULTADO_{a.cmd.upper()} {'OK' if ok else 'FALLO'} (cf-4b-rotacion {VERSION})")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
