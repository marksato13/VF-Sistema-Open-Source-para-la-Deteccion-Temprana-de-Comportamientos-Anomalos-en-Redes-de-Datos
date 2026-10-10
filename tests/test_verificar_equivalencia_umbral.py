"""El verificador de equivalencia de escalas detecta umbrales coherentes e incoherentes."""
from __future__ import annotations

import contextlib
import io
import json
import tempfile
import unittest
from pathlib import Path

import joblib
import numpy as np
from sklearn.ensemble import IsolationForest
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

from scripts.modeling import verificar_equivalencia_umbral as veq


class Equivalencia(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        d = Path(cls.tmp.name)
        X = np.random.default_rng(1).normal(size=(300, 6))
        modelo = Pipeline([("escalador", StandardScaler()),
                           ("if", IsolationForest(n_estimators=20, random_state=0))]).fit(X)
        cls.modelo = d / "modelo.joblib"
        joblib.dump(modelo, cls.modelo)
        # Umbral en decision_function como lo informaría entrenar_preliminar.py,
        # y su traducción a score_samples como la usa el motor.
        cls.u_df = -0.068892
        cls.u_ss = cls.u_df + float(modelo[-1].offset_)
        cls.manifiesto = d / "manifest.json"
        cls.manifiesto.write_text(json.dumps(
            {"evaluation": {"if_x": {"threshold_used": cls.u_ss}}}), encoding="utf-8")

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def test_offset_auto_es_menos_medio(self):
        r = veq.verificar(self.modelo)
        self.assertAlmostEqual(r["offset_"], -0.5)
        self.assertTrue(r["relacion_ss_df_ok"])

    def test_umbrales_coherentes_son_equivalentes(self):
        r = veq.verificar(self.modelo, self.manifiesto, "if_x", self.u_df)
        self.assertEqual(r["veredicto"], "EQUIVALENTE")
        self.assertAlmostEqual(r["umbral_decision_function_implicito"], self.u_df)

    def test_lee_el_umbral_donde_lo_lee_el_motor(self):
        # Estructura del manifiesto operativo de Sensor1: el detector recalibrado
        # solo aparece en detectors.<nombre>.calibration, que es lo que lee
        # motor_decision.load_threshold. Debe preferirse a evaluation.
        man = Path(self.tmp.name) / "manifest-operativo.json"
        man.write_text(json.dumps({
            "detectors": {"if_x": {"calibration": {"threshold": self.u_ss,
                                                   "comparison": "score < threshold"}}},
            "evaluation": {"otro": {"threshold_used": 9.9}}}), encoding="utf-8")
        r = veq.verificar(self.modelo, man, "if_x", self.u_df)
        self.assertEqual(r["veredicto"], "EQUIVALENTE")
        self.assertEqual(r["fuente_umbral"], "detectors.if_x.calibration.threshold")

    def test_regla_de_comparacion_distinta_se_rechaza(self):
        man = Path(self.tmp.name) / "manifest-regla.json"
        man.write_text(json.dumps({"detectors": {"if_x": {"calibration": {
            "threshold": self.u_ss, "comparison": "score > threshold"}}}}), encoding="utf-8")
        with self.assertRaises(ValueError):
            veq.verificar(self.modelo, man, "if_x", self.u_df)

    def test_umbral_sin_traducir_se_detecta(self):
        # El error que este guion existe para atrapar: usar el umbral de
        # decision_function tal cual en la escala de score_samples.
        mal = Path(self.tmp.name) / "manifest-mal.json"
        mal.write_text(json.dumps({"evaluation": {"if_x": {"threshold_used": self.u_df}}}),
                       encoding="utf-8")
        r = veq.verificar(self.modelo, mal, "if_x", self.u_df)
        self.assertEqual(r["veredicto"], "NO_EQUIVALENTE")

    def test_main_devuelve_codigo_y_evidencia(self):
        salida = Path(self.tmp.name) / "evidencia.json"
        with contextlib.redirect_stdout(io.StringIO()):
            codigo = veq.main(["--modelo", str(self.modelo), "--manifiesto", str(self.manifiesto),
                               "--detector", "if_x", "--umbral-decision", str(self.u_df),
                               "--salida", str(salida)])
        self.assertEqual(codigo, 0)
        self.assertEqual(json.loads(salida.read_text(encoding="utf-8"))["veredicto"], "EQUIVALENTE")


if __name__ == "__main__":
    unittest.main()
