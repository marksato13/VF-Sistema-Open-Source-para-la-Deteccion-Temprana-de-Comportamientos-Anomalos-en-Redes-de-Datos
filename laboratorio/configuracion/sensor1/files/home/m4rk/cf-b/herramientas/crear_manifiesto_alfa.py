#!/usr/bin/env python3
"""Crea el manifiesto del motor para α = 0,01 SIN tocar el original: copia el manifiesto desplegado y cambia solo
detectors.<det>.calibration.{threshold, alpha}. El motor (motor_decision.load_threshold) lee ese único valor; no hay otro
parámetro de umbral. No modifica `evaluation` (es el registro de la evaluación original) y anota el origen en `_alfa_B`.
Uso: crear_manifiesto_alfa.py <manifiesto_original> <salida> -> imprime sha256 de ambos. rc 0 ok; 1 si el original no es el esperado."""
import hashlib
import json
import sys

DETECTOR = "if_limpio_2026_10"
UMBRAL_ORIGINAL = -0.5693969936322356
ALFA_ORIGINAL = 0.05
UMBRAL_B = -0.6223889502095352
ALFA_B = 0.01


def crear(original_bytes):
    m = json.loads(original_bytes)
    cal = m["detectors"][DETECTOR]["calibration"]
    if float(cal["threshold"]) != UMBRAL_ORIGINAL or float(cal["alpha"]) != ALFA_ORIGINAL:
        raise ValueError("el manifiesto de partida no es el esperado: threshold=%r alpha=%r" % (cal["threshold"], cal["alpha"]))
    if cal.get("comparison") != "score < threshold":
        raise ValueError("regla de comparación inesperada: %r" % cal.get("comparison"))
    cal["threshold"], cal["alpha"] = UMBRAL_B, ALFA_B
    cal["_alfa_B"] = {"umbral_original": UMBRAL_ORIGINAL, "alfa_original": ALFA_ORIGINAL,
                      "origen": "umbral congelado de α=0,01 (UMBRALES_ALFA del publicador, calibración 2026-10-24)",
                      "sha256_manifiesto_original": hashlib.sha256(original_bytes).hexdigest()}
    return json.dumps(m, indent=2, sort_keys=True, ensure_ascii=False).encode("utf-8") + b"\n"


def main(origen, salida):
    ob = open(origen, "rb").read()
    try:
        nb = crear(ob)
    except (ValueError, KeyError) as e:
        print("PARAR:", e)
        return 1
    open(salida, "wb").write(nb)
    print("original %s\nnuevo    %s" % (hashlib.sha256(ob).hexdigest(), hashlib.sha256(nb).hexdigest()))
    return 0


if __name__ == "__main__":
    sys.exit(main(*sys.argv[1:3]))
