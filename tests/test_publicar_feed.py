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

    def test_reincidencia_escala_el_timeout(self):
        estado = {}
        e1 = pf.decisiones_a_entradas([dec("10.10.20.30", detector="x_heuristic")],
                                      estado, 1000.0, self.nunca)
        e2 = pf.decisiones_a_entradas([dec("10.10.20.30", detector="x_heuristic")],
                                      estado, 1100.0, self.nunca)
        self.assertEqual(e1[0]["hasta"], 1000 + 300)
        self.assertEqual(e2[0]["hasta"], 1100 + 1800)


if __name__ == "__main__":
    unittest.main()
