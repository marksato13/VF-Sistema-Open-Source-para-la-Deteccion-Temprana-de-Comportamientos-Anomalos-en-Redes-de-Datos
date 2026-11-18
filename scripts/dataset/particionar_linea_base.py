#!/usr/bin/env python3
"""Parte la linea base en entrenamiento, validacion y prueba sin fuga temporal.

**El problema.** Las variables usan hasta 60 s de historia
(``maximum_history_seconds``). Dos ventanas separadas 10 s comparten 50 s de
los mismos paquetes. Si una cae en entrenamiento y otra en validacion, el
umbral se calibra sobre datos que el modelo ya vio: sale optimista, y la cifra
de falsos positivos que se publique estara mal. Es el error que un tribunal
mira primero, y no se ve en ninguna metrica.

**La solucion, y por que no es la obvia.** Partir por filas al azar es lo peor
posible: mezcla ventanas contiguas. Partir en tres tramos contiguos -las
primeras 43 h a entrenar, las siguientes 14 a validar- no tiene fuga, pero
cada conjunto cubre horas distintas del dia: validarias la madrugada con un
modelo entrenado de dia, y la diferencia que midieras seria la curva diaria,
no el modelo.

Se parte en **bloques de horas** y se reparten ciclicamente, asi que los tres
conjuntos cubren el ciclo diario completo. Entre bloques consecutivos se
descarta una **banda de guarda** igual a la historia maxima: las ventanas que
caen ahi son las unicas que podrian compartir paquetes con el bloque vecino.

    python3 particionar_linea_base.py \\
        --entrada artifacts/linea-base/multilayer-v3.csv \\
        --salida  artifacts/linea-base/multilayer-v3-particionado.csv \\
        --informe artifacts/linea-base/particion.json

El reparto es deterministico -sin azar- para que la particion se pueda
reproducir a partir del CSV y de estos parametros, y nada mas.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
from collections import Counter
from datetime import datetime
from pathlib import Path

# 3 de cada 5 bloques a entrenar, 1 a validar, 1 a probar. Ciclico y en este
# orden para que ningun conjunto quede concentrado en una franja del dia.
PATRON = ["train", "train", "validation", "train", "test"]


def marca(valor: str) -> float:
    return datetime.fromisoformat(valor.replace("Z", "+00:00")).timestamp()


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for trozo in iter(lambda: f.read(1 << 20), b""):
            h.update(trozo)
    return h.hexdigest()


def particionar(filas: list[dict], bloque_s: int, guarda_s: int) -> tuple[list[dict], dict]:
    tiempos = [marca(f["window_end_utc"]) for f in filas]
    t0, t1 = min(tiempos), max(tiempos)
    n_bloques = max(1, math.ceil((t1 - t0) / bloque_s))

    reparto = Counter()
    descartadas = 0
    for fila, t in zip(filas, tiempos):
        indice = min(int((t - t0) // bloque_s), n_bloques - 1)
        inicio = t0 + indice * bloque_s
        # La banda de guarda va al PRINCIPIO de cada bloque salvo el primero:
        # esas ventanas son las unicas cuya historia entra en el bloque
        # anterior, que puede pertenecer a otro conjunto.
        if indice > 0 and (t - inicio) < guarda_s:
            fila["particion"] = "descartada_guarda"
            descartadas += 1
        else:
            fila["particion"] = PATRON[indice % len(PATRON)]
        reparto[fila["particion"]] += 1

    informe = {
        "filas": len(filas),
        "bloques": n_bloques,
        "bloque_segundos": bloque_s,
        "guarda_segundos": guarda_s,
        "patron": PATRON,
        "primera_ventana": filas[0]["window_end_utc"],
        "ultima_ventana": filas[-1]["window_end_utc"],
        "horas_cubiertas": round((t1 - t0) / 3600.0, 2),
        "reparto": dict(reparto),
        "descartadas_por_guarda": descartadas,
    }

    # Un conjunto vacio es un fallo silencioso: si el patron no llega a
    # asignarlos todos -pocos bloques- la particion sale coja, y publicar un
    # umbral calibrado sin prueba, o sin validacion, no lo delataria ninguna
    # metrica. Se avisa con el numero de bloques, que es lo que falta.
    vacios = [c for c in ("train", "validation", "test") if not reparto[c]]
    informe["conjuntos_vacios"] = vacios or "ninguno"
    if vacios:
        informe["motivo_probable"] = (
            "%d bloques para un patron de %d posiciones; con --bloque-horas "
            "%.3f saldrian los %d"
            % (n_bloques, len(PATRON), informe["horas_cubiertas"] / len(PATRON),
               len(PATRON))
            if n_bloques < len(PATRON) else "hay bloques de sobra: revisar PATRON")
    return filas, informe


def comprobar(filas: list[dict], guarda_s: int) -> list[str]:
    """Que ninguna ventana de dos conjuntos distintos este a menos de la guarda.

    Es la comprobacion que hace verificable la afirmacion "sin fuga temporal":
    sin ella seria una intencion, no un hecho.
    """
    utiles = [(marca(f["window_end_utc"]), f["particion"], f["entity_ip"])
              for f in filas if f["particion"] != "descartada_guarda"]
    utiles.sort()
    fallos = []
    for (t_a, p_a, ip_a), (t_b, p_b, ip_b) in zip(utiles, utiles[1:]):
        if p_a != p_b and (t_b - t_a) < guarda_s:
            fallos.append("%s (%s) y %s (%s) a %.0f s: menos que la guarda de %d s"
                          % (ip_a, p_a, ip_b, p_b, t_b - t_a, guarda_s))
            if len(fallos) >= 5:
                break
    return fallos


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--entrada", type=Path, required=True)
    p.add_argument("--salida", type=Path, required=True)
    p.add_argument("--informe", type=Path, required=True)
    p.add_argument("--bloque-horas", type=float, default=2.0,
                   help="duracion de cada bloque antes de rotar de conjunto")
    p.add_argument("--guarda-segundos", type=int, default=60,
                   help="igual a maximum_history_seconds del esquema")
    p.add_argument("--solo-elegibles", action="store_true",
                   help="descartar las ventanas con eligible_training=False, que "
                        "no tienen los 60 s de historia completos")
    args = p.parse_args()

    with args.entrada.open(newline="", encoding="utf-8") as f:
        lector = csv.DictReader(f)
        columnas = list(lector.fieldnames or [])
        filas = list(lector)

    if not filas:
        print(json.dumps({"error": "el CSV no tiene filas"}))
        return 1

    filas.sort(key=lambda f: (f["window_end_utc"], f["entity_ip"]))

    descartadas_no_elegibles = 0
    if args.solo_elegibles:
        antes = len(filas)
        filas = [f for f in filas if str(f.get("eligible_training", "")).lower() == "true"]
        descartadas_no_elegibles = antes - len(filas)
        if not filas:
            print(json.dumps({"error": "ninguna fila es elegible para entrenamiento"}))
            return 1

    bloque_s = int(args.bloque_horas * 3600)
    filas, informe = particionar(filas, bloque_s, args.guarda_segundos)
    informe["descartadas_no_elegibles"] = descartadas_no_elegibles
    informe["entrada_sha256"] = sha256(args.entrada)

    fallos = comprobar(filas, args.guarda_segundos)
    informe["fuga_temporal"] = fallos or "ninguna"
    vacios = [] if informe["conjuntos_vacios"] == "ninguno" else informe["conjuntos_vacios"]

    args.salida.parent.mkdir(parents=True, exist_ok=True)
    with args.salida.open("w", newline="", encoding="utf-8") as f:
        escritor = csv.DictWriter(f, fieldnames=columnas + ["particion"])
        escritor.writeheader()
        escritor.writerows(filas)

    informe["salida_sha256"] = sha256(args.salida)
    args.informe.write_text(json.dumps(informe, indent=2, sort_keys=True) + "\n",
                            encoding="utf-8")
    print(json.dumps(informe, indent=2, sort_keys=True))

    if fallos:
        print("FUGA TEMPORAL DETECTADA: la particion no es utilizable.")
        return 1
    if vacios:
        print("CONJUNTOS VACIOS (%s): la particion no es utilizable."
              % ", ".join(vacios))
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
