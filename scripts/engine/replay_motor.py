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

Reloj (``--reloj``):

- ``reticula`` (por omision, comportamiento del paso 1): los ciclos empiezan en
  una reticula fija de ``--paso`` s y el reloj no avanza durante el ciclo.
- ``coste`` (Etapa 2): el reloj simulado avanza dentro del ciclo con su coste
  REAL de proceso (multiplicado por ``--factor-cpu``), y el siguiente ciclo
  empieza cuando lo decidiria el motor: en modo periodico, ``max(fin + 0,5,
  inicio + paso)``; con ``--disparo eventos``, en el primer sondeo (cada
  ``--sondeo-segundos``) en que hay un PCAP cerrado no leido, o al vencer el
  paso. Asi los tiempos de decision incluyen la cola de proceso. El coste se
  mide en ESTA maquina: no es el del sensor (``--factor-cpu`` lo escala).

``--retraso-cierre`` suma un retraso al cierre de cada fichero (prueba de
ficheros retrasados): el fichero sigue sin leerse hasta que el reloj lo alcanza.

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
import math
import os
import time as tiempo_real
from pathlib import Path


def memoria_mb() -> dict:
    """Memoria del proceso (actual y pico), en MB. Windows: psapi; Linux: /proc y getrusage."""
    try:
        if os.name == "nt":
            import ctypes
            from ctypes import wintypes

            class PMC(ctypes.Structure):
                _fields_ = [("cb", wintypes.DWORD), ("PageFaultCount", wintypes.DWORD),
                            ("PeakWorkingSetSize", ctypes.c_size_t), ("WorkingSetSize", ctypes.c_size_t),
                            ("QuotaPeakPagedPoolUsage", ctypes.c_size_t), ("QuotaPagedPoolUsage", ctypes.c_size_t),
                            ("QuotaPeakNonPagedPoolUsage", ctypes.c_size_t),
                            ("QuotaNonPagedPoolUsage", ctypes.c_size_t),
                            ("PagefileUsage", ctypes.c_size_t), ("PeakPagefileUsage", ctypes.c_size_t)]
            c = PMC(); c.cb = ctypes.sizeof(PMC)
            k32 = ctypes.WinDLL("kernel32", use_last_error=True)
            k32.GetCurrentProcess.restype = wintypes.HANDLE
            psapi = ctypes.WinDLL("psapi", use_last_error=True)
            psapi.GetProcessMemoryInfo.argtypes = [wintypes.HANDLE, ctypes.POINTER(PMC), wintypes.DWORD]
            psapi.GetProcessMemoryInfo(k32.GetCurrentProcess(), ctypes.byref(c), c.cb)
            return {"rss_mb": round(c.WorkingSetSize / 2**20, 1), "pico_mb": round(c.PeakWorkingSetSize / 2**20, 1)}
        import resource
        pico = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024
        with open("/proc/self/statm") as fh:
            rss = int(fh.read().split()[1]) * os.sysconf("SC_PAGE_SIZE") / 2**20
        return {"rss_mb": round(rss, 1), "pico_mb": round(pico, 1)}
    except Exception:  # noqa: BLE001 - la medida nunca para el replay
        return {}


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
        # Hora de cierre de cada fichero: aparece el siguiente (+ retraso de prueba).
        self.cierre = [t + a.retraso_cierre for t in self.t_ficheros[1:]] + [math.inf]
        self.inicio_ciclo = self.ahora

    # --- reloj -------------------------------------------------------------
    def time(self) -> float:
        if self.a.reloj == "coste":
            return self.ahora + (tiempo_real.perf_counter() - self.t_inicio_ciclo) * self.a.factor_cpu
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
        reg.update(memoria_mb())
        self.salida_ciclos.write(json.dumps(reg) + "\n")
        self.salida_ciclos.flush()
        self.etapas.clear()
        self.llamadas.clear()
        self.arranque = False
        self._avanzar(self.ahora + self.a.paso)

    def _avanzar(self, nuevo: float) -> None:
        self.ahora = nuevo
        if self.ahora > self.a.hasta:
            raise _Fin()
        if self.reinicios and self.ahora >= self.reinicios[0]:
            self.reinicios.pop(0)
            raise _Reinicio()
        self.t_inicio_ciclo = tiempo_real.perf_counter()

    # --- espera del motor con reloj de coste ------------------------------
    def esperar_siguiente_ciclo(self, args, inicio_ciclo: float, ya_leidos) -> str:
        fin = self.time()
        dur = tiempo_real.perf_counter() - self.t_inicio_ciclo
        reg = {"t": self.ahora, "hora": dt.datetime.fromtimestamp(self.ahora, dt.timezone.utc).strftime("%H:%M:%S"),
               "dur_s": round(dur, 4), "fin_sim": round(fin, 4), "arranque": self.arranque}
        reg.update(memoria_mb())
        self.salida_ciclos.write(json.dumps(reg) + "\n")
        self.salida_ciclos.flush()
        self.etapas.clear()
        self.llamadas.clear()
        self.arranque = False
        plazo = inicio_ciclo + args.step_seconds
        if args.disparo == "periodico":
            self._avanzar(max(fin + 0.5, plazo))
            return "periodo"
        # Primer cierre de un fichero aun no leido (el motor solo ve cerrados).
        c_min = math.inf
        for i, f in enumerate(self.ficheros):
            if f.name not in ya_leidos and self.cierre[i] < c_min and self.ahora - self.cierre[i] <= args.history_seconds:
                c_min = self.cierre[i]
        objetivo = min(c_min, plazo)
        sondeo = args.sondeo_segundos
        k = max(1, math.ceil((objetivo - fin) / sondeo - 1e-9))
        nuevo = fin + k * sondeo
        motivo = "pcap_cerrado" if c_min <= nuevo and c_min <= plazo else "plazo"
        self._avanzar(nuevo)
        return motivo

    # --- anillo de PCAP ----------------------------------------------------
    def list_closed_pcap_files(self, capture_dir, pattern, max_age_seconds=None, now=None):
        ref = self.ahora if now is None else now
        n = bisect.bisect_right(self.t_ficheros, ref)  # ficheros que ya existen
        cerrados = []
        for i in range(max(0, n - 1)):
            mtime = self.cierre[i]
            if mtime > ref:  # retrasado: aun no cerrado
                continue
            if max_age_seconds is None or ref - mtime <= max_age_seconds:
                cerrados.append(self.ficheros[i])
        return cerrados

    # --- cola de EVE -------------------------------------------------------
    def nueva_cola(self, sim: "Simulacion"):
        class ColaEve:
            HOLGURA_S = 30.0

            def __init__(self, _path, desde=None, parse_ts=None, max_bytes=None) -> None:
                # Como EveTail: empieza al final de lo ya escrito y, con ``desde``,
                # retrocede hasta la primera linea con timestamp >= desde - HOLGURA_S.
                self.i = bisect.bisect_right(sim.escrita, sim.ahora)
                self.recuperacion = {"pedido_desde": desde, "completa": desde is None}
                if desde is not None and self.i > 0:
                    objetivo = desde - self.HOLGURA_S
                    j = bisect.bisect_left(sim.escrita, objetivo, 0, self.i)
                    self.recuperacion.update({"lineas": self.i - j, "completa": j > 0})
                    self.i = j

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
    ap.add_argument("--reloj", choices=("reticula", "coste"), default="reticula")
    ap.add_argument("--factor-cpu", type=float, default=1.0,
                    help="multiplica el coste real de proceso (reloj coste)")
    ap.add_argument("--retraso-cierre", type=float, default=0.0,
                    help="segundos que se retrasa el cierre de cada PCAP (prueba)")
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
    if a.reloj == "coste":
        if not hasattr(m, "esperar_siguiente_ciclo"):
            raise SystemExit("--reloj coste necesita un motor con esperar_siguiente_ciclo (Etapa 2)")
        m.esperar_siguiente_ciclo = sim.esperar_siguiente_ciclo
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
            print(json.dumps({"evento": "arranque_motor", "t": sim.ahora}), file=sys.stderr, flush=True)
            try:
                m.main()
            except _Reinicio:
                print(json.dumps({"evento": "reinicio", "t": sim.ahora}), file=sys.stderr, flush=True)
                continue
            except _Fin:
                break
    finally:
        sim.salida_ciclos.close()
    print(json.dumps({"evento": "fin", "s": round(tiempo_real.perf_counter() - t0, 1), **memoria_mb()}),
          file=sys.stderr, flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
