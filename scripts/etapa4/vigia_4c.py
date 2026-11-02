#!/usr/bin/env python3
"""Vigilancia EFECTIVA de la batería 4C: evalúa P1–P5 y X1–X3 (SALUD-CAPTURA §4.2) y emite el PERMISO que el
generador de la Kali exige antes de cada episodio (generar_campana.py --permiso --nonce).

Subórdenes:
  sensor   [SENSOR1 m4rk] solo lectura: unidades, lecturas SIGUSR1 del tcpdump del anillo, saltos del anillo,
           archivador, tráfico de la Kali fuera de la lista blanca (EVE) y, si se pide, la clase de salud de
           episodios terminados. Imprime un JSON.
  bucle    [BASTIÓN gadmin] cada --intervalo s: lee el sensor, srv-dmz (estado_sombra.py, cada --cada-srvdmz s) y
           las marcas de la Kali; decide continuar / pausa / cancelar; escribe el permiso en la Kali por UN canal SSH
           persistente (ControlMaster) y lo registra todo en <dir>/vigia.jsonl y <dir>/accesos-kali.log.

Fallo cerrado: si una lectura falla, la decisión es PAUSA (nunca «continuar» por omisión). Si el bastión pierde la
Kali, el permiso que ya tiene caduca a los --validez s y el generador se para solo; si sigue sin permiso válido
--permiso-max-espera s, se cancela él mismo.

Reglas (SALUD-CAPTURA §4.2, sin cambios; interpretación declarada en los comentarios de decidir()):
  P1 reinicio o parada de ppi-motor, ppi-motor-capture, ppi-via-rapida@ens37 o suricata
  P2 desfase de reloj > 1 s (sensor, Kali, srv-dmz), o desfase no medible con cota <= 1 s
  P3 salto del anillo > 7 s, o FALLO/PERDIDO nuevos en el archivador
  P4 descartes D del tcpdump del anillo que crecen, o sin lectura SIGUSR1 > 90 s
  P5 tres episodios consecutivos en C1 (exige un diagnóstico escrito para reanudar)
  reanudar: >= 300 s seguidos sin condición y >= 230 s desde el arranque del motor
  X1 C2+C3 > 20 % de los episodios: se cancela cuando ya es SEGURO (C2+C3 > 20 % de los planificados)
  X2 estado_sombra.py rc=1 en srv-dmz (evento aplicacion, tabla cyberflow, ruleset distinto, --aplicar)
  X3 flujo de la Kali hacia un destino fuera de la lista blanca DURANTE un episodio
"""
from __future__ import annotations

import argparse
import json
import os
import shlex
import subprocess
import sys
import tempfile
import time
from pathlib import Path

VERSION = "2026-11-02.1"
UNIDADES = ("ppi-motor", "ppi-motor-capture", "ppi-via-rapida@ens37", "suricata")
CRIT = {
    "intervalo_s": 60.0,          # una ronda por minuto (como la vigilancia de b01)
    "validez_s": 150.0,           # el permiso caduca si no se renueva en 2 rondas y media
    "reanudar_limpio_s": 300.0,   # SALUD §4.2: >= 5 min seguidos sin condición
    "historia_motor_s": 230.0,    # SALUD §4.2: >= 230 s de historia tras un arranque del motor
    "desfase_max_s": 1.0,         # P2
    "salto_anillo_max_s": 7.0,    # P3
    "sin_sigusr1_max_s": 90.0,    # P4
    "c1_consecutivos": 3,         # P5
    "x1_fraccion": 0.20,          # X1
    "cada_srvdmz_s": 300.0,       # X2: estado_sombra completo cada 5 min
}


# ----------------------------------------------------------------------------------------------- sensor (lectura)

def _uptime() -> float:
    return float(Path("/proc/uptime").read_text().split()[0])


def obs_sensor(a) -> dict:
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    import salud_captura as sc  # noqa: E402
    ahora = time.time()
    r: dict = {"version": VERSION, "reloj_epoch": ahora, "ok": True, "motivos": []}
    try:
        up = _uptime()
    except OSError:
        up = None
    uds = {}
    for u in UNIDADES:
        x = sc.leer_unidad(u, a.systemctl)
        if x.get("ok") and up is not None and x.get("arranque_mono_us"):
            x["arranque_epoch"] = ahora - (up - x["arranque_mono_us"] / 1e6)
        uds[u] = x
    r["unidades"] = uds
    # lecturas SIGUSR1 del tcpdump del anillo en los últimos --ventana-tcpdump s
    try:
        p = subprocess.run(shlex.split(a.journalctl) + ["-u", "ppi-motor-capture", "--since",
                           f"@{int(ahora - a.ventana_tcpdump)}", "-o", "short-iso-precise", "--no-pager"],
                           capture_output=True, text=True, timeout=30, stdin=subprocess.DEVNULL)
        if p.returncode != 0:
            r["tcpdump"] = {"ok": False, "motivo": f"journalctl rc={p.returncode}: {p.stderr.strip()[:120]}"}
        else:
            with tempfile.NamedTemporaryFile("w", suffix=".txt", delete=False) as fh:
                fh.write(p.stdout)
            try:
                lect = sc.leer_tcpdump_log(Path(fh.name))
            finally:
                os.unlink(fh.name)
            r["tcpdump"] = {"ok": True, "lecturas": [{k: x[k] for k in ("t", "pid", "descartados_kernel")}
                                                     for x in lect]}
    except (OSError, subprocess.TimeoutExpired) as e:
        r["tcpdump"] = {"ok": False, "motivo": f"journalctl: {e.__class__.__name__}"}
    r["anillo"] = sc.leer_anillo(Path(a.anillo), ultimos=a.anillo_ultimos)
    r["archivador"] = sc.leer_archivador(Path(a.archivador))
    r["eve"] = eve_fuera_lista(Path(a.eve), a.eve_cursor, a.origen, set(a.lista_blanca.split(",")),
                               a.eve_max_bytes)
    if a.muestras and a.clasificar:
        r["clases"] = clasificar_episodios(sc, Path(a.muestras), a.clasificar, a.journalctl)
    return r


def eve_fuera_lista(eve: Path, cursor: int, origen: str, blanca: set[str], max_bytes: int) -> dict:
    """Eventos de EVE con src_ip = origen y dest_ip fuera de la lista blanca, desde el byte `cursor`.
    cursor < 0: primera lectura, se coloca al final sin leer. Rotación (tamaño < cursor): desde 0."""
    try:
        tam = eve.stat().st_size
    except OSError as e:
        return {"ok": False, "motivo": f"EVE no legible: {e.__class__.__name__}"}
    if cursor < 0:
        return {"ok": True, "cursor": tam, "inicial": True, "fuera": []}
    rotado = tam < cursor
    desde = 0 if rotado else cursor
    if tam - desde > max_bytes:
        return {"ok": False, "motivo": f"EVE creció {tam - desde} B (> {max_bytes}): no verificable en esta ronda",
                "cursor": tam}
    aguja = f'"src_ip":"{origen}"'.encode()
    fuera, n = [], 0
    try:
        with eve.open("rb") as fh:
            fh.seek(desde)
            datos = fh.read(tam - desde)
    except OSError as e:
        return {"ok": False, "motivo": f"EVE no legible: {e.__class__.__name__}"}
    fin = datos.rfind(b"\n") + 1          # una línea a medio escribir se lee en la ronda siguiente
    for linea in datos[:fin].splitlines():
        if aguja not in linea:
            continue
        try:
            ev = json.loads(linea)
        except ValueError:
            continue
        n += 1
        if ev.get("src_ip") == origen and ev.get("dest_ip") not in blanca:
            # en los eventos flow, "timestamp" puede ser el cierre: la hora que cuenta es el inicio del flujo
            fuera.append({"ts": (ev.get("flow") or {}).get("start") or ev.get("timestamp"),
                          "dest_ip": ev.get("dest_ip"), "dest_port": ev.get("dest_port"),
                          "proto": ev.get("proto"), "event_type": ev.get("event_type")})
    return {"ok": True, "cursor": desde + fin, "rotado": rotado, "eventos_origen": n, "fuera": fuera[:200],
            "fuera_total": len(fuera)}


def clasificar_episodios(sc, muestras: Path, pedidos: list[str], journalctl: str) -> dict:
    out = {}
    try:
        ms = sc._leer_jsonl(muestras)
    except OSError as e:
        return {p.split(":", 1)[0]: {"clase": "C3", "motivo": f"muestras no legibles: {e}"} for p in pedidos}
    incs = sc.incrementos(ms)
    for p in pedidos:
        ep, de, ha = p.split(":")
        de, ha = float(de), float(ha)
        try:
            j = subprocess.run(shlex.split(journalctl) + ["-u", "ppi-motor-capture", "--since", f"@{int(de - 60)}",
                               "--until", f"@{int(ha + 60)}", "-o", "short-iso-precise", "--no-pager"],
                               capture_output=True, text=True, timeout=30, stdin=subprocess.DEVNULL)
            if j.returncode != 0:
                out[ep] = {"clase": "C3", "motivo": f"journalctl rc={j.returncode}"}
                continue
            with tempfile.NamedTemporaryFile("w", suffix=".txt", delete=False) as fh:
                fh.write(j.stdout)
            try:
                td = sc.leer_tcpdump_log(Path(fh.name))
            finally:
                os.unlink(fh.name)
            r = sc.clasificar(incs, td, de, ha, dict(sc.CRITERIOS))
            out[ep] = {"clase": r["clase"], "motivos": r.get("motivos", [])[:5]}
        except (OSError, subprocess.TimeoutExpired, ValueError) as e:
            out[ep] = {"clase": "C3", "motivo": f"{e.__class__.__name__}"}
    return out


# ----------------------------------------------------------------------------------------------- decisión (pura)

def estado_inicial(planificados: int) -> dict:
    return {"base": None, "ultima_condicion": None, "pausa_desde": None, "cancelado": None, "clases": {},
            "orden_fin": [], "p5_pendiente": None, "planificados": planificados, "ultimo_d": None,
            "ultima_srvdmz": None, "fallo_srvdmz": None}


def condiciones(st: dict, obs: dict, ahora: float, crit: dict) -> tuple[list[str], list[str]]:
    """(pausas, cancelaciones) presentes en esta ronda. Modifica st (bases y contadores)."""
    p, x = [], []
    s = obs.get("sensor") or {}
    if not s.get("ok", False):
        p.append(f"sin lectura del sensor: {s.get('motivo', 'error')}")
    else:
        uds = s.get("unidades", {})
        base = st["base"]
        if base is None:
            base = st["base"] = {u: {"nrestarts": (uds.get(u) or {}).get("nrestarts"),
                                     "arranque_epoch": (uds.get(u) or {}).get("arranque_epoch")} for u in UNIDADES}
            st["base_archivador"] = dict(s.get("archivador") or {})
        for u in UNIDADES:
            x_u = uds.get(u) or {}
            if not x_u.get("ok"):
                p.append(f"P1 {u}: estado no legible ({x_u.get('motivo')})")
                continue
            if x_u.get("activo") != "active":
                p.append(f"P1 {u} {x_u.get('activo')}")
            b = base[u]
            if b["nrestarts"] is not None and x_u.get("nrestarts") != b["nrestarts"] or \
                    b["arranque_epoch"] is not None and x_u.get("arranque_epoch") is not None and \
                    abs(x_u["arranque_epoch"] - b["arranque_epoch"]) > 2:
                p.append(f"P1 {u} reiniciada (NRestarts {b['nrestarts']}->{x_u.get('nrestarts')})")
                base[u] = {"nrestarts": x_u.get("nrestarts"), "arranque_epoch": x_u.get("arranque_epoch")}
        # P3
        an = s.get("anillo") or {}
        if not an.get("ok"):
            p.append(f"P3 anillo no legible ({an.get('motivo')})")
        elif (an.get("salto_max_s") or 0) > crit["salto_anillo_max_s"]:
            p.append(f"P3 salto del anillo {an['salto_max_s']:.0f} s > {crit['salto_anillo_max_s']:.0f} s")
        ar, bar = s.get("archivador") or {}, st.get("base_archivador") or {}
        if not ar.get("ok"):
            p.append(f"P3 archivador no legible ({ar.get('motivo')})")
        elif ar.get("lineas_fallo", 0) > bar.get("lineas_fallo", 0) or ar.get("perdidos", 0) > bar.get("perdidos", 0):
            p.append(f"P3 archivador con FALLO/PERDIDO nuevos ({ar.get('lineas_fallo')}/{ar.get('perdidos')})")
            st["base_archivador"] = dict(ar)
        # P4: D crece (dentro del mismo PID) o sin lectura SIGUSR1 > 90 s
        td = s.get("tcpdump") or {}
        if not td.get("ok"):
            p.append(f"P4 lecturas SIGUSR1 no disponibles ({td.get('motivo')})")
        else:
            lect = sorted((l for l in td.get("lecturas", []) if l.get("t") is not None), key=lambda l: l["t"])
            if not lect or ahora - lect[-1]["t"] > crit["sin_sigusr1_max_s"]:
                edad = "ninguna" if not lect else f"{ahora - lect[-1]['t']:.0f} s"
                p.append(f"P4 sin lectura SIGUSR1 del anillo en > {crit['sin_sigusr1_max_s']:.0f} s (última: {edad})")
            else:
                ult = lect[-1]
                prev = st.get("ultimo_d")
                ds = [l["descartados_kernel"] for l in lect if l["pid"] == ult["pid"]]
                if prev is not None and prev["pid"] == ult["pid"] and ult["descartados_kernel"] > prev["d"] \
                        or len(ds) > 1 and ds[-1] > ds[0]:
                    p.append(f"P4 descartes del tcpdump del anillo crecen (D={ult['descartados_kernel']})")
                st["ultimo_d"] = {"pid": ult["pid"], "d": ult["descartados_kernel"]}
        # X3: solo cuenta lo que cae dentro de un episodio en curso o terminado
        ev = s.get("eve") or {}
        if not ev.get("ok"):
            p.append(f"X3 no verificable: {ev.get('motivo')}")
        else:
            st.setdefault("fuera_lista", []).extend(ev.get("fuera", []))
    # X3: se reevalúa cada ronda (las marcas del episodio pueden llegar después que el evento de EVE); se guarda
    # 30 min. Fuera de los episodios se informa pero no cancela (tráfico propio de la Kali, no de ataque).
    retenidos = []
    for f in st.get("fuera_lista", []):
        t = _iso_epoch(f.get("ts"))
        if t is not None and _en_episodio(st, t):
            x.append(f"X3 tráfico de la Kali a {f.get('dest_ip')}:{f.get('dest_port')} ({f.get('event_type')}) "
                     f"durante un episodio")
            break
        if t is None or ahora - t < 1800:
            retenidos.append(f)
    st["fuera_lista"] = retenidos
    # P2
    for host in ("sensor", "kali", "srvdmz"):
        d = (obs.get("desfases") or {}).get(host)
        if d is None:
            continue
        if d["cota_s"] > crit["desfase_max_s"]:
            p.append(f"P2 desfase de {host} no medible (cota {d['cota_s']:.2f} s)")
        elif abs(d["desfase_s"]) > crit["desfase_max_s"]:
            p.append(f"P2 desfase de {host} {d['desfase_s']:+.2f} s")
    # X2 (srv-dmz): rc 1 cancela; rc 2/3 o fallo de SSH pausan (sombra no demostrada) hasta la siguiente lectura buena
    sd = obs.get("srvdmz")
    if sd is not None:
        st["ultima_srvdmz"] = ahora
        if sd.get("rc") == 1:
            x.append("X2 srv-dmz: " + (sd.get("resumen") or "aplicación detectada"))
        st["fallo_srvdmz"] = None if sd.get("rc") == 0 else f"rc={sd.get('rc')} {sd.get('resumen', '')}".strip()
    if st.get("fallo_srvdmz"):
        p.append("sombra de srv-dmz no demostrada: " + st["fallo_srvdmz"])
    if st.get("ultima_srvdmz") is None or ahora - st["ultima_srvdmz"] > 2 * crit["cada_srvdmz_s"] + crit["intervalo_s"]:
        p.append("sombra de srv-dmz sin lectura reciente")
    # clases de episodios -> P5 y X1
    for ep, c in (obs.get("clases") or {}).items():
        if ep not in st["clases"]:
            st["clases"][ep] = c["clase"]
    ordenados = [st["clases"][e] for e in st["orden_fin"] if e in st["clases"]]
    if len(ordenados) >= crit["c1_consecutivos"] and all(c == "C1" for c in ordenados[-crit["c1_consecutivos"]:]):
        clave = tuple(e for e in st["orden_fin"] if e in st["clases"])[-crit["c1_consecutivos"]:]
        if st.get("p5_visto") != list(clave):
            st["p5_visto"] = list(clave)
            st["p5_pendiente"] = {"desde": ahora, "episodios": list(clave)}
    if st.get("p5_pendiente"):
        diag = obs.get("diagnostico_p5_epoch")
        if diag is not None and diag >= st["p5_pendiente"]["desde"]:
            st["p5_pendiente"] = None
        else:
            p.append(f"P5 tres episodios consecutivos en C1 ({', '.join(st['p5_pendiente']['episodios'])}): "
                     f"falta el diagnóstico de Suricata escrito")
    malos = sum(1 for c in st["clases"].values() if c in ("C2", "C3"))
    if malos > crit["x1_fraccion"] * st["planificados"]:
        x.append(f"X1 {malos} episodios en C2/C3 > {crit['x1_fraccion']:.0%} de {st['planificados']}: "
                 f"ya no puede quedar por debajo")
    return p, x


def decidir(st: dict, obs: dict, ahora: float, crit: dict) -> dict:
    """{'estado': continuar|pausa|cancelar, 'causas': [...]}. La cancelación es definitiva."""
    if st["cancelado"]:
        return {"estado": "cancelar", "causas": st["cancelado"]}
    pausas, cancel = condiciones(st, obs, ahora, crit)
    if cancel:
        st["cancelado"] = cancel
        return {"estado": "cancelar", "causas": cancel}
    if pausas:
        st["ultima_condicion"] = ahora
        if st["pausa_desde"] is None:
            st["pausa_desde"] = ahora
        return {"estado": "pausa", "causas": pausas}
    espera = []
    if st["ultima_condicion"] is not None and ahora - st["ultima_condicion"] < crit["reanudar_limpio_s"]:
        espera.append(f"reanudación: {ahora - st['ultima_condicion']:.0f} s sin condición de "
                      f"{crit['reanudar_limpio_s']:.0f} s")
    m = ((obs.get("sensor") or {}).get("unidades") or {}).get("ppi-motor") or {}
    if m.get("arranque_epoch") is not None and ahora - m["arranque_epoch"] < crit["historia_motor_s"]:
        espera.append(f"historia del motor {ahora - m['arranque_epoch']:.0f} s < {crit['historia_motor_s']:.0f} s")
    if espera:
        return {"estado": "pausa", "causas": espera}
    st["pausa_desde"] = None
    return {"estado": "continuar", "causas": []}


def _iso_epoch(s) -> float | None:
    if not s:
        return None
    import re
    from datetime import datetime
    # EVE: 2026-11-02T19:10:00.123456+0000 ; marcas: 2026-11-02T19:10:00.123456+00:00
    s = re.sub(r"([+-]\d\d)(\d\d)$", r"\1:\2", str(s).replace("Z", "+00:00"))
    try:
        return datetime.fromisoformat(s).timestamp()
    except ValueError:
        return None


def _en_episodio(st: dict, t: float) -> bool:
    for ini, fin in st.get("intervalos", {}).values():
        if ini <= t <= (fin if fin is not None else float("inf")):
            return True
    return False


def asimilar_marcas(st: dict, marcas: list[dict]) -> list[tuple[str, float, float]]:
    """Actualiza intervalos de episodios; devuelve los episodios recién terminados (ep, inicio, fin)."""
    iv = st.setdefault("intervalos", {})
    nuevos = []
    for m in marcas:
        ev = m.get("evento")
        t = _iso_epoch((m.get("reloj") or {}).get("pared_utc"))
        if ev == "inicio" and t is not None:
            iv[m["episodio_id"]] = [t, None]
        elif ev == "fin" and t is not None and m.get("episodio_id") in iv:
            iv[m["episodio_id"]][1] = t
            st["orden_fin"].append(m["episodio_id"])
            nuevos.append((m["episodio_id"], iv[m["episodio_id"]][0], t))
        elif ev == "campana_fin":
            st["campana_fin"] = m.get("estado")
    return nuevos


# ----------------------------------------------------------------------------------------------- bucle (bastión)

def correr(cmd: list[str], entrada: str | None = None, timeout: float = 60) -> tuple[int | None, str, str, float, float]:
    t0 = time.time()
    try:
        p = subprocess.run(cmd, input=entrada, capture_output=True, text=True, timeout=timeout,
                           stdin=None if entrada is not None else subprocess.DEVNULL)
        return p.returncode, p.stdout, p.stderr, t0, time.time()
    except (OSError, subprocess.TimeoutExpired) as e:
        return None, "", f"{e.__class__.__name__}: {e}", t0, time.time()


def desfase(remoto: float, t0: float, t1: float) -> dict:
    return {"desfase_s": round(remoto - (t0 + t1) / 2, 3), "cota_s": round((t1 - t0) / 2, 3)}


def bucle(a, crit: dict, ejecutar=correr, dormir=time.sleep) -> int:
    d = Path(a.dir)
    d.mkdir(parents=True, exist_ok=True)
    log = (d / "vigia.jsonl").open("a", encoding="utf-8")
    accesos = (d / "accesos-kali.log").open("a", encoding="utf-8")
    st = estado_inicial(a.planificados)
    eve_cursor, n_marcas, seq, pendientes = -1, 0, 0, []
    ultima_sd = None
    fin_bucle = time.time() + a.max_duracion
    rc_final = 0

    def reg(o):
        log.write(json.dumps(o, ensure_ascii=False) + "\n")
        log.flush()

    reg({"evento": "vigia_inicio", "version": VERSION, "nonce": a.nonce, "crit": crit, "epoch": time.time()})
    def reloj_de(ssh: str) -> dict | None:
        """Sonda de reloj aparte (orden corta): la cota es la mitad del tiempo de ida y vuelta."""
        rc, out, _e, t0, t1 = ejecutar(shlex.split(ssh) + [a.orden_reloj])
        try:
            return desfase(float(out.split()[0]), t0, t1) if rc == 0 else {"desfase_s": 0.0, "cota_s": float("inf")}
        except (IndexError, ValueError):
            return {"desfase_s": 0.0, "cota_s": float("inf")}

    while True:
        ahora = time.time()
        obs: dict = {"desfases": {"sensor": reloj_de(a.ssh_sensor)}}
        if st.get("desfase_kali") is not None:
            obs["desfases"]["kali"] = st["desfase_kali"]          # medido en el canal de la ronda anterior
        # sensor
        cmd = shlex.split(a.ssh_sensor) + [a.orden_sensor + f" --eve-cursor {eve_cursor}" +
                                           "".join(f" --clasificar {e}:{i - 60:.3f}:{f + 60:.3f}"
                                                   for e, i, f in pendientes if ahora > f + 60 + 35)]
        rc, out, err, t0, t1 = ejecutar(cmd)
        try:
            s = json.loads(out) if rc == 0 else {"ok": False, "motivo": f"ssh rc={rc}: {err.strip()[:160]}"}
        except ValueError:
            s = {"ok": False, "motivo": "salida del sensor no es JSON"}
        obs["sensor"] = s
        if (s.get("eve") or {}).get("cursor") is not None:
            eve_cursor = s["eve"]["cursor"]
        if s.get("clases"):
            obs["clases"] = {k: v for k, v in s["clases"].items()}
            pendientes = [p for p in pendientes if p[0] not in s["clases"]]
        # srv-dmz (X2) cada cada_srvdmz_s
        if ultima_sd is None or ahora - ultima_sd >= crit["cada_srvdmz_s"]:
            obs["desfases"]["srvdmz"] = reloj_de(a.ssh_srvdmz)
            rc, out, err, t0, t1 = ejecutar(shlex.split(a.ssh_srvdmz) + [a.orden_srvdmz])
            lineas = out.splitlines()
            obs["srvdmz"] = {"rc": rc if rc in (0, 1, 2, 3) else None,
                             "resumen": " | ".join(l.strip() for l in lineas[:5])[:300] or err.strip()[:200]}
            ultima_sd = ahora
        # diagnóstico P5 escrito por una persona
        try:
            obs["diagnostico_p5_epoch"] = (d / "diagnostico-p5.txt").stat().st_mtime
        except OSError:
            pass
        # decisión con lo que sabemos ANTES de escribir el permiso (las marcas nuevas llegan en el mismo canal)
        dec = decidir(st, obs, ahora, crit)
        seq += 1
        permiso = {"nonce": a.nonce, "estado": dec["estado"], "causas": dec["causas"], "secuencia": seq,
                   "emitido_epoch": round(time.time(), 3),
                   "valido_hasta_epoch": round(time.time() + crit["validez_s"], 3), "vigia": VERSION}
        rc, out, err, t0, t1 = ejecutar(shlex.split(a.ssh_kali) + [a.orden_kali.replace("{N}", str(n_marcas + 1))],
                                        entrada=json.dumps(permiso, ensure_ascii=False) + "\n")
        accesos.write(f"{time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime(t0))} canal de control (permiso #{seq} "
                      f"{dec['estado']}) rc={rc} {t1 - t0:.2f}s\n")
        accesos.flush()
        marcas = []
        if rc == 0:
            lineas = out.splitlines()
            try:   # la Kali se mide en el propio canal; cuenta para P2 en la ronda siguiente
                st["desfase_kali"] = desfase(float(lineas[0]), t0, t1)
            except (IndexError, ValueError):
                st["desfase_kali"] = {"desfase_s": 0.0, "cota_s": float("inf")}
            for l in lineas[1:]:
                try:
                    marcas.append(json.loads(l))
                except ValueError:
                    pass
            n_marcas += len(marcas)
            for ep, i, f in asimilar_marcas(st, marcas):
                pendientes.append((ep, i, f))
        reg({"evento": "ronda", "epoch": ahora, "permiso": permiso, "kali_rc": rc, "marcas_nuevas": len(marcas),
             "desfases": obs["desfases"], "srvdmz": obs.get("srvdmz"), "sensor_ok": s.get("ok"),
             "sensor_motivo": s.get("motivo"), "clases": obs.get("clases"),
             "eve_fuera": (s.get("eve") or {}).get("fuera_total"), "pendientes_clase": [p[0] for p in pendientes]})
        if dec["estado"] == "cancelar" and any("X2" in c for c in dec["causas"]):
            reg({"evento": "reversion_necesaria", "procedimiento": "PROCEDIMIENTO-ETAPA4 §7", "epoch": time.time()})
        if st.get("campana_fin") is not None:
            reg({"evento": "vigia_fin", "campana_fin": st["campana_fin"], "clases": st["clases"],
                 "epoch": time.time()})
            rc_final = 0 if st["campana_fin"] == "completa" else 3
            break
        if time.time() > fin_bucle:
            reg({"evento": "vigia_fin", "motivo": "max_duracion", "epoch": time.time()})
            rc_final = 4
            break
        dormir(max(0.0, crit["intervalo_s"] - (time.time() - ahora)))
    log.close()
    accesos.close()
    return rc_final


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="orden", required=True)
    s = sub.add_parser("sensor")
    s.add_argument("--anillo", default="/var/lib/ppi-motor-capture")
    s.add_argument("--anillo-ultimos", type=int, default=12, help="ficheros de 5 s: 12 = último minuto")
    s.add_argument("--archivador", required=True)
    s.add_argument("--eve", default="/var/log/suricata/eve.json")
    s.add_argument("--eve-cursor", type=int, default=-1)
    s.add_argument("--eve-max-bytes", type=int, default=400 << 20)
    s.add_argument("--origen", default="10.10.20.30")
    s.add_argument("--lista-blanca", required=True, help="IPs separadas por comas")
    s.add_argument("--muestras", help="muestras.jsonl del muestreador de salud (para --clasificar)")
    s.add_argument("--clasificar", action="append", default=[], help="ep:desde:hasta (epoch)")
    s.add_argument("--ventana-tcpdump", type=float, default=150.0)
    s.add_argument("--systemctl", default="systemctl")
    s.add_argument("--journalctl", default="sudo -n journalctl")
    b = sub.add_parser("bucle")
    b.add_argument("--dir", required=True)
    b.add_argument("--nonce", required=True)
    b.add_argument("--planificados", type=int, default=25)
    b.add_argument("--ssh-sensor", required=True)
    b.add_argument("--orden-sensor", required=True, help="orden remota de 'sensor' (sin --eve-cursor ni --clasificar)")
    b.add_argument("--ssh-srvdmz", required=True)
    b.add_argument("--orden-srvdmz", required=True, help="imprime epoch en la 1.ª línea y sale con el rc de estado_sombra")
    b.add_argument("--ssh-kali", required=True, help="con ControlMaster/ControlPath: un único canal persistente")
    b.add_argument("--orden-kali", required=True,
                   help="lee el permiso por stdin, lo instala, imprime epoch y las marcas desde la línea {N}")
    b.add_argument("--orden-reloj", default="date +%s.%N")
    b.add_argument("--max-duracion", type=float, default=6 * 3600)
    for k, v in CRIT.items():
        b.add_argument("--" + k.replace("_", "-"), type=type(v), default=v)
    a = ap.parse_args(argv)
    if a.orden == "sensor":
        print(json.dumps(obs_sensor(a), ensure_ascii=False))
        return 0
    crit = {k: getattr(a, k) for k in CRIT}
    return bucle(a, crit)


if __name__ == "__main__":
    raise SystemExit(main())
