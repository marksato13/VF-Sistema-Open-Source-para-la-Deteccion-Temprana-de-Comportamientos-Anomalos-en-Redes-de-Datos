"""Cierre de la Etapa 3, punto 4: herramienta de observación de varios días del DNS legítimo."""
from __future__ import annotations

import datetime as dt
import gzip
import json
import sys
import tempfile
import unittest
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ / "scripts" / "etapa3"))

import observacion_dns as obs  # noqa: E402

DC1 = "10.10.10.20"
T_DIA1 = dt.datetime(2026, 11, 3, 15, 0, tzinfo=dt.timezone.utc).timestamp()   # 10:00 en Lima
T_DIA2 = T_DIA1 + 86400


def iso(t):
    return dt.datetime.fromtimestamp(t, dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%f+0000")


def q(t, src, ident, proto="UDP", nombre="a.lab", dst=DC1, sport=5000):
    return {"timestamp": iso(t), "event_type": "dns", "src_ip": src, "src_port": sport, "dest_ip": dst,
            "dest_port": 53, "proto": proto, "dns": {"type": "query", "id": ident, "rrname": nombre, "rrtype": "A"}}


def ans(t, asker, ident, rcode="NOERROR", nombre="a.lab"):
    return {"timestamp": iso(t), "event_type": "dns", "src_ip": DC1, "src_port": 53, "dest_ip": asker,
            "dest_port": 5000, "proto": "UDP", "dns": {"type": "answer", "id": ident, "rrname": nombre,
                                                         "rrtype": "A", "rcode": rcode}}


class ObservacionDns(unittest.TestCase):
    def test_metricas_y_criterio(self):
        ev = []
        # dia 1: cliente normal, 1 consulta/min durante 1 h, una con NXDOMAIN
        for i in range(60):
            ev.append(q(T_DIA1 + 60 * i, "10.10.20.21", i, nombre="n%d.lab" % i))
        ev.append(ans(T_DIA1 + 1, "10.10.20.21", 0, "NXDOMAIN", "n0.lab"))
        # copia del espejo de la primera consulta (< 5 ms): no cuenta
        ev.append(q(T_DIA1 + 0.001, "10.10.20.21", 0, nombre="n0.lab"))
        # el resolvedor reenviando hacia fuera: no es un origen cliente
        ev.append(q(T_DIA1 + 2, DC1, 77, dst="8.8.8.8"))
        # dia 2: arranque con 25 consultas en 1 s (supera la rafaga 18) y una por TCP
        for i in range(25):
            ev.append(q(T_DIA2 + i * 0.04, "10.10.50.10", 100 + i, nombre="s%d.lab" % i))
        ev.append(q(T_DIA2 + 5, "10.10.50.10", 999, proto="TCP", nombre="grande.lab"))
        # el atacante de una campana se excluye de la medida legitima
        ev.append(q(T_DIA2 + 7, "10.10.20.30", 1))
        with tempfile.TemporaryDirectory() as d:
            p1 = Path(d) / "eve-1.json"
            # compacto, como lo escribe Suricata (la atribución filtra por '"event_type":"dns"')
            p1.write_bytes("".join(json.dumps(e, separators=(",", ":")) + "\n" for e in ev[:63]).encode())
            p2 = Path(d) / "eve-2.json.gz"
            with gzip.open(p2, "wb") as fh:
                fh.write("".join(json.dumps(e, separators=(",", ":")) + "\n" for e in ev[63:]).encode())
            sal = Path(d) / "s.json"
            self.assertEqual(obs.main([str(sal), str(p1), str(p2), "--excluir", "10.10.20.30"]), 0)
            r = json.loads(sal.read_text(encoding="utf-8"))
        self.assertEqual(r["copias_espejo_descartadas"], 1)
        self.assertEqual(r["resumen"]["dias"], ["2026-11-03", "2026-11-04"])
        c = r["por_dia"]["2026-11-03"]["10.10.20.21"]
        self.assertEqual((c["udp"], c["tcp"], c["max_60s"], c["descartes_simulados"], c["nxdomain"]), (60, 0, 1, 0, 1))
        self.assertNotIn(DC1, r["por_dia"]["2026-11-03"])
        s = r["por_dia"]["2026-11-04"]["10.10.50.10"]
        self.assertEqual((s["udp"], s["tcp"], s["max_1s"]), (25, 1, 25))
        self.assertGreater(s["b_minima"], 18)
        self.assertEqual(s["descartes_simulados"], 7)        # 25 - 18 (la tasa repone < 1 en 1 s)
        self.assertNotIn("10.10.20.30", r["por_dia"]["2026-11-04"])
        self.assertFalse(r["resumen"]["P1_cumple"])
        self.assertEqual(r["resumen"]["P1_incumplimientos"], [["2026-11-04", "10.10.50.10", 7]])
        self.assertEqual(r["resumen"]["origenes_con_tcp53"], ["10.10.50.10"])
        self.assertEqual(r["cubeta"], {"tasa_por_s": 0.5, "rafaga": 18.0, "solo": "udp dport 53"})


if __name__ == "__main__":
    unittest.main()
