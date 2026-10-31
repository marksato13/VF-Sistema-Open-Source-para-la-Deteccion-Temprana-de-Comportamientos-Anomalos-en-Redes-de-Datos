"""Equivalencia del procesamiento incremental del motor con las funciones congeladas.

Contexto: en la campana A (2026-10-29) el motor tardo hasta 45 s por ciclo con
la inundacion HTTP porque recalculaba toda la historia de 230 s en cada ciclo.
scripts/engine/motor_incremental.py hace el mismo calculo con menos trabajo.
Estas pruebas cubren lo que el replay de la campana puede no ejercitar:
duplicados del espejo que cruzan el borde de un fichero, flujos cuyo propietario
cambia cuando la poda se lleva su primer paquete, ventanas que nacen por detras
de la ultima decidida, huecos en scored_windows, ventanas no elegibles,
entidades excluidas, ventanas que expiran sin sus PCAP y reinicios.
"""
from __future__ import annotations

import ipaddress
import json
import random
import struct
import sys
import tempfile
import unittest
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ / "scripts" / "engine"))
sys.path.insert(0, str(RAIZ / "scripts" / "features"))

import extract_multilayer_v2 as v2  # noqa: E402
import extract_multilayer_v3 as v3  # noqa: E402
import motor_incremental as inc  # noqa: E402

RED = ipaddress.ip_network("10.10.0.0/16")
PASO = 10


def paquete(rnd: random.Random, t: float, src: str, dst: str, proto: int = 6, sport: int = 40000,
            dport: int = 80, flags: int = 0x18, seq: int = 1, payload: int = 100, ttl: int = 64,
            icmp_type: int = -1, icmp_id: int = 0) -> v2.ParsedPacket:
    return v2.ParsedPacket(timestamp=t, src_ip=src, dst_ip=dst, ip_length=40 + payload, protocol=proto,
                           ttl=ttl, src_port=sport if proto in (6, 17) else 0,
                           dst_port=dport if proto in (6, 17) else 0, tcp_flags=flags if proto == 6 else 0,
                           tcp_seq=seq if proto == 6 else 0, tcp_payload_length=payload if proto == 6 else 0,
                           icmp_type=icmp_type, icmp_id=icmp_id)


def trafico(rnd: random.Random, t0: float, t1: float, n: int) -> list:
    """Tramas con contexto: flujos TCP/UDP/ICMP, respuestas primero, retransmisiones y copias del espejo."""
    hosts = ["10.10.20.21", "10.10.20.22", "10.10.30.10", "10.10.60.11", "192.168.5.5"]
    salida = []
    for _ in range(n):
        t = rnd.uniform(t0, t1)
        a, b = rnd.sample(hosts, 2)
        proto = rnd.choice([6, 6, 6, 17, 1])
        sport, dport = rnd.choice([40000, 40001, 40002]), rnd.choice([80, 443, 53])
        flags = rnd.choice([0x02, 0x12, 0x10, 0x18, 0x04])
        seq = rnd.choice([1, 2, 3])
        pay = rnd.choice([0, 100, 100, 500])
        ipid = rnd.choice([1, 2, 3])
        p = paquete(rnd, t, a, b, proto, sport, dport, flags, seq, pay, 64,
                    rnd.choice([0, 8]) if proto == 1 else -1, rnd.choice([1, 2]) if proto == 1 else 0)
        salida.append(v3.FrameContext(p, rnd.choice([20, 30]), ipid))
        r = rnd.random()
        if r < 0.25:  # copia entre VLAN: TTL-1, unos microsegundos despues (a veces ANTES)
            q = v2.ParsedPacket(**{**p.__dict__, "timestamp": t + rnd.uniform(-0.0004, 0.0004), "ttl": 63})
            salida.append(v3.FrameContext(q, 30, ipid))
        elif r < 0.35:  # copia identica (difusion)
            salida.append(v3.FrameContext(v2.ParsedPacket(**p.__dict__), 20, ipid))
    return salida


class Deduplicacion(unittest.TestCase):
    def test_anillo_deslizante_igual_a_la_global(self):
        for semilla in range(25):
            rnd = random.Random(semilla)
            d = inc.Deduplicador(v3.deduplicar_espejo)
            anillo, llegada, n = [], {}, 0
            for ciclo in range(12):
                nuevas = sorted(trafico(rnd, ciclo * 5.0, ciclo * 5.0 + 5.0, 60), key=lambda c: c.packet.timestamp)
                # un fichero puede traer alguna trama algo desordenada
                if len(nuevas) > 3 and rnd.random() < 0.5:
                    nuevas[1], nuevas[2] = nuevas[2], nuevas[1]
                for c in nuevas:
                    llegada[id(c)] = n
                    n += 1
                anillo.extend(nuevas)
                corte = ciclo * 5.0 - 18.0
                if anillo and anillo[0].packet.timestamp < corte:
                    anillo = [c for c in anillo if c.packet.timestamp >= corte]
                ref, ref_q = v3.deduplicar_espejo(anillo)
                got, got_q = d.actualizar(anillo, llegada)
                self.assertEqual(got_q, ref_q, f"semilla {semilla} ciclo {ciclo}")
                self.assertEqual([id(p) for p in got], [id(p) for p in ref], f"semilla {semilla} ciclo {ciclo}")

    def test_copia_que_llega_en_el_fichero_siguiente(self):
        # La primera copia (TTL 63) queda conservada mientras la segunda no ha llegado;
        # al llegar la de TTL 64, la funcion congelada descarta la primera.
        a = v2.ParsedPacket(timestamp=100.0000, src_ip="10.10.20.21", dst_ip="10.10.30.10", ip_length=140,
                            protocol=6, ttl=63, src_port=40000, dst_port=80, tcp_flags=0x18, tcp_seq=7,
                            tcp_payload_length=100)
        b = v2.ParsedPacket(**{**a.__dict__, "timestamp": 100.0002, "ttl": 64})
        ca, cb = v3.FrameContext(a, 30, 9), v3.FrameContext(b, 20, 9)
        d = inc.Deduplicador(v3.deduplicar_espejo)
        llegada = {id(ca): 0}
        self.assertEqual(d.actualizar([ca], llegada), ([a], 0))
        llegada[id(cb)] = 1
        self.assertEqual(d.actualizar([ca, cb], llegada), v3.deduplicar_espejo([ca, cb]))
        self.assertEqual(d.actualizar([ca, cb], llegada)[0], [b])


class Atribucion(unittest.TestCase):
    def test_anillo_deslizante_igual_a_la_global(self):
        for semilla in range(25):
            rnd = random.Random(1000 + semilla)
            at = inc.Atribuidor(v2.attribute_packets, v2.canonical_flow_key)
            anillo, llegada, n = [], {}, 0
            for ciclo in range(12):
                nuevas = sorted((c.packet for c in trafico(rnd, ciclo * 5.0, ciclo * 5.0 + 5.0, 60)),
                                key=lambda p: p.timestamp)
                for p in nuevas:
                    llegada[id(p)] = n
                    n += 1
                anillo.extend(nuevas)
                corte = ciclo * 5.0 - 18.0
                anillo = [p for p in anillo if p.timestamp >= corte]
                # a veces la deduplicacion retira un paquete viejo del medio
                if anillo and rnd.random() < 0.3:
                    anillo.pop(rnd.randrange(len(anillo)))
                orden = sorted(anillo, key=lambda p: (p.timestamp, llegada[id(p)]))
                ref = v2.attribute_packets(orden, RED)
                got = at.actualizar(orden, RED, lambda p: (p.timestamp, llegada[id(p)]))
                self.assertEqual(got, ref, f"semilla {semilla} ciclo {ciclo}")

    def test_cambio_de_propietario_al_podar_el_syn(self):
        # SYN del cliente y luego SYN-ACK del servidor: al podar el SYN, el primer paquete
        # que queda es el SYN-ACK y la funcion congelada vuelve a elegir al cliente;
        # al podar tambien el SYN-ACK, el siguiente (un dato del servidor) lo hace propietario.
        r = random.Random(0)
        syn = paquete(r, 1.0, "10.10.20.21", "10.10.30.10", 6, 40000, 80, 0x02, 1, 0)
        synack = paquete(r, 1.1, "10.10.30.10", "10.10.20.21", 6, 80, 40000, 0x12, 5, 0)
        dato = paquete(r, 2.0, "10.10.30.10", "10.10.20.21", 6, 80, 40000, 0x18, 6, 200)
        llegada = {id(syn): 0, id(synack): 1, id(dato): 2}
        at = inc.Atribuidor(v2.attribute_packets, v2.canonical_flow_key)
        orden = lambda p: (p.timestamp, llegada[id(p)])  # noqa: E731
        for anillo in ([syn, synack, dato], [synack, dato], [dato]):
            self.assertEqual(at.actualizar(anillo, RED, orden), v2.attribute_packets(anillo, RED))
        self.assertEqual(at.actualizar([dato], RED, orden)[0].entity_ip, "10.10.30.10")


def observaciones(rnd: random.Random, ent: str, t0: float, t1: float, n_p: int, n_a: int):
    lp = sorted((v2.PacketObservation(
        timestamp=rnd.uniform(t0, t1), entity_ip=ent, peer_ip=rnd.choice(["10.10.30.10", "10.10.30.11"]),
        ip_length=rnd.choice([60, 600, 1400]), protocol=rnd.choice([6, 17, 1]), target_port=rnd.choice([0, 80, 53]),
        flow_attempt=rnd.random() < 0.3, outbound=rnd.random() < 0.5, syn=rnd.random() < 0.2,
        syn_ack=rnd.random() < 0.2, rst=rnd.random() < 0.1, ttl=64, fragmented=False,
        tcp_payload_length=rnd.choice([0, 100]), retransmission=rnd.random() < 0.1,
        flow_id=("10.10.30.10", rnd.choice([80, 53]), 6), flow_duration_so_far=rnd.uniform(0, 30))
        for _ in range(n_p)), key=lambda o: o.timestamp)
    la = [v2.AppObservation(timestamp=rnd.uniform(t0, t1), entity_ip=ent,
                            kind=rnd.choice(["http", "dns_query", "dns_nxdomain", "tls"]),
                            error=rnd.random() < 0.3, event_key=str(rnd.randint(1, 5)),
                            method=rnd.choice(["GET", "POST"]), status=rnd.choice([200, 401, 403, 500]),
                            dns_name=rnd.choice(["a.x", "b.x"]), tls_version=rnd.choice(["", "TLS 1.3"]),
                            tls_incomplete=rnd.random() < 0.3) for _ in range(n_a)]
    return lp, la


class FilasPendientes(unittest.TestCase):
    def test_igual_a_build_rows_global_desde_la_primera_ancla_no_puntuada(self):
        for semilla in range(60):
            rnd = random.Random(semilla)
            t0 = 1_793_000_000 + rnd.uniform(0, 10)
            ents = ["10.10.20.21", "10.10.20.22", "10.10.30.10"]
            lp, la = [], []
            for e in ents:
                a, b = observaciones(rnd, e, t0 + rnd.uniform(0, 60), t0 + rnd.uniform(120, 230), 150, 40)
                lp += a
                la += b
            lp.sort(key=lambda o: o.timestamp)
            rnd.shuffle(la)  # el orden de EVE no es el temporal
            # capture_start por debajo o justo en la primera observacion: ventanas no elegibles al inicio
            cs = min(o.timestamp for o in lp + la) - rnd.choice([0.0, 30.0, 300.0])
            glob = v2.build_rows("motor-live", lp, la, step_seconds=PASO, capture_start=cs)
            # scored_windows con frontera, huecos (ventanas tardias por detras) y no elegibles nunca puntuadas
            puntuadas = {}
            for f in glob:
                w = v2.parse_eve_timestamp(f["window_end_utc"])
                if f["eligible_training"] and w < t0 + 180 and rnd.random() > 0.1:
                    puntuadas[(f["entity_ip"], f["window_end_utc"])] = w
            pp, pa = inc.agrupar_por_entidad(lp, la)
            for e in ents:
                ref = [f for f in glob if f["entity_ip"] == e]
                filas, a_min = inc.filas_pendientes(v2.build_rows, e, pp[e], pa[e], PASO, cs, puntuadas)
                necesarias = [f for f in ref if (e, f["window_end_utc"]) not in puntuadas]
                if a_min is None:
                    self.assertEqual(necesarias, [])
                    continue
                corte = inc.clave_ventana(a_min)
                self.assertEqual(filas, [f for f in ref if f["window_end_utc"] >= corte], f"semilla {semilla} {e}")
                self.assertTrue(all(f in filas for f in necesarias), f"semilla {semilla} {e}")
                self.assertEqual(necesarias[0]["window_end_utc"], corte)

    def test_anclas_de_entidad_excluida(self):
        rnd = random.Random(3)
        lp, la = observaciones(rnd, "10.10.60.11", 1000.0, 1100.0, 30, 5)
        glob = v2.build_rows("motor-live", lp, la, step_seconds=PASO, capture_start=900.0)
        puntuadas = {("10.10.60.11", f["window_end_utc"]): 0.0 for f in glob[:4]}
        puntuadas.pop(("10.10.60.11", glob[2]["window_end_utc"]))
        anclas = inc.anclas_sin_puntuar("10.10.60.11", lp, la, PASO, puntuadas)
        self.assertEqual([inc.clave_ventana(a) for a in anclas],
                         [f["window_end_utc"] for f in glob if ("10.10.60.11", f["window_end_utc"]) not in puntuadas])


class Eve(unittest.TestCase):
    EVENTOS = [
        {"timestamp": "2026-10-29T09:00:00.100000+0000", "event_type": "http", "src_ip": "10.10.20.21",
         "http": {"status": 401, "http_method": "post"}},
        {"timestamp": "2026-10-29T09:00:00.200000+0000", "event_type": "dns", "src_ip": "10.10.20.22",
         "dns": {"type": "query", "rrname": "Ejemplo.LAB"}},
        {"timestamp": "2026-10-29T09:00:00.300000+0000", "event_type": "dns", "src_ip": "10.10.20.22",
         "dns": {"type": "answer", "rcode": "NXDOMAIN"}},
        {"timestamp": "2026-10-29T09:00:00.400000+0000", "event_type": "tls", "src_ip": "8.8.8.8",
         "dest_ip": "10.10.20.23", "flow_id": 77, "tls": {"version": "TLS 1.3"}},
        {"timestamp": "2026-10-29T09:00:00.500000+0000", "event_type": "flow", "src_ip": "10.10.20.21"},
        {"timestamp": "2026-10-29T09:00:00.600000+0000", "event_type": "http", "src_ip": "192.168.1.1",
         "http": {"status": 200}},
        {"timestamp": "2026-10-29T09:00:00.700000+0000", "event_type": "alert", "src_ip": "10.10.20.21"},
        {"timestamp": "2026-10-29T09:00:00.800000+0000", "event_type": "stats", "stats": {"uptime": 1}},
    ]

    def test_por_linea_igual_que_el_volcado(self):
        lineas = [json.dumps(e) for e in self.EVENTOS]
        with tempfile.TemporaryDirectory() as tmp:
            ruta = Path(tmp) / "eve.jsonl"
            ruta.write_text("".join(x + "\n" for x in lineas), encoding="utf-8")
            ref = v2.load_app_observations(ruta, RED)
        got = [o for x in lineas for o in inc.observaciones_de_linea(v2, x, RED)]
        self.assertEqual(got, ref)
        self.assertEqual(len(got), 4)


class PuntuacionPorLotes(unittest.TestCase):
    def test_lote_igual_a_una_llamada_por_fila(self):
        try:
            import numpy as np
            from sklearn.ensemble import IsolationForest
            from sklearn.pipeline import make_pipeline
            from sklearn.preprocessing import StandardScaler
        except ImportError:  # pragma: no cover
            self.skipTest("sin scikit-learn")
        rng = np.random.default_rng(0)
        pipe = make_pipeline(StandardScaler(), IsolationForest(n_estimators=200, random_state=0))
        pipe.fit(rng.normal(size=(2000, 28)))
        X = rng.normal(size=(300, 28)) * rng.choice([0.1, 1.0, 10.0], size=(300, 1))
        lote = [float(v) for v in pipe.score_samples(X.tolist())]
        una = [float(pipe.score_samples([x])[0]) for x in X.tolist()]
        self.assertEqual(lote, una)


# --- Escenario sintetico de extremo a extremo ---------------------------------

def _trama(p: v2.ParsedPacket, vlan: int, ipid: int, payload: bytes = b"") -> bytes:
    eth = b"\x00\x0c\x29\x00\x00\x01" + b"\x00\x0c\x29\x00\x00\x02" + struct.pack("!HHH", 0x8100, vlan, 0x0800)
    if p.protocol == 6:
        l4 = struct.pack("!HHIIBBHHH", p.src_port, p.dst_port, p.tcp_seq, 0, 5 << 4, p.tcp_flags, 1024, 0, 0)
    elif p.protocol == 17:
        l4 = struct.pack("!HHHH", p.src_port, p.dst_port, 8 + len(payload), 0)
    else:
        l4 = struct.pack("!BBHHH", max(p.icmp_type, 0), 0, 0, p.icmp_id, 1)
    total = 20 + len(l4) + len(payload)
    ip = struct.pack("!BBHHHBBH4s4s", 0x45, 0, total, ipid, 0x4000, p.ttl, p.protocol, 0,
                     ipaddress.ip_address(p.src_ip).packed, ipaddress.ip_address(p.dst_ip).packed)
    return eth + ip + l4 + payload


def _escribir_pcap(ruta: Path, tramas: list[tuple[float, bytes]]) -> None:
    with ruta.open("wb") as fh:
        fh.write(struct.pack("<IHHiIII", 0xA1B2C3D4, 2, 4, 0, 0, 65535, 1))
        for t, b in tramas:
            s = int(t)
            fh.write(struct.pack("<IIII", s, int(round((t - s) * 1e6)), len(b), len(b)))
            fh.write(b)


def escenario(tmp: Path, t0: int) -> tuple[Path, Path]:
    """PCAP rotados cada 15 s y un eve.json que ejercitan los casos limite del motor."""
    import datetime as dt
    rnd = random.Random(7)
    capt = tmp / "pcap"
    capt.mkdir()
    tramas: list[tuple[float, bytes]] = []

    def tcp(t, s, d, sp, dp, fl, seq, pay=b"", ttl=64, vlan=20, ipid=None, copia=False):
        p = v2.ParsedPacket(timestamp=t, src_ip=s, dst_ip=d, ip_length=40 + len(pay), protocol=6, ttl=ttl,
                            src_port=sp, dst_port=dp, tcp_flags=fl, tcp_seq=seq, tcp_payload_length=len(pay))
        i = rnd.randint(1, 60000) if ipid is None else ipid
        tramas.append((t, _trama(p, vlan, i, pay)))
        if copia:  # el espejo la ve otra vez al salir del cortafuegos
            q = v2.ParsedPacket(**{**p.__dict__, "timestamp": t + 0.0002, "ttl": ttl - 1})
            tramas.append((t + 0.0002, _trama(q, 30, i, pay)))

    # Cliente normal con flujos cortos y copias del espejo durante todo el escenario.
    for k in range(0, 420, 3):
        t = t0 + k + rnd.uniform(0, 1)
        sp = 41000 + k
        tcp(t, "10.10.20.21", "10.10.30.10", sp, 80, 0x02, 100, copia=True)
        tcp(t + 0.01, "10.10.30.10", "10.10.20.21", 80, sp, 0x12, 500, copia=True)
        tcp(t + 0.02, "10.10.20.21", "10.10.30.10", sp, 80, 0x18, 101, b"G" * 80, copia=True)
        if k % 30 == 0:  # retransmision
            tcp(t + 0.5, "10.10.20.21", "10.10.30.10", sp, 80, 0x18, 101, b"G" * 80)
    # Flujo largo: su SYN se poda pronto; el siguiente paquete que queda es del servidor
    # y el propietario cambia en mitad de la historia (ventanas que nacen por detras).
    tcp(t0 + 20.0, "10.10.20.22", "10.10.30.10", 42000, 22, 0x02, 1)
    for k in range(40, 400, 7):
        tcp(t0 + k, "10.10.30.10", "10.10.20.22", 22, 42000, 0x18, 1000 + k, b"S" * 40)
    # Entidad excluida (gestion) y entidad fuera de la red.
    for k in range(5, 400, 11):
        tcp(t0 + k, "10.10.60.11", "10.10.30.10", 43000 + k, 443, 0x02, 1)
        tcp(t0 + k + 0.3, "192.168.5.5", "10.10.20.21", 44000 + k, 8080, 0x02, 1)
    # Copia que cruza el borde de un fichero (t0+45 es una rotacion).
    tcp(t0 + 44.9999, "10.10.20.23", "10.10.30.10", 45000, 80, 0x02, 9, ttl=63, ipid=4242)
    tcp(t0 + 45.0001, "10.10.20.23", "10.10.30.10", 45000, 80, 0x02, 9, ttl=64, ipid=4242)
    # Rafaga que cae en el fichero que se cierra tarde: hueco de PCAP de 200 a 290 s
    # (la captura no rota) mientras eve.json sigue: ventanas pendientes que expiran.
    tramas = [x for x in tramas if not (t0 + 200 <= x[0] < t0 + 290)]
    tramas.sort(key=lambda x: x[0])
    inicios = [t0 + 15 * i for i in range(29)]
    inicios = [s for s in inicios if not (t0 + 200 < s < t0 + 290)]
    for i, s in enumerate(inicios):
        fin = inicios[i + 1] if i + 1 < len(inicios) else s + 15
        nombre = dt.datetime.fromtimestamp(s, dt.timezone.utc).strftime("live-%Y%m%d%H%M%S.pcap")
        _escribir_pcap(capt / nombre, [x for x in tramas if s <= x[0] < fin])

    def iso(t):
        return dt.datetime.fromtimestamp(t, dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%f+0000")
    eventos = []
    for k in range(0, 420, 2):  # HTTP con 401 (fuerza bruta) desde una entidad solo L7
        eventos.append({"timestamp": iso(t0 + k + 0.5), "event_type": "http", "src_ip": "10.10.20.24",
                        "http": {"status": 401, "http_method": "POST"}})
    for k in range(0, 420, 5):
        eventos.append({"timestamp": iso(t0 + k + 0.2), "event_type": "dns", "src_ip": "10.10.20.21",
                        "dns": {"type": "query", "rrname": f"n{k}.lab"}})
        eventos.append({"timestamp": iso(t0 + k + 0.3), "event_type": "dns", "src_ip": "10.10.20.21",
                        "dns": {"type": "answer", "rcode": "NXDOMAIN" if k % 10 else "NOERROR"}})
        # un evento de flujo llega con la hora de INICIO del flujo (desordenado)
        eventos.append({"timestamp": iso(t0 + max(0, k - 40)), "event_type": "flow", "src_ip": "10.10.20.21"})
    eve = tmp / "eve.json"
    # En binario: Suricata escribe "\n"; en Windows write_text pondria "\r\n".
    eve.write_bytes("".join(json.dumps(e) + "\n" for e in eventos).encode("utf-8"))
    return capt, eve


class ExtremoAExtremo(unittest.TestCase):
    def test_escenario_sintetico_con_reinicio(self):
        try:
            import joblib
            import numpy as np
            from sklearn.ensemble import IsolationForest
            from sklearn.pipeline import make_pipeline
            from sklearn.preprocessing import StandardScaler
        except ImportError:  # pragma: no cover
            self.skipTest("sin scikit-learn")
        import replay_motor
        with tempfile.TemporaryDirectory() as d:
            tmp = Path(d)
            t0 = 1_793_260_800
            capt, eve = escenario(tmp, t0)
            pipe = make_pipeline(StandardScaler(), IsolationForest(n_estimators=50, random_state=0))
            pipe.fit(np.random.default_rng(1).normal(size=(500, 28)))
            modelo = tmp / "m" / "modelo.joblib"
            modelo.parent.mkdir()
            joblib.dump(pipe, modelo)
            (tmp / "m" / "manifest.json").write_text(json.dumps({"detectors": {"if_prueba": {"calibration": {
                "comparison": "score < threshold", "threshold": -0.55}}}}), encoding="utf-8")
            salida = tmp / "salida"
            verif = tmp / "verificacion.jsonl"
            sys.argv = ["replay_motor.py", "--motor", str(RAIZ / "scripts/engine/motor_decision.py"),
                        "--pcap-dir", str(capt), "--eve", str(eve), "--desde", str(t0 + 10),
                        "--hasta", str(t0 + 440), "--reiniciar-en", str(t0 + 330), "--salida", str(salida), "--",
                        "--model-path", str(modelo), "--manifest-path", str(tmp / "m" / "manifest.json"),
                        "--detector-name", "if_prueba", "--entity-network", "10.10.0.0/16",
                        "--excluir", "10.10.60.11/32", "--excluir-protocolos", "112,240",
                        "--step-seconds", "10", "--history-seconds", "90",
                        "--verificar-equivalencia", str(verif)]
            self.assertEqual(replay_motor.main(), 0)
            comprobaciones = [json.loads(x) for x in verif.read_text(encoding="utf-8").splitlines()]
            registro = [json.loads(x) for x in (salida / "motor_decision.log").read_text(encoding="utf-8").splitlines()]
            ciclos = [json.loads(x) for x in (salida / "_state" / "ciclos.jsonl").read_text(encoding="utf-8").splitlines()]

        malos = [c for c in comprobaciones if not c["ok"]]
        self.assertEqual(malos, [], json.dumps(malos[:2]))
        self.assertGreater(len(comprobaciones), 30)
        decisiones = [r for r in registro if r["event"] == "decision"]
        no_evaluadas = [r for r in registro if r["event"] == "ventana_no_evaluada"]
        claves = [(r["entity_ip"], r["window_end_utc"]) for r in decisiones + no_evaluadas]
        # sin decisiones duplicadas, tampoco a traves del reinicio
        self.assertEqual(len(claves), len(set(claves)))
        self.assertEqual(sum(r["event"] == "motor_startup" for r in registro), 2)
        # el hueco de PCAP deja ventanas que expiran como pcap_incompleto, sin convertirlas en trafico normal
        self.assertTrue(any(r["motivo"] == "pcap_incompleto" for r in no_evaluadas))
        # la entidad solo L7 se decide por el heuristico, nunca con el modelo sin paquetes
        l7 = [r for r in decisiones if r["entity_ip"] == "10.10.20.24"]
        self.assertTrue(l7 and all(r["score"] is None for r in l7))
        self.assertTrue(any(r["detector_name"] == "auth_failure_heuristic" for r in l7))
        # la excluida no se decide pero se cuenta; la de fuera de la red no aparece
        self.assertFalse(any(r["entity_ip"] in ("10.10.60.11", "192.168.5.5") for r in decisiones))
        self.assertGreater(max(r["excluidas_acumulado"] for r in decisiones), 0)
        # ventanas que quedaron pendientes y se decidieron despues
        self.assertTrue(any(r["pendiente_desde"] is not None for r in decisiones))
        # el servidor del flujo largo aparece como entidad cuando la poda cambia el propietario
        self.assertTrue(any(r["entity_ip"] == "10.10.30.10" for r in decisiones))
        # instrumentacion: un registro por ciclo con sus etapas y conteos
        self.assertEqual(len(ciclos), len(comprobaciones) + sum(1 for c in ciclos if c["entidades"] == 0
                                                                and c["observaciones_l7"] == 0
                                                                and c["paquetes_deduplicados"] == 0))
        self.assertTrue(all({"inicio_ciclo", "fin_ciclo", "duracion_s", "etapas_s", "marca_pcap", "marca_eve",
                             "decididas", "ventanas_pendientes", "no_evaluadas"} <= set(c) for c in ciclos))


if __name__ == "__main__":
    unittest.main()
