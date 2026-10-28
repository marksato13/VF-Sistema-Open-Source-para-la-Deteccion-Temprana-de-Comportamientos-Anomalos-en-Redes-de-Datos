"""Revision de la GUI del 28-oct: estados de respuesta, consulta por periodo y
textos que no deben afirmar lo que el panel no sabe.

El panel corre en el sensor: sabe que el motor DECIDIO una accion y si esta en
el feed que publico, pero no si el host la aplico. Ningun texto ni campo debe
mezclar esos tres estados.
"""
from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "scripts" / "engine"))

import dashboard as db  # noqa: E402


def dec(ip, t, decision="PERMIT", heur=None, det="if_limpio_2026_10"):
    d = {"event": "decision", "entity_ip": ip, "logged_at": t, "decision": decision,
         "detector_name": det, "window_end_utc": "x%s" % t}
    if heur:
        d["heuristico"] = heur
    return d


class EstadosDeRespuesta(unittest.TestCase):
    def test_registrada_publicada_y_ultima_renovacion(self):
        with tempfile.TemporaryDirectory() as tmp:
            feed = Path(tmp) / "feed.json"
            feed.write_text(json.dumps({"entradas": [
                {"ip": "10.10.20.30", "accion": "BLOCK", "hasta": 5000, "detector": "port_scan"},
                {"ip": "10.10.20.99", "accion": "LIMIT", "hasta": 5000, "detector": "modelo"}]}))
            v = db.acciones_vigentes([
                dec("10.10.20.30", 1000, heur={"accion": "BLOCK", "heuristico": "port_scan", "motivo": ""}),
                dec("10.10.20.30", 1060, heur={"accion": "BLOCK", "heuristico": "port_scan", "motivo": ""}),
                dec("10.10.20.31", 1050, "ALERT"),
            ], 1100, feed)
        por = {x["ip"]: x for x in v}
        # En el registro y en el feed.
        self.assertTrue(por["10.10.20.30"]["registrada"])
        self.assertTrue(por["10.10.20.30"]["publicada"])
        self.assertEqual(por["10.10.20.30"]["desde"], 1000)
        self.assertEqual(por["10.10.20.30"]["ultima"], 1060)
        # Solo en el registro: decidida pero aun no vista en el feed.
        self.assertTrue(por["10.10.20.31"]["registrada"])
        self.assertFalse(por["10.10.20.31"]["publicada"])
        # Solo en el feed: publicada sin decision en el tramo leido.
        self.assertFalse(por["10.10.20.99"]["registrada"])
        self.assertTrue(por["10.10.20.99"]["publicada"])
        # Ningun campo afirma la aplicacion en el host.
        for x in v:
            self.assertNotIn("aplicada", x)

    def test_salud_no_dice_respuesta_activa(self):
        s = db.resumen_salud("live", {"ppi-motor.service": True},
                             {"block": 1, "limit": 2, "alert_model": 2, "alert_auth_heuristic": 0},
                             {}, {"calibrado_en_esta_red": True})
        self.assertNotIn("respuesta activa", s["msg"])
        self.assertIn("LIMIT/BLOCK", s["msg"])
        self.assertIn("Respuestas", s["sub"])


class ConsultaPorPeriodo(unittest.TestCase):
    def _log(self, tmp, tiempos):
        p = Path(tmp) / "motor.log"
        p.write_text("\n".join(json.dumps(dec("10.0.0.%d" % (i % 3), t)) for i, t in enumerate(tiempos))
                     + "\n" + json.dumps({"event": "motor_startup", "logged_at": 1}) + "\n",
                     encoding="utf-8")
        return p

    def test_selecciona_por_logged_at_con_extremos_incluidos(self):
        with tempfile.TemporaryDirectory() as tmp:
            r = db.consultar_periodo(self._log(tmp, [100, 200, 300, 400]), 200, 300)
        self.assertEqual([d["logged_at"] for d in r["decisiones"]], [300, 200])
        self.assertEqual(r["total"], 2)
        self.assertFalse(r["truncado"])
        self.assertEqual((r["registro_desde"], r["registro_hasta"]), (100, 400))

    def test_tope_de_filas_se_declara(self):
        with tempfile.TemporaryDirectory() as tmp:
            r = db.consultar_periodo(self._log(tmp, list(range(10, 60))), None, None, limite=5)
        self.assertEqual(r["total"], 50)
        self.assertTrue(r["truncado"])
        self.assertEqual(len(r["decisiones"]), 5)
        self.assertEqual(r["decisiones"][0]["logged_at"], 59)

    def test_periodo_anterior_al_registro_se_puede_detectar(self):
        with tempfile.TemporaryDirectory() as tmp:
            r = db.consultar_periodo(self._log(tmp, [500, 600]), 100, 700)
        # El panel compara registro_desde con desde para avisar del hueco.
        self.assertGreater(r["registro_desde"], r["desde"])


class TextosServidos(unittest.TestCase):
    def setUp(self):
        self.admin = db.html_por_rol(db.HTML, "admin")

    def test_vacio_filtrado_no_deduce_permit(self):
        self.assertNotIn("el sistema está en PERMIT", self.admin)
        self.assertIn("No hay alertas de reglas en los registros cargados", self.admin)

    def test_respuestas_no_se_presentan_como_bloqueos_aplicados(self):
        self.assertNotIn("IPs bloqueadas ahora", self.admin)
        self.assertIn("Respuestas registradas como vigentes", self.admin)
        self.assertIn("La aplicación en el host no se verifica desde esta vista", self.admin)

    def test_umbral_vigente_e_historico_separados(self):
        self.assertNotIn("&minus;0,5689</strong>", self.admin)
        self.assertIn("if_limpio_2026_10", self.admin)
        self.assertIn("histórico, hasta 19-oct", self.admin)

    def test_modo_y_relay_y_guia(self):
        self.assertIn("Promoción con aprobación humana", self.admin)
        self.assertNotIn("alertas reales", self.admin)
        inv = json.loads((REPO / "docs/evaluacion/despliegue.json").read_text(encoding="utf-8"))
        self.assertNotIn("tonto", json.dumps(inv, ensure_ascii=False).lower())

    def test_alcance_visible_en_modo_operativo(self):
        script = self.admin.split("<script>", 1)[1]
        linea = next(l for l in script.splitlines() if l.startswith("const DEV_SECS"))
        self.assertNotIn("s-alcance", linea)


if __name__ == "__main__":
    unittest.main()
