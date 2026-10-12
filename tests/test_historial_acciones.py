"""Historial de acciones: episodios por IP, sin inventar lo que el registro no cubre."""
from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts" / "engine"))
import dashboard as db  # noqa: E402

AHORA = 1_000_000.0


def linea(t, ip, decision="PERMIT", detector="if_x", heuristico=None):
    return json.dumps({"event": "decision", "logged_at": t, "entity_ip": ip, "decision": decision,
                       "detector_name": detector, "heuristico": heuristico})


class Historial(unittest.TestCase):
    def setUp(self):
        db._CACHE_HISTORIAL.clear()
        self.log = Path(tempfile.mkdtemp()) / "motor_decision.log"

    def escribir(self, lineas):
        self.log.write_text("\n".join(lineas) + "\n", encoding="utf-8")

    def test_una_racha_es_un_episodio_y_gana_la_accion_mas_severa(self):
        scan = {"heuristico": "port_scan", "accion": "BLOCK", "motivo": "250 intentos"}
        self.escribir([
            linea(AHORA - 5000, "10.10.20.21"),
            linea(AHORA - 4000, "10.10.20.30", "ALERT"),                 # LIMIT por el modelo
            linea(AHORA - 3990, "10.10.20.30", heuristico=scan),         # BLOCK por la regla
            linea(AHORA - 3980, "10.10.20.30", "ALERT"),
        ])
        d = db.historial_acciones(self.log, AHORA)
        self.assertEqual(len(d["episodios"]), 1)
        e = d["episodios"][0]
        self.assertEqual((e["ip"], e["accion"], e["origen"], e["ventanas"]),
                         ("10.10.20.30", "BLOCK", "port_scan", 3))
        self.assertEqual((e["inicio"], e["fin"]), (AHORA - 4000, AHORA - 3980))
        self.assertFalse(e["vigente"])

    def test_mas_de_diez_minutos_separan_episodios_y_lo_reciente_sigue_vigente(self):
        self.escribir([linea(AHORA - 3000, "10.10.20.30", "ALERT"),
                       linea(AHORA - 100, "10.10.20.30", "ALERT")])
        d = db.historial_acciones(self.log, AHORA)
        self.assertEqual([e["vigente"] for e in d["episodios"]], [True, False])   # el mas nuevo, primero

    def test_infraestructura_y_lo_antiguo_quedan_fuera(self):
        self.escribir([linea(AHORA - 90000, "10.10.20.30", "ALERT"),      # hace mas de 24 h
                       linea(AHORA - 50, "10.10.10.20", "ALERT")])        # DNS: nunca se bloquea
        self.assertEqual(db.historial_acciones(self.log, AHORA)["episodios"], [])

    def test_desde_dice_hasta_donde_alcanza_el_registro(self):
        self.escribir([linea(AHORA - 600, "10.10.20.21")])
        self.assertEqual(db.historial_acciones(self.log, AHORA)["desde"], AHORA - 600)


if __name__ == "__main__":
    unittest.main()
