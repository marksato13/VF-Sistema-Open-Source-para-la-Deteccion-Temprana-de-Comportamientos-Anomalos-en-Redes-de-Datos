import unittest

from scripts.engine import heuristicos as h


def ventana(**kw):
    """Ventana base benigna; se sobreescriben features con kwargs."""
    base = {
        "http_request_count_60s": 0,
        "http_auth_failure_ratio_60s": 0.0,
        "flow_attempt_count_30s": 0,
        "unique_dst_port_ratio_30s": 0.0,
        "syn_completion_ratio_10s": 1.0,
        "dns_query_count_60s": 0,
        "dns_nxdomain_ratio_60s": 0.0,
        "unique_dns_name_ratio_60s": 0.0,
    }
    base.update(kw)
    return base


class VentanaBenigna(unittest.TestCase):
    def test_una_ventana_normal_no_dispara_nada(self):
        self.assertIsNone(h.evaluar(ventana()))

    def test_navegacion_normal_no_es_abuso(self):
        # 30 peticiones legítimas en 60 s, sin fallos de auth: por debajo de 100
        self.assertIsNone(h.evaluar(ventana(http_request_count_60s=30,
                                            http_auth_failure_ratio_60s=0.0)))


class FuerzaBruta(unittest.TestCase):
    def test_rafaga_de_401_es_block(self):
        v = h.evaluar(ventana(http_request_count_60s=40,
                              http_auth_failure_ratio_60s=0.95))
        self.assertIsNotNone(v)
        self.assertEqual(v["heuristico"], "brute_force")
        self.assertEqual(v["accion"], "BLOCK")

    def test_pocas_peticiones_no_disparan(self):
        self.assertIsNone(h.evaluar(ventana(http_request_count_60s=3,
                                            http_auth_failure_ratio_60s=1.0)))


class PortScan(unittest.TestCase):
    def test_muchos_puertos_pocos_completados_es_block(self):
        v = h.evaluar(ventana(flow_attempt_count_30s=50,
                              unique_dst_port_ratio_30s=0.9,
                              syn_completion_ratio_10s=0.1))
        self.assertIsNotNone(v)
        self.assertEqual(v["heuristico"], "port_scan")
        self.assertEqual(v["accion"], "BLOCK")

    def test_muchas_conexiones_completadas_no_es_scan(self):
        # muchos flujos pero todos completan: tráfico real, no escaneo
        self.assertIsNone(h.evaluar(ventana(flow_attempt_count_30s=50,
                                            unique_dst_port_ratio_30s=0.9,
                                            syn_completion_ratio_10s=0.95)))


class HttpAbuse(unittest.TestCase):
    def test_volumen_alto_sin_fallos_es_limit(self):
        v = h.evaluar(ventana(http_request_count_60s=500,
                              http_auth_failure_ratio_60s=0.0))
        self.assertIsNotNone(v)
        self.assertEqual(v["heuristico"], "http_abuse")
        self.assertEqual(v["accion"], "LIMIT")

    def test_volumen_alto_con_fallos_es_fuerza_bruta_no_abuso(self):
        # si además falla la auth, gana brute_force (BLOCK), más severo
        v = h.evaluar(ventana(http_request_count_60s=500,
                              http_auth_failure_ratio_60s=0.9))
        self.assertEqual(v["heuristico"], "brute_force")
        self.assertEqual(v["accion"], "BLOCK")


class DnsEntropy(unittest.TestCase):
    def test_muchos_nxdomain_es_limit(self):
        v = h.evaluar(ventana(dns_query_count_60s=40, dns_nxdomain_ratio_60s=0.8))
        self.assertIsNotNone(v)
        self.assertEqual(v["heuristico"], "dns_entropy")
        self.assertEqual(v["accion"], "LIMIT")

    def test_casi_todos_nombres_unicos_es_limit(self):
        v = h.evaluar(ventana(dns_query_count_60s=40, unique_dns_name_ratio_60s=0.95))
        self.assertEqual(v["heuristico"], "dns_entropy")

    def test_dns_normal_no_dispara(self):
        # pocas consultas, nombres repetidos: caché DNS normal
        self.assertIsNone(h.evaluar(ventana(dns_query_count_60s=5,
                                            unique_dns_name_ratio_60s=0.2)))


class Severidad(unittest.TestCase):
    def test_block_gana_a_limit(self):
        # dispara dns_entropy (LIMIT) y port_scan (BLOCK) a la vez -> BLOCK
        v = h.evaluar(ventana(flow_attempt_count_30s=50,
                              unique_dst_port_ratio_30s=0.9,
                              syn_completion_ratio_10s=0.1,
                              dns_query_count_60s=40,
                              dns_nxdomain_ratio_60s=0.9))
        self.assertEqual(v["accion"], "BLOCK")


class Configurable(unittest.TestCase):
    def test_umbral_a_medida_cambia_el_resultado(self):
        # con umbral por defecto (100) no es abuso; bajándolo a 10, sí
        v_normal = h.evaluar(ventana(http_request_count_60s=20))
        self.assertIsNone(v_normal)
        umbrales = {"http_abuse": {"min_http_req_60s": 10,
                                   "max_auth_fail_ratio_60s": 0.8,
                                   "accion": "LIMIT"}}
        v = h.evaluar(ventana(http_request_count_60s=20), umbrales)
        self.assertEqual(v["heuristico"], "http_abuse")

    def test_hay_version_de_umbrales(self):
        self.assertTrue(h.VERSION_UMBRALES)


if __name__ == "__main__":
    unittest.main()
