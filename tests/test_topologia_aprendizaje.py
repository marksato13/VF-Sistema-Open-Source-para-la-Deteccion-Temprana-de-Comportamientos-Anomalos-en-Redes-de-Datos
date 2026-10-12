"""La fila del aprendizaje supervisado en la vista «Construcción y entrenamiento».

Cada nodo nuevo tiene su texto en el detalle, su estado en vivo y sus ficheros en
«Ver archivos»: un nodo sin las tres cosas seria un dibujo, no una vista.
"""
from __future__ import annotations

import re
import sys
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "scripts" / "engine"))

import dashboard  # noqa: E402

NODOS = ["c_vivo", "a_oro", "a_san", "a_lin", "a_der", "a_inf", "a_ver", "a_hum"]


class FilaAprendizaje(unittest.TestCase):
    def test_cada_nodo_tiene_texto_estado_y_ficheros(self):
        html = dashboard.HTML
        construccion = html[html.index("construccion: {"):html.index("let topoVista")]
        for n in NODOS:
            self.assertIn("id: '%s'" % n, construccion, n)
            self.assertRegex(html, r"\n  %s: \{" % n)                 # TOPO_TEXTO
        self.assertIn("case 'a_oro': case 'a_san'", html)             # estado en vivo
        with tempfile.TemporaryDirectory() as tmp:
            r = Path(tmp)
            m = dashboard.estado_artefactos(r / "eve.json", None, r / "manifest.json",
                                            r / "motor.log", None, r / "d.json", raiz=r)
        for n in NODOS + ["reentrenamiento"]:
            self.assertTrue(m.get(n), n)
        self.assertFalse(m["a_oro"][0]["existe"])                     # no se inventa nada

    def test_ya_no_dice_politica_propuesta(self):
        self.assertNotIn("POLÍTICA PROPUESTA", dashboard.HTML)
        self.assertNotIn("id: 'c_reent'", dashboard.HTML)

    def test_las_aristas_unen_nodos_que_existen(self):
        html = dashboard.HTML
        construccion = html[html.index("construccion: {"):html.index("let topoVista")]
        ids = set(re.findall(r"id: '([a-z_]+)'", construccion))
        for desde, hasta in re.findall(r"desde: '([a-z_]+)',\s*hasta: '([a-z_]+)'", construccion):
            self.assertIn(desde, ids)
            self.assertIn(hasta, ids)


if __name__ == "__main__":
    unittest.main()
