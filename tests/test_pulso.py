"""El pulso del panel: lo que entra y lo que se acumula, sin inventar ceros."""
from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts" / "engine"))
import dashboard as db  # noqa: E402


class ContarFilas(unittest.TestCase):
    def setUp(self):
        db._CACHE_FILAS.clear()
        self.tmp = Path(tempfile.mkdtemp())
        self.csv = self.tmp / "d.csv"

    def test_cuenta_sin_la_cabecera_y_solo_lo_nuevo(self):
        self.csv.write_text("a,b\n1,2\n3,4\n", encoding="utf-8")
        self.assertEqual(db.contar_filas(self.csv), 2)
        pos = db._CACHE_FILAS["pos"]
        with self.csv.open("a", encoding="utf-8") as fh:
            fh.write("5,6\n")
        self.assertEqual(db.contar_filas(self.csv), 3)
        self.assertGreater(db._CACHE_FILAS["pos"], pos)

    def test_si_el_fichero_encoge_se_cuenta_desde_cero(self):
        self.csv.write_text("a\n1\n2\n3\n", encoding="utf-8")
        self.assertEqual(db.contar_filas(self.csv), 3)
        self.csv.write_text("a\n1\n", encoding="utf-8")
        self.assertEqual(db.contar_filas(self.csv), 1)

    def test_sin_fichero_no_hay_cifra(self):
        self.assertIsNone(db.contar_filas(self.tmp / "no-existe.csv"))


class Pulso(unittest.TestCase):
    def setUp(self):
        db._CACHE_FILAS.clear()
        self.tmp = Path(tempfile.mkdtemp())

    def test_lo_que_no_se_puede_leer_va_como_none(self):
        p = db.pulso_ingesta([], None, None, self.tmp / "feed.json", 1000.0)
        self.assertIsNone(p["ultima_decision"])
        self.assertIsNone(p["eve"])
        self.assertIsNone(p["dataset"])
        self.assertIsNone(p["feed"])
        self.assertEqual(p["decisiones_60s"], 0)

    def test_decisiones_del_ultimo_minuto_y_feed(self):
        feed = self.tmp / "feed.json"
        feed.write_text(json.dumps({"generado": 990.0, "entradas": [{"ip": "10.10.20.30"}]}),
                        encoding="utf-8")
        ds = self.tmp / "d.csv"
        ds.write_text("a\n1\n2\n", encoding="utf-8")
        decisiones = [{"logged_at": 900.0}, {"logged_at": 950.0}, {"logged_at": 995.0}, {"x": 1}]
        p = db.pulso_ingesta(decisiones, None, ds, feed, 1000.0)
        self.assertEqual(p["ultima_decision"], 995.0)
        self.assertEqual(p["decisiones_60s"], 2)
        self.assertEqual(p["feed"], {"generado": 990.0, "entradas": 1})
        self.assertEqual(p["dataset"]["filas"], 2)


if __name__ == "__main__":
    unittest.main()
