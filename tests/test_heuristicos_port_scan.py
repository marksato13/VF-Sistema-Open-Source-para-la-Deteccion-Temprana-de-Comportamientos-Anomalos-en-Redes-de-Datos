"""Pruebas del heurístico port_scan, incluida la rama OR de ráfaga (2026-10-06.2)."""
from __future__ import annotations

import importlib.util
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
MOD = REPO / "scripts/engine/heuristicos.py"
_spec = importlib.util.spec_from_file_location("heuristicos", MOD)
assert _spec and _spec.loader
h = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(h)


class PortScanTests(unittest.TestCase):
    def test_escaneo_normal_dispara(self):
        row = {"flow_attempt_count_30s": 50, "unique_dst_port_ratio_30s": 0.60,
               "syn_completion_ratio_10s": 0.05}
        v = h.evaluar(row)
        self.assertIsNotNone(v)
        self.assertEqual(v["heuristico"], "port_scan")
        self.assertEqual(v["accion"], "BLOCK")

    def test_rafaga_masiva_dispara_aunque_uratio_bajo(self):
        # El caso que fallaba (nota 26): el espejo deja el ratio bordeando 0,45 y a
        # veces cae por debajo; la rama OR debe cazar la ráfaga igualmente.
        row = {"flow_attempt_count_30s": 2007, "unique_dst_port_ratio_30s": 0.40,
               "syn_completion_ratio_10s": 0.0}
        v = h.evaluar(row)
        self.assertIsNotNone(v)
        self.assertEqual(v["heuristico"], "port_scan")

    def test_ventana_de_borde_no_dispara(self):
        # Pocos intentos (6): ni la regla normal ni la ráfaga -> no dispara.
        row = {"flow_attempt_count_30s": 6, "unique_dst_port_ratio_30s": 0.75,
               "syn_completion_ratio_10s": 0.0}
        self.assertIsNone(h.evaluar(row))

    def test_benigno_volumen_alto_con_completitud_no_es_scan(self):
        # Volumen alto pero con conexiones que SÍ completan (uso legítimo): la
        # ráfaga exige <=10 % completadas, así que no debe marcar port_scan.
        row = {"flow_attempt_count_30s": 300, "unique_dst_port_ratio_30s": 0.10,
               "syn_completion_ratio_10s": 0.90}
        v = h.evaluar(row)
        self.assertFalse(v and v.get("heuristico") == "port_scan")


if __name__ == "__main__":
    unittest.main()
