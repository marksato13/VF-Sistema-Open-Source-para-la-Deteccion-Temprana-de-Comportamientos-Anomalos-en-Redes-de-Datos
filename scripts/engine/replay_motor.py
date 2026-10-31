#!/usr/bin/env python3
"""Arnes de replay: ejecuta el main() REAL de un motor_decision.py con reloj simulado.

Sirve para comparar dos versiones del motor (la desplegada y una candidata) con
exactamente las mismas entradas, ciclo a ciclo, sin tocar su codigo:

- Reloj: ``time.time()`` del modulo del motor devuelve el instante simulado del
  ciclo; ``time.sleep()`` cierra el ciclo, mide su duracion real y avanza el
  reloj al siguiente punto de una reticula fija de ``--paso`` segundos. La
  reticula es la misma para las dos versiones, asi que las dos ven los mismos
  datos en cada ciclo aunque una tarde mas que la otra.
- PCAP: ``list_closed_pcap_files`` se sustituye por una emulacion del anillo
  de tcpdump sobre el archivo congelado: un fichero existe desde la hora de su
  nombre y esta cerrado cuando ya existe el siguiente; su mtime es la hora del
  siguiente. Se aplica el mismo filtro de antiguedad que el motor.
- EVE: ``EveTail`` se sustituye por una lectura del eve.json congelado en el
  orden del fichero. Una linea se considera escrita cuando el reloj alcanza el
  maximo de los timestamps de las lineas anteriores y la propia (el fichero se
  escribe en orden de tiempo salvo eventos de flujo, que llevan la hora de
  inicio del flujo). Igual que EveTail, al arrancar empieza al final de lo ya
  escrito.

Con ``--reiniciar-en`` el arnes corta el proceso simulado en ese instante y
vuelve a llamar a main() con el mismo registro, como un reinicio del servicio.

Con ``--perfilar`` envuelve las funciones del extractor y del motor que hacen
el trabajo pesado y acumula su tiempo por ciclo. El resto del ciclo (lectura
JSON de la cola de EVE, poda, registro) queda como ``resto_s``.

Salida: el registro del propio motor en ``--salida``/motor_decision.log y una
linea por ciclo en ``--salida``/ciclos-arnes.jsonl.
"""

from __future__ import annotations

import argparse
import bisect
import collections
import datetime as dt
import functools
import importlib.util
import json
import sys
import time as tiempo_real
from pathlib import Path


class _Fin(Exception):
    pass


class _Reinicio(Exception):
    pass


def epoch(valor: str) -> float:
    try:
        return float(valor)
    except ValueError:
        return dt.datetime.fromisoformat(valor.replace("Z", "+00:00")).timestamp()


def t_fichero(nombre: str) -> float:
    # live-YYYYmmddHHMMSS.pcap, en UTC (hora del sensor)
    sello = nombre.split("-", 1)[1].split(".", 1)[0]
    return dt.datetime.strptime(sello, "%Y%m%d%H%M%S").replace(tzinfo=dt.timezone.utc).timestamp()


def indexar_eve(ruta: Path, parse_ts) -> tuple[list[int], list[float]]:
    """Desplazamiento de cada linea y hora (maximo acumulado de timestamps) en que se considera escrita."""
    desplazamientos: list[int] = []
    escrita: list[float] = []
    maximo = float("-inf")
    pos = 0
    with ruta.open("rb") as fh:
        for linea in fh:
            # Suricata escribe "timestamp":"..." sin espacios; json.dumps pone uno tras los dos puntos.
            i = linea.find(b'"timestamp"')
            if i >= 0:
                a = linea.find(b'"', i + 11)
                b = linea.find(b'"', a + 1)
                try:
                    maximo = max(maximo, parse_ts(linea[a + 1:b].decode("ascii")))
                except (ValueError, UnicodeDecodeError):
                    pass
            desplazamientos.append(pos)
            escrita.append(maximo)
            pos += len(linea)
    desplazamientos.append(pos)
    return desplazamientos, escrita


class Simulacion:
    def __init__(self, a: argparse.Namespace) -> None:
        self.a = a
        self.ficheros = sorted(a.pcap_dir.glob("live-*.pcap"), key=lambda p: p.name)
        self.t_ficheros = [t_fichero(f.name) for f in self.ficheros]
        self.ahora = a.desde
        self.reinicios = sorted(a.reiniciar_en)
        self.salida_ciclos = (a.salida / "ciclos-arnes.jsonl").open("a", encoding="utf-8")
        self.etapas: collections.Counter = collections.Counter()
        self.llamadas: collections.Counter = collections.Counter()
        self.t_inicio_ciclo = tiempo_real.perf_counter()
        self.arranque = True
        self.desp: list[int] = []
        self.escrita: list[float] = []

    # --- reloj -------------------------------------------------------------
    def time(self) -> float:
        return self.ahora

    def perf_counter(self) -> float:
        return tiempo_real.perf_counter()

    def monotonic(self) -> float:
        return tiempo_real.monotonic()

    def sleep(self, _segundos: float) -> None:
        dur = tiempo_real.perf_counter() - self.t_inicio_ciclo
        etapas = {k: round(v, 4) for k, v in self.etapas.items()}
        reg = {"t": self.ahora, "hora": dt.datetime.fromtimestamp(self.ahora, dt.timezone.utc).strftime("%H:%M:%S"),
               "dur_s": round(dur, 4), "arranque": self.arranque}
        if self.a.perfilar:
            reg["etapas"] = etapas
            reg["llamadas"] = dict(self.llamadas)
            reg["resto_s"] = round(dur - sum(self.etapas.values()), 4)
        self.salida_ciclos.write(json.dumps(reg) + "\n")
        self.salida_ciclos.flush()
        self.etapas.clear()
        self.llamadas.clear()
        self.arranque = False
        self.ahora += self.a.paso
        if self.ahora > self.a.hasta:
            raise _Fin()
        if self.reinicios and self.ahora >= self.reinicios[0]:
            self.reinicios.pop(0)
            raise _Reinicio()
        self.t_inicio_ciclo = tiempo_real.perf_counter()

    # --- anillo de PCAP ----------------------------------------------------
    def list_closed_pcap_files(self, capture_dir, pattern, max_age_seconds=None, now=None):
        ref = self.ahora if now is None else now
        n = bisect.bisect_right(self.t_ficheros, ref)  # ficheros que ya existen
        cerrados = []
        for i in range(max(0, n - 1)):
            mtime = self.t_ficheros[i + 1]
            if max_age_seconds is None or ref - mtime <= max_age_seconds:
                cerrados.append(self.ficheros[i])
        return cerrados

    # --- cola de EVE -------------------------------------------------------
    def nueva_cola(self, sim: "Simulacion"):
        class ColaEve:
            def __init__(self, _path) -> None:
                # Como EveTail: empieza al final de lo ya escrito.
                self.i = bisect.bisect_right(sim.escrita, sim.ahora)

            def poll(self) -> list[str]:
                t0 = tiempo_real.perf_counter()
                j = bisect.bisect_right(sim.escrita, sim.ahora)
                if j <= self.i:
                    return []
                with sim.a.eve.open("rb") as fh:
                    fh.seek(sim.desp[self.i])
                    datos = fh.read(sim.desp[j] - sim.desp[self.i])
                self.i = j
                lineas = [raw.decode("utf-8", errors="replace") for raw in datos.split(b"\n") if raw.strip()]
                sim.etapas["cola_eve_lectura_s"] += tiempo_real.perf_counter() - t0
                return lineas

        return ColaEve

    # --- perfil ------------------------------------------------------------
    def cronometrar(self, nombre: str, funcion):
        @functools.wraps(funcion)
        def envoltura(*args, **kwargs):
            t0 = tiempo_real.perf_counter()
            try:
                return funcion(*args, **kwargs)
            finally:
                self.etapas[nombre + "_s"] += tiempo_real.perf_counter() - t0
                self.llamadas[nombre] += 1

        return envoltura


def cargar_motor(ruta: Path):
    # Como al ejecutarlo como script: su carpeta va primero en sys.path (heuristicos.py vive ahi).
    sys.path.insert(0, str(ruta.parent))
    spec = importlib.util.spec_from_file_location("motor_bajo_replay", ruta)
    modulo = importlib.util.module_from_spec(spec)
    sys.modules["motor_bajo_replay"] = modulo
    spec.loader.exec_module(modulo)
    return modulo


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--motor", required=True, type=Path, help="motor_decision.py a ejecutar (su repo aporta el extractor)")
    ap.add_argument("--pcap-dir", required=True, type=Path)
    ap.add_argument("--eve", required=True, type=Path)
    ap.add_argument("--desde", required=True, type=epoch, help="primer ciclo (epoch o ISO UTC)")
    ap.add_argument("--hasta", required=True, type=epoch, help="ultimo ciclo (epoch o ISO UTC)")
    ap.add_argument("--paso", type=float, default=10.0)
    ap.add_argument("--reiniciar-en", type=epoch, action="append", default=[])
    ap.add_argument("--perfilar", action="store_true")
    ap.add_argument("--salida", required=True, type=Path)
    a, args_motor = ap.parse_known_args()
    if args_motor and args_motor[0] == "--":
        args_motor = args_motor[1:]
    a.salida.mkdir(parents=True, exist_ok=True)

    m = cargar_motor(a.motor.resolve())
    sim = Simulacion(a)
    t0 = tiempo_real.perf_counter()
    sim.desp, sim.escrita = indexar_eve(a.eve, m.extractor.parse_eve_timestamp)
    print(json.dumps({"evento": "eve_indexado", "lineas": len(sim.escrita),
                      "s": round(tiempo_real.perf_counter() - t0, 1)}), file=sys.stderr, flush=True)

    m.time = sim
    m.EveTail = sim.nueva_cola(sim)
    m.list_closed_pcap_files = sim.list_closed_pcap_files
    if a.perfilar:
        ex, v3 = m.extractor, m.v3
        ex.attribute_packets = sim.cronometrar("atribucion", ex.attribute_packets)
        ex.load_app_observations = sim.cronometrar("eve_observaciones", ex.load_app_observations)
        ex.build_rows = sim.cronometrar("filas", ex.build_rows)
        v3.deduplicar_espejo = sim.cronometrar("deduplicacion", v3.deduplicar_espejo)
        m.parse_pcap_to_packets = sim.cronometrar("pcap_parseo", m.parse_pcap_to_packets)
        m.heuristicos.evaluar = sim.cronometrar("heuristicos", m.heuristicos.evaluar)
        carga_original = m.joblib.load

        def cargar_y_cronometrar(*x, **k):
            pipeline = carga_original(*x, **k)

            class Puntuador:
                def __getattr__(self, nombre):
                    return getattr(pipeline, nombre)

            p = Puntuador()
            p.score_samples = sim.cronometrar("puntuacion", pipeline.score_samples)
            return p

        m.joblib.load = cargar_y_cronometrar

    sys.argv = ["motor_decision.py", *args_motor,
                "--log-path", str(a.salida / "motor_decision.log"),
                "--state-dir", str(a.salida / "_state"),
                "--capture-dir", str(a.pcap_dir),
                "--eve-path", str(a.eve)]
    try:
        while True:
            sim.arranque = True
            sim.t_inicio_ciclo = tiempo_real.perf_counter()
            try:
                m.main()
            except _Reinicio:
                print(json.dumps({"evento": "reinicio", "t": sim.ahora}), file=sys.stderr, flush=True)
                continue
            except _Fin:
                break
    finally:
        sim.salida_ciclos.close()
    print(json.dumps({"evento": "fin", "s": round(tiempo_real.perf_counter() - t0, 1)}), file=sys.stderr, flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
