"""port_scan no confunde una ráfaga web legítima con un escaneo (3-nov)."""
import unittest

from scripts.engine import heuristicos as h


def fila(fa, up, sc, http=0):
    return {"flow_attempt_count_30s": fa, "unique_dst_port_ratio_30s": up,
            "syn_completion_ratio_10s": sc, "http_request_count_60s": http,
            "http_auth_failure_ratio_60s": 0.0}


class PortScan(unittest.TestCase):
    def test_escaneo_con_ratio_tope_del_espejo_dispara_block(self):
        v = h.evaluar(fila(4189, 0.47, 0.0))
        self.assertEqual((v["heuristico"], v["accion"]), ("port_scan", "BLOCK"))

    def test_escaneo_corto_con_ratio_bajo_045_dispara_por_rafaga(self):
        v = h.evaluar(fila(600, 0.41, 0.0))
        self.assertEqual(v["heuristico"], "port_scan")

    def test_250_descargas_al_puerto_80_no_son_escaneo(self):
        # caso real del 3-nov: 252 intentos, 1 puerto, «0 % completados» por el espejo
        v = h.evaluar(fila(252, 1 / 252, 0.0, http=467))
        self.assertEqual((v["heuristico"], v["accion"]), ("http_abuse", "LIMIT"))

    def test_cliente_a_una_peticion_por_segundo_no_es_abuso(self):
        # medido 3-nov: 60 peticiones reales/min llegan como 111-122 eventos (espejo x2)
        self.assertIsNone(h.evaluar(fila(122, 1 / 122, 0.0, http=122)))

    def test_flood_de_la_demo_sigue_siendo_abuso(self):
        v = h.evaluar(fila(250, 1 / 250, 0.0, http=470))
        self.assertEqual((v["heuristico"], v["accion"]), ("http_abuse", "LIMIT"))

    def test_trafico_web_moderado_no_dispara_nada(self):
        self.assertIsNone(h.evaluar(fila(60, 1 / 60, 0.0, http=60)))


if __name__ == "__main__":
    unittest.main()
