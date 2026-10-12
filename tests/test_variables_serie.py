"""La seccion Variables: serie reciente del dataset y rango normal del oro."""
from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts" / "engine"))
import dashboard as db  # noqa: E402


class SerieDelDataset(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.csv = self.tmp / "d.csv"
        filas = ["entity_ip,window_end_utc,packet_rate_10s"]
        # Tres ventanas, dos entidades en cada una: la serie toma el maximo.
        for i, (a, b) in enumerate([(1.0, 5.0), (2.0, 3.0), (9.0, 4.0)]):
            ven = "2026-10-12T10:00:%02dZ" % (i * 10)
            filas += ["10.10.20.21,%s,%s" % (ven, a), "10.10.20.22,%s,%s" % (ven, b)]
        self.csv.write_text("\n".join(filas) + "\n", encoding="utf-8")

    def test_serie_es_el_maximo_por_ventana_en_orden(self):
        m = db.muestra_del_dataset(self.csv, ["packet_rate_10s"])["por_variable"]["packet_rate_10s"]
        self.assertEqual(m["serie"], [5.0, 3.0, 9.0])
        self.assertEqual(m["ultimo"]["valor"], 9.0)
        self.assertEqual(m["ultimo"]["entidad"], "10.10.20.21")
        self.assertEqual(m["ultimo"]["ventana"], "2026-10-12T10:00:20Z")

    def test_los_campos_anteriores_siguen(self):
        m = db.muestra_del_dataset(self.csv, ["packet_rate_10s"])["por_variable"]["packet_rate_10s"]
        self.assertEqual((m["n"], m["min"], m["max"]), (6, 1.0, 9.0))


class RangoDelOro(unittest.TestCase):
    def setUp(self):
        db._CACHE_ORO.clear()
        self.tmp = Path(tempfile.mkdtemp())

    def test_sin_configuracion_o_sin_oro_no_hay_rango(self):
        self.assertEqual(db.rango_oro(None, ["x"], respaldo=self.tmp / "no.toml"), {})
        toml = self.tmp / "c.toml"
        toml.write_text('[rutas]\nraiz = "%s"\n[reentrenamiento]\noro = "oro.csv"\n'
                        % self.tmp.as_posix(), encoding="utf-8")
        self.assertEqual(db.rango_oro(toml, ["x"]), {})

    def test_rango_con_los_cuantiles_de_la_politica(self):
        (self.tmp / "oro.csv").write_text(
            "x,y\n" + "\n".join("%d,%d" % (i, 2 * i) for i in range(1001)) + "\n", encoding="utf-8")
        toml = self.tmp / "c.toml"
        toml.write_text('[rutas]\nraiz = "%s"\n[reentrenamiento]\noro = "oro.csv"\n'
                        'cuantil_referencia = 0.9\n' % self.tmp.as_posix(), encoding="utf-8")
        r = db.rango_oro(toml, ["x", "y", "no_existe"])
        self.assertEqual(set(r), {"x", "y"})
        self.assertAlmostEqual(r["x"][0], 100.0)
        self.assertAlmostEqual(r["x"][1], 900.0)
        self.assertAlmostEqual(r["y"][1], 1800.0)


if __name__ == "__main__":
    unittest.main()
