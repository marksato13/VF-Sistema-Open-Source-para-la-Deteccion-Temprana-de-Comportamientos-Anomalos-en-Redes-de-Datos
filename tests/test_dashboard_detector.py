"""El panel muestra el MISMO detector que el motor aunque la unidad no se lo pase.

Regresión: la unidad de Sensor1 no pasaba --detector-name y el panel caía a
`ocsvm_scaled`, mostrando las cifras del OCSVM mientras el motor ejecutaba el
Isolation Forest recalibrado.
"""
from __future__ import annotations

import importlib.util
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
_spec = importlib.util.spec_from_file_location("dashboard_detector", REPO / "scripts/engine/dashboard.py")
dashboard = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(dashboard)


def raiz_con(local: str | None, generico: str | None) -> tempfile.TemporaryDirectory:
    t = tempfile.TemporaryDirectory()
    configs = Path(t.name) / "configs"
    configs.mkdir()
    if local is not None:
        (configs / "cyberflow.local.toml").write_text(local, encoding="utf-8")
    if generico is not None:
        (configs / "cyberflow.toml").write_text(generico, encoding="utf-8")
    return t


class ResolverDetector(unittest.TestCase):
    def test_el_argumento_explicito_manda(self):
        with raiz_con('[motor]\ndetector = "if_local"\n', None) as t:
            self.assertEqual(dashboard.resolver_detector("if_cli", Path(t))[0], "if_cli")

    def test_sin_argumento_usa_el_detector_del_perfil_local(self):
        with raiz_con('[motor]\ndetector = "if_recalibrado_2026_09"\n',
                      '[motor]\nmodo = "observacion"\n') as t:
            det, fuente = dashboard.resolver_detector(None, Path(t))
        self.assertEqual(det, "if_recalibrado_2026_09")
        self.assertIn("cyberflow.local.toml", fuente)

    def test_el_local_gana_al_generico(self):
        with raiz_con('[motor]\ndetector = "if_local"\n', '[motor]\ndetector = "if_generico"\n') as t:
            self.assertEqual(dashboard.resolver_detector(None, Path(t))[0], "if_local")

    def test_sin_detector_declarado_cae_al_valor_por_omision(self):
        # Igual que el generador: mot.get("detector", "ocsvm_scaled").
        with raiz_con(None, '[motor]\nmodo = "observacion"\n') as t:
            self.assertEqual(dashboard.resolver_detector(None, Path(t))[0], "ocsvm_scaled")

    def test_toml_roto_no_tumba_el_panel(self):
        with raiz_con("esto no es toml [[[", '[motor]\ndetector = "if_generico"\n') as t:
            self.assertEqual(dashboard.resolver_detector(None, Path(t))[0], "if_generico")


if __name__ == "__main__":
    unittest.main()
