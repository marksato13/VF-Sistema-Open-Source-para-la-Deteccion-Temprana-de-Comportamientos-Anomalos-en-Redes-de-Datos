#!/usr/bin/env python3
"""Registro de α para la Campaña B (se ejecuta en el Sensor1 en el preflight; solo lectura de lo desplegado).

α = 0,01 es el valor del EXPERIMENTO: se aplica al análisis de las señales del IF, no al motor. Este registro deja por escrito, con
hashes, (1) el umbral congelado de α = 0,01 tal como está en el publicador desplegado, (2) el umbral que el motor desplegado usa
de verdad (manifiesto del modelo, α = 0,05) y (3) que son distintos a propósito. rc 0 si todo coincide con lo esperado; 1 si no.
Uso: registrar_alfa.py --publicador publicar_feed_v2.py --manifiesto manifest-if-*.json --modelo X.joblib --salida alfa-b.json
"""
import argparse
import hashlib
import json
import re
import sys
import time

ALFA_EXPERIMENTO = "0.01"
UMBRAL_ALFA_EXPERIMENTO = -0.6223889502095352
UMBRAL_MOTOR_ESPERADO = -0.5693969936322356


def sha(p):
    return hashlib.sha256(open(p, "rb").read()).hexdigest()


def umbrales_del_publicador(texto):
    m = re.search(r"UMBRALES_ALFA\s*=\s*\{(.*?)\}", texto, re.S)
    if not m:
        raise ValueError("no se encontró UMBRALES_ALFA")
    return {k: float(v) for k, v in re.findall(r'"([0-9.]+)"\s*:\s*(-?[0-9.]+)', m.group(1))}


def registrar(publicador, manifiesto, modelo, ahora=time.time, detector="if_limpio_2026_10", motor_alfa="0.05"):
    u = umbrales_del_publicador(open(publicador, encoding="utf-8").read())
    man = json.load(open(manifiesto, encoding="utf-8"))
    cal = man["detectors"][detector]["calibration"]          # lo que el motor usa: --detector-name if_limpio_2026_10
    motor = float(cal["threshold"])
    errores = []
    # `evaluation.threshold_used` es el registro de la evaluación ORIGINAL (α=0,05): no se reescribe y no se compara.
    if u.get(ALFA_EXPERIMENTO) != UMBRAL_ALFA_EXPERIMENTO:
        errores.append("el publicador no trae α=0,01 con el umbral congelado: %r" % u.get(ALFA_EXPERIMENTO))
    esperado = UMBRAL_ALFA_EXPERIMENTO if motor_alfa == "0.01" else UMBRAL_MOTOR_ESPERADO
    if motor != esperado:
        errores.append("el umbral del motor desplegado cambió: %r (esperado %r para α=%s)" % (motor, esperado, motor_alfa))
    return {"registrado_en": ahora(), "alfa_experimento": float(ALFA_EXPERIMENTO), "umbral_alfa_experimento": u.get(ALFA_EXPERIMENTO),
            "umbrales_publicador": u, "motor": {"detector": detector, "alpha": cal.get("alpha"), "umbral": motor, "distinto_a_proposito": motor != u.get(ALFA_EXPERIMENTO)},
            "aplicacion": "señales del IF (senales-if.jsonl: score y alfa_superados) y su análisis; el IF no restringe con la política if_senal",
            "sha256": {"publicador": sha(publicador), "manifiesto": sha(manifiesto), "modelo": sha(modelo)},
            "errores": errores, "ok": not errores}


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    for a in ("publicador", "manifiesto", "modelo", "salida"):
        p.add_argument("--" + a, required=True)
    p.add_argument("--motor-alfa", choices=("0.05", "0.01"), default="0.01", help="α que el motor DEBE usar durante B (0.01 con el manifiesto nuevo)")
    a = p.parse_args(argv)
    r = registrar(a.publicador, a.manifiesto, a.modelo, motor_alfa=a.motor_alfa)
    json.dump(r, open(a.salida, "w", encoding="utf-8"), indent=1, sort_keys=True)
    print(json.dumps({"ok": r["ok"], "errores": r["errores"]}))
    return 0 if r["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
