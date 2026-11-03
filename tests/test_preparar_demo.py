"""Botón «Preparar demo»: panel -> petición -> feed firmado -> agente del host."""
import json
import tempfile
import unittest
from pathlib import Path

from scripts.engine import dashboard as db
from scripts.engine import publicar_feed as pf
from scripts.enforce import agente_enforce as ag


class Peticion(unittest.TestCase):
    def setUp(self):
        self.dir = Path(tempfile.mkdtemp())
        self.ruta = self.dir / "peticiones" / "preparar.json"

    def test_el_panel_deja_las_ips_de_la_demo(self):
        pet = db.pedir_preparacion(self.ruta, "admin", 1000.0)
        self.assertEqual(json.loads(self.ruta.read_text())["id"], pet["id"])
        self.assertEqual(pet["ips"], ["10.10.20.30", "10.10.20.21"])

    def test_el_publicador_la_mete_en_el_feed(self):
        pet = db.pedir_preparacion(self.ruta, "admin", 1000.0)
        lib = pf.liberaciones_pedidas(self.ruta, 1010.0)
        self.assertEqual([(x["id"], x["ip"]) for x in lib],
                         [(pet["id"], "10.10.20.30"), (pet["id"], "10.10.20.21")])

    def test_una_peticion_vieja_no_viaja(self):
        db.pedir_preparacion(self.ruta, "admin", 1000.0)
        self.assertEqual(pf.liberaciones_pedidas(self.ruta, 1000.0 + 601), [])

    def test_sin_peticion_no_hay_liberaciones(self):
        self.assertEqual(pf.liberaciones_pedidas(self.dir / "no.json", 1000.0), [])


class Agente(unittest.TestCase):
    FEED = {"liberaciones": [{"id": "abc", "ip": "10.10.20.30", "t": 1000.0},
                             {"id": "abc", "ip": "no-es-ip", "t": 1000.0}]}

    def test_aplica_una_vez(self):
        self.assertEqual(ag.liberaciones_nuevas(self.FEED, {}, 1020.0), [("abc", "10.10.20.30")])
        self.assertEqual(ag.liberaciones_nuevas(self.FEED, {"abc:10.10.20.30": 1020.0}, 1030.0), [])

    def test_caducada_o_futura_se_ignora(self):
        self.assertEqual(ag.liberaciones_nuevas(self.FEED, {}, 1000.0 + 601), [])
        self.assertEqual(ag.liberaciones_nuevas(self.FEED, {}, 1000.0 - 120), [])

    def test_feed_sin_liberaciones(self):
        self.assertEqual(ag.liberaciones_nuevas({"entradas": []}, {}, 1000.0), [])


class Estado(unittest.TestCase):
    def test_lista_con_motor_feed_agente_e_ips(self):
        d = Path(tempfile.mkdtemp())
        log = d / "motor.log"
        log.write_text("x")
        ahora = log.stat().st_mtime + 2
        pet = db.pedir_preparacion(d / "p.json", "admin", ahora - 20)
        (d / "feed.json").write_text(json.dumps({"generado": ahora - 3, "liberaciones": [{"id": pet["id"]}]}))
        (d / "ac").mkdir()
        (d / "ac" / "srv-dmz.json").write_text(json.dumps({
            "host": "srv-dmz", "generado": ahora - 2, "agente": "active", "reglas": {},
            "liberadas": {ip: {"desde": ahora - 10} for ip in db.DEMO_IPS}}))
        e = db.estado_preparacion(d / "p.json", log, d / "feed.json", d / "ac", ahora)
        self.assertTrue(e["listo"], e["checks"])

    def test_ip_con_regla_no_esta_lista(self):
        d = Path(tempfile.mkdtemp())
        log = d / "motor.log"
        log.write_text("x")
        ahora = log.stat().st_mtime + 2
        (d / "ac").mkdir()
        (d / "ac" / "srv-dmz.json").write_text(json.dumps({
            "host": "srv-dmz", "generado": ahora - 2, "agente": "active",
            "reglas": {"10.10.20.30": {"accion": "BLOCK"}}}))
        (d / "feed.json").write_text(json.dumps({"generado": ahora - 3}))
        e = db.estado_preparacion(d / "p.json", log, d / "feed.json", d / "ac", ahora)
        self.assertFalse(e["listo"])


if __name__ == "__main__":
    unittest.main()
