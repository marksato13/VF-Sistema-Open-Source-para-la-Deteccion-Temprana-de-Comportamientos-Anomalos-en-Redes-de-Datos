"""El catalogo de escenarios: contenido para copiar, nunca para ejecutar.

Se comprueba que carga normal/anomalo, que cada escenario trae lo que el panel
necesita (comando, explicacion, variables) y que el endpoint es de admin. El
catalogo real del repo tambien se valida, para que un JSON roto no llegue vivo.
"""

from __future__ import annotations

import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("dashboard", REPO / "scripts/engine/dashboard.py")
assert SPEC and SPEC.loader
dash = importlib.util.module_from_spec(SPEC)
sys.modules["dashboard"] = dash
SPEC.loader.exec_module(dash)

CATALOGO = REPO / "configs/escenarios.json"


class Catalogo(unittest.TestCase):
    def test_el_catalogo_del_repo_carga(self):
        d = dash.cargar_escenarios(CATALOGO)
        self.assertTrue(d["normal"], "sin escenarios normales")
        self.assertTrue(d["anomalo"], "sin escenarios anomalos")

    def test_cada_escenario_trae_lo_necesario(self):
        d = dash.cargar_escenarios(CATALOGO)
        for grupo in ("normal", "anomalo"):
            for esc in d[grupo]:
                for campo in ("id", "nombre", "explica", "comando", "variables", "responde"):
                    self.assertIn(campo, esc, "%s/%s falta %s" % (grupo, esc.get("id"), campo))
                self.assertTrue(esc["variables"], esc["id"])

    def test_incluye_los_ataques_probados(self):
        ids = {e["id"] for e in dash.cargar_escenarios(CATALOGO)["anomalo"]}
        for esperado in ("escaneo", "web", "fuerzabruta", "arpspoof"):
            self.assertIn(esperado, ids)

    def test_un_json_roto_no_rompe_el_panel(self):
        with tempfile.TemporaryDirectory() as t:
            p = Path(t) / "x.json"
            p.write_text("{ roto", encoding="utf-8")
            d = dash.cargar_escenarios(p)
            self.assertEqual(d, {"normal": [], "anomalo": []})

    def test_es_ruta_de_admin(self):
        self.assertIn("/api/escenarios", dash.RUTAS_ADMIN)


if __name__ == "__main__":
    unittest.main()
