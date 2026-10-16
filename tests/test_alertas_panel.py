"""Alertas, acciones vigentes y simulador del panel.

La regla de accion del panel tiene que ser la misma que la del publicador del
feed: si no, el panel avisaria de una cosa y el host aplicaria otra.
"""
from __future__ import annotations

import json
import sys
import tempfile
import time
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "scripts" / "engine"))
sys.path.insert(0, str(REPO / "scripts"))

import dashboard as db  # noqa: E402
import simular_ataque as sim  # noqa: E402


def dec(ip, t, decision="PERMIT", heur=None, det="if_recalibrado_2026_09", **kw):
    d = {"event": "decision", "entity_ip": ip, "logged_at": t, "decision": decision,
         "detector_name": det, "window_end_utc": "x%s" % t}
    if heur:
        d["heuristico"] = heur
    d.update(kw)
    return d


class ReglaDeAccion(unittest.TestCase):
    def test_bloqueo_por_regla_aunque_el_modelo_diga_permit(self):
        d = dec("10.10.20.30", 1, heur={"accion": "BLOCK", "heuristico": "port_scan", "motivo": "m"})
        self.assertEqual(db.accion_de(d)[0], "BLOCK")

    def test_anomalia_del_modelo_limita(self):
        self.assertEqual(db.accion_de(dec("1.1.1.1", 1, "ALERT"))[0], "LIMIT")

    def test_regla_legacy_bloquea_y_permit_no_pide_nada(self):
        self.assertEqual(db.accion_de(dec("1.1.1.1", 1, "ALERT", det="auth_failure_heuristic"))[0], "BLOCK")
        self.assertIsNone(db.accion_de(dec("1.1.1.1", 1)))

    def test_coincide_con_el_publicador(self):
        try:
            import publicar_feed
        except Exception as e:  # noqa: BLE001 - sin dependencias del feed
            self.skipTest("publicar_feed no importable: %s" % e)
        casos = [dec("a", 1, "ALERT"), dec("a", 1, "ALERT", det="x_heuristic"),
                 dec("a", 1, heur={"accion": "LIMIT", "heuristico": "dns_entropy", "motivo": ""}),
                 dec("a", 1, "ALERT", heur={"accion": "BLOCK", "heuristico": "port_scan", "motivo": ""}),
                 dec("a", 1)]
        for c in casos:
            p = publicar_feed._verdicto_de(c)
            a = db.accion_de(c)
            self.assertEqual(p[0] if p else None, a[0] if a else None, c)
        self.assertEqual(db.NUNCA_BLOQUEAR, publicar_feed.NUNCA_BLOQUEAR_POR_DEFECTO)


class AccionesVigentes(unittest.TestCase):
    def test_block_reciente_vigente_y_limit_viejo_caducado(self):
        ahora = 10_000.0
        v = db.acciones_vigentes([
            dec("10.10.20.30", ahora - 20, heur={"accion": "BLOCK", "heuristico": "port_scan", "motivo": "m"}),
            dec("10.10.20.30", ahora - 30, heur={"accion": "BLOCK", "heuristico": "port_scan", "motivo": "m"}),
            dec("10.10.20.34", ahora - 900, "ALERT"),
        ], ahora)
        self.assertEqual([x["ip"] for x in v], ["10.10.20.30"])
        self.assertEqual(v[0]["accion"], "BLOCK")
        self.assertEqual(v[0]["expira_s"], 300 + db.CADENCIA_FEED_S - 20)
        self.assertEqual(v[0]["ofensas"], 2)
        self.assertEqual(v[0]["fuente"], "registro")

    def test_nunca_bloquear_no_aparece(self):
        v = db.acciones_vigentes([dec("10.10.10.20", 99, heur={"accion": "LIMIT", "heuristico": "dns_entropy", "motivo": ""})], 100)
        self.assertEqual(v, [])

    def test_nivel_de_reincidencia_y_feed(self):
        with tempfile.TemporaryDirectory() as tmp:
            estado = Path(tmp) / "estado.json"
            estado.write_text(json.dumps({"10.10.20.30": {"bloqueos": 2, "ultimo_visto": 1}}))
            feed = Path(tmp) / "feed.json"
            feed.write_text(json.dumps({"entradas": [
                {"ip": "10.10.20.99", "accion": "LIMIT", "hasta": 1500, "motivo": "modelo:x",
                 "detector": "x", "nivel": 0, "revisar_humano": False}]}))
            v = db.acciones_vigentes(
                [dec("10.10.20.30", 1000, heur={"accion": "BLOCK", "heuristico": "port_scan", "motivo": ""})],
                1100, feed, estado)
        por = {x["ip"]: x for x in v}
        self.assertEqual(por["10.10.20.30"]["nivel"], 2)
        self.assertEqual(
            por["10.10.20.30"]["expira_s"],
            1000 + 1800 + db.CADENCIA_FEED_S - 1100,
        )
        self.assertEqual(por["10.10.20.99"]["fuente"], "feed")
        self.assertEqual(por["10.10.20.99"]["expira_s"], 400)

    def test_contadores_por_accion(self):
        ahora = time.time()
        c = db.compute_counters([
            dec("a", ahora - 5, heur={"accion": "BLOCK", "heuristico": "port_scan", "motivo": ""}),
            dec("b", ahora - 5, "ALERT"), dec("c", ahora - 5)], detector_modelo="if_recalibrado_2026_09")
        self.assertEqual((c["block"], c["limit"], c["ips_con_accion"]), (1, 1, 2))


class Simulador(unittest.TestCase):
    def test_se_niega_a_escribir_en_un_registro_real(self):
        with tempfile.TemporaryDirectory() as tmp:
            log = Path(tmp) / "motor_decision.log"
            log.write_text(json.dumps(dec("1.1.1.1", 1)) + "\n")
            self.assertEqual(sim.main(["--log", str(log), "--ventanas", "1", "--intervalo", "0"]), 2)
            self.assertEqual(len(log.read_text().splitlines()), 1)

    def test_cada_ataque_produce_la_accion_del_motor_de_reglas(self):
        esperado = {"escaneo": ("BLOCK", "port_scan"), "dns": ("LIMIT", "dns_entropy"),
                    "fuerza-bruta": ("BLOCK", "brute_force"), "http": ("LIMIT", "http_abuse"),
                    "modelo": ("LIMIT", "modelo")}
        with tempfile.TemporaryDirectory() as tmp:
            log = Path(tmp) / "demo.log"
            self.assertEqual(sim.main(["--log", str(log), "--ataque", "todos",
                                       "--ventanas", "2", "--intervalo", "0"]), 0)
            filas = [json.loads(l) for l in log.read_text(encoding="utf-8").splitlines()]
        self.assertTrue(all(f["demo"] and f["simulado"] for f in filas))
        for nombre, (acc, origen) in esperado.items():
            ip = sim.ATAQUES[nombre]["ip"]
            rafagas = [f for f in filas if f["entity_ip"] == ip and db.accion_de(f)]
            self.assertTrue(any(db.accion_de(f)[0] == acc and db.accion_de(f)[2] == origen
                                for f in rafagas), nombre)
        self.assertIsNone(db.accion_de(filas[0]))       # la ventana previa es normal


if __name__ == "__main__":
    unittest.main()
