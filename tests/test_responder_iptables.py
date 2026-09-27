"""El responder: alerta sostenida, lista de seguridad e interlock de calibracion.

La prueba que mas importa es la del interlock: con un modelo sin calibrar el
motor alerta el 92 % de las ventanas, asi que aplicar bloqueo seria una
denegacion de servicio autoinfligida. El responder debe NEGARSE a aplicar en ese
caso, aunque se pida --aplicar.
"""

from __future__ import annotations

import importlib.util
import ipaddress
import json
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
RUTA = REPO / "scripts/engine/responder_iptables.py"
SPEC = importlib.util.spec_from_file_location("responder_iptables", RUTA)
assert SPEC and SPEC.loader
r = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = r
SPEC.loader.exec_module(r)


def linea(ip, t, decision="ALERT", det="ocsvm_scaled"):
    return json.dumps({"event": "decision", "entity_ip": ip, "decision": decision,
                       "detector_name": det, "logged_at": t})


class ListaDeSeguridad(unittest.TestCase):
    def test_gateways_y_dns_nunca(self):
        for ip in ("10.10.20.1", "10.10.30.2", "10.10.40.254", "10.10.10.20"):
            self.assertTrue(r.es_infraestructura(ipaddress.ip_address(ip)), ip)

    def test_un_host_normal_no_es_infraestructura(self):
        for ip in ("10.10.20.30", "10.10.30.10", "10.10.20.21"):
            self.assertFalse(r.es_infraestructura(ipaddress.ip_address(ip)), ip)


class Politica(unittest.TestCase):
    def registro(self, filas):
        d = tempfile.mkdtemp()
        p = Path(d) / "m.log"
        p.write_text("\n".join(filas) + "\n", encoding="utf-8")
        return p

    def test_alerta_sostenida_si_ventana_suelta_no(self):
        ahora = time.time()
        filas = [linea("10.10.20.30", ahora - i) for i in range(8)]   # 8 alertas
        filas += [linea("10.10.20.99", ahora - 1)]                     # 1 alerta
        datos = r.parse_registro(self.registro(filas), ahora - 60, "ocsvm_scaled")
        cand = r.candidatos(datos, minimo=6, redes_fuera=[])
        ips = [c["ip"] for c in cand]
        self.assertIn("10.10.20.30", ips)      # sostenida
        self.assertNotIn("10.10.20.99", ips)   # una sola, es ruido

    def test_no_cuenta_permit_ni_otro_detector(self):
        ahora = time.time()
        filas = [linea("10.10.20.30", ahora - i, decision="PERMIT") for i in range(9)]
        filas += [linea("10.10.20.30", ahora - i, det="auth_heuristic") for i in range(9)]
        datos = r.parse_registro(self.registro(filas), ahora - 60, "ocsvm_scaled")
        self.assertEqual(r.candidatos(datos, 6, []), [])

    def test_fuera_de_ventana_no_cuenta(self):
        ahora = time.time()
        filas = [linea("10.10.20.30", ahora - 500 - i) for i in range(9)]  # viejas
        datos = r.parse_registro(self.registro(filas), ahora - 60, "ocsvm_scaled")
        self.assertEqual(r.candidatos(datos, 6, []), [])

    def test_respeta_excluir(self):
        ahora = time.time()
        filas = [linea("10.10.60.11", ahora - i) for i in range(9)]
        datos = r.parse_registro(self.registro(filas), ahora - 60, "ocsvm_scaled")
        fuera = [ipaddress.ip_network("10.10.60.11/32")]
        self.assertEqual(r.candidatos(datos, 6, fuera), [])


class InterlockDeCalibracion(unittest.TestCase):
    """Con --aplicar pero sin calibrar, NO se aplica: modo seco + rechazo."""

    def correr(self, *args):
        d = tempfile.mkdtemp()
        p = Path(d) / "m.log"
        ahora = time.time()
        p.write_text("\n".join(linea("10.10.20.30", ahora - i) for i in range(8)) + "\n",
                     encoding="utf-8")
        out = subprocess.run(
            [sys.executable, str(RUTA), "--registro", str(p), *args],
            capture_output=True, text=True)
        return json.loads(out.stdout)

    def test_sin_calibrar_con_aplicar_se_niega(self):
        inf = self.correr("--aplicar", "--calibrado", "false")
        self.assertEqual(inf["modo"], "seco")
        self.assertIn("rechazado", inf)
        self.assertEqual(inf["n_candidatos"], 1)   # detecta, pero no aplica

    def test_seco_por_omision(self):
        inf = self.correr("--calibrado", "true")
        self.assertEqual(inf["modo"], "seco")
        self.assertNotIn("rechazado", inf)

    def test_candidato_detectado_igual(self):
        # Aunque no aplique, la deteccion se ve: es lo que se ejecuta en seco
        # contra el registro real para decidir antes de dar poder de corte.
        inf = self.correr("--calibrado", "false")
        self.assertEqual([c["ip"] for c in inf["candidatos"]], ["10.10.20.30"])


if __name__ == "__main__":
    unittest.main()
