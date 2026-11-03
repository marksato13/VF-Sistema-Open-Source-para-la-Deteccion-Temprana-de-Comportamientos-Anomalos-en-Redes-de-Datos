"""Acuse de aplicacion del host y paso 5 del escenario en el panel."""
import json
import sys
import tempfile
import time
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "scripts" / "engine"))
sys.path.insert(0, str(REPO / "scripts" / "enforce"))
import acuse_aplicacion as ac  # noqa: E402
import dashboard as dash  # noqa: E402

NFT = [{"metainfo": {}},
       {"set": {"name": "cyberflow_bloqueados", "elem": [{"elem": {"val": "10.10.20.30", "expires": 120}}]}},
       {"set": {"name": "cyberflow_limitados", "elem": [{"elem": {"val": "10.10.20.21", "expires": 40}},
                                                         {"elem": {"val": "10.10.20.30", "expires": 9}}]}},
       {"set": {"name": "otro_set", "elem": ["10.0.0.1"]}}]


class Reglas(unittest.TestCase):
    def test_lee_los_dos_sets_y_block_gana(self):
        r = ac.reglas_de_nft(NFT)
        self.assertEqual(r["10.10.20.30"], {"accion": "BLOCK", "expira_en": 120})
        self.assertEqual(r["10.10.20.21"]["accion"], "LIMIT")
        self.assertNotIn("10.0.0.1", r)

    def test_tabla_vacia(self):
        self.assertEqual(ac.reglas_de_nft([]), {})


class Transiciones(unittest.TestCase):
    def test_aplicada_cambiada_retirada(self):
        antes = {"a": {"accion": "LIMIT"}, "b": {"accion": "BLOCK"}}
        ahora = {"a": {"accion": "BLOCK"}, "c": {"accion": "LIMIT"}}
        ev = {e["ip"]: e for e in ac.transiciones(antes, ahora, 5.0)}
        self.assertEqual(ev["a"]["evento"], "cambiada")
        self.assertEqual(ev["b"]["evento"], "retirada")
        self.assertEqual(ev["c"]["evento"], "aplicada")

    def test_liberacion_se_registra_una_vez(self):
        lib = {"10.10.20.30": {"desde": 100.0, "gracia": 120}}
        doc, h = ac.acuse({}, None, lib, None, "active", {}, 110.0, "srv")
        doc2, _ = ac.acuse({}, None, lib, None, "active", h, 120.0, "srv")
        self.assertEqual([e["evento"] for e in doc2["eventos"]], ["liberada"])
        self.assertEqual(doc["liberadas"]["10.10.20.30"]["gracia_hasta"], 220.0)

    def test_error_de_nft_no_borra_el_historial(self):
        h = {"reglas": {"a": {"accion": "BLOCK"}}, "eventos": [{"t": 1, "ip": "a", "evento": "aplicada"}]}
        doc, h2 = ac.acuse({}, "nft: OSError", {}, None, "active", h, 10.0, "srv")
        self.assertEqual(h2, h)
        self.assertEqual(doc["error"], "nft: OSError")

    def test_caducidad_absoluta(self):
        doc, _ = ac.acuse({"a": {"accion": "BLOCK", "expira_en": 30}}, None, {}, None, "active", {}, 1000.0, "srv")
        self.assertEqual(doc["reglas"]["a"]["expira"], 1030.0)


class PasoCinco(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.ahora = time.time()
        self.log = self.tmp / "motor.log"
        self.log.write_text("", encoding="utf-8")
        self.acuses = self.tmp / "acuses"
        self.acuses.mkdir()

    def escribir(self, doc):
        (self.acuses / "srv-dmz.json").write_text(json.dumps(doc), encoding="utf-8")

    def test_regla_y_eventos_de_la_ip_desde_t0(self):
        self.escribir({"host": "srv-dmz", "generado": self.ahora - 4, "agente": "active",
                       "reglas": {"10.10.20.30": {"accion": "BLOCK", "expira": self.ahora + 300}},
                       "eventos": [{"t": self.ahora - 900, "ip": "10.10.20.30", "evento": "aplicada"},
                                   {"t": self.ahora - 20, "ip": "10.10.20.30", "evento": "aplicada", "accion": "BLOCK"},
                                   {"t": self.ahora - 20, "ip": "10.10.20.21", "evento": "aplicada"}]})
        r = dash.estado_escenario(self.log, "10.10.20.30", str(self.ahora - 60), self.ahora, None, None, self.acuses)
        a = r["aplicacion"][0]
        self.assertEqual(a["regla"]["accion"], "BLOCK")
        self.assertEqual(len(a["eventos"]), 1)
        self.assertFalse(a["atrasado"])

    def test_acuse_viejo_queda_atrasado(self):
        self.escribir({"host": "srv-dmz", "generado": self.ahora - 120, "reglas": {}})
        r = dash.estado_escenario(self.log, "10.10.20.30", "", self.ahora, None, None, self.acuses)
        self.assertTrue(r["aplicacion"][0]["atrasado"])

    def test_sin_directorio_de_acuses(self):
        r = dash.estado_escenario(self.log, "10.10.20.30", "", self.ahora, None, None)
        self.assertIsNone(r["aplicacion"])

    def test_acuse_corrupto_se_ignora(self):
        (self.acuses / "x.json").write_text("{no", encoding="utf-8")
        r = dash.estado_escenario(self.log, "10.10.20.30", "", self.ahora, None, None, self.acuses)
        self.assertEqual(r["aplicacion"], [])


if __name__ == "__main__":
    unittest.main()
