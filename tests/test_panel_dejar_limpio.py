"""«Dejar limpio» (cadena v2, 16-nov): control D5 que el publicador consume."""
import importlib.util
import json
import sys
import tempfile
import time
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "scripts/engine"))
spec = importlib.util.spec_from_file_location("dash_limpio", REPO / "scripts/engine/dashboard.py")
dash = importlib.util.module_from_spec(spec)
spec.loader.exec_module(dash)


class DejarLimpio(unittest.TestCase):
    def setUp(self):
        self.d = Path(tempfile.mkdtemp())
        (self.d / "solicitudes").mkdir()
        self.ctl = self.d / "control.json"
        self.feed = self.d / "feed.json"

    def test_deja_control_con_el_formato_del_publicador(self):
        r = dash.pedir_limpieza_v2(self.ctl, "mark", 1.0)
        self.assertTrue(r["ok"])
        c = json.loads(self.ctl.read_text(encoding="utf-8"))
        self.assertEqual((c["accion"], c["origen"], c["id"]), ("reset_origen", "10.10.20.30", r["id"]))
        self.assertTrue((self.d / "solicitudes" / (r["id"] + ".json")).exists())

    def test_no_pisa_un_control_pendiente(self):
        dash.pedir_limpieza_v2(self.ctl, "mark", 1.0)
        r = dash.pedir_limpieza_v2(self.ctl, "mark", 2.0)
        self.assertFalse(r["ok"])

    def test_estado_solo_acepta_el_acuse_de_esa_peticion(self):
        ahora = time.time()
        self.ctl.with_name("control.json.ack").write_text(json.dumps({"id": "otro", "ok": True}), encoding="utf-8")
        self.feed.write_text(json.dumps({"entradas": [{"ip": "10.10.20.30", "hasta": ahora + 60}]}), encoding="utf-8")
        e = dash.estado_limpieza_v2(self.ctl, self.feed, "abc", ahora)
        self.assertIsNone(e["ack"])
        self.assertTrue(e["kali_en_feed"])
        self.ctl.with_name("control.json.ack").write_text(json.dumps({"id": "abc", "ok": True}), encoding="utf-8")
        self.feed.write_text(json.dumps({"entradas": []}), encoding="utf-8")
        e = dash.estado_limpieza_v2(self.ctl, self.feed, "abc", ahora)
        self.assertTrue(e["ack"]["ok"])
        self.assertFalse(e["kali_en_feed"])

    def test_feed_ilegible_no_es_limpio(self):
        e = dash.estado_limpieza_v2(self.ctl, self.feed, "abc", time.time())
        self.assertIsNone(e["kali_en_feed"])


if __name__ == "__main__":
    unittest.main()
