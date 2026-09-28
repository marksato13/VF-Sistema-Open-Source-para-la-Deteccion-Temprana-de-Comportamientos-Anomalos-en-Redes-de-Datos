"""El mapa de artefactos: ficheros reales por componente, con estado en vivo.

Da forma a los "cuadraditos" del panel. Se comprueba que agrupa por nodo, que
marca existe/no existe sin inventar, y que resume el anillo de PCAP (un
directorio que rota) en vez de listarlo entero.
"""

from __future__ import annotations

import importlib.util
import sys
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("dashboard", REPO / "scripts/engine/dashboard.py")
assert SPEC and SPEC.loader
dash = importlib.util.module_from_spec(SPEC)
sys.modules["dashboard"] = dash
SPEC.loader.exec_module(dash)


class MapaDeArtefactos(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.d = Path(self.tmp.name)
        (self.d / "eve.json").write_text("{}\n", encoding="utf-8")
        (self.d / "dataset.csv").write_text("a,b\n1,2\n", encoding="utf-8")
        (self.d / "manifest.json").write_text("{}", encoding="utf-8")
        (self.d / "ocsvm_scaled.joblib").write_bytes(b"x" * 10)
        (self.d / "m.log").write_text("l\n", encoding="utf-8")
        cap = self.d / "captura"
        cap.mkdir()
        (cap / "live-1.pcap").write_bytes(b"p" * 100)
        (cap / "live-2.pcap").write_bytes(b"p" * 50)
        self.cap = cap

    def mapa(self):
        return dash.estado_artefactos(
            self.d / "eve.json", self.d / "dataset.csv", self.d / "manifest.json",
            self.d / "m.log", None, self.d / "desc.json",
            raiz=self.d, capture_dir=self.cap)

    def test_agrupa_por_nodo(self):
        m = self.mapa()
        for nodo in ("captura", "suricata", "motor", "variables", "modelo",
                     "reentrenamiento", "control", "registro", "panel"):
            self.assertIn(nodo, m, nodo)
            self.assertTrue(m[nodo], "%s sin ficheros" % nodo)

    def test_existencia_real_no_inventada(self):
        m = self.mapa()
        eve = m["suricata"][0]
        self.assertTrue(eve["existe"])
        self.assertEqual(eve["tipo"], "json")
        self.assertGreater(eve["bytes"], 0)
        # desc.json no se creo: debe marcarse como ausente, no fingir bytes.
        desc = [f for f in m["variables"] if f["ruta"].endswith("desc.json")][0]
        self.assertFalse(desc["existe"])
        self.assertNotIn("bytes", desc)

    def test_el_anillo_pcap_se_resume(self):
        anillo = self.mapa()["captura"][0]
        self.assertEqual(anillo["tipo"], "pcap")
        self.assertEqual(anillo["n"], 2)
        self.assertEqual(anillo["bytes"], 150)

    def test_el_modelo_apunta_al_joblib_y_manifest(self):
        rutas = [f["ruta"] for f in self.mapa()["modelo"]]
        self.assertTrue(any(r.endswith("ocsvm_scaled.joblib") for r in rutas))
        self.assertTrue(any(r.endswith("manifest.json") for r in rutas))

    def test_artefactos_es_ruta_de_admin(self):
        # Revela rutas internas: el lector no debe recibirlo.
        self.assertIn("/api/artefactos", dash.RUTAS_ADMIN)


if __name__ == "__main__":
    unittest.main()
