"""El grafico de Actividad no pinta LIMIT/BLOCK de la infraestructura protegida.

3-nov: el DNS 10.10.10.20 dispara dns_entropy (LIMIT) a diario; el motor lo
registra pero nunca se publica ni aplica. Los contadores ya lo excluian; el
grafico por minuto seguia mostrando barras amarillas.
"""
import sys
import time
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts" / "engine"))

import dashboard  # noqa: E402


class ActividadInfra(unittest.TestCase):
    def test_dns_protegido_no_cuenta_limit(self):
        ahora = time.time()
        dns = next(iter(sorted(dashboard.NUNCA_BLOQUEAR)))
        decs = [
            {"logged_at": ahora - 10, "decision": "PERMIT", "entity_ip": dns,
             "heuristico": {"accion": "LIMIT", "heuristico": "dns_entropy", "motivo": "x"}},
            {"logged_at": ahora - 10, "decision": "PERMIT", "entity_ip": "10.10.20.30",
             "heuristico": {"accion": "BLOCK", "heuristico": "port_scan", "motivo": "y"}},
        ]
        cubos = dashboard.bucket_by_minute(decs, minutes=5)
        self.assertEqual(sum(b["limit"] for b in cubos), 0)
        self.assertEqual(sum(b["block"] for b in cubos), 1)
        self.assertEqual(sum(b["permit"] for b in cubos), 2)


if __name__ == "__main__":
    unittest.main()
