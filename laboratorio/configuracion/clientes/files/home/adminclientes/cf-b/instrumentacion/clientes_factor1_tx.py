#!/usr/bin/env python3
"""Envoltorio de `clientes_lab.py` SIN modificarlo (mismo patrón que `clientes_factor1.py`, que fija el factor horario en 1,0): registra UNA línea por
acción con hora y resultado, para E4. Reversible: basta parar el proceso; `clientes_lab.py` no se toca.

Registro TSV: t_inicio, t_fin, perfil, origen, accion, metodo, ruta, codigo, resultado, esperado, latencia_ms
  - resultado: `ok` (la acción terminó sin excepción) o `excepcion:<Tipo>` (el mismo criterio con el que el generador cuenta `fallidas`);
  - codigo: código HTTP si lo hubo (`-` en DNS, ping, puerto cerrado);
  - esperado: código(s) que el diseño del perfil prevé para esa acción (api_404 -> 404, api_500 -> 500, api_post -> 201|500, api_auth -> 401), `-` si ninguno.
Uso: clientes_factor1_tx.py --registro FICHERO.tsv [--max-acciones N] [--sin-factor1] <argumentos de clientes_lab.py>"""
import os
import sys
import threading
import time

sys.dont_write_bytecode = True
sys.path.insert(0, os.environ.get("CF_LAB", "/home/adminclientes/laboratorio"))
import clientes_lab  # noqa: E402

ESPERADO = {"api_404": "404", "api_500": "500", "api_post": "201|500", "api_auth": "401"}
_ctx = threading.local()
_lock = threading.Lock()


def _args(argv):
    reg, maxa, f1, resto, i = None, 0, True, [], 0
    while i < len(argv):
        a = argv[i]
        if a == "--registro":
            reg, i = argv[i + 1], i + 2
        elif a == "--max-acciones":
            maxa, i = int(argv[i + 1]), i + 2
        elif a == "--sin-factor1":
            f1, i = False, i + 1
        else:
            resto.append(a)
            i += 1
    if not reg:
        raise SystemExit("hace falta --registro")
    return reg, maxa, f1, resto


def main():
    reg, maxa, f1, resto = _args(sys.argv[1:])
    if f1:
        clientes_lab.factor_horario = lambda ahora, forzar_laborable=False: 1.0
    perfil = origen = "-"
    for i, a in enumerate(resto):
        if a == "--perfil":
            perfil = resto[i + 1]
        if a == "--origen":
            origen = resto[i + 1]
    fh = open(reg, "a", encoding="utf-8", buffering=1)
    if fh.tell() == 0:
        fh.write("# t_inicio\tt_fin\tperfil\torigen\taccion\tmetodo\truta\tcodigo\tresultado\tesperado\tlatencia_ms\n")
    n = [0]

    orig_http, orig_resp = clientes_lab.Cliente._http, clientes_lab.http.client.HTTPConnection.getresponse

    def http(self, ruta, metodo="GET", *a, **k):
        _ctx.metodo, _ctx.ruta = metodo, ruta
        return orig_http(self, ruta, metodo, *a, **k)

    def getresponse(self, *a, **k):
        r = orig_resp(self, *a, **k)
        _ctx.codigo = r.status
        return r
    clientes_lab.Cliente._http = http
    clientes_lab.http.client.HTTPConnection.getresponse = getresponse

    def envolver(nombre):
        orig = getattr(clientes_lab.Cliente, nombre)

        def accion(self, *a, **k):
            _ctx.metodo = _ctx.ruta = _ctx.codigo = "-"
            t0, res = time.time(), "ok"
            try:
                return orig(self, *a, **k)
            except BaseException as ex:                      # el generador cuenta cualquier excepción como acción fallida
                res = "excepcion:" + type(ex).__name__
                raise
            finally:
                t1 = time.time()
                with _lock:
                    fh.write("%.6f\t%.6f\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%.1f\n" % (t0, t1, perfil, origen, nombre, _ctx.metodo, _ctx.ruta, _ctx.codigo, res,
                                                                                     ESPERADO.get(nombre, "-"), (t1 - t0) * 1000))
                    n[0] += 1
                if maxa and n[0] >= maxa:
                    fh.flush()
                    os._exit(0)                              # solo para pruebas (--max-acciones); en la corrida real no se usa
        setattr(clientes_lab.Cliente, nombre, accion)

    acciones = {a for p in clientes_lab.PERFILES.values() for a in p["acciones"]}
    for a in sorted(acciones):
        envolver(a)
    sys.argv = ["clientes_lab.py"] + resto
    raise SystemExit(clientes_lab.main())


if __name__ == "__main__":
    main()
