#!/usr/bin/env python3
"""PROPUESTA DE BANCO (#3): lector de la auditoría D5 que sobrevive a la rotación. Solo lectura, solo biblioteca estándar.

Contrato:
 - ESCRIBE un solo actor: el publicador derivado (hacer_publicador_d5.py, sin cambios), agregando líneas JSONL abriendo el fichero por
   nombre en cada escritura; por eso la rotación por renombrado (sin copytruncate) no necesita señal ni reinicio.
 - LEE el cliente/adaptador, en solo lectura. Nunca escribe, rota ni borra la auditoría.
 - La unión de generaciones es la traza: `ruta` (actual), `ruta.1`, `ruta.2`, ... y las comprimidas `ruta.N.gz`. Las líneas se unen por `id`
   (y la secuencia viaja en la línea `publicado`), no por el fichero en el que cayeron.
 - Lectura estable: se compara la correspondencia nombre -> (dev, inodo) antes y después de leer; si cambió (rotación o desplazamiento
   .N -> .N+1 en medio) se repite. Comparar solo inodos no basta: un desplazamiento sin fichero nuevo los deja iguales.
 - Una línea ilegible (truncada) se CUENTA y se reporta; un directorio o un fichero ilegible se reporta como problema. Nada se oculta."""
import gzip
import hashlib
import json
import os
import re
import time


def generaciones(ruta):
    d, base = os.path.split(os.fspath(ruta))
    d = d or "."
    pat = re.compile("^" + re.escape(base) + r"(?:\.(\d+))?(?:\.gz)?$")
    out = []
    try:
        nombres = os.listdir(d)
    except OSError:
        return []
    for n in nombres:
        m = pat.match(n)
        if m:
            out.append((0 if m.group(1) is None else int(m.group(1)), n))
    return [os.path.join(d, n) for _, n in sorted(out)]            # actual primero; luego .1, .2, ... (de más nueva a más vieja)


def _huella(rutas):
    h = []
    for p in rutas:
        try:
            s = os.stat(p)
            h.append((p, s.st_dev, s.st_ino))                      # nombre -> inodo: un desplazamiento .N -> .N+1 también cambia la huella
        except OSError:
            h.append((p, None, None))
    return frozenset(h)


def _leer_una(p):
    g = {"ruta": p, "bytes": 0, "sha256": None, "lineas": 0, "ilegibles": 0, "error": None, "leida": True}
    lin = []
    if os.path.isdir(p):
        g["error"] = "es un directorio"
        return g, lin
    try:
        crudo = open(p, "rb").read()
    except OSError as ex:
        g["leida"] = False
        g["error"] = ex.__class__.__name__
        return g, lin
    g["bytes"], g["sha256"] = len(crudo), hashlib.sha256(crudo).hexdigest()
    if p.endswith(".gz"):
        try:
            crudo = gzip.decompress(crudo)
        except (OSError, EOFError) as ex:
            g["error"] = "gz ilegible: " + ex.__class__.__name__
            return g, lin
    for l in crudo.decode("utf-8", "replace").splitlines():
        if not l.strip():
            continue
        try:
            x = json.loads(l)
            if not isinstance(x, dict):
                raise ValueError
            x["_gen"] = os.path.basename(p)
            lin.append(x)
            g["lineas"] += 1
        except ValueError:
            g["ilegibles"] += 1
    return g, lin


def leer(ruta, intentos=5, entre_lecturas=None, dormir=time.sleep):
    """Devuelve {lineas, generaciones, ilegibles, problemas, estable, intentos}. `entre_lecturas(i)` es solo un asiento de prueba."""
    gens, lineas = [], []
    for i in range(intentos):
        rutas = generaciones(ruta)
        antes = _huella(rutas)
        gens, lineas = [], []
        for p in rutas:
            g, l = _leer_una(p)
            gens.append(g)
            lineas += l
        if entre_lecturas:
            entre_lecturas(i)
        if _huella(generaciones(ruta)) == antes and all(g["leida"] for g in gens):
            break
        dormir(0.01)
    else:
        return _res(gens, lineas, False, intentos)
    return _res(gens, lineas, True, i + 1)


def _res(gens, lineas, estable, intentos):
    vistos, unicas = set(), []
    for x in lineas:                                              # mismas líneas en dos ficheros (copia) no cuentan dos veces
        k = json.dumps({a: b for a, b in x.items() if a != "_gen"}, sort_keys=True)
        if k not in vistos:
            vistos.add(k)
            unicas.append(x)
    return {"lineas": unicas, "generaciones": gens, "ilegibles": sum(g["ilegibles"] for g in gens),
            "problemas": [g["ruta"] + ": " + g["error"] for g in gens if g["error"]], "estable": estable, "intentos": intentos}
