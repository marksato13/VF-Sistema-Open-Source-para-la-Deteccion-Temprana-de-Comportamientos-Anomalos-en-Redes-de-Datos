#!/usr/bin/env python3
"""Re-trocea un anillo de PCAP archivado como lo habria escrito ``tcpdump -G N``.

Sirve para el replay de la Etapa 2: con los PCAP de 15 s archivados del 3B se
generan los ficheros que habria producido una rotacion de 5 s, con los MISMOS
paquetes y bytes, para comparar el motor con las dos rotaciones sin volver a
capturar.

Emulacion de ``tcpdump -G`` (tcpdump.c): al procesar cada paquete se toma
``t = time(NULL)`` (segundos enteros); si ``t - Gflag_time >= N`` se cierra el
fichero, ``Gflag_time = t`` y se abre uno nuevo cuyo nombre es ``strftime(t)``.
La rotacion solo ocurre AL PROCESAR un paquete: en un tramo sin trafico el
fichero sigue abierto.

``t`` es la hora de PROCESO, no el sello del paquete: en el anillo del 3B el
primer paquete de cada fichero lleva un sello hasta ~0,9 s anterior al nombre
(el kernel entrega los paquetes por bloques). Aqui ``t = int(sello +
--retraso-proceso)``; el retraso se calibra reproduciendo el anillo de 15 s
archivado (``--verificar`` da la concordancia paquete a paquete). La hora real
de proceso de cada paquete no esta en el PCAP: es un supuesto declarado.

``Gflag_time`` inicial = hora del nombre del primer fichero archivado.
Solo formato pcap clasico (el que escribe tcpdump -w), micro o nanosegundos.
"""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import struct
import sys
from pathlib import Path

MAGIC = {b"\xd4\xc3\xb2\xa1": ("<", 1e-6), b"\xa1\xb2\xc3\xd4": (">", 1e-6),
         b"\x4d\x3c\xb2\xa1": ("<", 1e-9), b"\xa1\xb2\x3c\x4d": (">", 1e-9)}


def t_fichero(nombre: str) -> int:
    sello = nombre.split("-", 1)[1].split(".", 1)[0]
    return int(dt.datetime.strptime(sello, "%Y%m%d%H%M%S").replace(tzinfo=dt.timezone.utc).timestamp())


def nombre_de(t: int) -> str:
    return "live-%s.pcap" % dt.datetime.fromtimestamp(t, dt.timezone.utc).strftime("%Y%m%d%H%M%S")


def leer_paquetes(ruta: Path):
    """(cabecera_global, iterador de (sello_s, registro_crudo)).

    Un fichero de menos de 24 bytes (vacio o sin cabecera) devuelve (None, vacio).
    Un registro truncado al final (fichero aun abierto o cortado) se ignora.
    """
    datos = ruta.read_bytes()
    if len(datos) < 24 or datos[:4] not in MAGIC:
        return None, iter(())
    orden, escala = MAGIC[datos[:4]]
    cab = datos[:24]

    def gen():
        i = 24
        while i + 16 <= len(datos):
            ts_s, ts_f, incl, _orig = struct.unpack(orden + "IIII", datos[i:i + 16])
            if i + 16 + incl > len(datos):
                return
            yield ts_s + ts_f * escala, datos[i:i + 16 + incl]
            i += 16 + incl

    return cab, gen()


def trocear(origen: list[Path], destino: Path, segundos: int, retraso: float = 0.0) -> dict:
    destino.mkdir(parents=True, exist_ok=True)
    g_time = t_fichero(origen[0].name)
    cab_global = None
    fh = None
    resumen = {"ficheros": 0, "paquetes": 0, "bytes_registros": 0}
    try:
        for ruta in origen:
            cab, paquetes = leer_paquetes(ruta)
            if cab is None:
                continue
            if cab_global is None:
                cab_global = cab
            elif cab[:4] != cab_global[:4] or cab[20:24] != cab_global[20:24]:
                raise SystemExit("%s: formato o tipo de enlace distinto" % ruta.name)
            for sello, reg in paquetes:
                t = int(sello + retraso)
                rotar = fh is not None and t - g_time >= segundos
                if fh is None or rotar:
                    if rotar:
                        fh.close()
                        g_time = t
                    fh = (destino / nombre_de(g_time)).open("wb")
                    fh.write(cab_global)
                    resumen["ficheros"] += 1
                fh.write(reg)
                resumen["paquetes"] += 1
                resumen["bytes_registros"] += len(reg)
    finally:
        if fh is not None:
            fh.close()
    return resumen


def asignacion(ficheros: list[Path]) -> tuple[list[str], str]:
    """Nombre del fichero de cada paquete, en orden, y sha256 de todos los registros."""
    nombres: list[str] = []
    h = hashlib.sha256()
    for f in ficheros:
        _, paquetes = leer_paquetes(f)
        for _, reg in paquetes:
            nombres.append(f.name)
            h.update(reg)
    return nombres, h.hexdigest()


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--origen", required=True, type=Path, help="directorio con live-*.pcap archivados")
    ap.add_argument("--destino", required=True, type=Path)
    ap.add_argument("--segundos", type=int, required=True)
    ap.add_argument("--desde", default=None, help="primer fichero a incluir (nombre live-...)")
    ap.add_argument("--hasta", default=None, help="ultimo fichero a incluir (nombre live-...)")
    ap.add_argument("--retraso-proceso", type=float, default=0.0,
                    help="segundos entre el sello del paquete y la hora en que tcpdump lo procesa")
    ap.add_argument("--verificar", action="store_true",
                    help="concordancia paquete a paquete del fichero asignado (con --segundos "
                         "igual al del origen)")
    a = ap.parse_args()
    origen = sorted(a.origen.glob("live-*.pcap"), key=lambda p: p.name)
    if a.desde:
        origen = [p for p in origen if p.name >= a.desde]
    if a.hasta:
        origen = [p for p in origen if p.name <= a.hasta]
    if not origen:
        raise SystemExit("sin ficheros")
    if a.destino.exists() and any(a.destino.glob("live-*.pcap")):
        raise SystemExit("el destino ya tiene ficheros: no se sobrescribe")
    resumen = trocear(origen, a.destino, a.segundos, a.retraso_proceso)
    resumen["retraso_proceso"] = a.retraso_proceso
    nuevos = sorted(a.destino.glob("live-*.pcap"), key=lambda p: p.name)
    asig_n, sha_n = asignacion(nuevos)
    asig_o, sha_o = asignacion(origen)
    # Mismos registros y en el mismo orden: solo cambia en que fichero cae cada uno.
    resumen["registros_identicos"] = sha_n == sha_o and len(asig_n) == len(asig_o)
    resumen["sha256_registros"] = sha_n
    if a.verificar:
        iguales = sum(1 for x, y in zip(asig_o, asig_n) if x == y)
        no_vacios = [p.name for p in origen if p.stat().st_size > 24]
        resumen["verificacion"] = {
            "paquetes": len(asig_o), "misma_asignacion": iguales,
            "concordancia": round(iguales / max(1, len(asig_o)), 6),
            "ficheros_origen": len(no_vacios), "ficheros_nuevos": len(nuevos),
            "nombres_comunes": len(set(no_vacios) & {p.name for p in nuevos})}
    print(json.dumps(resumen, sort_keys=True))
    return 0 if resumen["registros_identicos"] else 1


if __name__ == "__main__":
    sys.exit(main())
