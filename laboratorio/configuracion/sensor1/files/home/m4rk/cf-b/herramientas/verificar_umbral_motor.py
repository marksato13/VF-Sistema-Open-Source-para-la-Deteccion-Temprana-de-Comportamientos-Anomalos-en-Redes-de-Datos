#!/usr/bin/env python3
"""Verifica en SOMBRA (solo lectura) que el motor en marcha usa el umbral esperado. Sensor1, sin sudo.
Evidencia, de más fuerte a más débil: (1) el registro `motor_startup` posterior a --desde trae `threshold` == umbral y el
`manifest_path` esperado; (2) TODAS las decisiones posteriores traen `threshold` == umbral (el motor lo escribe en cada una);
(3) coherencia: para cada decisión puntuada, decision_if == ALERT  <=>  score < umbral (la regla del motor, `score < threshold`);
(4) hay al menos --min-decisiones. Opcional: --pid comprueba que /proc/<pid>/cmdline lleva --manifest-path esperado.
También informa cuántas decisiones habrían sido ALERT con el umbral anterior (cuánto cambia el IF) y que ninguna restricción
nace del IF (eso lo prueba el publicador, no este script). rc 0 todo bien; 1 alguna comprobación falla; 2 uso/lectura."""
import argparse
import json
import os
import sys

UMBRAL_ANTERIOR = -0.5693969936322356


def leer_registros(ruta, desde, max_bytes=64 << 20):
    with open(ruta, "rb") as fh:
        fh.seek(0, 2)
        fh.seek(max(0, fh.tell() - max_bytes))
        for l in fh.read().splitlines():
            try:
                r = json.loads(l)
            except ValueError:
                continue
            t = r.get("timestamp") or r.get("logged_at") or 0
            if t >= desde:
                yield r


def verificar(registros, umbral, manifiesto, min_decisiones, cmdline=None):
    res, fallos = {}, []
    arranques = [r for r in registros if r.get("event") == "motor_startup"]
    dec = [r for r in registros if r.get("event") == "decision"]
    res["arranques"], res["decisiones"] = len(arranques), len(dec)
    if not arranques:
        fallos.append("no hay registro motor_startup posterior a --desde: el motor no se reinició con la nueva configuración")
    else:
        a = arranques[-1]
        if a.get("threshold") != umbral:
            fallos.append("motor_startup.threshold = %r, esperado %r" % (a.get("threshold"), umbral))
        if manifiesto and a.get("manifest_path") != manifiesto:
            fallos.append("motor_startup.manifest_path = %r, esperado %r" % (a.get("manifest_path"), manifiesto))
        res["startup"] = {"threshold": a.get("threshold"), "manifest_path": a.get("manifest_path")}
    posteriores = [r for r in dec if not arranques or r.get("logged_at", 0) >= arranques[-1].get("timestamp", 0)]
    distintos = [r for r in posteriores if r.get("threshold") != umbral]
    if distintos:
        fallos.append("%d decisiones con threshold distinto (p. ej. %r)" % (len(distintos), distintos[0].get("threshold")))
    puntuadas = [r for r in posteriores if r.get("score") is not None]
    incoherentes = [r for r in puntuadas if (r.get("decision_if") == "ALERT") != (r["score"] < umbral)]
    if incoherentes:
        fallos.append("%d decisiones donde decision_if no sigue 'score < umbral' (p. ej. score %r)" % (len(incoherentes), incoherentes[0]["score"]))
    if len(posteriores) < min_decisiones:
        fallos.append("solo %d decisiones posteriores al arranque (mínimo %d)" % (len(posteriores), min_decisiones))
    res.update(posteriores=len(posteriores), puntuadas=len(puntuadas),
               alertas_con_umbral_nuevo=sum(1 for r in puntuadas if r["score"] < umbral),
               alertas_que_habria_con_el_anterior=sum(1 for r in puntuadas if r["score"] < UMBRAL_ANTERIOR))
    if cmdline is not None:
        if manifiesto and ("--manifest-path " + manifiesto) not in cmdline:
            fallos.append("la línea de comandos del proceso no lleva --manifest-path %s" % manifiesto)
        if "--enforce" in cmdline:
            fallos.append("el motor corre con --enforce (no es sombra)")
        res["cmdline_ok"] = not any("cmdline" in f or "enforce" in f for f in fallos)
    res["fallos"], res["ok"] = fallos, not fallos
    return res


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--log", required=True)
    p.add_argument("--umbral", type=float, required=True)
    p.add_argument("--manifiesto", default="")
    p.add_argument("--desde", type=float, required=True, help="epoch del reinicio del motor")
    p.add_argument("--min-decisiones", type=int, default=20)
    p.add_argument("--pid", type=int, default=0)
    a = p.parse_args(argv)
    try:
        regs = list(leer_registros(a.log, a.desde))
        cmd = None
        if a.pid:
            cmd = open("/proc/%d/cmdline" % a.pid, "rb").read().replace(b"\0", b" ").decode()
    except OSError as e:
        print(json.dumps({"ok": False, "fallos": ["lectura: %s" % e]}))
        return 2
    r = verificar(regs, a.umbral, a.manifiesto, a.min_decisiones, cmd)
    print(json.dumps(r, sort_keys=True, ensure_ascii=False))
    return 0 if r["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
