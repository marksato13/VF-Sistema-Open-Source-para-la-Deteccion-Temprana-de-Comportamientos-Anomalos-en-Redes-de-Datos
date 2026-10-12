"""Evaluador de la comparacion con Suricata: protocolo y cifras publicadas."""
from __future__ import annotations

import copy
import json
import sys
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "scripts" / "evaluacion"))
import comparacion as cmp  # noqa: E402

DATOS = json.loads((REPO / "docs" / "evaluacion" / "comparacion-suricata.json").read_text(encoding="utf-8"))


class CifrasPublicadas(unittest.TestCase):
    """Las notas 26, 28 y 31 deben salir tal cual del evaluador."""

    def setUp(self):
        self.r = cmp.evaluar(DATOS)

    def test_total_sin_firma(self):
        t = self.r["sin_firma"]
        self.assertEqual([(t[c]["detectados"], t[c]["n"]) for c in cmp.CONDICIONES],
                         [(0, 9), (6, 9), (7, 9), (9, 9)])
        self.assertEqual((t["combinado"]["latencia_mediana_s"], t["combinado"]["latencia_min_s"],
                          t["combinado"]["latencia_max_s"]), (13.0, 4.0, 23.0))

    def test_por_familia(self):
        f = {x["familia"]: x for x in self.r["por_familia"]}
        self.assertEqual(f["dns"]["modelo"]["detectados"], 0)
        self.assertEqual(f["escaneo"]["heuristicos"]["detectados"], 1)
        self.assertTrue(f["nikto"]["con_firma"])
        self.assertEqual(f["nikto"]["suricata"]["latencia_mediana_s"], 3.4)
        self.assertEqual(f["nikto"]["heuristicos"]["n"], 0)          # no medido, no 0/1

    def test_falsos_positivos_en_su_unidad(self):
        fp = self.r["falsos_positivos"]
        self.assertEqual(fp["combinado"]["unidad"], "ventanas normales con acción")
        self.assertEqual((fp["combinado"]["valor"], fp["combinado"]["de"]), (0, 527))
        self.assertEqual(fp["suricata"]["valor"], "no medido")
        self.assertNotIn("F1", json.dumps(self.r))
        self.assertNotIn("precision", json.dumps(self.r))


class Protocolo(unittest.TestCase):
    def test_la_unidad_es_el_episodio(self):
        d = copy.deepcopy(DATOS)
        d["protocolo"]["unidad"] = "alerta"
        with self.assertRaises(cmp.EntradaInvalida):
            cmp.evaluar(d)

    def test_cyberflow_no_consume_alertas(self):
        d = copy.deepcopy(DATOS)
        d["protocolo"]["cyberflow"]["consume"] = "alertas de Suricata"
        with self.assertRaises(cmp.EntradaInvalida):
            cmp.evaluar(d)

    def test_el_codigo_del_motor_no_lee_alertas(self):
        """Lo que la entrada declara se comprueba en el codigo: los extractores y
        los heuristicos no leen event_type == alert."""
        for ruta in ("scripts/features/extract_multilayer_v2.py", "scripts/engine/heuristicos.py"):
            texto = (REPO / ruta).read_text(encoding="utf-8")
            self.assertNotIn('"alert"', texto, ruta)
            self.assertNotIn("'alert'", texto, ruta)

    def test_latencia_negativa_o_texto_raro_se_rechaza(self):
        for malo in (-1, "rapido"):
            d = copy.deepcopy(DATOS)
            d["episodios"][0]["detecciones"]["modelo"] = malo
            with self.assertRaises(cmp.EntradaInvalida):
                cmp.evaluar(d)

    def test_el_panel_lo_sirve_solo_al_admin(self):
        sys.path.insert(0, str(REPO / "scripts" / "engine"))
        import dashboard
        r = dashboard.estado_comparacion(None)
        self.assertNotIn("error", r)
        self.assertEqual(r["sin_firma"]["combinado"]["detectados"], 9)
        self.assertIn("/api/comparacion", dashboard.RUTAS_ADMIN)
        lector = dashboard.html_por_rol(dashboard.HTML, "lector")
        self.assertNotIn('id="s-comparacion"', lector)
        self.assertIn("error", dashboard.estado_comparacion(REPO / "no-existe.json"))

    def test_markdown_dice_no_medido(self):
        md = cmp.markdown(cmp.evaluar(DATOS))
        self.assertIn("no medido", md)
        self.assertIn("9/9 · 13 s [4–23]", md)


if __name__ == "__main__":
    unittest.main()
