"""Almacen incremental de decisiones: leer a trozos da lo mismo que leer de una vez."""
from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts" / "engine"))
import dashboard as db  # noqa: E402


def linea(t, ip, decision="PERMIT", score=-0.40, umbral=-0.57):
    return json.dumps({"event": "decision", "logged_at": t, "entity_ip": ip, "decision": decision,
                       "detector_name": "if_x", "score": score, "threshold": umbral,
                       "heuristico": None}) + "\n"


class Almacen(unittest.TestCase):
    def setUp(self):
        self.viejo = db.DECISIONES_CACHE_S
        db.DECISIONES_CACHE_S = 0.0           # cada llamada mira el fichero
        db._ALMACENES.clear()
        self.log = Path(tempfile.mkdtemp()) / "motor_decision.log"

    def tearDown(self):
        db.DECISIONES_CACHE_S = self.viejo
        db._ALMACENES.clear()

    def politicas(self):
        return [(d["logged_at"], d.get("politica_modelo")) for d in db.read_decisions(self.log, 10**6, 1 << 30)]

    def test_a_trozos_igual_que_de_una_vez_incluida_la_politica(self):
        filas = [linea(1000 + 10 * k, "10.10.20.22", "ALERT" if k % 2 else "PERMIT",
                       score=-0.70 if k % 2 else -0.40) for k in range(40)]
        # escribe en trozos, uno de ellos partido a mitad de linea
        with self.log.open("w", encoding="utf-8") as fh:
            for k, f in enumerate(filas):
                if k == 17:
                    fh.write(f[:25]); fh.flush(); db.read_decisions(self.log, 10)
                    fh.write(f[25:])
                else:
                    fh.write(f)
                fh.flush()
                db.read_decisions(self.log, 10)
        a_trozos = self.politicas()
        db._ALMACENES.clear()
        self.assertEqual(a_trozos, self.politicas())
        self.assertEqual(len(a_trozos), 40)
        self.assertIn("sostenida", {p for _, p in a_trozos})

    def test_la_ventana_nueva_vuelve_sostenida_a_la_anterior(self):
        self.log.write_text(linea(1000, "10.10.20.30", "ALERT", -0.70)
                            + linea(1010, "10.10.20.30", "ALERT", -0.70), encoding="utf-8")
        self.assertEqual({p for _, p in self.politicas()}, {"suelta"})
        with self.log.open("a", encoding="utf-8") as fh:
            fh.write(linea(1020, "10.10.20.30", "ALERT", -0.70))
        self.assertEqual({p for _, p in self.politicas()}, {"sostenida"})

    def test_rotacion_empieza_de_cero(self):
        self.log.write_text(linea(1000, "a") + linea(1001, "b"), encoding="utf-8")
        self.assertEqual(len(self.politicas()), 2)
        self.log.write_text(linea(2000, "c"), encoding="utf-8")       # mas corto: rotado
        self.assertEqual([t for t, _ in self.politicas()], [2000])

    def test_tramo_por_bytes(self):
        filas = [linea(1000 + k, "x") for k in range(100)]
        self.log.write_bytes("".join(filas).encode("utf-8"))
        n = len(db.read_decisions(self.log, 10**6, max_bytes=len(filas[0]) * 10))
        self.assertIn(n, (10, 11))


if __name__ == "__main__":
    unittest.main()
