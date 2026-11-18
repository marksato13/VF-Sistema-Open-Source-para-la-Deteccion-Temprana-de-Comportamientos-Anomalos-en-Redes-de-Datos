#!/usr/bin/env python3
"""Fiabilidad de la regla K4b (evaluar_ecarga.k4b) frente al DISEÑO del generador errático. Banco, sin datos de E-carga.

Modelo del perfil «erratico» de clientes_lab.py (sha256 ae5134a7…, leído el 06-nov), sin modificarlo:
  - entre acciones: exponencial de media ritmo / factor (ritmo 5 s; factor_horario de madrugada 0,12);
  - fuera de ráfaga, cada acción abre una ráfaga con probabilidad 0,02; la ráfaga dura U(20, 90) s y multiplica el
    factor por 6.
  - flujos por acción: el generador no lo fija; en la referencia de desarrollo (04-nov, misma franja) hubo 130–139
    flujos/h frente a ≈ 86 acciones/h esperadas. Se simula con F flujos por acción (1 y 1,5 de media) para cubrir
    ambas lecturas.
Mide, en ventanas de 3 600 s y con la regla congelada:
  - P(al menos una ráfaga real en la ventana);
  - P(rafaga_detectada | hubo ráfaga real) y P(rafaga_detectada | no hubo ninguna) (falsa detección);
  - episodios detectados que no solapan ninguna ráfaga real, por hora.
Semilla fija: el resultado es reproducible.
"""
import importlib.util
import json
import random
import sys
from pathlib import Path

spec = importlib.util.spec_from_file_location("ev", Path(__file__).resolve().parents[1] / "sensor1" / "evaluar_ecarga.py")
ev = importlib.util.module_from_spec(spec)
spec.loader.exec_module(ev)


def ventana(rng, factor=0.12, ritmo=5.0, flujos_accion=1.0, dur=3600.0, calentamiento=900.0):
    t, en_rafaga, fin_r, flujos, rafagas = -calentamiento, False, 0.0, [], []
    while t < dur:
        f = factor
        if en_rafaga and t > fin_r:
            en_rafaga = False
        elif not en_rafaga and rng.random() < 0.02:
            en_rafaga, fin_r = True, t + rng.uniform(20, 90)
            rafagas.append([t, fin_r])
        if en_rafaga:
            f *= 6.0
        if t >= 0:
            n = 1 + (1 if rng.random() < flujos_accion - 1 else 0)
            flujos += [t] * n
        t += rng.expovariate(1.0 / max(ritmo / f, 0.05))
    rafagas = [[max(a, 0), min(b, dur)] for a, b in rafagas if b > 0 and a < dur]
    return flujos, rafagas


def main(n=4000, semilla=20261106):
    out = {}
    for fa in (1.0, 1.5):
        rng = random.Random(semilla)
        con, sin, det_con, det_sin, falsos, flujos_h = 0, 0, 0, 0, 0, 0
        for _ in range(n):
            fl, rf = ventana(rng, flujos_accion=fa)
            r = ev.k4b(fl, 0.0, 3600.0, 0.12, 5.0)
            flujos_h += r["flujos"]
            d = r["estado"] == "rafaga_detectada"
            if rf:
                con += 1
                det_con += d
            else:
                sin += 1
                det_sin += d
            for e in r["episodios"]:
                if not any(e["desde"] < b and a < e["hasta"] for a, b in rf):
                    falsos += 1
        out[f"flujos_por_accion={fa}"] = {
            "ventanas": n, "flujos_por_hora_media": round(flujos_h / n, 1),
            "P(hay_rafaga_real)": round(con / n, 3),
            "P(detectada | hay_rafaga)": round(det_con / con, 3) if con else None,
            "P(detectada | sin_rafaga)": round(det_sin / sin, 3) if sin else None,
            "episodios_falsos_por_hora": round(falsos / n, 3)}
    print(json.dumps({"semilla": semilla, "regla": "evaluar_ecarga " + ev.VERSION, "resultado": out}, indent=1))


if __name__ == "__main__":
    main(*(int(x) for x in sys.argv[1:]))
