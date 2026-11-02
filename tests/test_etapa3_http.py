"""Etapa 3, punto 5: vista HTTP (registros tardíos, copias) y confusiones entre reglas."""
from __future__ import annotations

import datetime as dt
import json
import sys
import unittest
from collections import namedtuple
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts" / "engine"))
import heuristicos  # noqa: E402
import http_heuristica as hh  # noqa: E402

P = namedtuple("P", "timestamp src_ip dst_ip src_port dst_port protocol")
ATK, SRV, CLI = "10.10.20.30", "10.10.30.10", "10.10.20.26"
T0 = 1793520000.0


def ev(t, src, sport, status=401, flow=None, tx=0, url="/auth", dport=18081):
    ts = dt.datetime.fromtimestamp(t, dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%f") + "+0000"
    return json.dumps({"timestamp": ts, "event_type": "http", "flow_id": flow or sport, "tx_id": tx,
                       "src_ip": src, "src_port": sport, "dest_ip": SRV, "dest_port": dport,
                       "http": {"url": url, "status": status, "http_method": "GET"}})


class Vista(unittest.TestCase):
    def test_transaccion_con_tramas_cuenta_y_registro_tardio_no(self):
        v = hh.VistaHttp()
        paquetes = []
        for i in range(10):                         # transacciones reales: tramas en el cable
            t = T0 + i
            paquetes += [P(t - 0.01, ATK, SRV, 40000 + i, 18081, 6), P(t, SRV, ATK, 18081, 40000 + i, 6)]
            v.linea(ev(t, ATK, 40000 + i))
        for i in range(30):                         # registros tardíos: flujos sin tramas recientes
            v.linea(ev(T0 + 20 + i * 0.5, ATK, 30000 + i))
            paquetes.append(P(T0 - 200, ATK, SRV, 30000 + i, 18081, 6))
        c = v.campos_por_entidad(T0 + 40, sorted(paquetes))[ATK]
        self.assertEqual(c["httph_peticiones_60s"], 10)
        self.assertEqual(c["httph_tardios_excluidos_60s"], 30)
        self.assertEqual(c["httph_fallo_auth_ratio_60s"], 1.0)

    def test_causal_no_usa_tramas_posteriores_al_fin_de_ventana(self):
        v = hh.VistaHttp()
        v.linea(ev(T0 + 9.9, ATK, 40000))
        c = v.campos_por_entidad(T0 + 10, [P(T0 + 10.5, ATK, SRV, 40000, 18081, 6)])[ATK]
        self.assertEqual(c["httph_peticiones_60s"], 0)      # la trama aún no existe al decidir
        c = v.campos_por_entidad(T0 + 10, [P(T0 + 9.8, ATK, SRV, 40000, 18081, 6)])[ATK]
        self.assertEqual(c["httph_peticiones_60s"], 1)

    def test_copias_del_espejo_cuentan_una_vez(self):
        v = hh.VistaHttp()
        v.linea(ev(T0, ATK, 40000, flow=7, tx=0))
        v.linea(ev(T0 + 0.0001, ATK, 40000, flow=7, tx=0))
        c = v.campos_por_entidad(T0 + 1, [P(T0, ATK, SRV, 40000, 18081, 6)])[ATK]
        self.assertEqual(c["httph_peticiones_60s"], 1)

    def test_ventana_y_poda(self):
        v = hh.VistaHttp()
        v.linea(ev(T0, ATK, 40000))
        pk = [P(T0, ATK, SRV, 40000, 18081, 6)]
        self.assertEqual(v.campos_por_entidad(T0 + 59.9, pk)[ATK]["httph_peticiones_60s"], 1)
        self.assertEqual(v.campos_por_entidad(T0 + 60, pk), {})
        v.podar(T0 + 1)
        self.assertEqual(v.campos_por_entidad(T0 + 30, pk), {})


class Reglas(unittest.TestCase):
    def fila(self, n, fallo, tardios=0, **extra):
        return dict({"httph_peticiones_60s": n, "httph_fallo_auth_ratio_60s": fallo,
                     "httph_tardios_excluidos_60s": tardios}, **extra)

    def test_sin_vista_http_no_disparan_las_reglas_http(self):
        self.assertIsNone(heuristicos.evaluar({"http_request_count_60s": 9000, "http_auth_failure_ratio_60s": 1.0}))

    def test_fuerza_bruta_e_inundacion_se_conservan(self):
        self.assertEqual(heuristicos.evaluar(self.fila(7900, 1.0))["heuristico"], "brute_force")
        self.assertEqual(heuristicos.evaluar(self.fila(18000, 0.0))["heuristico"], "http_abuse")

    def test_cliente_legitimo_con_su_pico_no_dispara(self):
        self.assertIsNone(heuristicos.evaluar(self.fila(117, 0.0)))     # pico de 10.10.20.26 en el 3B
        u = heuristicos.UMBRALES_POR_DEFECTO["http_abuse"]["min_http_req_60s"]
        self.assertIsNone(heuristicos.evaluar(self.fila(u - 1, 0.0)))
        self.assertIsNotNone(heuristicos.evaluar(self.fila(u, 0.0)))

    def test_solo_registros_tardios_no_disparan(self):
        self.assertIsNone(heuristicos.evaluar(self.fila(0, 0.0, tardios=300)))

    def test_cola_de_inundacion_no_es_escaneo(self):
        # ventana posterior a una inundación: sin SYN en 10 s (ratio 0 por división
        # segura), miles de intentos a UN puerto en 30 s
        fila = {"flow_attempt_count_30s": 1032, "unique_dst_port_ratio_30s": 0.001,
                "syn_completion_ratio_10s": 0.0}
        self.assertIsNone(heuristicos.evaluar(fila))

    def test_escaneo_breve_y_sostenido_siguen_disparando(self):
        breve = {"flow_attempt_count_30s": 2006, "unique_dst_port_ratio_30s": 0.499, "syn_completion_ratio_10s": 0.0}
        sost = {"flow_attempt_count_30s": 40000, "unique_dst_port_ratio_30s": 0.999, "syn_completion_ratio_10s": 0.0}
        self.assertEqual(heuristicos.evaluar(breve)["heuristico"], "port_scan")
        self.assertEqual(heuristicos.evaluar(sost)["heuristico"], "port_scan")


if __name__ == "__main__":
    unittest.main()
