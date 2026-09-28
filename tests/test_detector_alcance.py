"""El detector de alcance propone infraestructura con evidencia, no excluye."""

from __future__ import annotations

import importlib.util
import sys
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
RUTA = REPO / "scripts/dataset/detector_alcance.py"
SPEC = importlib.util.spec_from_file_location("detector_alcance", RUTA)
assert SPEC and SPEC.loader
det = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = det
SPEC.loader.exec_module(det)


def fila(ip, ventana, dst_ip=0.0, protos=0.0):
    return {"entity_ip": ip, "window_end_utc": ventana,
            "unique_dst_ip_ratio_30s": str(dst_ip), "protocol_diversity_30s": str(protos)}


class Deteccion(unittest.TestCase):
    def dataset(self):
        filas = []
        ventanas = ["2026-09-27T10:00:%02dZ" % s for s in range(0, 20)]
        for v in ventanas:
            # gateway .1: siempre presente, muchos destinos, varios protocolos
            filas.append(fila("10.10.20.1", v, dst_ip=0.8, protos=0.2))
            # cliente .21: presente a ratos, pocos destinos
            if int(v[-3:-1]) % 3 == 0:
                filas.append(fila("10.10.20.21", v, dst_ip=0.1, protos=0.0))
        return filas, len(ventanas)

    def test_el_gateway_sale_como_infraestructura(self):
        filas, tot = self.dataset()
        r = det.analizar(filas, tot)
        g = [e for e in r if e["ip"] == "10.10.20.1"][0]
        self.assertEqual(g["veredicto"], "infraestructura_probable")
        self.assertTrue(g["senales"])

    def test_el_cliente_no_sale_como_infraestructura(self):
        filas, tot = self.dataset()
        r = det.analizar(filas, tot)
        c = [e for e in r if e["ip"] == "10.10.20.21"][0]
        self.assertNotEqual(c["veredicto"], "infraestructura_probable")

    def test_ordena_por_evidencia(self):
        filas, tot = self.dataset()
        r = det.analizar(filas, tot)
        self.assertEqual(r[0]["ip"], "10.10.20.1")  # el mas sospechoso, primero

    def test_una_sola_senal_no_basta_para_infraestructura(self):
        # Solo el ultimo octeto .1 (1 punto) no debe bastar: evita auto-excluir
        # por una corazonada. Presencia baja, sin trafico raro.
        filas = [fila("10.10.30.1", "2026-09-27T10:00:00Z")]  # 1 de 5 ventanas
        r = det.analizar(filas, 5)
        self.assertEqual(r[0]["veredicto"], "indeterminado")


if __name__ == "__main__":
    unittest.main()
