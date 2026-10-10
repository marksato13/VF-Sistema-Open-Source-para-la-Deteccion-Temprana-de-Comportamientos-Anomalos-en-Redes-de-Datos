"""Cadena completa: entrenar_preliminar -> promover_preliminar -> lo que carga el motor.

La guía de replicación tiene que producir EXACTAMENTE un artefacto que el motor
acepte. Aquí se ejecuta la cadena real sobre un CSV particionado sintético y se
comprueba con el código del propio motor (`load_threshold`, `score_samples` sobre
una fila cruda en el orden del extractor) y del panel (`load_model_summary`).
"""
from __future__ import annotations

import contextlib
import csv
import importlib.util
import io
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

import joblib
import numpy as np

REPO = Path(__file__).resolve().parents[1]
V2 = REPO / "configs/features/multilayer-v2.json"
V3 = REPO / "configs/features/multilayer-v3.json"


def _cargar(nombre, ruta, rutas_extra=()):
    for r in rutas_extra:
        if str(r) not in sys.path:
            sys.path.insert(0, str(r))
    spec = importlib.util.spec_from_file_location(nombre, ruta)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


promover = _cargar("promover_preliminar", REPO / "scripts/modeling/promover_preliminar.py")
motor = _cargar("motor_decision", REPO / "scripts/engine/motor_decision.py",
                (REPO / "scripts/features", REPO / "scripts/engine"))
panel = _cargar("dashboard_promocion", REPO / "scripts/engine/dashboard.py")


def nombres(esquema):
    c = json.loads(Path(esquema).read_text(encoding="utf-8"))
    return [f["name"] for f in sorted(c["features"], key=lambda f: f["order"])]


class CadenaDePromocion(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        d = Path(cls.tmp.name)
        cols = nombres(V3)                         # la línea base real es v3 (31)
        rng = np.random.default_rng(7)
        cls.csv = d / "particionado.csv"
        with cls.csv.open("w", newline="", encoding="utf-8") as fh:
            w = csv.writer(fh)
            w.writerow(cols + ["particion", "eligible_training"])
            for i in range(600):
                parte = ("train", "train", "validation", "train", "test")[i % 5]
                w.writerow([f"{abs(x):.6f}" for x in rng.normal(1.0, 0.3, len(cols))]
                           + [parte, "true"])

        def entrenar(esquema, base):
            subprocess.run([sys.executable, str(REPO / "scripts/modeling/entrenar_preliminar.py"),
                            "--entrada", str(cls.csv), "--schema", str(esquema),
                            "--salida", str(d / f"{base}.joblib"),
                            "--informe", str(d / f"{base}.json"), "--n-estimators", "30"],
                           check=True, capture_output=True)
            return d / f"{base}.joblib", d / f"{base}.json"

        cls.paquete, cls.informe = entrenar(V2, "if-v2")
        cls.paquete_v3, cls.informe_v3 = entrenar(V3, "if-v3")
        cls.modelo = d / "desplegable.joblib"
        cls.manifiesto = d / "manifest-desplegable.json"
        cls.r = promover.promover(cls.paquete, "if_prueba", cls.modelo, cls.manifiesto,
                                  cls.informe, deteccion_global=0.69, deteccion_kali=0.69,
                                  deteccion_fuente="prueba")

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def test_el_motor_lee_el_umbral_y_puntua_una_fila_cruda(self):
        umbral = motor.load_threshold(self.manifiesto, "if_prueba")
        informe = json.loads(self.informe.read_text(encoding="utf-8"))
        pipe = joblib.load(self.modelo)
        offset = float(pipe[-1].offset_)
        self.assertAlmostEqual(umbral, informe["umbral_decision_function"] + offset, places=12)
        fila = [[1.0] * len(motor.extractor.FEATURE_NAMES)]     # orden del extractor v2
        self.assertTrue(np.isfinite(float(pipe.score_samples(fila)[0])))

    def test_mismo_orden_que_el_extractor_del_motor(self):
        man = json.loads(self.manifiesto.read_text(encoding="utf-8"))
        feats = man["detectors"]["if_prueba"]["features"]
        self.assertEqual(feats, list(motor.extractor.FEATURE_NAMES))
        self.assertEqual(len(feats), 28)

    def test_hash_del_artefacto_y_equivalencia(self):
        man = json.loads(self.manifiesto.read_text(encoding="utf-8"))
        self.assertEqual(man["detectors"]["if_prueba"]["model_sha256"], promover.sha256(self.modelo))
        self.assertEqual(self.r["equivalencia"], "EQUIVALENTE")
        self.assertEqual(self.r["max_desvio_ss_menos_df_vs_offset"], 0.0)

    def test_el_panel_muestra_el_detector_promocionado(self):
        s = panel.load_model_summary(self.manifiesto, "if_prueba")
        informe = json.loads(self.informe.read_text(encoding="utf-8"))
        self.assertAlmostEqual(s["threshold"], self.r["umbral_score_samples"])
        self.assertAlmostEqual(s["test_fpr"], informe["fpr_test"])
        self.assertAlmostEqual(s["detection_rate"], 0.69)

    def test_un_modelo_entrenado_con_v3_se_rechaza(self):
        d = Path(self.tmp.name)
        with self.assertRaises(ValueError):
            promover.promover(self.paquete_v3, "if_v3", d / "m3.joblib", d / "man3.json",
                              self.informe_v3)

    def test_el_esquema_v3_no_es_el_contrato_del_motor(self):
        d = Path(self.tmp.name)
        with self.assertRaises(ValueError):
            promover.promover(self.paquete_v3, "if_v3b", d / "m3b.joblib", d / "man3b.json",
                              self.informe_v3, esquema=V3)

    def test_no_sobrescribe_un_artefacto(self):
        with self.assertRaises(FileExistsError):
            promover.promover(self.paquete, "if_prueba", self.modelo, self.manifiesto, self.informe)

    def test_informe_de_otro_paquete_se_rechaza(self):
        d = Path(self.tmp.name)
        with self.assertRaises(ValueError):
            promover.promover(self.paquete, "if_x", d / "mx.joblib", d / "manx.json", self.informe_v3)

    def test_funciona_en_un_proceso_limpio(self):
        # En el mismo proceso el motor ya importó el extractor y eso ocultaba un fallo
        # de carga que solo aparecía en un proceso nuevo (como en Sensor1).
        d = Path(self.tmp.name)
        r = subprocess.run([sys.executable, str(REPO / "scripts/modeling/promover_preliminar.py"),
                            "--paquete", str(self.paquete), "--informe", str(self.informe),
                            "--detector", "if_limpio", "--salida-modelo", str(d / "limpio.joblib"),
                            "--salida-manifiesto", str(d / "limpio.json")],
                           capture_output=True, text=True)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(json.loads(r.stdout)["equivalencia"], "EQUIVALENTE")

    def test_main_imprime_el_resumen(self):
        d = Path(self.tmp.name)
        with contextlib.redirect_stdout(io.StringIO()) as out:
            codigo = promover.main(["--paquete", str(self.paquete), "--informe", str(self.informe),
                                    "--detector", "if_cli", "--salida-modelo", str(d / "cli.joblib"),
                                    "--salida-manifiesto", str(d / "cli.json")])
        self.assertEqual(codigo, 0)
        self.assertEqual(json.loads(out.getvalue())["equivalencia"], "EQUIVALENTE")


class PanelConManifiestoDeLaboratorio(unittest.TestCase):
    def test_lee_el_umbral_de_detectors_y_tolera_metricas_ausentes(self):
        with tempfile.TemporaryDirectory() as t:
            m = Path(t) / "m.json"
            m.write_text(json.dumps({"detectors": {"if_y": {"calibration": {
                "threshold": -0.5, "comparison": "score < threshold"}}}}), encoding="utf-8")
            s = panel.load_model_summary(m, "if_y")
            self.assertEqual(s["threshold"], -0.5)
            self.assertIsNone(s["test_fpr"])
            self.assertIsNone(s["detection_rate"])


if __name__ == "__main__":
    unittest.main()
