#!/usr/bin/env python3
"""Guardia de E-carga v2 (PROTOCOLO-CARGA-v2 §3.7). SOLO LECTURA: lee muestras.txt del bastión y dice si se cumple
alguna condición de parada anticipada. No para nada por sí misma: lo hace muestreo_bastion.sh con su resultado.
VERSION 2026-11-06.2: mismas condiciones; avisa también de lecturas fallidas (ERROR) de rulesets y traza del agente.

  guardia.py MUESTRAS.txt        -> JSON {"parar": bool, "motivos": [...], "avisos": [...], "muestras": n, "t": última}

Condiciones (las de §3.7, sin añadir ninguna; la línea base es la PRIMERA muestra del fichero):
  1. MemAvailable < 1 GiB (1 048 576 kB) o /home libre < 2 GB, tomado como 2 GiB (2 097 152 kB): la lectura más
     prudente de «2 GB».
  2. --aplicar o --enforce en Sensor1 o en el agente, ruleset distinto del de la línea base (Sensor1 o srv-dmz), o un
     evento «aplicacion» nuevo en la traza del agente (§2.1: una aplicación sí es motivo de parada).
  3. Reinicio de un servicio de la cadena: cambia el PID o NRestarts del relé, ppi-motor, ppi-motor-capture,
     ppi-via-rapida@ens37, suricata, ppi-publicar-feed-v2 o el agente (los de O1; el panel no es de la cadena).
  4. firma_invalida o paquete_invalido sostenidos más de 60 s: el contador sube sobre la línea base y vuelve a subir
     en una muestra tomada >= 60 s después de la primera subida.
  5. EVE parado más de 60 s: el último evento stats tiene más de 60 s respecto a la hora de la muestra.
Un dato que no se puede leer no es «cumple»: se informa como aviso (SIN_LECTURA). No es condición de §3.7, así que no
para por sí solo; queda en la evidencia y el S correspondiente saldrá sin medida (null).
"""
import datetime as dt
import json
import re
import sys

CADENA_S = ("ppi-motor", "ppi-motor-capture", "ppi-via-rapida@ens37", "suricata", "ppi-publicar-feed-v2")
MEM_MIN_KB = 1048576
HOME_MIN_KB = 2097152
SOSTENIDO_S = 60.0
EVE_MAX_S = 60.0


def bloques(texto):
    for b in texto.split("### ")[1:]:
        cab, _, cuerpo = b.partition("\n")
        try:
            t = float(cab.split()[1])
        except (IndexError, ValueError):
            continue
        yield t, cuerpo


def leer(t, c):
    m = {"t": t, "pid": {}, "falta": []}
    r = re.search(r"^B relay pid=(\d+) nr=(\d+)", c, re.M)
    if r:
        m["pid"]["relay"] = (r.group(1), r.group(2))
    else:
        m["falta"].append("relé")
    for u in CADENA_S:
        r = re.search(r"^S %s pid=(\d+) nr=(\d+)" % re.escape(u), c, re.M)
        if r:
            m["pid"][u] = (r.group(1), r.group(2))
        else:
            m["falta"].append(u)
    r = re.search(r"^D agente pid=(\d+) nr=(\d+) \S+ aplicar_cmd=(\d+)", c, re.M)
    if r:
        m["pid"]["agente"] = (r.group(1), r.group(2))
        m["aplicar_cmd"] = int(r.group(3))
    else:
        m["falta"].append("agente")
    r = re.search(r"enforce_aplicar=(\d+)", c)
    m["enforce_aplicar"] = int(r.group(1)) if r else None
    r = re.search(r"home_libre_kb=(\d+) carga=\S+ \S+ \S+ memdisp_kb=(\d+)", c)
    m["home_kb"], m["mem_kb"] = (int(r.group(1)), int(r.group(2))) if r else (None, None)
    r = re.search(r"^S ruleset=([0-9a-f]{16})$", c, re.M)
    m["ruleset_s"] = r.group(1) if r else None
    r = re.search(r"^D aplicacion=(\d+) firma_invalida=(\d+) paquete_invalido=(\d+) ruleset=([0-9a-f]{16})$", c, re.M)
    if r:
        m["aplicacion"], m["firma"], m["paquete"], m["ruleset_d"] = (int(r.group(1)), int(r.group(2)),
                                                                     int(r.group(3)), r.group(4))
    else:
        m["aplicacion"] = m["firma"] = m["paquete"] = m["ruleset_d"] = None
    r = re.search(r"^S eve_ultimo_stats=(\S+) \d+ \d+ \d+$", c, re.M)
    m["eve_t"] = None
    if r:
        try:
            m["eve_t"] = dt.datetime.strptime(r.group(1)[:26] + r.group(1)[-5:], "%Y-%m-%dT%H:%M:%S.%f%z").timestamp()
        except ValueError:
            pass
    return m


def evaluar(texto):
    ms = [leer(t, c) for t, c in bloques(texto)]
    res = {"parar": False, "motivos": [], "avisos": [], "muestras": len(ms), "t": ms[-1]["t"] if ms else None}
    if not ms:
        res["avisos"].append("SIN_LECTURA: ninguna muestra")
        return res
    base = ms[0]
    mot = res["motivos"]
    primera_subida = {}
    for m in ms:
        t = m["t"]
        if m["falta"]:
            res["avisos"].append(f"SIN_LECTURA {t:.0f}: " + ", ".join(m["falta"]))
        if m["mem_kb"] is not None and m["mem_kb"] < MEM_MIN_KB:
            mot.append(f"{t:.0f}: MemAvailable {m['mem_kb']} kB < 1 GiB")
        if m["home_kb"] is not None and m["home_kb"] < HOME_MIN_KB:
            mot.append(f"{t:.0f}: /home libre {m['home_kb']} kB < 2 GiB")
        if m["home_kb"] is None:
            res["avisos"].append(f"SIN_LECTURA {t:.0f}: recursos")
        if m["enforce_aplicar"]:
            mot.append(f"{t:.0f}: {m['enforce_aplicar']} proceso(s) con --aplicar/--enforce en Sensor1")
        if m.get("aplicar_cmd"):
            mot.append(f"{t:.0f}: agente con --aplicar")
        for k in ("ruleset_s", "ruleset_d"):
            if m[k] is not None and base[k] is not None and m[k] != base[k]:
                mot.append(f"{t:.0f}: {k} {base[k]} -> {m[k]}")
        if m["aplicacion"] is not None and base["aplicacion"] is not None and m["aplicacion"] > base["aplicacion"]:
            mot.append(f"{t:.0f}: {m['aplicacion'] - base['aplicacion']} evento(s) aplicacion nuevos")
        for u, v in m["pid"].items():
            if u in base["pid"] and v != base["pid"][u]:
                mot.append(f"{t:.0f}: reinicio de {u} (pid/nr {base['pid'][u]} -> {v})")
        for k in ("firma", "paquete"):
            if m[k] is None or base[k] is None or m[k] <= base[k]:
                continue
            if k not in primera_subida:
                primera_subida[k] = (t, m[k])
            elif t - primera_subida[k][0] >= SOSTENIDO_S and m[k] > primera_subida[k][1]:
                mot.append(f"{t:.0f}: {k}_invalido sigue subiendo {SOSTENIDO_S:.0f} s después de la primera subida "
                           f"({base[k]} -> {primera_subida[k][1]} -> {m[k]})")
        # 2026-11-06.2: una lectura fallida (ERROR) de ruleset o de la traza del agente se avisa; no para por sí sola.
        for k, n in (("ruleset_s", "ruleset de Sensor1"), ("ruleset_d", "ruleset de srv-dmz"), ("aplicacion", "traza del agente")):
            if m[k] is None:
                res["avisos"].append(f"SIN_LECTURA {t:.0f}: {n}")
        if m["eve_t"] is None:
            res["avisos"].append(f"SIN_LECTURA {t:.0f}: último stats de EVE")
        elif t - m["eve_t"] > EVE_MAX_S:
            mot.append(f"{t:.0f}: EVE sin stats desde hace {t - m['eve_t']:.0f} s (> 60 s)")
    res["motivos"] = list(dict.fromkeys(mot))
    res["avisos"] = list(dict.fromkeys(res["avisos"]))
    res["parar"] = bool(res["motivos"])
    return res


if __name__ == "__main__":
    with open(sys.argv[1], encoding="utf-8", errors="replace") as f:
        r = evaluar(f.read())
    print(json.dumps(r, ensure_ascii=False))
    sys.exit(1 if r["parar"] else 0)
