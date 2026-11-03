"""Seccion «Escenario en vivo» y agrupacion de anomalias marginales."""
import json
import sys
import tempfile
import time
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "scripts" / "engine"))
import dashboard as dash  # noqa: E402

U = -0.569


def dec(ip, t, decision="PERMIT", score=-0.5, heur=None):
    return {"event": "decision", "entity_ip": ip, "logged_at": t, "decision": decision,
            "detector_name": "if_limpio_2026_10", "score": score, "threshold": U,
            "heuristico": heur, "window_end_utc": "x%s" % t}


class Marginal(unittest.TestCase):
    def test_borde_del_umbral_es_marginal(self):
        self.assertTrue(dash.es_marginal(dec("1.1.1.1", 0, "ALERT", -0.575)))

    def test_lejos_del_umbral_no(self):
        self.assertFalse(dash.es_marginal(dec("1.1.1.1", 0, "ALERT", -0.65)))

    def test_una_regla_nunca_es_marginal(self):
        h = {"accion": "BLOCK", "heuristico": "port_scan", "motivo": "x"}
        self.assertFalse(dash.es_marginal(dec("1.1.1.1", 0, "ALERT", -0.575, h)))

    def test_permit_no_es_marginal(self):
        self.assertFalse(dash.es_marginal(dec("1.1.1.1", 0, "PERMIT", -0.5)))

    def test_contadores_separan_relevantes(self):
        ahora = time.time()
        ds = [dec("a", ahora - 5, "ALERT", -0.575), dec("b", ahora - 5, "ALERT", -0.7),
              dec("c", ahora - 5, "PERMIT", -0.5,
                  {"accion": "LIMIT", "heuristico": "dns_entropy", "motivo": "x"})]
        c = dash.compute_counters(ds, detector_modelo="if_limpio_2026_10")
        self.assertEqual(c["alert_model_marginal"], 1)
        self.assertEqual(c["acciones_relevantes"], 2)


class Escenario(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.log = self.tmp / "motor.log"
        self.feed = self.tmp / "feed.json"
        self.ahora = time.time()
        filas = [dec("10.10.20.30", self.ahora - 300, "PERMIT"),
                 dec("10.10.20.30", self.ahora - 20, "ALERT", -0.7,
                     {"accion": "BLOCK", "heuristico": "port_scan", "motivo": "90 intentos/30s"}),
                 dec("10.10.20.21", self.ahora - 10, "PERMIT")]
        self.log.write_text("\n".join(json.dumps(f) for f in filas) + "\n", encoding="utf-8")
        self.feed.write_text(json.dumps({"generado": self.ahora - 2, "entradas": [
            {"ip": "10.10.20.30", "accion": "BLOCK", "motivo": "port_scan", "hasta": self.ahora + 300, "nivel": 1}]}),
            encoding="utf-8")

    def test_solo_la_ip_y_desde_el_inicio(self):
        r = dash.estado_escenario(self.log, "10.10.20.30", str(self.ahora - 60), self.ahora, self.feed, None)
        self.assertEqual(len(r["decisiones"]), 1)
        self.assertEqual(r["decisiones"][0]["accion"], "BLOCK")
        self.assertEqual(r["feed"]["entrada"]["accion"], "BLOCK")
        self.assertEqual(r["decisiones_60s"], 2)

    def test_ip_invalida(self):
        r = dash.estado_escenario(self.log, "10.10.20.30; rm", "0", self.ahora, self.feed, None)
        self.assertIn("error", r)

    def test_sin_feed(self):
        r = dash.estado_escenario(self.log, "10.10.20.21", "", self.ahora, None, None)
        self.assertIsNone(r["feed"])
        self.assertEqual(r["decisiones"][0]["accion"], "PERMIT")


if __name__ == "__main__":
    unittest.main()
