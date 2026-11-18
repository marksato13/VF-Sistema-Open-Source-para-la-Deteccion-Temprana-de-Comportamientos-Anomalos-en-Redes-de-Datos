"""Cierre de la Etapa 3, hallazgo 1: lectura continua de detector_rapido.py --flujo.

En 585da7b el modo flujo combinaba ``select`` sobre el descriptor con ``sys.stdin.buffer``:
los paquetes ya copiados al búfer de Python no hacen «legible» el descriptor, así que una
ráfaga escrita de una vez no se emitía hasta que llegaba otro byte o se cerraba la tubería.

Estas pruebas lanzan el detector como proceso, con la tubería ABIERTA, igual que la unidad
(tcpdump -U -w - | detector_rapido.py --flujo). En POSIX fallan con 585da7b y pasan con la
corrección (en Windows la versión antigua no usaba select, de ahí que allí no reproduzcan).
"""
from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ / "scripts" / "engine"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import detector_rapido as dr  # noqa: E402
import escaneo_temprano as et  # noqa: E402
from test_escaneo_temprano import _pcap, ATK, SRV, CLI, S  # noqa: E402

SCRIPT = RAIZ / "scripts" / "engine" / "detector_rapido.py"
K = et.PARAMETROS_POR_OMISION["K"]
G = et.PARAMETROS_POR_OMISION["g"]
T0 = 1793520000.0
PASO = 0.001
CABECERA = 24


def _registros(paquetes) -> bytes:
    """Los registros de paquete, sin la cabecera global."""
    return _pcap(paquetes)[CABECERA:]


def _rafaga(n=12):
    return [(T0 + i * PASO, ATK, SRV, 40000 + i, 1 + i, S, i) for i in range(n)]


def _t_evidencia_esperado():
    return T0 + (K - 1) * PASO + G


class _Proceso:
    def __init__(self, d: Path, tic=0.05):
        self.sal = d / "s.jsonl"
        self.res = d / "r.jsonl"
        self.p = subprocess.Popen(
            [sys.executable, str(SCRIPT), "--flujo", "--tic", str(tic), "--salida", str(self.sal),
             "--resumen", str(self.res)],
            stdin=subprocess.PIPE, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, cwd=str(RAIZ))

    def escribir(self, b: bytes):
        self.p.stdin.write(b)
        self.p.stdin.flush()
        return time.time()

    def lineas(self):
        if not self.sal.exists():
            return []
        return [json.loads(x) for x in self.sal.read_text(encoding="utf-8").splitlines() if x.strip()]

    def esperar_lineas(self, n=1, plazo=3.0):
        lim = time.time() + plazo
        while time.time() < lim:
            r = self.lineas()
            if len(r) >= n:
                return r
            time.sleep(0.02)
        return self.lineas()

    def cerrar(self, plazo=5.0):
        try:
            self.p.stdin.close()
        except OSError:
            pass
        try:
            return self.p.wait(plazo)
        finally:
            if self.p.poll() is None:
                self.p.kill()
                self.p.wait()


class LecturaContinua(unittest.TestCase):
    def setUp(self):
        self._td = tempfile.TemporaryDirectory()
        self.d = Path(self._td.name)

    def tearDown(self):
        self._td.cleanup()

    def test_rafaga_completa_en_una_escritura_con_tuberia_abierta(self):
        """Cabecera, ráfaga y un paquete posterior (que resuelve g) en UNA escritura."""
        pr = _Proceso(self.d)
        try:
            datos = _pcap(_rafaga() + [(T0 + 0.2, CLI, SRV, 5000, 80, S, 1)])
            t_escrito = pr.escribir(datos)
            r = pr.esperar_lineas(1)
            self.assertEqual(len(r), 1, "la señal debe salir con la tubería todavía abierta")
            self.assertIsNone(pr.p.poll(), "el proceso sigue vivo: no se ha cerrado la entrada")
            self.assertAlmostEqual(r[0]["t_evidencia"], _t_evidencia_esperado(), places=4)
            self.assertGreaterEqual(r[0]["disponible_en"], t_escrito - 0.5)
            self.assertGreaterEqual(r[0]["emitido_en"], r[0]["disponible_en"])
            self.assertLess(r[0]["emitido_en"] - t_escrito, 1.0)
        finally:
            self.assertEqual(pr.cerrar(), 0)

    def test_cabeceras_y_paquetes_partidos_entre_escrituras(self):
        """Trozos de 7 bytes: parte la cabecera global, las de registro y los paquetes."""
        pr = _Proceso(self.d)
        try:
            datos = _pcap(_rafaga() + [(T0 + 0.2, CLI, SRV, 5000, 80, S, 1)])
            for i in range(0, len(datos), 7):
                pr.escribir(datos[i:i + 7])
                time.sleep(0.002)
            r = pr.esperar_lineas(1)
            self.assertEqual(len(r), 1)
            self.assertIsNone(pr.p.poll())
            self.assertAlmostEqual(r[0]["t_evidencia"], _t_evidencia_esperado(), places=4)
            self.assertEqual(r[0]["puertos_fallidos"], K)
        finally:
            self.assertEqual(pr.cerrar(), 0)

    def test_emite_sin_bytes_adicionales_al_poder_resolver_el_vencimiento(self):
        """Sin paquete posterior la evidencia NO se completa (el reloj no se adelanta con el
        de pared); el paquete que permite resolver g basta, sin más bytes ni cierre."""
        pr = _Proceso(self.d)
        try:
            pr.escribir(_pcap(_rafaga()))
            time.sleep(0.6)
            self.assertEqual(pr.lineas(), [], "no se avanza artificialmente el reloj de evidencia")
            t_escrito = pr.escribir(_registros([(T0 + 0.2, CLI, SRV, 5000, 80, S, 1)]))
            r = pr.esperar_lineas(1)
            self.assertEqual(len(r), 1)
            self.assertIsNone(pr.p.poll())
            self.assertAlmostEqual(r[0]["t_evidencia"], _t_evidencia_esperado(), places=4)
            self.assertGreaterEqual(r[0]["disponible_en"], t_escrito - 0.05)
        finally:
            self.assertEqual(pr.cerrar(), 0)

    def test_trafico_escaso_cierre_y_sin_espera_activa(self):
        """Paquetes sueltos cada 0,25 s sin escaneo, cierre de la entrada: sale enseguida,
        sin disparos, y sin consumir CPU mientras espera."""
        pr = _Proceso(self.d)
        try:
            pr.escribir(_pcap([]))
            for i in range(6):
                pr.escribir(_registros([(T0 + i, CLI, SRV, 5000 + i, 80, S, i)]))
                time.sleep(0.25)
            time.sleep(1.0)
            t_cierre = time.time()
            rc = pr.cerrar()
            dur = time.time() - t_cierre
        finally:
            if pr.p.poll() is None:
                pr.cerrar()
        self.assertEqual(rc, 0)
        self.assertLess(dur, 2.0, "el cierre de la entrada termina el proceso")
        self.assertEqual(pr.lineas(), [])
        res = [json.loads(x) for x in pr.res.read_text(encoding="utf-8").splitlines()]
        self.assertTrue(res)
        self.assertEqual(res[-1]["paquetes_tcp"], 6)
        self.assertEqual(res[-1].get("bytes_pendientes", 0), 0)  # campo nuevo; 585da7b no lo tiene
        # ~2,5 s de pared con tic 0,05: una espera activa consumiría ~2,5 s de CPU
        self.assertLess(res[-1]["cpu_s"], 0.5, res[-1])


class AnalizadorIncremental(unittest.TestCase):
    def test_equivale_al_lector_de_fichero_con_cualquier_troceo(self):
        import io
        datos = _pcap(_rafaga(5) + [(T0 + 0.3, CLI, SRV, 1, 2, S, 3)])
        lp = dr.LectorPcap(io.BytesIO(datos))
        ref = []
        while (x := lp.siguiente()) is not None:
            ref.append(x)
        for trozo in (1, 3, 16, 17, 24, 25, 1000):
            an = dr.AnalizadorPcapIncremental()
            out = []
            for i in range(0, len(datos), trozo):
                out += an.alimentar(datos[i:i + trozo])
            self.assertEqual(out, ref, trozo)
            self.assertEqual(an.pendientes, 0)

    def test_registro_incompleto_queda_pendiente(self):
        datos = _pcap([(T0, ATK, SRV, 1, 2, S, 3)])
        an = dr.AnalizadorPcapIncremental()
        self.assertEqual(an.alimentar(datos[:-1]), [])
        self.assertEqual(an.pendientes, len(datos) - CABECERA - 1)
        self.assertEqual(len(an.alimentar(datos[-1:])), 1)

    def test_no_pcap(self):
        with self.assertRaises(ValueError):
            dr.AnalizadorPcapIncremental().alimentar(b"\x00" * 24)


class FiltroDeLaUnidad(unittest.TestCase):
    """Hallazgo 3: la unidad y el banco usan el mismo filtro, que admite tramas 802.1Q."""

    UNIDAD = RAIZ / "deploy" / "enforcement" / "candidato-etapa3" / "ppi-via-rapida@.service"

    def _filtro(self):
        import re
        texto = self.UNIDAD.read_text(encoding="utf-8")
        m = re.search(r'-w - "([^"]+)"', texto)
        self.assertIsNotNone(m, "ExecStart debe llevar el filtro entre comillas dobles")
        return m.group(1)

    def test_unidad_y_banco_mismo_filtro(self):
        sys.path.insert(0, str(RAIZ / "deploy" / "pruebas-aisladas"))
        import importlib
        ev = importlib.import_module("ensayo_via_rapida")
        self.assertEqual(self._filtro(), ev.FILTRO_UNIDAD)
        self.assertEqual(self._filtro(), "tcp or (vlan and tcp)")

    def test_filtro_compila_y_mira_la_etiqueta(self):
        import shutil
        if shutil.which("tcpdump") is None:
            self.skipTest("sin tcpdump (se ejecuta en el banco)")
        r = subprocess.run(["tcpdump", "-d", "-y", "EN10MB", self._filtro()], capture_output=True, text=True)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("0x8100", r.stdout)   # rama para la etiqueta dentro de la trama


if __name__ == "__main__":
    unittest.main()
