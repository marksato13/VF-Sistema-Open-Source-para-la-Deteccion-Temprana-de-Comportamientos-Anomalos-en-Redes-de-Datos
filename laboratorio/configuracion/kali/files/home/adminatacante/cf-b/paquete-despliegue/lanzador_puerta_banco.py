#!/usr/bin/env python3
"""COPIA DE BANCO del lanzador de la puerta D5 del bastión (no instalada, no conectada al orquestador del laboratorio). Equivale al modo `puerta` de `compuerta_b.py`
(que NO se modifica y se importa de `--herramientas`) pero la puerta es la INTEGRADA (`d5_episodio_banco.puerta_fn_banco`): limpieza sin reinicio con acuse, bloqueo persistente y
transporte SSH al Sensor1 (`transporte_bastion`). Cada turno del bucle construye objetos NUEVOS (como la puerta real) y comparte solo ficheros.
Subcomandos:
  ejecutar  --dir D --d5-banco F --sensor DESTINO --clave K --known-hosts H [--puerto P] [--espera-fin S] ...   bucle de la puerta (rc 0)
  reanudar  --dir D --quien Q --motivo M            decisión MANUAL registrada que desbloquea la puerta (la siguiente invocación solo consulta el id pendiente)
  descartar-pendiente --dir D --quien Q --motivo M  decisión MANUAL registrada que descarta el pendiente (permite un id nuevo)
`--espera-fin` por omisión 15 s (valor actual de `compuerta_b`); la propuesta del Hallazgo 2 es 75 s y está pendiente de decisión."""
import argparse
import importlib.util
import os
import sys

sys.dont_write_bytecode = True
AQUI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, AQUI)
import transporte_bastion as tb  # noqa: E402


class NftSintetico:
    """srv-dmz SINTÉTICO (solo banco): sin restricciones en los sets."""

    def __call__(self, peticion):
        op = peticion["operaciones"][0]["op"]
        return {"ok": True, "estado": {"sets": {"bloqueados": {}, "limitados": {}}, "descartes_limite": {}}} if op == "listar" else {"ok": True}


def cargar_banco(ruta):
    spec = importlib.util.spec_from_file_location("d5_episodio_banco", ruta)
    m = importlib.util.module_from_spec(spec)
    sys.modules["d5_episodio_banco"] = m
    spec.loader.exec_module(m)
    return m


def _ssh(a):
    return tb.SshReal(a.sensor, a.clave, timeout=a.timeout_ssh, puerto=a.puerto, known_hosts=a.known_hosts, uid=a.uid_pruebas, home=a.home_pruebas)


def _limpieza(a, ssh):
    return tb.LimpiezaRemota(ssh, os.path.join(a.dir, "estado"), esperar_s=a.esperar_limpieza, sondeo=a.sondeo_consulta, fallos_consulta=a.fallos_consulta)


def ejecutar(a):
    sys.path.insert(0, a.herramientas or AQUI)
    import compuerta_b as cb
    banco = cargar_banco(a.d5_banco)
    traza = os.path.join(a.dir, "agente-traza.jsonl")
    if not os.path.exists(traza):
        open(traza, "a").close()
    srv = None
    if not a.srv_sintetico:
        import orquestar_b as ob
        srv = ob.SshRunners(a.ssh_sensor_legado, a.ssh_srv_legado).srv

    def puerta_fn():
        ssh = _ssh(a)
        lim = _limpieza(a, ssh)
        rn = tb.runners_distribuidos(banco, lim, ssh, NftSintetico() if a.srv_sintetico else None, traza, srv=srv)
        return banco.puerta_fn_banco(a.dir, rn, espera_agente=a.espera_agente, espera_feed=a.espera_feed, sondeo=a.sondeo_puerta)
    cb.bucle(a.dir, puerta_fn, sondeo=a.sondeo_bucle, max_iter=a.max_iter, espera_fin=a.espera_fin)
    return 0


def _puerta_sola(a):
    banco = cargar_banco(a.d5_banco)
    ssh = _ssh(a) if a.sensor else (lambda args: (_ for _ in ()).throw(ConnectionError("sin transporte")))
    lim = tb.LimpiezaRemota(ssh, os.path.join(a.dir, "estado"))
    rn = tb.runners_distribuidos(banco, lim, ssh, NftSintetico(), os.path.join(a.dir, "agente-traza.jsonl"))
    pu = banco.PuertaBanco(rn, registro=os.path.join(a.dir, "puerta-banco.jsonl"), estado_bloqueo=os.path.join(a.dir, "puerta-bloqueo.json"))
    return pu, lim


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="modo", required=True)
    e = sub.add_parser("ejecutar")
    for n, d in (("--dir", None), ("--d5-banco", None), ("--sensor", None), ("--clave", None), ("--known-hosts", None)):
        e.add_argument(n, required=True)
    e.add_argument("--puerto", type=int, default=22)
    e.add_argument("--herramientas", default=None)
    e.add_argument("--espera-fin", type=float, default=15.0)
    e.add_argument("--espera-agente", type=float, default=25.0)
    e.add_argument("--espera-feed", type=float, default=60.0)
    e.add_argument("--sondeo-puerta", type=float, default=2.0)
    e.add_argument("--sondeo-bucle", type=float, default=2.0)
    e.add_argument("--esperar-limpieza", type=float, default=20.0)
    e.add_argument("--sondeo-consulta", type=float, default=0.5)
    e.add_argument("--fallos-consulta", type=int, default=3)
    e.add_argument("--timeout-ssh", type=float, default=15.0)
    e.add_argument("--max-iter", type=int, default=0)
    e.add_argument("--srv-sintetico", action="store_true", help="solo banco: srv-dmz sintético")
    e.add_argument("--ssh-sensor-legado", default="", help="laboratorio: orden ssh del Sensor1 para `orquestar_b.SshRunners`")
    e.add_argument("--ssh-srv-legado", default="", help="laboratorio: orden ssh de srv-dmz para `orquestar_b.SshRunners`")
    e.add_argument("--uid-pruebas", type=int, default=None)
    e.add_argument("--home-pruebas", default=None)
    for nombre in ("reanudar", "descartar-pendiente"):
        s = sub.add_parser(nombre)
        s.add_argument("--dir", required=True)
        s.add_argument("--d5-banco", required=True)
        s.add_argument("--quien", required=True)
        s.add_argument("--motivo", required=True)
        s.add_argument("--sensor", default=None)
    a = p.parse_args(argv)
    if a.modo == "ejecutar":
        return ejecutar(a)
    a.clave = a.known_hosts = a.puerto = a.uid_pruebas = a.home_pruebas = None
    a.timeout_ssh = 5
    pu, lim = _puerta_sola(a)
    try:
        if a.modo == "reanudar":
            pu.reanudar_manual(a.quien, a.motivo)
        else:
            lim.descartar_pendiente(a.quien, a.motivo)
    except ValueError as ex:
        print("rechazado: %s" % ex)
        return 2
    print("registrado: %s" % a.modo)
    return 0


if __name__ == "__main__":
    sys.exit(main())
