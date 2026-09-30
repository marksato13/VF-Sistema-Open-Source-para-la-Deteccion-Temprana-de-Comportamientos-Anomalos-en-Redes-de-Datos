import unittest

from scripts.engine import escalada as e


class Escalera(unittest.TestCase):
    def test_limit_es_300_plano(self):
        st = {}
        v = e.procesar(st, "10.0.0.1", "LIMIT", ahora=1000.0)
        self.assertEqual(v["timeout_s"], 300)
        self.assertFalse(v["revisar_humano"])

    def test_bloqueos_escalan_300_1800_3600(self):
        st = {}
        v1 = e.procesar(st, "10.0.0.9", "BLOCK", ahora=1000.0)
        v2 = e.procesar(st, "10.0.0.9", "BLOCK", ahora=1100.0)
        v3 = e.procesar(st, "10.0.0.9", "BLOCK", ahora=1200.0)
        self.assertEqual((v1["timeout_s"], v2["timeout_s"], v3["timeout_s"]),
                         (300, 1800, 3600))

    def test_tope_no_pasa_de_3600_ni_hay_infinito(self):
        st = {}
        for i in range(6):
            v = e.procesar(st, "10.0.0.9", "BLOCK", ahora=1000.0 + i)
        self.assertEqual(v["timeout_s"], 3600)   # nunca crece a infinito

    def test_tercer_bloqueo_marca_revision_humana(self):
        st = {}
        e.procesar(st, "10.0.0.9", "BLOCK", ahora=1.0)
        e.procesar(st, "10.0.0.9", "BLOCK", ahora=2.0)
        v3 = e.procesar(st, "10.0.0.9", "BLOCK", ahora=3.0)
        self.assertTrue(v3["revisar_humano"])

    def test_decaimiento_reinicia_tras_la_ventana(self):
        st = {}
        e.procesar(st, "10.0.0.9", "BLOCK", ahora=1000.0)          # nivel 1
        # más de 24 h después: debe reiniciarse a 300
        v = e.procesar(st, "10.0.0.9", "BLOCK", ahora=1000.0 + 24 * 3600 + 1)
        self.assertEqual(v["timeout_s"], 300)
        self.assertEqual(v["nivel"], 1)

    def test_reincidencia_dentro_de_la_ventana_no_reinicia(self):
        st = {}
        e.procesar(st, "10.0.0.9", "BLOCK", ahora=1000.0)
        v = e.procesar(st, "10.0.0.9", "BLOCK", ahora=1000.0 + 23 * 3600)
        self.assertEqual(v["timeout_s"], 1800)

    def test_accion_invalida_falla(self):
        with self.assertRaises(ValueError):
            e.procesar({}, "10.0.0.1", "DROP", ahora=1.0)

    def test_podar_quita_las_viejas(self):
        st = {"10.0.0.1": {"bloqueos": 1, "ultimo_visto": 0.0},
              "10.0.0.2": {"bloqueos": 1, "ultimo_visto": 1_000_000.0}}
        quitadas = e.podar(st, ahora=1_000_000.0)
        self.assertEqual(quitadas, 1)
        self.assertIn("10.0.0.2", st)
        self.assertNotIn("10.0.0.1", st)


if __name__ == "__main__":
    unittest.main()
