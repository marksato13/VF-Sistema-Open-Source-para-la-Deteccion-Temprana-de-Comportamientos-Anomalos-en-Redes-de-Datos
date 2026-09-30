import os
import shutil
import tempfile
import unittest

from scripts.engine import feed
from scripts.enforce import agente_enforce as ag

TIENE_OPENSSL = shutil.which("openssl") is not None


def feed_con(entradas, ahora=1000.0):
    return feed.construir(entradas, ahora=ahora)


class Vigentes(unittest.TestCase):
    def test_descarta_caducadas(self):
        f = {"entradas": [{"ip": "10.10.20.30", "accion": "BLOCK", "hasta": 900}]}
        self.assertEqual(ag.vigentes(f, ahora=1000.0, nunca=set()), {})

    def test_mantiene_vigentes(self):
        f = {"entradas": [{"ip": "10.10.20.30", "accion": "BLOCK", "hasta": 1300}]}
        v = ag.vigentes(f, ahora=1000.0, nunca=set())
        self.assertEqual(v["10.10.20.30"]["accion"], "BLOCK")

    def test_salta_nunca_bloquear(self):
        f = {"entradas": [{"ip": "10.10.60.1", "accion": "BLOCK", "hasta": 1300}]}
        self.assertEqual(ag.vigentes(f, 1000.0, {"10.10.60.1"}), {})

    def test_gana_el_mas_severo_por_ip(self):
        f = {"entradas": [
            {"ip": "10.10.20.30", "accion": "LIMIT", "hasta": 1300},
            {"ip": "10.10.20.30", "accion": "BLOCK", "hasta": 1300}]}
        v = ag.vigentes(f, 1000.0, set())
        self.assertEqual(v["10.10.20.30"]["accion"], "BLOCK")


class PlanNftables(unittest.TestCase):
    def test_crea_sets_y_flush(self):
        cmds = ag.plan_nftables({}, ahora=1000.0)
        texto = " ".join(" ".join(c) for c in cmds)
        self.assertIn("add table inet cyberflow", texto)
        self.assertIn(ag.SET_BLOCK, texto)
        self.assertIn("flush set inet cyberflow " + ag.SET_BLOCK, texto)

    def test_block_va_al_set_con_timeout(self):
        vig = {"10.10.20.30": {"accion": "BLOCK", "hasta": 1300}}
        cmds = ag.plan_nftables(vig, ahora=1000.0)
        texto = " ".join(" ".join(c) for c in cmds)
        self.assertIn("10.10.20.30 timeout 300s", texto)
        self.assertIn("element inet cyberflow " + ag.SET_BLOCK, texto)

    def test_limit_va_a_su_set(self):
        vig = {"10.10.20.9": {"accion": "LIMIT", "hasta": 1200}}
        cmds = ag.plan_nftables(vig, ahora=1000.0)
        texto = " ".join(" ".join(c) for c in cmds)
        self.assertIn("element inet cyberflow " + ag.SET_LIMIT, texto)
        self.assertIn("10.10.20.9 timeout 200s", texto)


@unittest.skipUnless(TIENE_OPENSSL, "requiere openssl")
class VerificacionFirma(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.mkdtemp()
        self.priv = os.path.join(self.dir, "priv.pem")
        self.pub = os.path.join(self.dir, "pub.pem")
        feed.generar_claves(self.priv, self.pub)

    def tearDown(self):
        shutil.rmtree(self.dir, ignore_errors=True)

    def test_firma_valida_devuelve_feed(self):
        datos = feed.serializar(feed_con([{"ip": "10.10.20.30", "accion": "BLOCK",
                                           "hasta": 1300}]))
        firma = feed.firmar(datos, self.priv)
        self.assertIsNotNone(ag.verificar_feed(datos, firma, self.pub))

    def test_firma_invalida_devuelve_none_failsafe(self):
        datos = feed.serializar(feed_con([{"ip": "10.10.20.30", "accion": "BLOCK",
                                           "hasta": 1300}]))
        firma = feed.firmar(datos, self.priv)
        manipulado = datos.replace(b"BLOCK", b"PERMIT")
        self.assertIsNone(ag.verificar_feed(manipulado, firma, self.pub))


if __name__ == "__main__":
    unittest.main()
