"""Las cifras del modelo en uso solo se muestran si son de ESE modelo."""
from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts" / "engine"))
import dashboard as db  # noqa: E402


class EvaluacionDelVigente(unittest.TestCase):
    def setUp(self):
        self.ruta = Path(tempfile.mkdtemp()) / "m.json"
        self.ruta.write_text(json.dumps({"detector": "if_x", "fpr_oro": {"valor": 0.04}}),
                             encoding="utf-8")

    def test_solo_para_el_detector_que_nombra(self):
        self.assertEqual(db.evaluacion_del_vigente("if_x", self.ruta)["fpr_oro"]["valor"], 0.04)
        self.assertIsNone(db.evaluacion_del_vigente("otro_modelo", self.ruta))

    def test_sin_fichero_o_ilegible_no_hay_cifras(self):
        self.assertIsNone(db.evaluacion_del_vigente("if_x", self.ruta.parent / "no.json"))
        self.ruta.write_text("{roto", encoding="utf-8")
        self.assertIsNone(db.evaluacion_del_vigente("if_x", self.ruta))

    def test_el_fichero_del_repositorio_cuadra(self):
        d = json.loads(db.EVALUACION_VIGENTE.read_text(encoding="utf-8"))
        dk = d["deteccion_kali"]
        self.assertEqual(sum(f["detectadas"] for f in d["por_familia"]), dk["detectadas"])
        self.assertEqual(sum(f["total"] for f in d["por_familia"]), dk["total"])


class RedAnalizada(unittest.TestCase):
    def test_el_argumento_manda_y_si_no_el_toml(self):
        self.assertEqual(db.red_analizada("10.0.0.0/8", None), "10.0.0.0/8")
        toml = Path(tempfile.mkdtemp()) / "c.toml"
        toml.write_text('[red]\nred_entidades = "10.10.0.0/16"\n', encoding="utf-8")
        self.assertEqual(db.red_analizada(None, toml), "10.10.0.0/16")


if __name__ == "__main__":
    unittest.main()
