"""Franja de salud y estado de drops del panel.

La salud la decide el servidor (``resumen_salud``) para que haya una sola
verdad y se pueda probar. El bug P0 era que una accion LIMIT/BLOCK por
heuristico -sin ALERT del modelo- quedaba bajo "todo operando con normalidad".
Los drops son un ACUMULADO desde el arranque: solo un incremento entre muestras
es perdida en curso.
"""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "scripts" / "engine"))

import dashboard as db  # noqa: E402

DROPS_OK = {"nivel": "estable", "subiendo": False, "atrasado": False, "total": 0}


def salud(counters, drops=None, services=None, calib=True, modo="live"):
    return db.resumen_salud(
        modo,
        services if services is not None else {"motor": True, "captura": True},
        counters,
        drops if drops is not None else DROPS_OK,
        {"calibrado_en_esta_red": calib},
    )


def ctr(block=0, limit=0, alert_model=0, alert_auth_heuristic=0):
    return {"block": block, "limit": limit, "alert_model": alert_model,
            "alert_auth_heuristic": alert_auth_heuristic}


class ResumenSalud(unittest.TestCase):
    def test_p0_limit_por_heuristico_no_queda_como_todo_normal(self):
        # PERMIT del modelo + LIMIT por heuristico (p.ej. dns_entropy), sin ALERT
        # del modelo: compute_counters da limit=1, alert_model=0.
        s = salud(ctr(limit=1))
        self.assertEqual(s["nivel"], "warn")
        self.assertNotIn("normalidad", s["msg"])
        self.assertIn("LIMIT", s["sub"])

    def test_p0_block_sin_alerta_del_modelo_se_ve(self):
        s = salud(ctr(block=1))
        self.assertEqual(s["nivel"], "warn")
        self.assertIn("BLOCK", s["sub"])

    def test_accion_de_regla_no_se_llama_alerta_del_modelo(self):
        # Una accion por regla no debe anunciarse como "anomalía del modelo".
        s = salud(ctr(block=1))
        self.assertNotIn("anomalía del modelo", s["sub"])

    def test_sin_actividad_es_ok(self):
        s = salud(ctr())
        self.assertEqual(s["nivel"], "ok")
        self.assertIn("normalidad", s["msg"])

    def test_servicio_caido_manda_sobre_todo_lo_demas(self):
        s = salud(ctr(block=9, limit=9, alert_model=9),
                  services={"motor": True, "captura": False})
        self.assertEqual(s["nivel"], "bad")

    def test_sin_calibrar_avisa_y_separa_la_regla_del_modelo(self):
        s = salud(ctr(block=1, alert_model=3), calib=False)
        self.assertEqual(s["nivel"], "warn")
        self.assertIn("sin calibrar", s["msg"])
        # La accion por regla se menciona como independiente del modelo.
        self.assertIn("deterministas", s["sub"])

    def test_demo_manda(self):
        s = salud(ctr(), modo="demo")
        self.assertIn("DEMO", s["msg"])

    def test_ok_nunca_dice_sin_drops_si_el_dato_esta_atrasado(self):
        s = salud(ctr(), drops={"nivel": "atrasado", "subiendo": False,
                                "atrasado": True, "total": 7})
        self.assertEqual(s["nivel"], "ok")
        self.assertIn("atrasado", s["sub"])

    def test_drops_subiendo_sin_otra_actividad_avisa(self):
        s = salud(ctr(), drops={"nivel": "subiendo", "subiendo": True,
                                "atrasado": False, "total": 12, "delta": 4})
        self.assertEqual(s["nivel"], "warn")
        self.assertIn("descartando", s["msg"])
        self.assertIn("+4", s["sub"])


class DropsEstado(unittest.TestCase):
    MARCA1 = "2026-10-12T19:00:00.000000+0000"
    MARCA2 = "2026-10-12T19:00:05.000000+0000"

    def _cm(self, drops, marca):
        return {"kernel_packets": 100, "kernel_drops": drops, "kernel_ifdrops": 0,
                "medido_en": marca}

    def test_acumulado_constante_no_es_subida(self):
        prev = {"medido_en": self.MARCA1, "total": 5}
        d = db.drops_estado(self._cm(5, self.MARCA2), prev,
                            db._epoch_de_ts(self.MARCA2))
        self.assertFalse(d["subiendo"])
        self.assertEqual(d["delta"], 0)
        self.assertEqual(d["nivel"], "estable")

    def test_acumulado_creciente_es_subida(self):
        prev = {"medido_en": self.MARCA1, "total": 5}
        d = db.drops_estado(self._cm(9, self.MARCA2), prev,
                            db._epoch_de_ts(self.MARCA2))
        self.assertTrue(d["subiendo"])
        self.assertEqual(d["delta"], 4)
        self.assertEqual(d["nivel"], "subiendo")

    def test_primera_muestra_no_afirma_subida(self):
        d = db.drops_estado(self._cm(5, self.MARCA1), None,
                            db._epoch_de_ts(self.MARCA1))
        self.assertFalse(d["subiendo"])
        self.assertIsNone(d["delta"])
        self.assertEqual(d["total"], 5)

    def test_stats_viejo_es_atrasado_no_cero(self):
        ahora = db._epoch_de_ts(self.MARCA1) + 9999
        d = db.drops_estado(self._cm(0, self.MARCA1), None, ahora)
        self.assertTrue(d["atrasado"])
        self.assertEqual(d["nivel"], "atrasado")

    def test_sin_metricas_sin_dato(self):
        d = db.drops_estado(None, None, 1000.0)
        self.assertEqual(d["nivel"], "sin_dato")
        self.assertIsNone(d["total"])

    def test_marca_de_suricata_con_zona_sin_dos_puntos_se_parsea(self):
        self.assertIsNotNone(db._epoch_de_ts(self.MARCA1))


if __name__ == "__main__":
    unittest.main()
