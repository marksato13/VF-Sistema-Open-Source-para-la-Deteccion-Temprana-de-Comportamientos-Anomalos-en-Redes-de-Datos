"""Etapa 3: vía rápida de escaneo (escaneo_temprano / detector_rapido)."""
from __future__ import annotations

import io
import json
import struct
import sys
import tempfile
import unittest
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ / "scripts" / "engine"))

import escaneo_temprano as et  # noqa: E402
import detector_rapido as dr  # noqa: E402

S, SA, R, RA, A = 0x02, 0x12, 0x04, 0x14, 0x10
ATK, SRV, CLI = "10.10.20.30", "10.10.30.10", "10.10.20.21"


def det(**kw):
    return et.DetectorEscaneoTemprano("10.10.0.0/16", frozenset({"10.10.60.11"}), **kw)


def escaneo(d, t0, puertos, paso=0.0005, src=ATK, dst=SRV, sport0=40000):
    out = []
    for i, p in enumerate(puertos):
        out += d.observar(t0 + i * paso, src, dst, sport0 + i, p, S, 1000 + i, 60)
    return out


class Regla(unittest.TestCase):
    def test_dispara_tras_g_sin_respuesta_con_K_puertos(self):
        d = det(K=10, W=2.0, g=0.1)
        self.assertEqual(escaneo(d, 100.0, range(1, 11)), [])
        self.assertEqual(d.avanzar(100.09), [])            # aún no han pasado g s
        r = d.avanzar(100.2)
        self.assertEqual(len(r), 1)
        self.assertEqual(r[0]["origen"], ATK)
        self.assertEqual(r[0]["destino"], SRV)
        self.assertEqual(r[0]["puertos_fallidos"], 10)
        # el instante de la evidencia es el vencimiento exacto del décimo intento
        self.assertAlmostEqual(r[0]["t_evidencia"], 100.0 + 9 * 0.0005 + 0.1, places=5)

    def test_no_dispara_con_K_menos_uno(self):
        d = det(K=10, W=2.0, g=0.1)
        escaneo(d, 100.0, range(1, 10))
        self.assertEqual(d.avanzar(110.0), [])

    def test_rst_cuenta_en_el_momento_sin_esperar_g(self):
        d = det(K=5, W=2.0, g=1.0)
        escaneo(d, 100.0, range(1, 6))
        r = []
        for i, p in enumerate(range(1, 6)):
            r += d.observar(100.01 + i * 0.001, SRV, ATK, p, 40000 + i, RA, 0, 40)
        self.assertEqual(len(r), 1)
        self.assertLess(r[0]["t_evidencia"], 100.02)

    def test_conexiones_completadas_no_cuentan(self):
        d = det(K=5, W=2.0, g=0.1)
        for i, p in enumerate((22, 80, 443, 445, 3389, 8080)):
            d.observar(100.0 + i * 0.001, CLI, SRV, 50000 + i, p, S, 7 + i, 60)
            d.observar(100.0003 + i * 0.001, SRV, CLI, p, 50000 + i, SA, 9, 60)
        self.assertEqual(d.avanzar(105.0), [])

    def test_syn_ack_tardio_retira_el_intento(self):
        d = det(K=3, W=5.0, g=0.1)
        escaneo(d, 100.0, (1, 2))
        d.avanzar(100.2)                                   # 2 fallidos
        d.observar(100.25, SRV, ATK, 1, 40000, SA, 5, 60)  # el puerto 1 contesta tarde
        escaneo(d, 100.3, (3,), sport0=40010)
        self.assertEqual(d.avanzar(100.5), [])             # quedan 2 (2 y 3), no 3

    def test_muchas_conexiones_al_mismo_puerto_no_suman(self):
        """Inundación HTTP o fuerza bruta: miles de SYN a 80 sin respuesta = 1 puerto."""
        d = det(K=10, W=2.0, g=0.1)
        for i in range(3000):
            d.observar(100.0 + i * 0.0005, ATK, SRV, 20000 + i, 80, S, i, 60)
        self.assertEqual(d.avanzar(110.0), [])

    def test_copias_span_y_retransmisiones(self):
        d = det(K=10, W=2.0, g=0.1)
        for i, p in enumerate(range(1, 10)):
            for copia in (0.0, 0.0002):                     # copia del espejo
                d.observar(100.0 + i * 0.001 + copia, ATK, SRV, 40000 + i, p, S, 1, 60)
            d.observar(101.0 + i * 0.001, ATK, SRV, 40000 + i, p, S, 1, 60)  # retransmisión
        self.assertEqual(d.copias_span, 9)
        self.assertEqual(d.retransmisiones, 9)
        self.assertEqual(d.avanzar(110.0), [])             # 9 puertos distintos < 10

    def test_puertos_fuera_de_la_ventana_W_no_cuentan(self):
        d = det(K=10, W=2.0, g=0.1)
        for i, p in enumerate(range(1, 11)):
            d.observar(100.0 + i * 0.5, ATK, SRV, 40000 + i, p, S, 1, 60)
        self.assertEqual(d.avanzar(120.0), [])             # nunca 10 en 2 s

    def test_por_par_origen_destino(self):
        d = det(K=10, W=2.0, g=0.1)
        escaneo(d, 100.0, range(1, 6), dst=SRV)
        escaneo(d, 100.0, range(6, 11), dst="10.10.10.20", sport0=41000)
        self.assertEqual(d.avanzar(105.0), [])

    def test_origen_excluido_o_fuera_de_red(self):
        d = det(K=3, W=2.0, g=0.1)
        escaneo(d, 100.0, range(1, 6), src="10.10.60.11")
        escaneo(d, 100.0, range(1, 6), src="8.8.8.8", sport0=42000)
        self.assertEqual(d.avanzar(105.0), [])

    def test_refractario_y_nuevo_disparo(self):
        d = det(K=3, W=2.0, g=0.1, refractario_s=60.0)
        escaneo(d, 100.0, (1, 2, 3))
        self.assertEqual(len(d.avanzar(100.5)), 1)
        escaneo(d, 110.0, (4, 5, 6), sport0=41000)
        self.assertEqual(d.avanzar(110.5), [])             # mismo episodio
        escaneo(d, 200.0, (7, 8, 9), sport0=42000)
        self.assertEqual(len(d.avanzar(200.5)), 1)         # pasado el refractario

    def test_causalidad_no_usa_paquetes_futuros(self):
        """Evaluado en t, un SYN-ACK posterior a t no evita el conteo de t (y se registra así)."""
        d = det(K=2, W=2.0, g=0.1)
        escaneo(d, 100.0, (1, 2))
        r = d.avanzar(100.15)
        self.assertEqual(len(r), 1)
        self.assertLessEqual(r[0]["t_evidencia"], 100.15)

    def test_identificador_estable_y_evidencia(self):
        a, b = det(K=3), det(K=3)
        for x in (a, b):
            escaneo(x, 100.0, (5, 6, 7))
        ra, rb = a.avanzar(101.0), b.avanzar(101.0)
        self.assertEqual(ra[0]["id"], rb[0]["id"])
        self.assertEqual(ra[0]["muestra_puertos"], [5, 6, 7])
        self.assertEqual(ra[0]["regla"], "port_scan_temprano")
        self.assertIn("version", ra[0])

    def test_poda_no_rompe(self):
        d = det(K=3, W=2.0, g=0.1)
        escaneo(d, 100.0, (1, 2))
        d.podar(400.0)
        self.assertEqual(d.avanzar(401.0), [])
        d.observar(401.1, SRV, ATK, 1, 40000, SA, 1, 60)   # respuesta a intento podado


def _pcap(paquetes) -> bytes:
    out = struct.pack("<IHHiIII", 0xA1B2C3D4, 2, 4, 0, 0, 65535, 1)
    for t, src, dst, sp, dp, fl, seq in paquetes:
        ip = struct.pack("!BBHHHBBH4s4s", 0x45, 0, 40, 0, 0, 64, 6, 0,
                         bytes(map(int, src.split("."))), bytes(map(int, dst.split("."))))
        tcp = struct.pack("!HHIIBBHHH", sp, dp, seq, 0, 0x50, fl, 1024, 0, 0)
        fr = b"\x00" * 12 + b"\x08\x00" + ip + tcp
        s, us = int(t), int(round((t - int(t)) * 1e6))
        out += struct.pack("<IIII", s, us, len(fr), len(fr)) + fr
    return out


class Proceso(unittest.TestCase):
    def test_modo_ficheros_avanza_a_la_frontera_del_fichero_siguiente(self):
        """El escaneo cae al final de un fichero: el disparo sale al cerrar ese fichero,
        con el reloj del detector avanzado a la marca del siguiente (causal)."""
        t0 = 1793520000.0  # 2026-11-01T08:40:00Z
        with tempfile.TemporaryDirectory() as d:
            d = Path(d)
            p1 = [(t0 + 0.5 + i * 0.001, ATK, SRV, 40000 + i, 1 + i, S, i) for i in range(12)]
            (d / "r-20261101084000.pcap").write_bytes(_pcap(p1))
            (d / "r-20261101084001.pcap").write_bytes(_pcap([(t0 + 1.2, CLI, SRV, 5, 80, S, 1)]))
            sal = d / "s.jsonl"
            dr.main(["--ficheros", str(d), "--patron", "r-*.pcap", "--una-vez", "--salida", str(sal)])
            r = [json.loads(x) for x in sal.read_text().splitlines()]
            self.assertEqual(len(r), 1)
            self.assertAlmostEqual(r[0]["t_evidencia"], t0 + 0.5 + 9 * 0.001 + 0.1, places=4)
            self.assertIn("disponible_en", r[0])
            self.assertIn("emitido_en", r[0])

    def test_lector_pcap_flujo(self):
        b = _pcap([(1.5, ATK, SRV, 1, 2, S, 3)])
        lp = dr.LectorPcap(io.BytesIO(b))
        t, fr = lp.siguiente()
        self.assertAlmostEqual(t, 1.5)
        self.assertEqual(dr.tcp_de_trama(fr)[:5], (ATK, SRV, 1, 2, S))
        self.assertIsNone(lp.siguiente())


if __name__ == "__main__":
    unittest.main()
