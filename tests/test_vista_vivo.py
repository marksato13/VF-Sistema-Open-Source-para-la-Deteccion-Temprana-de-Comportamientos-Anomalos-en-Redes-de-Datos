"""«Datos en vivo»: cada trama y cada evento con la variable real que alimentan.

Se construye un PCAP y un eve.json pequeños y se comprueba que la vista pasa por
la misma cadena que el motor (plano de control fuera, copias del espejo fuera,
atribución al iniciador, entidades excluidas fuera) y que el valor que muestra
para cada variable es el de la fila de build_rows, no uno recalculado aparte.
"""

import importlib.util
import json
import os
import socket
import struct
import sys
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "scripts" / "engine"))
import vista_vivo  # noqa: E402

spec = importlib.util.spec_from_file_location("dashboard_vivo", REPO / "scripts/engine/dashboard.py")
dashboard = importlib.util.module_from_spec(spec)
spec.loader.exec_module(dashboard)

T0 = 1_760_054_501.0          # dentro de una ventana [..500, ..510]
CLIENTE, SERVIDOR, EXCLUIDA = "10.10.20.21", "10.10.30.10", "10.10.20.99"
MAC_C, MAC_S = bytes.fromhex("005056aa0001"), bytes.fromhex("005056bb0002")


def _ipv4(src, dst, proto, payload, ttl=64, ip_id=1):
    total = 20 + len(payload)
    cab = struct.pack("!BBHHHBBH4s4s", 0x45, 0, total, ip_id, 0, ttl, proto, 0,
                      socket.inet_aton(src), socket.inet_aton(dst))
    return cab + payload


def _tcp(sport, dport, seq, flags, datos=b""):
    return struct.pack("!HHIIBBHHH", sport, dport, seq, 0, 5 << 4, flags, 65535, 0, 0) + datos


def _eth(dst, src, cuerpo, vlan=20, tipo=0x0800):
    return dst + src + struct.pack("!HHH", 0x8100, vlan, tipo) + cuerpo


def _arp(mac, spa, tpa):
    return struct.pack("!HHBBH6s4s6s4s", 1, 0x0800, 6, 4, 1, mac, socket.inet_aton(spa),
                       b"\x00" * 6, socket.inet_aton(tpa))


def _pcap(ruta, tramas):
    with open(ruta, "wb") as fh:
        fh.write(struct.pack("<IHHiIII", 0xA1B2C3D4, 2, 4, 0, 0, 65535, 1))
        for ts, frame in tramas:
            seg = int(ts)
            fh.write(struct.pack("<IIII", seg, int(round((ts - seg) * 1e6)), len(frame), len(frame)))
            fh.write(frame)


def _iso(ts):
    return datetime.fromtimestamp(ts, timezone.utc).isoformat()


class VistaVivo(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        raiz = Path(cls.tmp.name)
        anillo = raiz / "anillo"
        anillo.mkdir()
        c2s = lambda cuerpo, **k: _eth(MAC_S, MAC_C, _ipv4(CLIENTE, SERVIDOR, 6, cuerpo, **k))
        s2c = lambda cuerpo, **k: _eth(MAC_C, MAC_S, _ipv4(SERVIDOR, CLIENTE, 6, cuerpo, **k))
        tramas = [
            (T0 + 0.10, c2s(_tcp(40000, 80, 1000, 0x02), ip_id=10)),               # SYN
            (T0 + 0.1002, c2s(_tcp(40000, 80, 1000, 0x02), ttl=63, ip_id=10)),     # copia del espejo
            (T0 + 0.20, s2c(_tcp(80, 40000, 5000, 0x12), ip_id=20)),               # SYN-ACK
            (T0 + 0.30, c2s(_tcp(40000, 80, 1001, 0x10), ip_id=11)),               # ACK puro
            (T0 + 0.40, c2s(_tcp(40000, 80, 1001, 0x18, b"x" * 100), ip_id=12)),   # datos
            (T0 + 0.60, c2s(_tcp(40000, 80, 1001, 0x18, b"x" * 100), ip_id=13)),   # retransmisión
            (T0 + 0.70, _eth(MAC_S, MAC_C, _ipv4("10.10.20.2", "224.0.0.18", 112, b"\x00" * 20))),  # CARP
            (T0 + 0.80, _eth(MAC_S, MAC_C, _ipv4(EXCLUIDA, SERVIDOR, 6, _tcp(41000, 22, 1, 0x02)))),
            (T0 + 0.90, _eth(b"\xff" * 6, MAC_C, _arp(MAC_C, CLIENTE, "10.10.20.1"), tipo=0x0806)),
        ]
        _pcap(anillo / "live-0001.pcap", tramas)
        _pcap(anillo / "live-0002.pcap", [])          # el que tcpdump está escribiendo
        ahora = os.stat(anillo / "live-0001.pcap").st_mtime + 1

        eve = raiz / "eve.json"
        base = {"src_ip": CLIENTE, "src_port": 40001, "dest_ip": SERVIDOR, "dest_port": 80,
                "vlan": [20], "flow_id": 77}
        eventos = [
            dict(base, timestamp=_iso(T0 + 1), event_type="flow"),
            dict(base, timestamp=_iso(T0 + 2), event_type="http",
                 http={"http_method": "post", "status": 401}),
            dict(base, timestamp=_iso(T0 + 3), event_type="dns", dest_port=53,
                 dns={"type": "query", "rrname": "noexiste.example"}),
            dict(base, timestamp=_iso(T0 + 3.1), event_type="dns", dest_port=53,
                 dns={"type": "answer", "rrname": "noexiste.example", "rcode": "NXDOMAIN"}),
            dict(base, timestamp=_iso(T0 + 4), event_type="tls", dest_port=443,
                 tls={"version": "TLS 1.3"}),
            dict(base, timestamp=_iso(T0 + 5), event_type="http", src_ip=EXCLUIDA,
                 http={"http_method": "GET", "status": 200}),
        ]
        eve.write_text("".join(json.dumps(e) + "\n" for e in eventos), encoding="utf-8")

        cls.cfg = {"red_entidades": "10.10.0.0/16", "excluir": [EXCLUIDA + "/32"],
                   "excluir_protocolos": [112, 240], "directorio": str(anillo),
                   "anillo_glob": "live-*.pcap", "fuente": "prueba"}
        cls.r = vista_vivo.calcular(eve, cls.cfg, ahora=ahora)
        cls.todos = vista_vivo.calcular(eve, cls.cfg, ahora=ahora, todos=True)

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def _fila(self, evento):
        filas = [t for t in self.r["tramas"] if t["evento"] == evento]
        self.assertEqual(len(filas), 1, [t["evento"] for t in self.r["tramas"]])
        return filas[0]

    @staticmethod
    def _f(fila, nombre):
        return next(f for f in fila["features"] if f["feature"] == nombre)

    def test_misma_cadena_que_el_motor(self):
        p = self.r["pcap"]
        self.assertEqual(p["ficheros"], ["live-0001.pcap"])   # el último no se lee
        self.assertEqual(p["plano_control"], 1)
        self.assertEqual(p["duplicados_espejo"], 1)
        self.assertEqual(p["entidad_excluida"], 1)
        self.assertEqual(p["sin_emparejar"], 0)
        self.assertNotIn(EXCLUIDA, {t["entidad"] for t in self.r["tramas"]})

    def test_trama_lleva_vlan_mac_y_su_origen(self):
        syn = self._fila("SYN")
        self.assertEqual((syn["vlan"], syn["mac_src"]), (20, "00:50:56:aa:00:01"))
        self.assertEqual((syn["entidad"], syn["sentido"]), (CLIENTE, "enviada"))
        self.assertEqual(syn["fuente"], {"fichero": "live-0001.pcap", "trama": 1})
        self.assertEqual(syn["ventana_fin"], _iso(1_760_054_510))

    def test_el_syn_ack_se_atribuye_al_cliente(self):
        sa = self._fila("SYN-ACK")
        self.assertEqual((sa["entidad"], sa["sentido"]), (CLIENTE, "recibida"))
        self.assertEqual(self._f(sa, "syn_completion_ratio_10s")["aporte"], "+1 completado")

    def test_valor_es_el_de_build_rows(self):
        syn = self._fila("SYN")
        self.assertEqual(self._f(syn, "syn_completion_ratio_10s")["valor"], 1.0)
        self.assertEqual(self._f(syn, "syn_rate_10s")["valor"], 0.1)          # 1 SYN / 10 s
        self.assertEqual(self._f(syn, "flow_attempt_count_30s")["uso"], "conteo")
        retr = self._fila("PSH-ACK retransmisión")
        self.assertEqual(self._f(retr, "tcp_retransmission_ratio_10s")["valor"], 0.5)

    def test_filtro_solo_tramas_que_aportan(self):
        self.assertNotIn("ACK", [t["evento"] for t in self.r["tramas"]])
        self.assertIn("ACK", [t["evento"] for t in self.todos["tramas"]])

    def test_arp_alimenta_capa_2_fuera_del_scoring(self):
        arp = self._fila("ARP petición")
        self.assertEqual(self._f(arp, "arp_request_rate_10s")["uso"], "capa 2 (fuera del scoring)")

    def test_eventos_eve(self):
        e = self.r["eve"]
        self.assertEqual(e["ignorados"].get("flow"), 1)
        tipos = {x["evento"]: x for x in self.r["eventos"]}
        http = tipos["HTTP POST 401"]
        self.assertEqual(self._f(http, "http_auth_failure_ratio_60s")["valor"], 1.0)
        self.assertEqual(http["fuente"]["fichero"], "eve.json")
        self.assertIn("DNS respuesta NXDOMAIN", tipos)
        self.assertEqual(self._f(tipos["DNS respuesta NXDOMAIN"], "dns_nxdomain_ratio_60s")["valor"], 1.0)
        self.assertIn("TLS TLS 1.3", tipos)
        self.assertNotIn(EXCLUIDA, {x["entidad"] for x in self.r["eventos"]})

    def test_matriz_de_trazabilidad(self):
        m = {f["feature"]: f for f in vista_vivo.matriz_trazabilidad()}
        usos = [f["uso"] for f in m.values()]
        self.assertEqual(usos.count("modelo"), 28)
        self.assertEqual(usos.count("solo extractor v3 (capa 2, fuera del scoring)"), 3)
        self.assertIn("port_scan", m["unique_dst_port_ratio_30s"]["heuristicos"])
        self.assertIn("brute_force", m["http_auth_failure_ratio_60s"]["heuristicos"])
        self.assertEqual(m["dns_query_rate_60s"]["fuente"], "eve.json")
        self.assertTrue(all(f["registro"] for f in m.values()))

    def test_config_lee_el_toml_del_motor(self):
        with tempfile.TemporaryDirectory() as tmp:
            raiz = Path(tmp)
            (raiz / "configs").mkdir()
            (raiz / "configs" / "cyberflow.local.toml").write_text(
                '[red]\nred_entidades = "10.10.0.0/16"\nexcluir = ["10.10.60.11/32"]\n'
                'excluir_protocolos = [112, 240]\n[captura]\ndirectorio = "/x"\n', encoding="utf-8")
            cfg = vista_vivo.config(raiz)
            self.assertEqual(cfg["excluir"], ["10.10.60.11/32"])
            self.assertEqual(cfg["fuente"], "configs/cyberflow.local.toml")
            self.assertEqual(vista_vivo.config(raiz, directorio="/y")["directorio"], "/y")

    def test_rutas_solo_admin_y_seccion_recortada(self):
        self.assertTrue({"/api/vivo", "/api/vivo/flujo", "/api/trazabilidad"} <= dashboard.RUTAS_ADMIN)
        self.assertNotIn('id="s-vivo"', dashboard.html_por_rol(dashboard.HTML, "lector"))
        self.assertIn('id="s-vivo"', dashboard.html_por_rol(dashboard.HTML, "admin"))

    def test_flujo_usa_las_mismas_claves_que_el_motor(self):
        # La fila provisional se confirma cruzándola con /api/vivo: fichero#trama
        # y byte de eve.json tienen que coincidir.
        eve = Path(self.cfg["directorio"]).parent / "eve.json"
        f = vista_vivo.flujo(eve, self.cfg, {"pf": "live-0001.pcap", "po": 0, "pn": 0, "eo": 0},
                             todos=True)
        claves = {r["k"] for r in f["pcap"]["filas"]}
        for t in self.todos["tramas"]:
            self.assertIn(f"{t['fuente']['fichero']}#{t['fuente']['trama']}", claves)
        bytes_eve = {r["k"] for r in f["eve"]["filas"] if r["estado"] == "aporta"}
        self.assertEqual(bytes_eve, {str(e["fuente"]["byte"]) for e in self.r["eventos"]})


class FlujoVivo(unittest.TestCase):
    """La lista tipo Wireshark: solo lo nuevo, también del fichero que se escribe."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        raiz = Path(self.tmp.name)
        self.anillo = raiz / "anillo"
        self.anillo.mkdir()
        self.eve = raiz / "eve.json"
        self.cfg = {"red_entidades": "10.10.0.0/16", "excluir": [EXCLUIDA + "/32"],
                    "excluir_protocolos": [112, 240], "directorio": str(self.anillo),
                    "anillo_glob": "live-*.pcap"}
        c2s = lambda cuerpo, **k: _eth(MAC_S, MAC_C, _ipv4(CLIENTE, SERVIDOR, 6, cuerpo, **k))
        s2c = lambda cuerpo, **k: _eth(MAC_C, MAC_S, _ipv4(SERVIDOR, CLIENTE, 6, cuerpo, **k))
        self.syn = c2s(_tcp(40000, 80, 1000, 0x02), ip_id=10)
        self.copia = c2s(_tcp(40000, 80, 1000, 0x02), ttl=63, ip_id=10)
        self.syn_ack = s2c(_tcp(80, 40000, 5000, 0x12), ip_id=20)
        self.ack = c2s(_tcp(40000, 80, 1001, 0x10), ip_id=11)
        self.carp = _eth(MAC_S, MAC_C, _ipv4("10.10.20.2", "224.0.0.18", 112, b"\x00" * 20))

    def tearDown(self):
        self.tmp.cleanup()

    @staticmethod
    def _registro(ts, frame):
        seg = int(ts)
        return struct.pack("<IIII", seg, int(round((ts - seg) * 1e6)), len(frame), len(frame)) + frame

    def test_lee_el_fichero_en_curso_y_solo_lo_nuevo(self):
        activo = self.anillo / "live-0001.pcap"
        _pcap(activo, [(T0 + 0.1, self.syn), (T0 + 0.1002, self.copia)])
        tercero = self._registro(T0 + 0.2, self.syn_ack)
        with open(activo, "ab") as fh:
            fh.write(tercero[:20])                       # tcpdump a medio escribir
        a = vista_vivo.flujo(None, self.cfg, todos=True)
        self.assertEqual([r["trama"] for r in a["pcap"]["filas"]], [1, 2])
        self.assertEqual(a["pcap"]["filas"][1]["estado"], "copia del espejo (descartada)")
        with open(activo, "ab") as fh:
            fh.write(tercero[20:] + self._registro(T0 + 0.3, self.ack))
        b = vista_vivo.flujo(None, self.cfg, a["cursor"], todos=True)
        filas = b["pcap"]["filas"]
        self.assertEqual([r["trama"] for r in filas], [3, 4])
        # Sin estado: el SYN-ACK se apunta a quien lo recibe, que es quien inició.
        self.assertEqual((filas[0]["flags"], filas[0]["entidad"]), ("SYN-ACK", CLIENTE))
        self.assertIn("syn_completion_ratio_10s", [x["feature"] for x in filas[0]["aportes"]])
        self.assertEqual(vista_vivo.flujo(None, self.cfg, b["cursor"])["pcap"]["nuevas"], 0)

    def test_sigue_al_fichero_siguiente_al_rotar(self):
        _pcap(self.anillo / "live-0001.pcap", [(T0 + 0.1, self.syn)])
        a = vista_vivo.flujo(None, self.cfg)
        with open(self.anillo / "live-0001.pcap", "ab") as fh:
            fh.write(self._registro(T0 + 0.2, self.carp))
        _pcap(self.anillo / "live-0002.pcap", [(T0 + 15.1, self.ack)])
        b = vista_vivo.flujo(None, self.cfg, a["cursor"], todos=True)
        self.assertEqual([r["k"] for r in b["pcap"]["filas"]], ["live-0001.pcap#2", "live-0002.pcap#1"])
        self.assertEqual(b["pcap"]["filas"][0]["estado"], "plano de control")
        self.assertEqual(b["cursor"]["pf"], "live-0002.pcap")
        # Por omisión solo lo que aporta con señal propia: el ACK puro no sale.
        self.assertEqual(vista_vivo.flujo(None, self.cfg, a["cursor"])["pcap"]["filas"], [])

    def test_eve_no_parte_lineas_a_medias(self):
        base = {"src_ip": CLIENTE, "src_port": 40001, "dest_ip": SERVIDOR, "dest_port": 80}
        uno = json.dumps(dict(base, timestamp=_iso(T0), event_type="http",
                              http={"http_method": "GET", "status": 404})) + "\n"
        dos = json.dumps(dict(base, timestamp=_iso(T0 + 1), event_type="flow")) + "\n"
        self.eve.write_bytes(uno.encode() + dos.encode()[:15])
        a = vista_vivo.flujo(self.eve, self.cfg, todos=True)
        self.assertEqual([r["tipo"] for r in a["eve"]["filas"]], ["http"])
        self.assertIn("http_error_ratio_60s", [x["feature"] for x in a["eve"]["filas"][0]["aportes"]])
        with open(self.eve, "ab") as fh:
            fh.write(dos.encode()[15:])
        b = vista_vivo.flujo(self.eve, self.cfg, a["cursor"], todos=True)
        self.assertEqual([(r["tipo"], r["byte"]) for r in b["eve"]["filas"]], [("flow", len(uno))])
        self.assertEqual(b["eve"]["filas"][0]["estado"], "no lo usa el motor")


if __name__ == "__main__":
    unittest.main()
