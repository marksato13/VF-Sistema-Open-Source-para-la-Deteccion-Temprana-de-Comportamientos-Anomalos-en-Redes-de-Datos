"""Los contadores del panel cuentan por el DETECTOR ACTIVO, no uno fijo.

Regresión: con `ocsvm_scaled` hardcodeado, tras congelar el modelo recalibrado
(`if_recalibrado_2026_09`) los contadores del modelo salían en 0.
"""
from __future__ import annotations

import importlib.util
import sys
import time
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("dashboard", REPO / "scripts/engine/dashboard.py")
assert SPEC and SPEC.loader
dash = importlib.util.module_from_spec(SPEC)
sys.modules["dashboard"] = dash
SPEC.loader.exec_module(dash)


def d(detector, decision="ALERT"):
    return {"decision": decision, "detector_name": detector,
            "entity_ip": "10.10.20.30", "logged_at": time.time()}


class Contadores(unittest.TestCase):
    def test_cuenta_el_detector_activo_recalibrado(self):
        c = dash.compute_counters([d("if_recalibrado_2026_09")],
                                  detector_modelo="if_recalibrado_2026_09")
        self.assertEqual(c["alert_model"], 1)

    def test_no_cuenta_el_viejo_si_el_activo_es_otro(self):
        # regresión: un ALERT de ocsvm_scaled NO es del modelo activo recalibrado
        c = dash.compute_counters([d("ocsvm_scaled")],
                                  detector_modelo="if_recalibrado_2026_09")
        self.assertEqual(c["alert_model"], 0)

    def test_por_defecto_sigue_contando_ocsvm(self):
        c = dash.compute_counters([d("ocsvm_scaled")])
        self.assertEqual(c["alert_model"], 1)

    def test_permit_del_modelo_activo(self):
        c = dash.compute_counters([d("if_recalibrado_2026_09", decision="PERMIT")],
                                  detector_modelo="if_recalibrado_2026_09")
        self.assertEqual(c["permit_model"], 1)

    def test_heuristico_de_fuerza_bruta_se_cuenta_aparte(self):
        c = dash.compute_counters([d("auth_failure_heuristic")],
                                  detector_modelo="if_recalibrado_2026_09")
        self.assertEqual(c["alert_auth_heuristic"], 1)
        self.assertEqual(c["alert_model"], 0)


if __name__ == "__main__":
    unittest.main()
