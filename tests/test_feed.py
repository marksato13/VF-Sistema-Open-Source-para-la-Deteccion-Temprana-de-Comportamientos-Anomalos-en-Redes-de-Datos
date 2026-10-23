import os
import shutil
import tempfile
import unittest

from scripts.engine import feed as f

TIENE_OPENSSL = shutil.which("openssl") is not None


def entrada(ip, accion="BLOCK", hasta=2000, alcance="all", motivo="x", detector="d"):
    return {"ip": ip, "accion": accion, "hasta": hasta, "alcance": alcance,
            "motivo": motivo, "detector": detector}


class Construccion(unittest.TestCase):
    def test_serializacion_es_determinista_e_independiente_del_orden(self):
        a = f.construir([entrada("10.0.0.2"), entrada("10.0.0.1")], ahora=1000.0)
        b = f.construir([entrada("10.0.0.1"), entrada("10.0.0.2")], ahora=1000.0)
        self.assertEqual(f.serializar(a), f.serializar(b))

    def test_lleva_version_y_entradas(self):
        feed = f.construir([entrada("10.0.0.1")], ahora=1000.0, umbrales="v1")
        self.assertEqual(feed["version"], f.VERSION_FEED)
        self.assertEqual(feed["umbrales"], "v1")
        self.assertEqual(len(feed["entradas"]), 1)


@unittest.skipUnless(TIENE_OPENSSL, "requiere openssl")
class Firma(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.mkdtemp()
        self.priv = os.path.join(self.dir, "priv.pem")
        self.pub = os.path.join(self.dir, "pub.pem")
        f.generar_claves(self.priv, self.pub)

    def tearDown(self):
        shutil.rmtree(self.dir, ignore_errors=True)

    def test_genera_par_de_claves(self):
        self.assertTrue(os.path.exists(self.priv))
        self.assertTrue(os.path.exists(self.pub))
        # la privada es 0600
        self.assertEqual(os.stat(self.priv).st_mode & 0o777, 0o600)

    def test_firmar_y_verificar_roundtrip(self):
        datos = f.serializar(f.construir([entrada("10.0.0.1")], ahora=1000.0))
        firma = f.firmar(datos, self.priv)
        self.assertTrue(f.verificar(datos, firma, self.pub))

    def test_feed_manipulado_no_verifica(self):
        datos = f.serializar(f.construir([entrada("10.0.0.1")], ahora=1000.0))
        firma = f.firmar(datos, self.priv)
        manipulado = datos.replace(b"10.0.0.1", b"10.0.0.9")
        self.assertFalse(f.verificar(manipulado, firma, self.pub))

    def test_otra_clave_no_verifica(self):
        datos = f.serializar(f.construir([entrada("10.0.0.1")], ahora=1000.0))
        firma = f.firmar(datos, self.priv)
        otra_priv = os.path.join(self.dir, "otra.pem")
        otra_pub = os.path.join(self.dir, "otra.pub")
        f.generar_claves(otra_priv, otra_pub)
        self.assertFalse(f.verificar(datos, firma, otra_pub))


if __name__ == "__main__":
    unittest.main()
