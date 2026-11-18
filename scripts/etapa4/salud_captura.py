#!/usr/bin/env python3
"""Salud de la captura y del procesamiento (Etapa 4). Solo lectura: no toca servicios ni contadores.

Mide por separado cada fuente, con su contador REAL, su unidad y su alcance. Un campo que no se
puede leer queda ``null`` con su ``motivo``: nunca se escribe 0 en su lugar.

Subcomandos:

  muestrear   toma una muestra (o una cada ``--intervalo`` s hasta ``--hasta``) y la añade a un JSONL.
  intervalos  convierte las muestras en incrementos entre muestras consecutivas, marcando reinicios
              (cambio de PID, NRestarts que sube, uptime de Suricata que baja, contador que decrece).
  clasificar  clasifica un periodo [desde, hasta] con los incrementos que lo cubren (cota conservadora:
              última muestra <= desde y primera >= hasta) y los criterios fijados en SALUD-CAPTURA.md.

Fuentes y contadores (unidades):

  suricata     stats.log, último bloque completo: capture.kernel_packets y capture.kernel_drops
               (paquetes; acumulados desde el arranque de Suricata, todos los hilos: ``totals: yes``)
               y el uptime de la línea ``Date:`` (s). Alcance: socket AF_PACKET de Suricata en la
               interfaz del espejo. No ve pérdidas anteriores (switch, SPAN, hipervisor).
  suricata_eve eventos ``stats`` de eve.json (2026-11-06.1, sustituye a stats.log para clasificar): ver
               ``medida_suricata_eve``. stats.log se sigue pudiendo muestrear, pero ya no decide la clase si se
               da ``--suricata-eve``.
  interfaz     /sys/class/net/<if>/statistics: rx_packets, rx_dropped, rx_missed_errors,
               rx_fifo_errors, rx_over_errors (tramas, acumulados desde el arranque del sistema).
               Cada contador se informa por separado y SIN clasificar. Qué cuenta rx_dropped en esta
               interfaz (vmxnet3) no está determinado (pendiente P3 del cierre 4A): no se atribuye a una
               causa concreta ni se presenta como pérdida del tráfico evaluado.
  unidades     systemctl show: MainPID, NRestarts, ActiveState, ExecMainStartTimestampMonotonic.
  anillo       ficheros live-YYYYmmddHHMMSS.pcap: número, el más nuevo, y el mayor salto entre
               inicios consecutivos de los últimos ``--anillo-ultimos`` (s).
  archivador   ESTADO.txt y líneas OK / FALLO / PERDIDO de archivar.log (ficheros, no paquetes).
  via_rapida   última línea de via-rapida-resumen.jsonl: paquetes_tcp (acumulado del proceso),
               bytes_pendientes (bytes de un registro PCAP a medio llegar; NO es pérdida ni cola),
               cpu_s, bloque_hasta y su antigüedad (s).
  motor        última línea de ciclos.jsonl: duracion_s, retraso_pcap_s = inicio_ciclo − marca_pcap,
               ventanas_pendientes, antigüedad del ciclo (s).
  proc_io      /proc/<pid>/io de los procesos indicados (wchar/rchar, bytes acumulados del proceso).
               Con el tcpdump y el detector de la vía rápida, Δwchar(tcpdump) − Δrchar(detector)
               aproxima lo que se acumula en la tubería entre dos muestras (no es pérdida).

Las estadísticas de tcpdump (paquetes capturados, recibidos por el filtro y descartados por el
kernel) solo existen cuando el propio tcpdump las imprime (SIGUSR1 o al terminar). ``--tcpdump-log``
lee esas líneas de un fichero exportado del journal (``journalctl -o short-iso-precise``) y las
asocia al PID; las cifras son acumuladas del proceso y libpcap las suma entre lecturas.
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import re
import subprocess
import sys
import time
from pathlib import Path

VERSION = "2026-11-06.1"  # .1 (06-nov): Suricata por EVE stats (cero explícito, ausente, desactualizada, error,
#                           cobertura, identidad de proceso). 2026-11-02.2: cobertura SIGUSR1 completa.

# ---------------------------------------------------------------- lectura de fuentes


def _no(motivo: str) -> dict:
    return {"ok": False, "motivo": motivo}


_RE_DATE = re.compile(r"^Date: (\d+)/(\d+)/(\d+) -- (\d+):(\d+):(\d+) \(uptime: (?:(\d+)d, )?(\d+)h (\d+)m (\d+)s\)")
_RE_CONT = re.compile(r"^([a-z0-9_.]+)\s*\|\s*Total\s*\|\s*(\d+)\s*$")


def leer_stats_suricata(path: Path, cola_bytes: int = 1 << 20) -> dict:
    """Último bloque de stats.log que contenga capture.kernel_drops (el último puede estar a medias)."""
    try:
        with path.open("rb") as fh:
            fh.seek(0, os.SEEK_END)
            tam = fh.tell()
            fh.seek(max(0, tam - cola_bytes))
            texto = fh.read().decode("utf-8", "replace")
    except OSError as e:
        return _no(f"no legible: {e.__class__.__name__}")
    bloques, actual = [], None
    for linea in texto.splitlines():
        m = _RE_DATE.match(linea)
        if m:
            actual = {"_m": m, "c": {}}
            bloques.append(actual)
            continue
        if actual is not None:
            mc = _RE_CONT.match(linea.strip())
            if mc:
                actual["c"][mc.group(1)] = int(mc.group(2))
    for b in reversed(bloques):
        c = b["c"]
        if "capture.kernel_drops" in c and "capture.kernel_packets" in c:
            m = b["_m"]
            mes, dia, anio, hh, mm, ss = (int(m.group(i)) for i in range(1, 7))
            uptime = int(m.group(7) or 0) * 86400 + int(m.group(8)) * 3600 + int(m.group(9)) * 60 + int(m.group(10))
            fecha = dt.datetime(anio, mes, dia, hh, mm, ss, tzinfo=dt.timezone.utc)
            return {"ok": True, "fecha_utc": fecha.isoformat(), "t": fecha.timestamp(), "uptime_s": uptime,
                    "kernel_packets": c["capture.kernel_packets"], "kernel_drops": c["capture.kernel_drops"],
                    "decoder_pkts": c.get("decoder.pkts")}
    return _no("sin bloque con capture.kernel_drops en la cola del fichero")


# ---------------------------------------------------------------- Suricata por EVE stats (2026-11-06.1)
#
# Por qué (cierre complementario 4A, P1): Suricata 7 escribe stats.log con ``null-values: no`` (por omisión), que
# OMITE los contadores a cero. Con 0 descartes, ``capture.kernel_drops`` no aparece en ningún bloque reciente y
# ``leer_stats_suricata`` devolvía el último bloque antiguo que sí lo tenía: «mismo bloque» o sin medida -> C3.
# Los eventos ``stats`` de EVE (cada ``stats.interval`` = 8 s) escriben SIEMPRE ``capture.kernel_drops``, también a
# cero, junto con ``stats.uptime``. Se prefiere leer EVE a cambiar la configuración de Suricata (no hace falta
# reiniciarlo, no cambia el YAML 0962ce68 ni el ensayo del anillo).
#
# Estados de la medida de un periodo (nunca se convierte una ausencia en cero):
#   cero_explicito          cobertura completa, un solo proceso, kernel_drops presente en todas las muestras, Δ = 0
#   descartes               igual, con Δ kernel_drops > 0
#   ausente                 hay muestras, pero falta kernel_drops o kernel_packets en alguna del tramo
#   desactualizada          la fuente dejó de producir muestras (última > eve_max_hueco_s antes de «ahora») o el
#                           uptime no avanza entre muestras (contadores congelados)
#   error_lectura           fichero no legible, línea stats corrupta en mitad del fichero, dos muestras con la misma
#                           hora y valores distintos, o contador que decrece dentro del mismo proceso
#   cobertura_insuficiente  sin muestra en [desde − borde, desde] o en [hasta, hasta + borde], hueco > eve_max_hueco_s,
#                           o reinicio de Suricata dentro del tramo (no se mezclan bloques de procesos distintos)
# Identidad del proceso: arranque estimado = t − uptime. Dos muestras son del mismo proceso si su arranque estimado
# difiere <= eve_tolerancia_arranque_s y el uptime crece. Un proceso nuevo NUNCA reutiliza bloques del anterior.

CRITERIOS_EVE = {
    # Fijados el 2026-11-06 ANTES de la observación técnica de integración; no se ajustan con sus resultados.
    "eve_intervalo_s": 8.0,              # stats.interval del suricata.yaml desplegado (0962ce68…)
    "eve_max_hueco_s": 20.0,             # 2 intervalos + 4 s: más separadas = tramo sin medida
    "eve_borde_s": 10.0,                 # muestra que acota cada extremo: a <= 10 s fuera del periodo
    "eve_tolerancia_arranque_s": 3.0,    # uptime entero (s) + jitter de escritura
}

_AGUJA_STATS = b'"event_type":"stats"'


def _t_eve(ts: str) -> float:
    # "2026-11-06T03:15:10.368372+0000"
    return dt.datetime.strptime(ts[:26] + ts[-5:], "%Y-%m-%dT%H:%M:%S.%f%z").timestamp()


def _muestra_eve(linea: bytes) -> dict:
    e = json.loads(linea)
    st = e["stats"]
    cap = st.get("capture") if isinstance(st.get("capture"), dict) else {}
    def ent(v):
        return int(v) if isinstance(v, int) and not isinstance(v, bool) and v >= 0 else None
    return {"t": _t_eve(e["timestamp"]), "uptime_s": ent(st.get("uptime")),
            "kernel_packets": ent(cap.get("kernel_packets")), "kernel_drops": ent(cap.get("kernel_drops"))}


def _abrir(path: Path):
    import gzip
    return gzip.open(path, "rb") if path.suffix == ".gz" else path.open("rb")


def leer_eve_stats(rutas: list[Path], desde: float | None = None, bloque: int = 4 << 20) -> dict:
    """Muestras ``stats`` de uno o varios EVE (actual y rotados, .gz admitido), ordenadas y sin repetidas.

    Con ``desde`` y fichero sin comprimir se lee por bloques DESDE EL FINAL y se para cuando el bloque ya empieza
    antes de ``desde`` (el EVE diario puede pasar de 400 MB). Una línea stats que no se puede interpretar cuenta
    como ``parcial`` si es la última del fichero sin salto de línea (escritura en curso o corte de copytruncate) y
    como ``invalida`` en cualquier otro sitio."""
    res = {"ok": True, "muestras": [], "errores": [], "parciales": 0, "invalidas": [], "repetidas": 0,
           "conflictos": [], "ficheros": []}
    crudas = []
    for p in rutas:
        p = Path(p)
        info = {"ruta": str(p)}
        try:
            if p.suffix != ".gz" and desde is not None:
                lineas, completo = _cola_desde(p, desde, bloque)
            else:
                with _abrir(p) as fh:
                    datos = fh.read()
                lineas, completo = datos.split(b"\n"), True
            info["tam"] = p.stat().st_size
        except (OSError, EOFError) as e:
            res["ok"] = False
            res["errores"].append(f"{p}: no legible ({e.__class__.__name__})")
            res["ficheros"].append(info)
            continue
        n = 0
        ult = len(lineas) - 1
        for i, l in enumerate(lineas):
            if _AGUJA_STATS not in l:
                continue
            try:
                m = _muestra_eve(l)
            except (ValueError, KeyError, TypeError):
                if i == ult and l.strip():
                    res["parciales"] += 1          # última línea sin '\n': se leerá entera en la siguiente lectura
                elif i == 0 and not completo:
                    pass                           # primera línea de un bloque leído desde el final: cortada a propósito
                else:
                    res["invalidas"].append(f"{p}: línea stats no interpretable")
                continue
            m["fuente"] = p.name
            crudas.append(m)
            n += 1
        info["muestras"] = n
        res["ficheros"].append(info)
    crudas.sort(key=lambda m: (m["t"], m["uptime_s"] or -1))
    for m in crudas:
        if res["muestras"] and res["muestras"][-1]["t"] == m["t"]:
            a = res["muestras"][-1]
            if all(a[k] == m[k] for k in ("uptime_s", "kernel_packets", "kernel_drops")):
                res["repetidas"] += 1              # misma muestra en dos ficheros (copytruncate) o leída dos veces
            else:
                res["conflictos"].append(m["t"])
            continue
        res["muestras"].append(m)
    return res


def _cola_desde(p: Path, desde: float, bloque: int) -> tuple[list[bytes], bool]:
    """Líneas del final del fichero hasta cubrir ``desde`` (con una muestra anterior). (líneas, leído_entero)."""
    with p.open("rb") as fh:
        fh.seek(0, os.SEEK_END)
        tam = fh.tell()
        pos, datos = tam, b""
        while pos > 0:
            pos = max(0, pos - bloque)
            fh.seek(pos)
            datos = fh.read(tam - pos)
            primera = None
            for l in datos.split(b"\n")[1:]:       # la primera puede estar cortada
                if _AGUJA_STATS in l:
                    try:
                        primera = _t_eve(json.loads(l)["timestamp"])
                    except (ValueError, KeyError, TypeError):
                        continue
                    break
            if primera is not None and primera < desde - CRITERIOS_EVE["eve_max_hueco_s"]:
                break
        return datos.split(b"\n"), pos == 0


def medida_suricata_eve(lect: dict, desde: float, hasta: float, ahora: float, crit: dict | None = None) -> dict:
    """Medida de Suricata en [desde, hasta] a partir de ``leer_eve_stats``. Ver los estados arriba."""
    c = dict(CRITERIOS_EVE, **(crit or {}))
    res = {"fuente": "eve_stats", "version": VERSION, "periodo": [desde, hasta], "estado": None, "motivos": [],
           "paquetes": None, "descartes": None, "descartes_parciales": None, "criterios": c,
           "repetidas": lect.get("repetidas", 0), "parciales": lect.get("parciales", 0)}
    def fin(estado, *mot):
        res["estado"] = estado
        res["motivos"].extend(mot)
        return res
    if not lect.get("ok"):
        return fin("error_lectura", *lect.get("errores", []))
    ms = lect["muestras"]
    if lect.get("invalidas"):
        return fin("error_lectura", f"{len(lect['invalidas'])} línea(s) stats no interpretables en mitad del EVE")
    if lect.get("conflictos"):
        return fin("error_lectura", f"{len(lect['conflictos'])} muestra(s) con la misma hora y valores distintos")
    if not ms:
        return fin("ausente", "el EVE no tiene eventos stats")
    borde, hueco_max, tol = c["eve_borde_s"], c["eve_max_hueco_s"], c["eve_tolerancia_arranque_s"]
    ultima = ms[-1]["t"]
    res["ultima_muestra"] = ultima
    a = [m for m in ms if desde - borde <= m["t"] <= desde]
    b = [m for m in ms if hasta <= m["t"] <= hasta + borde]
    if not b and ultima < hasta and ahora - ultima > hueco_max:
        return fin("desactualizada", f"la última muestra stats es de hace {round(ahora - ultima, 1)} s "
                                     f"(> {hueco_max} s) y no llega al fin del periodo")
    if not a or not b:
        return fin("cobertura_insuficiente",
                   *(["sin muestra stats en [desde − %g s, desde]" % borde] if not a else []),
                   *(["sin muestra stats en [hasta, hasta + %g s]" % borde] if not b else []))
    ma, mb = a[-1], b[0]
    tramo = [m for m in ms if ma["t"] <= m["t"] <= mb["t"]]
    res["acotado_por"] = [ma["t"], mb["t"]]
    res["muestras"] = len(tramo)
    huecos = [(round(y["t"] - x["t"], 1), x["t"]) for x, y in zip(tramo, tramo[1:]) if y["t"] - x["t"] > hueco_max]
    faltan = [m["t"] for m in tramo if m["kernel_drops"] is None or m["kernel_packets"] is None or m["uptime_s"] is None]
    # procesos: arranque estimado t − uptime estable y uptime creciente
    procesos, congeladas, decrecen = [], 0, 0
    for x, y in zip(tramo, tramo[1:]):
        if None in (x["uptime_s"], y["uptime_s"]):
            continue
        mismo = abs((y["t"] - y["uptime_s"]) - (x["t"] - x["uptime_s"])) <= tol and y["uptime_s"] >= x["uptime_s"]
        if y["uptime_s"] == x["uptime_s"] and y["t"] - x["t"] > tol:
            congeladas += 1
        elif not mismo:
            procesos.append(y["t"])
        elif None not in (x["kernel_drops"], y["kernel_drops"], x["kernel_packets"], y["kernel_packets"]) and \
                (y["kernel_drops"] < x["kernel_drops"] or y["kernel_packets"] < x["kernel_packets"]):
            decrecen += 1
    res["reinicios"] = procesos
    res["arranque_estimado"] = sorted({round(m["t"] - m["uptime_s"]) for m in tramo if m["uptime_s"] is not None})
    # descartes observados entre muestras compatibles (informativo aunque la cobertura falle)
    parc = 0
    for x, y in zip(tramo, tramo[1:]):
        if None in (x["kernel_drops"], y["kernel_drops"], x["uptime_s"], y["uptime_s"]):
            continue
        if abs((y["t"] - y["uptime_s"]) - (x["t"] - x["uptime_s"])) <= tol and y["kernel_drops"] > x["kernel_drops"]:
            parc += y["kernel_drops"] - x["kernel_drops"]
    res["descartes_parciales"] = parc
    if decrecen:
        return fin("error_lectura", f"{decrecen} contador(es) que decrecen sin cambio de proceso")
    if faltan:
        return fin("ausente", f"{len(faltan)} muestra(s) del tramo sin kernel_drops/kernel_packets/uptime")
    if congeladas:
        return fin("desactualizada", f"{congeladas} par(es) de muestras con el mismo uptime: contadores congelados")
    mot = []
    if procesos:
        mot.append(f"reinicio de Suricata dentro del tramo ({len(procesos)}): no se mezclan procesos")
    if huecos:
        h = max(huecos)
        mot.append(f"{len(huecos)} hueco(s) entre muestras stats > {hueco_max} s (máximo {h[0]} s desde {h[1]})")
    if mot:
        return fin("cobertura_insuficiente", *mot)
    res["paquetes"] = mb["kernel_packets"] - ma["kernel_packets"]
    res["descartes"] = mb["kernel_drops"] - ma["kernel_drops"]
    res["intervalos_con_descartes"] = [[x["t"], y["t"], y["kernel_drops"] - x["kernel_drops"]]
                                       for x, y in zip(tramo, tramo[1:]) if y["kernel_drops"] > x["kernel_drops"]][:50]
    if res["descartes"] > 0:
        return fin("descartes", f"Suricata: {res['descartes']} descartes de {res['paquetes']} paquetes")
    return fin("cero_explicito")


def comprobar_i5(lect: dict, ahora: float, ventana_s: float = 1800.0, crit: dict | None = None) -> dict:
    """I5 (SALUD-CAPTURA §4.1, solo 4C): 0 kernel_drops de Suricata en los ``ventana_s`` previos.

    El periodo termina en la última muestra stats (no en «ahora»: la muestra de «ahora» aún no existe) y exige que
    esa muestra sea reciente (<= eve_max_hueco_s). cumple = cero_explicito; no_cumple = descartes (o descartes
    parciales observados); no_demostrable = cualquier otro estado. Solo «cumple» permite iniciar la 4C."""
    c = dict(CRITERIOS_EVE, **(crit or {}))
    ms = lect.get("muestras") or []
    if not lect.get("ok") or not ms:
        med = medida_suricata_eve(lect, ahora - ventana_s, ahora, ahora, c)
    else:
        hasta = ms[-1]["t"]
        med = medida_suricata_eve(lect, hasta - ventana_s, hasta, ahora, c)
        if ahora - hasta > c["eve_max_hueco_s"]:
            med["estado"] = "desactualizada"
            med["motivos"].append(f"última muestra stats de hace {round(ahora - hasta, 1)} s")
    if med["estado"] == "cero_explicito":
        dec = "cumple"
    elif med["estado"] == "descartes" or (med.get("descartes_parciales") or 0) > 0:
        dec = "no_cumple"
    else:
        dec = "no_demostrable"
    return {"i5": dec, "ventana_s": ventana_s, "medida": med}


CAMPOS_IF = ("rx_packets", "rx_dropped", "rx_missed_errors", "rx_fifo_errors", "rx_over_errors")


def leer_interfaz(nombre: str, raiz: Path = Path("/sys/class/net")) -> dict:
    d = {"ok": True}
    for c in CAMPOS_IF:
        try:
            d[c] = int((raiz / nombre / "statistics" / c).read_text().strip())
        except (OSError, ValueError) as e:
            d[c] = None
            d.setdefault("faltan", []).append(f"{c}: {e.__class__.__name__}")
    if all(d[c] is None for c in CAMPOS_IF):
        return _no("ningún contador legible")
    return d


def leer_unidad(nombre: str, systemctl: str = "systemctl") -> dict:
    props = ("MainPID", "NRestarts", "ActiveState", "ExecMainStartTimestampMonotonic")
    try:
        r = subprocess.run([systemctl, "show", nombre] + [f"-p{p}" for p in props],
                           capture_output=True, text=True, timeout=10)
    except (OSError, subprocess.TimeoutExpired) as e:
        return _no(f"systemctl: {e.__class__.__name__}")
    if r.returncode != 0:
        return _no(f"systemctl rc={r.returncode}")
    kv = dict(l.split("=", 1) for l in r.stdout.splitlines() if "=" in l)
    if not kv:
        return _no("salida vacía")
    def ent(k):
        try:
            return int(kv.get(k, ""))
        except ValueError:
            return None
    return {"ok": True, "pid": ent("MainPID"), "nrestarts": ent("NRestarts"),
            "activo": kv.get("ActiveState"), "arranque_mono_us": ent("ExecMainStartTimestampMonotonic")}


_RE_PCAP = re.compile(r"^live-(\d{14})\.pcap$")


def _t_nombre(n: str) -> float | None:
    m = _RE_PCAP.match(n)
    if not m:
        return None
    return dt.datetime.strptime(m.group(1), "%Y%m%d%H%M%S").replace(tzinfo=dt.timezone.utc).timestamp()


def leer_anillo(d: Path, ultimos: int = 40) -> dict:
    try:
        nombres = sorted(n for n in os.listdir(d) if _RE_PCAP.match(n))
    except OSError as e:
        return _no(f"no legible: {e.__class__.__name__}")
    if not nombres:
        return _no("sin ficheros live-*.pcap")
    ts = [_t_nombre(n) for n in nombres[-ultimos:]]
    saltos = [b - a for a, b in zip(ts, ts[1:])]
    try:
        mtime = (d / nombres[-1]).stat().st_mtime
    except OSError:
        mtime = None
    return {"ok": True, "ficheros": len(nombres), "mas_nuevo": nombres[-1], "inicio_mas_nuevo": ts[-1],
            "mtime_mas_nuevo": mtime, "salto_max_s": max(saltos) if saltos else None, "saltos_contados": len(saltos)}


def leer_archivador(d: Path) -> dict:
    est = d / "ESTADO.txt"
    log = d / "archivar.log"
    try:
        estado = est.read_text(encoding="utf-8", errors="replace").strip()
    except OSError as e:
        return _no(f"ESTADO.txt no legible: {e.__class__.__name__}")
    ok = fallo = perdido = 0
    try:
        with log.open(encoding="utf-8", errors="replace") as fh:
            for l in fh:
                partes = l.split(" ", 2)
                if len(partes) < 2:
                    continue
                if partes[1] == "OK":
                    ok += 1
                elif partes[1] == "FALLO":
                    fallo += 1
                    if "PERDIDO" in l:
                        perdido += 1
    except OSError as e:
        return {"ok": False, "motivo": f"archivar.log no legible: {e.__class__.__name__}", "estado": estado}
    return {"ok": True, "estado": estado, "lineas_ok": ok, "lineas_fallo": fallo, "perdidos": perdido}


def ultima_linea_json(path: Path, cola_bytes: int = 65536) -> dict | None:
    try:
        with path.open("rb") as fh:
            fh.seek(0, os.SEEK_END)
            tam = fh.tell()
            fh.seek(max(0, tam - cola_bytes))
            lineas = fh.read().decode("utf-8", "replace").splitlines()
    except OSError:
        return None
    for l in reversed(lineas):
        try:
            return json.loads(l)
        except ValueError:
            continue
    return None


def leer_via_rapida(path: Path, ahora: float) -> dict:
    d = ultima_linea_json(path)
    if d is None:
        return _no("resumen ausente o ilegible")
    if "paquetes_tcp" not in d or "bloque_hasta" not in d:
        return _no("la última línea no es un resumen de flujo")
    return {"ok": True, "paquetes_tcp": d["paquetes_tcp"], "bytes_pendientes": d.get("bytes_pendientes"),
            "cpu_s": d.get("cpu_s"), "bloque_hasta": d["bloque_hasta"],
            "antiguedad_s": round(ahora - float(d["bloque_hasta"]), 3)}


def leer_motor(path: Path, ahora: float) -> dict:
    d = ultima_linea_json(path)
    if d is None or d.get("event") != "ciclo":
        return _no("ciclos.jsonl ausente o sin ciclo en la cola")
    ret = None
    if d.get("inicio_ciclo") is not None and d.get("marca_pcap") is not None:
        ret = round(float(d["inicio_ciclo"]) - float(d["marca_pcap"]), 3)
    fin = d.get("fin_ciclo")
    return {"ok": True, "duracion_s": d.get("duracion_s"), "retraso_pcap_s": ret,
            "ventanas_pendientes": d.get("ventanas_pendientes"), "fin_ciclo": fin,
            "antiguedad_s": round(ahora - float(fin), 3) if fin is not None else None}


def leer_proc_io(pid: int, raiz: Path = Path("/proc")) -> dict:
    try:
        txt = (raiz / str(pid) / "io").read_text()
        cmd = (raiz / str(pid) / "cmdline").read_bytes().split(b"\0")[0].decode("utf-8", "replace")
    except OSError as e:
        return {"ok": False, "pid": pid, "motivo": f"/proc/{pid}/io: {e.__class__.__name__}"}
    kv = dict(l.split(": ", 1) for l in txt.splitlines() if ": " in l)
    return {"ok": True, "pid": pid, "exe": os.path.basename(cmd), "wchar": int(kv["wchar"]), "rchar": int(kv["rchar"])}


def hijos(pid: int, raiz: Path = Path("/proc")) -> list[int]:
    try:
        return [int(x) for x in (raiz / str(pid) / "task" / str(pid) / "children").read_text().split()]
    except (OSError, ValueError):
        return []


_RE_TCPDUMP = re.compile(r"(\d+) packets? captured, (\d+) packets? received by filter, (\d+) packets? dropped by kernel")
_RE_JOURNAL = re.compile(r"^(\S+)\s+\S+\s+[^\[]+\[(\d+)\]:")


def leer_tcpdump_log(path: Path) -> list[dict]:
    """Líneas de estadísticas de tcpdump exportadas del journal (short-iso-precise), con PID y hora."""
    out = []
    try:
        lineas = path.read_text(encoding="utf-8", errors="replace").splitlines()
    except OSError:
        return out
    for l in lineas:
        m = _RE_TCPDUMP.search(l)
        if not m:
            continue
        j = _RE_JOURNAL.match(l)
        t = pid = None
        if j:
            try:
                t = dt.datetime.fromisoformat(j.group(1)).timestamp()
            except ValueError:
                t = None
            pid = int(j.group(2))
        out.append({"t": t, "pid": pid, "capturados": int(m.group(1)), "recibidos_filtro": int(m.group(2)),
                    "descartados_kernel": int(m.group(3))})
    return out


def muestra(a) -> dict:
    ahora = time.time()
    m = {"t": round(ahora, 3), "utc": dt.datetime.fromtimestamp(ahora, dt.timezone.utc).isoformat(),
         "version": VERSION}
    if a.suricata_stats:
        m["suricata"] = leer_stats_suricata(a.suricata_stats)
    if a.interfaz:
        m["interfaz"] = leer_interfaz(a.interfaz)
    if a.unidad:
        m["unidades"] = {u: leer_unidad(u, a.systemctl) for u in a.unidad}
    if a.anillo:
        m["anillo"] = leer_anillo(a.anillo, a.anillo_ultimos)
    if a.archivador:
        m["archivador"] = leer_archivador(a.archivador)
    if a.resumen_rapida:
        m["via_rapida"] = leer_via_rapida(a.resumen_rapida, ahora)
    if a.ciclos:
        m["motor"] = leer_motor(a.ciclos, ahora)
    pids = list(a.pid or [])
    if a.hijos_de_unidad:
        u = leer_unidad(a.hijos_de_unidad, a.systemctl)
        if u.get("ok") and u.get("pid"):
            pids += hijos(u["pid"])
    if pids:
        m["proc_io"] = [leer_proc_io(p) for p in pids]
    return m


# ---------------------------------------------------------------- incrementos


def _delta(a, b, k):
    if not (a and b and a.get("ok") and b.get("ok")):
        return None
    if a.get(k) is None or b.get(k) is None:
        return None
    return b[k] - a[k]


def incremento(m0: dict, m1: dict) -> dict:
    inc = {"desde": m0["t"], "hasta": m1["t"], "reinicios": []}
    s0, s1 = m0.get("suricata"), m1.get("suricata")
    if s0 is not None or s1 is not None:
        if not (s0 and s1 and s0.get("ok") and s1.get("ok")):
            inc["suricata"] = {"ok": False, "motivo": "muestra sin stats de Suricata"}
        elif s1["uptime_s"] < s0["uptime_s"] or s1["kernel_packets"] < s0["kernel_packets"] \
                or s1["kernel_drops"] < s0["kernel_drops"]:
            inc["suricata"] = {"ok": False, "motivo": "contadores reiniciados (uptime o contador decrece)"}
            inc["reinicios"].append("suricata")
        elif s1["t"] == s0["t"]:
            inc["suricata"] = {"ok": False, "motivo": "mismo bloque de stats en ambas muestras"}
        else:
            dp, dd = s1["kernel_packets"] - s0["kernel_packets"], s1["kernel_drops"] - s0["kernel_drops"]
            inc["suricata"] = {"ok": True, "desde_stats": s0["t"], "hasta_stats": s1["t"], "paquetes": dp,
                               "descartes": dd, "proporcion": (dd / dp) if dp else None}
    i0, i1 = m0.get("interfaz"), m1.get("interfaz")
    if i0 is not None or i1 is not None:
        d = {c: _delta(i0, i1, c) for c in CAMPOS_IF}
        if any(v is not None and v < 0 for v in d.values()):
            inc["interfaz"] = {"ok": False, "motivo": "contador de la interfaz decrece (reinicio del sistema o del driver)"}
            inc["reinicios"].append("interfaz")
        else:
            inc["interfaz"] = {"ok": any(v is not None for v in d.values()), **d}
    u0, u1 = m0.get("unidades") or {}, m1.get("unidades") or {}
    if u0 or u1:
        inc["unidades"] = {}
        for nombre in sorted(set(u0) | set(u1)):
            a, b = u0.get(nombre), u1.get(nombre)
            if not (a and b and a.get("ok") and b.get("ok")):
                inc["unidades"][nombre] = {"ok": False, "motivo": "estado de la unidad no leído"}
                continue
            cambio = a["pid"] != b["pid"] or (b["nrestarts"] or 0) > (a["nrestarts"] or 0) \
                or a["arranque_mono_us"] != b["arranque_mono_us"] or b["activo"] != "active"
            inc["unidades"][nombre] = {"ok": True, "reinicio_o_parada": cambio, "pid": [a["pid"], b["pid"]],
                                       "activo": b["activo"]}
            if cambio:
                inc["reinicios"].append(nombre)
    if m1.get("anillo") is not None:
        an = m1["anillo"]
        inc["anillo"] = {"ok": an.get("ok", False), "salto_max_s": an.get("salto_max_s"),
                         "motivo": an.get("motivo")}
    a0, a1 = m0.get("archivador"), m1.get("archivador")
    if a1 is not None:
        if a0 and a1 and a0.get("ok") and a1.get("ok"):
            inc["archivador"] = {"ok": True, "nuevos_ok": a1["lineas_ok"] - a0["lineas_ok"],
                                 "nuevos_fallo": a1["lineas_fallo"] - a0["lineas_fallo"],
                                 "nuevos_perdidos": a1["perdidos"] - a0["perdidos"], "estado": a1["estado"]}
        else:
            inc["archivador"] = {"ok": False, "motivo": (a1 or {}).get("motivo", "sin muestra previa")}
    v0, v1 = m0.get("via_rapida"), m1.get("via_rapida")
    if v1 is not None:
        if v0 and v1 and v0.get("ok") and v1.get("ok"):
            dp = v1["paquetes_tcp"] - v0["paquetes_tcp"]
            inc["via_rapida"] = {"ok": dp >= 0, "paquetes_tcp": dp, "antiguedad_s": v1["antiguedad_s"],
                                 "bytes_pendientes": v1["bytes_pendientes"]}
            if dp < 0:
                inc["via_rapida"]["motivo"] = "paquetes_tcp decrece: el detector se reinició"
                inc["reinicios"].append("via_rapida")
        else:
            inc["via_rapida"] = {"ok": False, "motivo": (v1 or {}).get("motivo", "sin muestra previa")}
    if m1.get("motor") is not None:
        mo = m1["motor"]
        inc["motor"] = {k: mo.get(k) for k in ("ok", "duracion_s", "retraso_pcap_s", "ventanas_pendientes",
                                               "antiguedad_s", "motivo")}
    p0 = {p["pid"]: p for p in (m0.get("proc_io") or []) if p.get("ok")}
    p1 = {p["pid"]: p for p in (m1.get("proc_io") or []) if p.get("ok")}
    if m1.get("proc_io") is not None:
        comunes = sorted(set(p0) & set(p1))
        inc["proc_io"] = {str(p): {"exe": p1[p]["exe"], "dwchar": p1[p]["wchar"] - p0[p]["wchar"],
                                   "drchar": p1[p]["rchar"] - p0[p]["rchar"]} for p in comunes}
        td = [p for p in comunes if p1[p]["exe"] == "tcpdump"]
        py = [p for p in comunes if p1[p]["exe"].startswith("python")]
        if len(td) == 1 and len(py) == 1:
            inc["tuberia_acumulacion_bytes"] = (p1[td[0]]["wchar"] - p0[td[0]]["wchar"]) - \
                                               (p1[py[0]]["rchar"] - p0[py[0]]["rchar"])
    return inc


def incrementos(muestras: list[dict]) -> list[dict]:
    m = sorted(muestras, key=lambda x: x["t"])
    return [incremento(a, b) for a, b in zip(m, m[1:])]


# ---------------------------------------------------------------- clasificación

CRITERIOS = {
    # SALUD-CAPTURA.md §4: fijados ANTES de las nuevas pruebas; no se ajustan con los resultados.
    "max_hueco_muestras_s": 30.0,      # dos muestras consecutivas más separadas: tramo sin medida
    "rotacion_s": 5.0,                 # rotación del anillo instalada en 4A (se pasa con --rotacion)
    "tolerancia_rotacion_s": 2.0,      # salto entre inicios > rotación + tolerancia = hueco de anillo
    "motor_retraso_max_s": 25.0,       # Etapa 2, R2: máximo de logged_at − window_end
    "via_antiguedad_max_s": 2.0,       # resumen de la vía rápida sin avanzar > 2 s con tic de 0,05 s
    # Estadísticas SIGUSR1 de tcpdump (SALUD-CAPTURA §2.1): una lectura cada 30 s; la lectura que acota el inicio
    # a <= 30 s antes, la que acota el fin a <= 30 s después y, entre ellas, lecturas consecutivas del MISMO PID.
    "tcpdump_periodo_s": 30.0,
    # Tolerancia de PLANIFICACIÓN (declarada el 2-nov, antes de cualquier medida en vivo): el timer lleva
    # AccuracySec=1s (dispara en [:00, :01] y [:30, :31]) y entre la señal y la marca del journal pasa < 1 s.
    # Sin ella, un disparo a :00,9 seguido de otro a :30,2 + escritura daría 30,x s y un C3 falso.
    "tcpdump_tolerancia_s": 2.0,
}


def cobertura_tcpdump(lecturas: list[dict], desde: float, hasta: float, crit: dict) -> dict:
    """Cobertura de las estadísticas SIGUSR1 de UN tcpdump (anillo o vía rápida, nunca mezclados) en [desde, hasta].

    Devuelve {"ok": bool, "motivos_c3": [...], "descartados_kernel": int|None, ...}. ok=False => C3.
    Exige (criterio publicado + tolerancia declarada, lim = periodo + tolerancia):
      - lectura a <= lim antes de desde y lectura a <= lim después de hasta;
      - entre ellas, ningún hueco > lim entre lecturas consecutivas;
      - un solo PID en todo el tramo (otro PID = reinicio de tcpdump o fuentes mezcladas);
      - contadores válidos: enteros >= 0, capturados <= recibidos, y no decrecientes dentro del PID.
    Lecturas sin hora o sin PID no cuentan (se informan)."""
    lim = crit["tcpdump_periodo_s"] + crit["tcpdump_tolerancia_s"]
    validas, sin_id = [], 0
    for r in lecturas:
        if r.get("t") is None or r.get("pid") is None:
            sin_id += 1
            continue
        validas.append(r)
    validas.sort(key=lambda r: r["t"])
    res = {"ok": False, "motivos_c3": [], "descartados_kernel": None, "lecturas_sin_hora_o_pid": sin_id,
           "limite_s": lim}
    if not validas:
        res["motivos_c3"].append("tcpdump sin lecturas SIGUSR1")
        return res
    a = [r for r in validas if r["t"] <= desde]
    b = [r for r in validas if r["t"] >= hasta]
    if not a or not b:
        res["motivos_c3"].append("tcpdump sin lecturas SIGUSR1 que acoten el periodo"
                                 + (" (ninguna anterior o igual al inicio)" if not a else "")
                                 + (" (ninguna posterior o igual al fin)" if not b else ""))
        return res
    ra, rb = a[-1], b[0]
    tramo = [r for r in validas if ra["t"] <= r["t"] <= rb["t"]]
    res.update({"desde": ra["t"], "hasta": rb["t"], "lecturas": len(tramo),
                "pids": sorted({r["pid"] for r in tramo})})
    mot = res["motivos_c3"]
    if desde - ra["t"] > lim:
        mot.append(f"tcpdump: la lectura que acota el inicio está {round(desde - ra['t'], 1)} s antes (> {lim} s)")
    if rb["t"] - hasta > lim:
        mot.append(f"tcpdump: la lectura que acota el fin está {round(rb['t'] - hasta, 1)} s después (> {lim} s)")
    if len(res["pids"]) > 1:
        mot.append("tcpdump: varios PID en el periodo " + str(res["pids"])
                   + " (reinicio del proceso o lecturas de dos capturas mezcladas)")
    huecos = [(y["t"] - x["t"], x["t"]) for x, y in zip(tramo, tramo[1:]) if y["t"] - x["t"] > lim]
    if huecos:
        h, t0 = max(huecos)
        mot.append(f"tcpdump: {len(huecos)} hueco(s) entre lecturas SIGUSR1 > {lim} s (máximo {round(h, 1)} s desde {t0})")
    campos = ("capturados", "recibidos_filtro", "descartados_kernel")
    invalidas = [r for r in tramo if any(not isinstance(r.get(c), int) or r[c] < 0 for c in campos)
                 or r["capturados"] > r["recibidos_filtro"]]
    if invalidas:
        mot.append(f"tcpdump: {len(invalidas)} lectura(s) con contadores inválidos")
    elif len(res["pids"]) == 1 and any(y[c] < x[c] for x, y in zip(tramo, tramo[1:]) for c in campos):
        mot.append("tcpdump: contador acumulado que decrece sin cambio de PID (lectura inválida)")
    if not mot:
        res["ok"] = True
        res["descartados_kernel"] = rb["descartados_kernel"] - ra["descartados_kernel"]
        res["pid"] = ra["pid"]
    return res


def clasificar(incs: list[dict], tcpdump: list[dict], desde: float, hasta: float, crit: dict,
               suricata_eve: dict | None = None) -> dict:
    """Clase del periodo según OBJETIVOS-Y-CRITERIOS §6.1, con la cota conservadora de las muestras.

    ``suricata_eve`` (resultado de ``medida_suricata_eve`` para el MISMO periodo): si se da, decide la parte de
    Suricata en lugar de stats.log. cero_explicito -> nada; descartes -> C1; cualquier otro estado -> C3 con su
    nombre. Sin él, se conserva el comportamiento de 2026-11-02.2 (stats.log), para reproducir lo histórico."""
    previos = [i for i in incs if i["desde"] <= desde]
    if not previos:
        return {"clase": "insuficiente", "motivos": ["ninguna muestra anterior o igual al inicio del periodo"]}
    ini = max(previos, key=lambda i: i["desde"])["desde"]
    posteriores = [i for i in incs if i["hasta"] >= hasta]
    if not posteriores:
        return {"clase": "insuficiente", "motivos": ["ninguna muestra posterior o igual al fin del periodo"]}
    fin = min(posteriores, key=lambda i: i["hasta"])["hasta"]
    tramo = [i for i in incs if i["desde"] >= ini and i["hasta"] <= fin]
    motivos_c3, motivos_c2, motivos_c1, info = [], [], [], {}
    # cobertura de las muestras
    huecos = [i for i in tramo if i["hasta"] - i["desde"] > crit["max_hueco_muestras_s"]]
    if huecos:
        motivos_c3.append(f"{len(huecos)} tramo(s) sin muestra > {crit['max_hueco_muestras_s']} s")
    # reinicios de cualquier componente
    reinicios = sorted({r for i in tramo for r in i["reinicios"]})
    if reinicios:
        motivos_c3.append("reinicio o parada: " + ", ".join(reinicios))
    # suricata
    if suricata_eve is not None:
        se = suricata_eve
        info["suricata"] = {"fuente": "eve_stats", "estado": se.get("estado"), "paquetes": se.get("paquetes"),
                            "descartes": se.get("descartes"), "descartes_parciales": se.get("descartes_parciales"),
                            "acotado_por": se.get("acotado_por"), "motivos": se.get("motivos")}
        if [round(x, 3) for x in se.get("periodo") or []] != [round(desde, 3), round(hasta, 3)]:
            motivos_c3.append("Suricata (EVE): la medida dada no es del mismo periodo")
        elif se.get("estado") == "descartes":
            motivos_c1.append(f"Suricata (EVE): {se['descartes']} descartes de {se['paquetes']} paquetes")
        elif se.get("estado") != "cero_explicito":
            motivos_c3.append(f"Suricata (EVE) {se.get('estado')}: " + "; ".join(se.get("motivos") or []))
    else:
        s_ok = [i["suricata"] for i in tramo if i.get("suricata", {}).get("ok")]
        s_no = [i for i in tramo if "suricata" in i and not i["suricata"].get("ok")]
        if s_no or not s_ok:
            motivos_c3.append("Suricata sin medida completa en el periodo")
        dd = sum(s["descartes"] for s in s_ok)
        dp = sum(s["paquetes"] for s in s_ok)
        info["suricata"] = {"fuente": "stats.log", "paquetes": dp, "descartes": dd, "intervalos": len(s_ok)}
        if dd > 0:
            motivos_c1.append(f"Suricata: {dd} descartes de {dp} paquetes")
    # anillo
    saltos = [i["anillo"]["salto_max_s"] for i in tramo if i.get("anillo", {}).get("ok")
              and i["anillo"].get("salto_max_s") is not None]
    lim = crit["rotacion_s"] + crit["tolerancia_rotacion_s"]
    if saltos and max(saltos) > lim:
        motivos_c3.append(f"hueco en el anillo: salto {max(saltos)} s > {lim} s")
    if not saltos:
        motivos_c3.append("anillo sin medida")
    # archivador
    arc = [i["archivador"] for i in tramo if "archivador" in i]
    if arc:
        if any(not a.get("ok") for a in arc):
            motivos_c3.append("archivador sin medida")
        elif any(a["nuevos_fallo"] or a["nuevos_perdidos"] for a in arc):
            motivos_c3.append("archivador con FALLO o PERDIDO")
    # motor
    ret = [i["motor"]["retraso_pcap_s"] for i in tramo if i.get("motor", {}).get("ok")
           and i["motor"].get("retraso_pcap_s") is not None]
    info["motor_retraso_pcap_max_s"] = max(ret) if ret else None
    # via rápida (informativa: no clasifica el IF, sí la evaluación de la vía rápida)
    vr = [i["via_rapida"] for i in tramo if "via_rapida" in i]
    info["via_rapida"] = {"medida": bool(vr) and all(v.get("ok") for v in vr),
                          "antiguedad_max_s": max((v.get("antiguedad_s") or 0) for v in vr) if vr else None}
    # tcpdump: cobertura SIGUSR1 completa de UNA captura (§2.1). Antes (2026-11-02.1) bastaba una lectura <= desde
    # y otra >= hasta de cualquier PID, aunque estuvieran a horas y faltaran todas las intermedias: daba C0.
    cob = cobertura_tcpdump(tcpdump, desde, hasta, crit)
    info["tcpdump"] = cob
    if not cob["ok"]:
        motivos_c3.extend(cob["motivos_c3"])
    elif cob["descartados_kernel"] > 0:
        motivos_c2.append(f"tcpdump PID {cob['pid']}: {cob['descartados_kernel']} descartados por el kernel")
    if motivos_c3:
        clase = "C3"
    elif motivos_c2:
        clase = "C2"
    elif motivos_c1:
        clase = "C1"
    else:
        clase = "C0"
    return {"clase": clase, "periodo": [desde, hasta], "acotado_por": [ini, fin],
            "motivos": motivos_c3 + motivos_c2 + motivos_c1, "info": info}


# ---------------------------------------------------------------- CLI


def _leer_jsonl(p: Path) -> list[dict]:
    out = []
    with p.open(encoding="utf-8") as fh:
        for l in fh:
            l = l.strip()
            if l:
                out.append(json.loads(l))
    return out


def _t(s: str) -> float:
    try:
        return float(s)
    except ValueError:
        return dt.datetime.fromisoformat(s.replace("Z", "+00:00")).timestamp()


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="cmd", required=True)
    m = sub.add_parser("muestrear")
    m.add_argument("--salida", type=Path, required=True)
    m.add_argument("--suricata-stats", type=Path)
    m.add_argument("--interfaz")
    m.add_argument("--unidad", action="append")
    m.add_argument("--anillo", type=Path)
    m.add_argument("--anillo-ultimos", type=int, default=40)
    m.add_argument("--archivador", type=Path)
    m.add_argument("--resumen-rapida", type=Path)
    m.add_argument("--ciclos", type=Path)
    m.add_argument("--pid", type=int, action="append")
    m.add_argument("--hijos-de-unidad")
    m.add_argument("--systemctl", default="systemctl")
    m.add_argument("--intervalo", type=float, default=0.0, help="0 = una sola muestra")
    m.add_argument("--hasta", type=_t, default=None, help="epoch o ISO-8601; con --intervalo")
    i = sub.add_parser("intervalos")
    i.add_argument("muestras", type=Path)
    i.add_argument("salida", type=Path)
    c = sub.add_parser("clasificar")
    c.add_argument("--incrementos", type=Path, required=True)
    c.add_argument("--tcpdump-log", type=Path, action="append", default=[])
    c.add_argument("--desde", type=_t, required=True)
    c.add_argument("--hasta", type=_t, required=True)
    c.add_argument("--rotacion", type=float, default=CRITERIOS["rotacion_s"])
    c.add_argument("--suricata-eve", type=Path, action="append", default=[],
                   help="eve.json y sus rotados: Suricata se mide por EVE stats (2026-11-06.1)")
    e = sub.add_parser("suricata-eve", help="medida de Suricata en [desde, hasta] por EVE stats (JSON)")
    e.add_argument("--eve", type=Path, action="append", required=True)
    e.add_argument("--desde", type=_t, required=True)
    e.add_argument("--hasta", type=_t, required=True)
    i5 = sub.add_parser("i5", help="I5: 0 kernel_drops en la ventana previa. rc 0 cumple, 1 no cumple, 2 no demostrable")
    i5.add_argument("--eve", type=Path, action="append", required=True)
    i5.add_argument("--ventana", type=float, default=1800.0)
    a = p.parse_args(argv)
    if a.cmd == "suricata-eve":
        res = medida_suricata_eve(leer_eve_stats(a.eve, desde=a.desde), a.desde, a.hasta, time.time())
        print(json.dumps(res, indent=1, sort_keys=True, ensure_ascii=False))
        return 0
    if a.cmd == "i5":
        ahora = time.time()
        res = comprobar_i5(leer_eve_stats(a.eve, desde=ahora - a.ventana - 120), ahora, a.ventana)
        res["evaluado_en"] = ahora
        print(json.dumps(res, indent=1, sort_keys=True, ensure_ascii=False))
        return {"cumple": 0, "no_cumple": 1}.get(res["i5"], 2)
    if a.cmd == "muestrear":
        import contextlib
        destino = (contextlib.nullcontext(sys.stdout) if str(a.salida) == "-"
                   else a.salida.open("a", encoding="utf-8"))
        with destino as fh:
            while True:
                fh.write(json.dumps(muestra(a), sort_keys=True) + "\n")
                fh.flush()
                if a.intervalo <= 0 or (a.hasta is not None and time.time() >= a.hasta):
                    break
                time.sleep(a.intervalo)
        return 0
    if a.cmd == "intervalos":
        incs = incrementos(_leer_jsonl(a.muestras))
        with a.salida.open("w", encoding="utf-8") as fh:
            for x in incs:
                fh.write(json.dumps(x, sort_keys=True) + "\n")
        print(f"{len(incs)} incrementos; con reinicio: {sum(1 for x in incs if x['reinicios'])}")
        return 0
    crit = dict(CRITERIOS, rotacion_s=a.rotacion)
    if a.hasta <= a.desde:
        print("error: --hasta debe ser posterior a --desde", file=sys.stderr)
        return 2
    for f in a.tcpdump_log:
        if not f.is_file():  # un journal que no se pudo exportar no es "cero lecturas": se para
            print(f"error: --tcpdump-log no legible: {f}", file=sys.stderr)
            return 2
    td = [r for f in a.tcpdump_log for r in leer_tcpdump_log(f)]
    se = None
    if a.suricata_eve:
        se = medida_suricata_eve(leer_eve_stats(a.suricata_eve, desde=a.desde), a.desde, a.hasta, time.time())
    res = clasificar(_leer_jsonl(a.incrementos), td, a.desde, a.hasta, crit, suricata_eve=se)
    res["criterios"] = dict(crit, **(CRITERIOS_EVE if se is not None else {}))
    res["version"] = VERSION
    print(json.dumps(res, indent=1, sort_keys=True))
    return 0


if __name__ == "__main__":
    sys.exit(main())
