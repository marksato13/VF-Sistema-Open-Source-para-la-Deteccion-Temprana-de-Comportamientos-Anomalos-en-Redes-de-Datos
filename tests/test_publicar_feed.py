import unittest

from scripts.engine import publicar_feed as pf


def dec(ip, decision="ALERT", detector="ocsvm_scaled"):
    return {"event": "decision", "entity_ip": ip, "decision": decision,
            "detector_name": detector, "logged_at": 1000.0}


class DecisionesAEntradas(unittest.TestCase):
    def setUp(self):
        self.nunca = pf.NUNCA_BLOQUEAR_POR_DEFECTO

    def test_alerta_del_modelo_es_limit(self):
        ent = pf.decisiones_a_entradas([dec("10.10.20.30")], {}, 1000.0, self.nunca)
        self.assertEqual(len(ent), 1)
        self.assertEqual(ent[0]["accion"], "LIMIT")
        self.assertEqual(ent[0]["hasta"], 1000 + 300)

    def test_alerta_de_heuristico_es_block(self):
        ent = pf.decisiones_a_entradas(
            [dec("10.10.20.30", detector="auth_failure_heuristic")], {}, 1000.0, self.nunca)
        self.assertEqual(ent[0]["accion"], "BLOCK")

    def test_permit_se_ignora(self):
        ent = pf.decisiones_a_entradas([dec("10.10.20.30", decision="PERMIT")],
                                       {}, 1000.0, self.nunca)
        self.assertEqual(ent, [])

    def test_nunca_bloquear_se_salta(self):
        ent = pf.decisiones_a_entradas([dec("10.10.60.11")], {}, 1000.0, self.nunca)
        self.assertEqual(ent, [])

    def test_gana_el_mas_severo_por_ip(self):
        # misma IP con ALERT del modelo (LIMIT) y de heurístico (BLOCK) -> BLOCK
        ent = pf.decisiones_a_entradas(
            [dec("10.10.20.30"), dec("10.10.20.30", detector="auth_failure_heuristic")],
            {}, 1000.0, self.nunca)
        self.assertEqual(len(ent), 1)
        self.assertEqual(ent[0]["accion"], "BLOCK")

    def test_campo_heuristico_block(self):
        d = dec("10.10.20.30", decision="PERMIT")
        d["heuristico"] = {"heuristico": "port_scan", "accion": "BLOCK", "motivo": "x"}
        ent = pf.decisiones_a_entradas([d], {}, 1000.0, self.nunca)
        self.assertEqual(ent[0]["accion"], "BLOCK")
        self.assertEqual(ent[0]["detector"], "port_scan")

    def test_heuristico_limit_con_modelo_limit_es_limit(self):
        d = dec("10.10.20.30", decision="ALERT")   # modelo -> LIMIT
        d["heuristico"] = {"heuristico": "http_abuse", "accion": "LIMIT", "motivo": "x"}
        ent = pf.decisiones_a_entradas([d], {}, 1000.0, self.nunca)
        self.assertEqual(ent[0]["accion"], "LIMIT")

    def test_heuristico_block_gana_a_modelo_limit(self):
        d = dec("10.10.20.30", decision="ALERT")   # modelo -> LIMIT
        d["heuristico"] = {"heuristico": "brute_force", "accion": "BLOCK", "motivo": "x"}
        ent = pf.decisiones_a_entradas([d], {}, 1000.0, self.nunca)
        self.assertEqual(ent[0]["accion"], "BLOCK")

    def test_reincidencia_escala_el_timeout(self):
        estado = {}
        e1 = pf.decisiones_a_entradas([dec("10.10.20.30", detector="x_heuristic")],
                                      estado, 1000.0, self.nunca)
        e2 = pf.decisiones_a_entradas([dec("10.10.20.30", detector="x_heuristic")],
                                      estado, 1100.0, self.nunca)
        self.assertEqual(e1[0]["hasta"], 1000 + 300)
        self.assertEqual(e2[0]["hasta"], 1100 + 1800)


class VersionDeUmbrales(unittest.TestCase):
    """La etiqueta del feed debe describir las reglas del código instalado."""

    def test_sin_argumento_usa_la_del_codigo(self):
        v, aviso = pf.version_umbrales("")
        self.assertEqual(v, pf.heuristicos.VERSION_UMBRALES)
        self.assertIsNone(aviso)

    def test_argumento_coincidente_no_avisa(self):
        v, aviso = pf.version_umbrales(pf.heuristicos.VERSION_UMBRALES)
        self.assertEqual(v, pf.heuristicos.VERSION_UMBRALES)
        self.assertIsNone(aviso)

    def test_argumento_viejo_avisa_y_gana_el_codigo(self):
        # El caso real de Sensor1: la unidad pasaba 2026-10-06.1 con el motor en .2.
        v, aviso = pf.version_umbrales("2026-10-06.1")
        self.assertEqual(v, pf.heuristicos.VERSION_UMBRALES)
        self.assertIn("2026-10-06.1", aviso)


if __name__ == "__main__":
    unittest.main()
