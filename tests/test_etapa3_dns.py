"""Etapa 3, punto 4: vista DNS de los heurísticos (copias del espejo, reenvíos, NXDOMAIN)."""
from __future__ import annotations

import datetime as dt
import json
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts" / "engine"))
import dns_heuristica as dh  # noqa: E402
import heuristicos  # noqa: E402

DC1, SUP, CLI, ATK = "10.10.10.20", "10.10.10.1", "10.10.20.22", "10.10.20.30"
T0 = 1793520000.0


def ev(t, src, dst, nombre, tipo="query", id_=1, sport=40000, rcode=None, rrtype="A"):
    d = {"type": tipo, "id": id_, "rrname": nombre, "rrtype": rrtype}
    if rcode:
        d["rcode"] = rcode
    ts = dt.datetime.fromtimestamp(t, dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%f") + "+0000"
    return json.dumps({"timestamp": ts, "event_type": "dns", "src_ip": src, "src_port": sport,
                       "dest_ip": dst, "dest_port": 53, "proto": "UDP", "dns": d})


class Vista(unittest.TestCase):
    def test_copias_del_espejo_cuentan_una_vez(self):
        v = dh.VistaDns()
        for i in range(10):
            v.linea(ev(T0 + i, CLI, DC1, "n%d.x" % i, id_=i))
            v.linea(ev(T0 + i + 0.0001, CLI, DC1, "n%d.x" % i, id_=i))   # copia VLAN destino
        self.assertEqual(v.campos(CLI, T0 + 30)["dnsh_consultas_60s"], 10)
        self.assertEqual(v.copias, 10)

    def test_reintento_no_es_copia(self):
        v = dh.VistaDns()
        v.linea(ev(T0, CLI, DC1, "a.x"))
        v.linea(ev(T0 + 1.0, CLI, DC1, "a.x"))   # reintento a 1 s: es otra consulta en el cable
        self.assertEqual(v.campos(CLI, T0 + 5)["dnsh_consultas_60s"], 2)

    def test_reenvio_del_resolvedor_no_cuenta_y_su_nxdomain_tampoco(self):
        v = dh.VistaDns()
        for i in range(40):
            t = T0 + i
            v.linea(ev(t, CLI, DC1, "h%d.francos-sac.com" % i, id_=i, sport=5000 + i))
            v.linea(ev(t + 0.01, DC1, SUP, "h%d.francos-sac.com" % i, id_=900 + i, sport=7000 + i))
            v.linea(ev(t + 0.05, DC1, SUP, "h%d.francos-sac.com" % i, "answer", 900 + i, 7000 + i, "NXDOMAIN"))
            v.linea(ev(t + 0.06, CLI, DC1, "h%d.francos-sac.com" % i, "answer", i, 5000 + i, "NOERROR"))
        c = v.campos(DC1, T0 + 45)
        self.assertEqual(c["dnsh_consultas_60s"], 0)
        self.assertEqual(c["dnsh_reenvios_excluidos_60s"], 40)
        self.assertIsNone(heuristicos.evaluar(dict(c)))
        cc = v.campos(CLI, T0 + 45)
        self.assertEqual(cc["dnsh_consultas_60s"], 40)
        self.assertEqual(cc["dnsh_nxdomain_ratio_60s"], 0.0)   # el cliente recibió NOERROR

    def test_consultas_propias_del_resolvedor_siguen_contando(self):
        v = dh.VistaDns()
        for i in range(35):
            v.linea(ev(T0 + i, DC1, SUP, "r%d.raro" % i, id_=i, sport=6000 + i))
            v.linea(ev(T0 + i + 0.02, DC1, SUP, "r%d.raro" % i, "answer", i, 6000 + i, "NXDOMAIN"))
        c = v.campos(DC1, T0 + 40)
        self.assertEqual(c["dnsh_consultas_60s"], 35)
        self.assertEqual(c["dnsh_nxdomain_ratio_60s"], 1.0)
        fila = dict(c)
        self.assertEqual(heuristicos.evaluar(fila)["heuristico"], "dns_entropy")

    def test_causal_consulta_del_resolvedor_anterior_al_cliente_es_propia(self):
        v = dh.VistaDns()
        v.linea(ev(T0, DC1, SUP, "a.x", id_=1))
        v.linea(ev(T0 + 0.5, CLI, DC1, "a.x", id_=2))
        v.linea(ev(T0 + 5.0, DC1, SUP, "b.x", id_=3))      # cliente preguntó b.x hace > delta
        v.linea(ev(T0 + 1.0, CLI, DC1, "b.x", id_=4))
        c = v.campos(DC1, T0 + 10)
        self.assertEqual(c["dnsh_consultas_60s"], 2)

    def test_mismo_nombre_otro_tipo_no_es_reenvio(self):
        v = dh.VistaDns()
        v.linea(ev(T0, CLI, DC1, "a.x", rrtype="A"))
        v.linea(ev(T0 + 0.1, DC1, SUP, "a.x", rrtype="AAAA", id_=9))
        self.assertEqual(v.campos(DC1, T0 + 1)["dnsh_consultas_60s"], 1)

    def test_ventana_y_poda(self):
        v = dh.VistaDns()
        v.linea(ev(T0, CLI, DC1, "a.x"))
        v.linea(ev(T0 + 70, CLI, DC1, "b.x", id_=2))
        # misma semántica que el extractor: (fin - 60, fin]
        self.assertEqual(v.campos(CLI, T0 + 59.9)["dnsh_consultas_60s"], 1)
        self.assertEqual(v.campos(CLI, T0 + 60)["dnsh_consultas_60s"], 0)
        self.assertEqual(v.campos(CLI, T0)["dnsh_consultas_60s"], 1)
        self.assertEqual(v.campos(CLI, T0 + 75)["dnsh_consultas_60s"], 1)
        v.podar(T0 + 10)
        self.assertEqual(v.campos(CLI, T0 + 59.9)["dnsh_consultas_60s"], 0)
        self.assertEqual(v.campos(CLI, T0 + 75)["dnsh_consultas_60s"], 1)

    def test_lineas_no_dns_se_ignoran(self):
        v = dh.VistaDns()
        v.linea('{"event_type":"http","timestamp":"2026-11-01T08:00:00.000000+0000"}')
        v.linea(b"no json")
        self.assertEqual(v.consultas, {})


class Regla(unittest.TestCase):
    def test_sin_vista_no_dispara_aunque_las_caracteristicas_del_if_si(self):
        fila = {"dns_query_count_60s": 200, "dns_nxdomain_ratio_60s": 1.0, "unique_dns_name_ratio_60s": 1.0}
        self.assertIsNone(heuristicos.evaluar(fila))

    def test_dga_dispara_y_cliente_legitimo_hexadecimal_no(self):
        v = dh.VistaDns()
        for i in range(140):       # 2,3 consultas/s con nombres aleatorios (escenario dns_inusual)
            v.linea(ev(T0 + i / 2.3, ATK, DC1, "%016x.lab-ppi" % (i * 7919), id_=i, sport=30000 + i))
        for i in range(19):        # peor legítimo del 3B: 19 consultas/60 s, subdominios hexadecimales
            v.linea(ev(T0 + i * 3, CLI, DC1, "%012x.francos-sac.com" % i, id_=i, sport=20000 + i))
        r = heuristicos.evaluar(v.campos(ATK, T0 + 60))
        self.assertEqual((r["heuristico"], r["accion"]), ("dns_entropy", "LIMIT"))
        self.assertIsNone(heuristicos.evaluar(v.campos(CLI, T0 + 60)))

    def test_umbral_justo(self):
        u = heuristicos.UMBRALES_POR_DEFECTO["dns_entropy"]
        base = {"dnsh_nxdomain_ratio_60s": 0.0, "dnsh_nombres_unicos_ratio_60s": 1.0, "dnsh_reenvios_excluidos_60s": 0}
        self.assertIsNone(heuristicos.evaluar(dict(base, dnsh_consultas_60s=u["min_consultas_60s"] - 1)))
        self.assertIsNotNone(heuristicos.evaluar(dict(base, dnsh_consultas_60s=u["min_consultas_60s"])))
        self.assertIsNone(heuristicos.evaluar(dict(base, dnsh_consultas_60s=100, dnsh_nombres_unicos_ratio_60s=0.5)))


if __name__ == "__main__":
    unittest.main()
