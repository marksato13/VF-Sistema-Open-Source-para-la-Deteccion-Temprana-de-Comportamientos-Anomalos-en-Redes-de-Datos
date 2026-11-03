"""Regla icmp_flood (3-nov): calibrada con 3 119 148 ventanas reales del Sensor1."""
import unittest

from scripts.engine import heuristicos as h


def ventana(pps, icmp):
    return {"packet_rate_10s": pps, "icmp_ratio_10s": icmp}


class IcmpFlood(unittest.TestCase):
    def test_el_flood_de_la_demo_bloquea(self):
        for pps in (318.2, 1784.1, 3997.3):                      # ventanas reales de la Kali
            v = h.evaluar(ventana(pps, 1.0))
            self.assertEqual((v["heuristico"], v["accion"]), ("icmp_flood", "BLOCK"), pps)

    def test_lo_legitimo_mas_alto_no(self):
        self.assertIsNone(h.evaluar(ventana(43.6, 1.0)))        # .21, maximo legitimo medido
        self.assertIsNone(h.evaluar(ventana(30.0, 1.0)))        # ping normal de la Kali

    def test_mucho_trafico_que_no_es_icmp_no(self):
        self.assertIsNone(h.evaluar(ventana(1843.2, 0.05)))     # 10.10.40.20, trafico normal alto

    def test_version_subida(self):
        self.assertEqual(h.VERSION_UMBRALES, "2026-11-03.2")


if __name__ == "__main__":
    unittest.main()
