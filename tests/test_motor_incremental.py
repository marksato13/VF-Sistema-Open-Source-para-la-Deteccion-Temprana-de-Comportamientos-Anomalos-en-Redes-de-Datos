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
import math
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

    def test_deslizar_igual_a_la_global_con_atribucion(self):
        """Via por deltas (pendiente 2): Deduplicador.deslizar + Atribuidor.deslizar dan lo mismo
        que deduplicar_espejo + attribute_packets sobre todo el horizonte [corte, ...], con copias
        del espejo, tramas desordenadas, llegadas tardias (anteriores a lo ya presente), varias
        anclas por ciclo sin llegadas y llegadas ya fuera del horizonte."""
        for semilla in range(40):
            rnd = random.Random(500 + semilla)
            d = inc.Deduplicador(v3.deduplicar_espejo)
            at = inc.Atribuidor(v2.attribute_packets, v2.canonical_flow_key)
            buffer, llegada, llegada_p, n = [], {}, {}, 0
            pendientes_llegar: list = []
            diferidas: list = []
            corte = -1e9
            for ciclo in range(14):
                nuevas = sorted(trafico(rnd, ciclo * 5.0, ciclo * 5.0 + 5.0, 50), key=lambda c: c.packet.timestamp)
                if len(nuevas) > 3 and rnd.random() < 0.5:
                    nuevas[1], nuevas[2] = nuevas[2], nuevas[1]
                # copia del espejo que llega en el fichero SIGUIENTE: la de TTL 63 se conserva
                # hasta que llega la de TTL 64 y entonces pasa a descartada (cambio de estado)
                nuevas += diferidas
                diferidas = []
                for c in rnd.sample(nuevas, min(4, len(nuevas))):
                    p = c.packet
                    a63 = v3.FrameContext(v2.ParsedPacket(**{**p.__dict__, "ttl": 63}), 30, 777 + ciclo)
                    b64 = v3.FrameContext(v2.ParsedPacket(**{**p.__dict__, "ttl": 64,
                                                             "timestamp": p.timestamp + 0.0002}), 20, 777 + ciclo)
                    nuevas.append(a63)
                    diferidas.append(b64)
                if rnd.random() < 0.3:  # fichero retrasado: tramas de hace 8-12 s
                    nuevas += trafico(rnd, ciclo * 5.0 - 12.0, ciclo * 5.0 - 8.0, 10)
                for c in nuevas:
                    llegada[id(c)] = n
                    llegada_p[id(c.packet)] = n
                    n += 1
                buffer.extend(nuevas)
                pendientes_llegar.extend(nuevas)
                for _ in range(rnd.choice([1, 1, 2, 3])):  # anclas del ciclo
                    corte = max(corte, ciclo * 5.0 - 20.0 + rnd.uniform(0, 4))
                    horizonte = [c for c in buffer if c.packet.timestamp >= corte]
                    ref_paq, ref_q = v3.deduplicar_espejo(horizonte)
                    ref_obs = v2.attribute_packets(ref_paq, RED)
                    paq, q, entran, salen = d.deslizar(corte, pendientes_llegar, llegada)
                    pendientes_llegar = []
                    obs = at.deslizar(paq, entran, salen, RED, lambda p: (p.timestamp, llegada_p[id(p)]))
                    msg = f"semilla {semilla} ciclo {ciclo}"
                    self.assertEqual(q, ref_q, msg)
                    self.assertEqual([id(p) for p in paq], [id(p) for p in ref_paq], msg)
                    self.assertEqual(obs, ref_obs, msg)
                    # las observaciones salen en orden de tiempo (el motor biseca sobre ellas)
                    self.assertEqual([o.timestamp for o in obs], sorted(o.timestamp for o in obs), msg)
                buffer = [c for c in buffer if c.packet.timestamp >= corte - rnd.uniform(0, 3)]

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

    def test_fila_de_ancla_igual_a_build_rows_global_del_horizonte(self):
        """Optimizacion de fila_de_ancla (pendiente 2): la fila A es identica a la de build_rows
        sobre TODO el horizonte [A-230, ...] de la entidad, en todos los casos limite: solo
        paquetes en (A-60, A-30], contenido justo en A, solo L7, primera justo en A, huecos."""
        from dataclasses import replace
        H = 230
        n = 0
        for semilla in range(80):
            rnd = random.Random(1000 + semilla)
            t0 = 1_793_000_000 + rnd.choice([0.0, rnd.uniform(0, 10)])
            e = "10.10.20.21"
            lp, la = [], []
            for _ in range(rnd.randint(1, 4)):  # rafagas separadas por huecos
                a = t0 + rnd.uniform(0, 400)
                p_, a_ = observaciones(rnd, e, a, a + rnd.choice([0.5, 5, 40]), rnd.choice([0, 1, 30]),
                                       rnd.choice([0, 0, 1, 8]))
                lp += p_
                la += a_
            # marcas justo en la reticula
            for x in rnd.sample(lp, min(3, len(lp))):
                lp.append(replace(x, timestamp=float(math.ceil(x.timestamp / PASO) * PASO)))
            if not lp and not la:
                continue
            lp.sort(key=lambda o: o.timestamp)
            ts = [o.timestamp for o in lp + la]
            for ancla in range(int(math.floor(min(ts) / PASO)) * PASO, int(math.ceil(max(ts) / PASO)) * PASO + 70, PASO):
                hp = [o for o in lp if o.timestamp >= ancla - H]
                ha = [o for o in la if o.timestamp >= ancla - H]
                if not hp and not ha:
                    continue
                primera = min(hp + ha, key=lambda o: o.timestamp)
                cs = primera.timestamp - rnd.choice([0.0, 30.0, 300.0])
                lp60 = [o for o in hp if ancla - inc.REGISTRO_S < o.timestamp <= ancla]
                la60 = [o for o in ha if ancla - 60 < o.timestamp <= ancla]
                fila = inc.fila_de_ancla(v2.build_rows, lp60, la60, ancla, PASO, cs, replace, primera=primera)
                # via del motor: sin primera; solo si todo cae justo en A busca una anterior
                anterior = next((o for o in hp if o.timestamp <= ancla - inc.REGISTRO_S),
                                next((o for o in ha if o.timestamp < ancla), None))
                fila_motor = inc.fila_de_ancla(v2.build_rows, lp60, la60, ancla, PASO, cs, replace,
                                               buscar_anterior=lambda: anterior)
                self.assertEqual(fila_motor, fila, f"via del motor: semilla {semilla} ancla {ancla}")
                if not lp60 and not la60:
                    self.assertIsNone(fila)
                    continue
                rp, ra = list(hp), list(ha)
                if max(o.timestamp for o in rp + ra) <= ancla - PASO:
                    ult = max(rp + ra, key=lambda o: o.timestamp)
                    (rp if any(ult is o for o in rp) else ra).append(replace(ult, timestamp=ancla + PASO / 2))
                ref = [f for f in v2.build_rows("motor-live", rp, ra, step_seconds=PASO, capture_start=cs)
                       if f["window_end_utc"] == inc.clave_ventana(ancla)]
                self.assertEqual(fila, ref[0] if ref else None, f"semilla {semilla} ancla {ancla}")
                n += 1
        self.assertGreater(n, 500)

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


class TiemposDeRegistro(unittest.TestCase):
    """decidido_en, logged_at y registro_escrito_en distinguen decidir de quedar disponible."""

    def test_logged_at_antes_del_write_y_disponibilidad_despues(self):
        import motor_decision as md

        with tempfile.TemporaryDirectory() as d:
            log = Path(d) / "motor_decision.log"
            log.write_text("", encoding="utf-8")

            class Reloj:
                """Cada lectura avanza 1 s y anota si la linea ya era visible en el fichero."""
                def __init__(self):
                    self.t, self.visto = 100.0, []

                def time(self):
                    self.t += 1.0
                    self.visto.append((self.t, "10.10.20.21" in log.read_text(encoding="utf-8")))
                    return self.t

            reloj, original = Reloj(), md.time
            md.time = reloj
            try:
                regs = [{"event": "decision", "decision": "ALERT", "entity_ip": "10.10.20.21",
                         "window_end_utc": "2026-10-29T09:00:00Z", "decidido_en": 50.0},
                        {"event": "ventana_no_evaluada", "entity_ip": "10.10.20.22",
                         "window_end_utc": "2026-10-29T09:00:00Z", "decidido_en": 51.0}]
                disponible = md.escribir_registros(log, regs)
                self.assertIsNone(md.escribir_registros(log, []))
            finally:
                md.time = original
            escritos = [json.loads(x) for x in log.read_text(encoding="utf-8").splitlines()]

        self.assertEqual(len(escritos), 2)
        logged = {r["logged_at"] for r in escritos}
        self.assertEqual(len(logged), 1, "un solo instante de escritura por lote")
        (t_log,) = logged
        # logged_at se tomo con el registro aun NO visible; la disponibilidad, ya visible
        self.assertIn((t_log, False), reloj.visto)
        self.assertIn((disponible, True), reloj.visto)
        self.assertGreater(disponible, t_log)
        self.assertTrue(all(r["decidido_en"] <= r["logged_at"] for r in escritos))


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
        # horizonte por ventana: una comprobacion por ancla tratada, en orden y sin repetir
        # (tambien a traves del reinicio, que reanuda desde la ultima ventana registrada)
        anclas = [c["ancla"] for c in comprobaciones]
        self.assertEqual(anclas, sorted(set(anclas)))
        self.assertTrue(all(c["horizonte_s"] == 90 for c in comprobaciones))
        self.assertTrue(all("historial_completo" in r and r["horizonte_s"] == 90 for r in decisiones))
        # tras el reinicio el horizonte se recupera del anillo y de eve.json
        arranques = [r for r in registro if r["event"] == "motor_startup"]
        self.assertIsNotNone(arranques[1]["ancla_reanudada"])
        self.assertGreater(arranques[1]["recuperacion_eve"].get("lineas", 0), 0)
        self.assertTrue(all({"inicio_ciclo", "fin_ciclo", "duracion_s", "etapas_s", "marca_pcap", "marca_eve",
                             "decididas", "ventanas_pendientes", "no_evaluadas", "registro_escrito_en",
                             "registros_escritos"} <= set(c) for c in ciclos))
        # tiempos de registro: decidir <= escribir <= disponible, y el ciclo cuenta lo que escribio
        self.assertTrue(all(r["decidido_en"] <= r["logged_at"] for r in decisiones + no_evaluadas))
        # pendientes que nunca debieron existir: se cancelan con evidencia, no expiran como
        # ventana_no_regenerada (el flujo largo cambia de propietario al podar su SYN)
        canceladas = [r for r in registro if r["event"] == "pendiente_cancelada"]
        self.assertFalse(any(r["motivo"] == "ventana_no_regenerada" for r in no_evaluadas))
        self.assertTrue(canceladas)
        for r in canceladas:
            self.assertEqual((r["obs_pcap_propio"], r["obs_eve_propio"]), (0, 0))
            self.assertNotIn((r["entity_ip"], r["window_end_utc"]), set(claves))
        por_ciclo = {}
        for r in decisiones + no_evaluadas + canceladas:
            por_ciclo.setdefault(r["inicio_ciclo"], []).append(r)
        for c in ciclos:
            escritos = por_ciclo.get(c["inicio_ciclo"], [])
            self.assertEqual(c["registros_escritos"], len(escritos))
            if escritos:
                self.assertGreaterEqual(c["registro_escrito_en"], max(r["logged_at"] for r in escritos))
            else:
                self.assertIsNone(c["registro_escrito_en"])


class HorizontePorVentana(unittest.TestCase):
    """Cierre de la Etapa 2: la fila de una ventana no depende de cuando se decide.

    Mismo escenario con tres formas de mirar: periodico cada 10 s; por eventos con
    sondeo de 0,25 s y cierres retrasados 3 s; y por eventos con dos reinicios del
    motor. Toda ventana decidida en dos configuraciones tiene el mismo vector, el
    mismo score y la misma decision; ninguna se decide dos veces.
    """

    def correr(self, tmp, capt, eve, modelo, nombre, extra_arnes, disparo):
        import replay_motor
        salida = tmp / nombre
        sys.argv = ["replay_motor.py", "--motor", str(RAIZ / "scripts/engine/motor_decision.py"),
                    "--pcap-dir", str(capt), "--eve", str(eve), "--desde", str(self.t0 + 10),
                    "--hasta", str(self.t0 + 440), "--salida", str(salida), *extra_arnes, "--",
                    "--model-path", str(modelo), "--manifest-path", str(tmp / "m" / "manifest.json"),
                    "--detector-name", "if_prueba", "--entity-network", "10.10.0.0/16",
                    "--excluir", "10.10.60.11/32", "--excluir-protocolos", "112,240",
                    "--step-seconds", "10", "--history-seconds", "90", "--disparo", disparo,
                    "--volcar-caracteristicas", str(salida / "x.jsonl")]
        self.assertEqual(replay_motor.main(), 0)
        dec = {}
        claves = []
        for linea in (salida / "motor_decision.log").read_text(encoding="utf-8").splitlines():
            r = json.loads(linea)
            if r["event"] in ("decision", "ventana_no_evaluada"):
                claves.append((r["entity_ip"], r["window_end_utc"]))
            if r["event"] == "decision":
                dec[(r["entity_ip"], r["window_end_utc"])] = r
        x = {}
        for linea in (salida / "x.jsonl").read_text(encoding="utf-8").splitlines():
            r = json.loads(linea)
            x[(r["entity_ip"], r["window_end_utc"])] = (r["x"], r["score"])
        self.assertEqual(len(claves), len(set(claves)), nombre + ": decisiones duplicadas")
        return dec, x

    def test_misma_fila_con_cualquier_cadencia_retraso_o_reinicio(self):
        try:
            import joblib
            import numpy as np
            from sklearn.ensemble import IsolationForest
            from sklearn.pipeline import make_pipeline
            from sklearn.preprocessing import StandardScaler
        except ImportError:  # pragma: no cover
            self.skipTest("sin scikit-learn")
        with tempfile.TemporaryDirectory() as d:
            tmp = Path(d)
            self.t0 = 1_793_260_800
            capt, eve = escenario(tmp, self.t0)
            pipe = make_pipeline(StandardScaler(), IsolationForest(n_estimators=50, random_state=0))
            pipe.fit(np.random.default_rng(1).normal(size=(500, 28)))
            modelo = tmp / "m" / "modelo.joblib"
            modelo.parent.mkdir()
            joblib.dump(pipe, modelo)
            (tmp / "m" / "manifest.json").write_text(json.dumps({"detectors": {"if_prueba": {"calibration": {
                "comparison": "score < threshold", "threshold": -0.55}}}}), encoding="utf-8")
            a = self.correr(tmp, capt, eve, modelo, "periodico", [], "periodico")
            b = self.correr(tmp, capt, eve, modelo, "eventos-retraso", ["--retraso-cierre", "3"], "eventos")
            c = self.correr(tmp, capt, eve, modelo, "eventos-reinicios",
                            ["--reiniciar-en", str(self.t0 + 150), "--reiniciar-en", str(self.t0 + 330)], "eventos")
        for nombre, (dec, x) in (("eventos-retraso", b), ("eventos-reinicios", c)):
            comunes = set(a[0]) & set(dec)
            self.assertGreater(len(comunes), 0.9 * len(a[0]), nombre)
            distintas = [k for k in comunes if (a[0][k]["decision"], a[0][k]["score"], a[0][k]["detector_name"])
                         != (dec[k]["decision"], dec[k]["score"], dec[k]["detector_name"])
                         or a[1].get(k) != x.get(k)]
            self.assertEqual(distintas, [], nombre)
        # tras cada reinicio el horizonte se recupera: ninguna ventana posterior al primer
        # arranque queda con historial incompleto
        tardias = [k for k, r in c[0].items() if r["historial_completo"] is False
                   and json.loads(json.dumps(k))[1] > "2026-10-29T08:01:40"]
        self.assertEqual(tardias, [])


class ContabilidadPendientes(unittest.TestCase):
    """Las 14 ventana_no_regenerada del replay completo del 3B (Etapa 2, pendiente 1).

    Una pendiente se da de alta con la atribucion de la ULTIMA ancla tratada; su
    ventana se decide con el horizonte PROPIO. Si un flujo cambia de propietario
    entre ambos horizontes, la entidad puede no tener nada en su propia ventana: la
    pendiente nunca debio existir y se cancela con evidencia. Estas pruebas
    comprueban, con un calculo independiente del motor (las funciones congeladas
    sobre la lista de paquetes del escenario), que:

    - toda ventana registrable por la regla causal (contenido en (A-60, A] con el
      horizonte [A-90, ...]) se decide o queda no evaluada con motivo, y ninguna se
      cancela (sin perdidas ocultas);
    - toda cancelacion corresponde a una ventana NO registrable con su horizonte
      propio y SI con el de su alta (cambio de propietario);
    - los limites temporales: un paquete justo en la reticula registra su ancla y
      las 5 siguientes, nunca la de t+60;
    - una entidad sin actividad reciente no deja ventanas, pendientes ni
      cancelaciones mas alla de su ultimo paquete + 60 s.
    """

    T0 = 1_793_260_800
    HORIZONTE = 90

    def escenario(self, tmp: Path):
        import datetime as dt
        t0 = self.T0
        paquetes: list = []
        rnd = random.Random(11)

        def pk(t, s, d, sp, dp, fl, proto=6, seq=1, pay=0):
            paquetes.append(v2.ParsedPacket(timestamp=t, src_ip=s, dst_ip=d, ip_length=40 + pay, protocol=proto,
                                            ttl=64, src_port=sp, dst_port=dp, tcp_flags=fl, tcp_seq=seq,
                                            tcp_payload_length=pay))

        # trafico de fondo: anclas con contenido en todo el escenario
        for k in range(0, 420, 3):
            t = t0 + k + rnd.uniform(0, 1)
            pk(t, "10.10.20.21", "10.10.30.10", 41000 + k, 80, 0x02, seq=100)
            pk(t + 0.01, "10.10.30.10", "10.10.20.21", 80, 41000 + k, 0x12, seq=500)
        # cambio de propietario: el SYN de 10.10.20.22 sale del horizonte y el flujo pasa
        # a ser de 10.10.30.11 (el servidor, que es quien sigue enviando)
        pk(t0 + 20.0, "10.10.20.22", "10.10.30.11", 42000, 22, 0x02)
        for k in range(30, 400, 4):
            pk(t0 + k + 0.5, "10.10.30.11", "10.10.20.22", 22, 42000, 0x18, seq=1000 + k, pay=40)
        # limites temporales: un paquete justo en la reticula
        pk(t0 + 200.0, "10.10.20.25", "10.10.30.12", 5353, 53, 0, proto=17)
        pk(t0 + 300.0, "10.10.20.26", "10.10.30.12", 5354, 53, 0, proto=17)
        # sin actividad reciente: rafaga corta y silencio
        for k in range(20):
            pk(t0 + 150 + k * 0.25, "10.10.20.27", "10.10.30.12", 46000 + k, 443, 0x02)
        paquetes.sort(key=lambda p: p.timestamp)
        capt = tmp / "pcap"
        capt.mkdir()
        for i in range(29):
            s = t0 + 15 * i
            nombre = dt.datetime.fromtimestamp(s, dt.timezone.utc).strftime("live-%Y%m%d%H%M%S.pcap")
            _escribir_pcap(capt / nombre, [(p.timestamp, _trama(p, 20, 1000 + j))
                                           for j, p in enumerate(paquetes) if s <= p.timestamp < s + 15])
        eve = tmp / "eve.json"
        eve.write_bytes(b"")
        return capt, eve, paquetes

    def registrables(self, paquetes, ancla, corte):
        """Entidades con contenido en (A-60, A] segun attribute_packets sobre [corte, A]."""
        obs = v2.attribute_packets([p for p in paquetes if corte <= p.timestamp <= ancla], RED)
        return {o.entity_ip for o in obs if ancla - inc.REGISTRO_S < o.timestamp <= ancla}

    def correr(self, tmp, capt, eve, nombre, extra_arnes, extra_motor):
        try:
            import joblib
            import numpy as np
            from sklearn.ensemble import IsolationForest
            from sklearn.pipeline import make_pipeline
            from sklearn.preprocessing import StandardScaler
        except ImportError:  # pragma: no cover
            self.skipTest("sin scikit-learn")
        import replay_motor
        modelo = tmp / "m" / "modelo.joblib"
        if not modelo.exists():
            modelo.parent.mkdir()
            pipe = make_pipeline(StandardScaler(), IsolationForest(n_estimators=50, random_state=0))
            pipe.fit(np.random.default_rng(1).normal(size=(500, 28)))
            joblib.dump(pipe, modelo)
            (tmp / "m" / "manifest.json").write_text(json.dumps({"detectors": {"if_prueba": {"calibration": {
                "comparison": "score < threshold", "threshold": -0.55}}}}), encoding="utf-8")
        salida = tmp / nombre
        sys.argv = ["replay_motor.py", "--motor", str(RAIZ / "scripts/engine/motor_decision.py"),
                    "--pcap-dir", str(capt), "--eve", str(eve), "--desde", str(self.T0 + 10),
                    "--hasta", str(self.T0 + 440), "--salida", str(salida), *extra_arnes, "--",
                    "--model-path", str(modelo), "--manifest-path", str(tmp / "m" / "manifest.json"),
                    "--detector-name", "if_prueba", "--entity-network", "10.10.0.0/16",
                    "--step-seconds", "10", "--history-seconds", str(self.HORIZONTE), *extra_motor]
        self.assertEqual(replay_motor.main(), 0)
        return [json.loads(x) for x in (salida / "motor_decision.log").read_text(encoding="utf-8").splitlines()]

    def test_cancelaciones_justificadas_y_sin_perdidas(self):
        import datetime as dt
        iso = lambda a: dt.datetime.fromtimestamp(a, dt.timezone.utc).isoformat()  # noqa: E731
        epoch = lambda s: dt.datetime.fromisoformat(s).timestamp()  # noqa: E731
        with tempfile.TemporaryDirectory() as d:
            tmp = Path(d)
            capt, eve, paquetes = self.escenario(tmp)
            for nombre, extra_arnes, extra_motor in (
                    ("eventos-retraso", ["--retraso-cierre", "3"], ["--disparo", "eventos"]),
                    ("periodico", [], ["--disparo", "periodico"])):
                registro = self.correr(tmp, capt, eve, nombre, extra_arnes, extra_motor)
                with self.subTest(configuracion=nombre):
                    self.comprobar(registro, paquetes, iso, epoch)

    def comprobar(self, registro, paquetes, iso, epoch):
        dec = {(r["entity_ip"], r["window_end_utc"]) for r in registro if r["event"] == "decision"}
        noev = {(r["entity_ip"], r["window_end_utc"]): r for r in registro if r["event"] == "ventana_no_evaluada"}
        canc = [r for r in registro if r["event"] == "pendiente_cancelada"]
        self.assertFalse(any(r["motivo"] == "ventana_no_regenerada" for r in noev.values()))
        # el escenario ejercita el cambio de propietario
        self.assertTrue(any(r["entity_ip"] == "10.10.20.22" for r in canc), "sin cancelaciones del flujo largo")
        # 1. cada cancelacion: no registrable con su horizonte propio, registrable con el de su alta
        for r in canc:
            a = epoch(r["window_end_utc"])
            self.assertEqual(r["corte_propio"], a - self.HORIZONTE)
            self.assertNotIn(r["entity_ip"], self.registrables(paquetes, a, a - self.HORIZONTE))
            self.assertLess(r["corte_incorporacion"], r["corte_propio"])
            self.assertIn(r["entity_ip"], self.registrables(paquetes, a, r["corte_incorporacion"]))
            self.assertGreater(r["obs_pcap_incorporacion"], 0)
            self.assertTrue(r["paquetes_atribuidos_a"], "los paquetes no se pierden: van al otro extremo")
        # 2. ninguna ventana registrable se pierde ni se cancela (anclas con historia elegible)
        canceladas = {(r["entity_ip"], r["window_end_utc"]) for r in canc}
        for a in range(self.T0 + 90, self.T0 + 410, 10):
            for ent in self.registrables(paquetes, a, a - self.HORIZONTE):
                k = (ent, iso(a))
                self.assertNotIn(k, canceladas)
                self.assertTrue(k in dec or k in noev, "ventana registrable sin registro: %s" % (k,))
        # 3. limites temporales: paquete justo en la reticula -> anclas t..t+50, nunca t+60
        for ent, t in (("10.10.20.25", self.T0 + 200), ("10.10.20.26", self.T0 + 300)):
            vistas = sorted(epoch(w) - t for e, w in dec | set(noev) if e == ent)
            self.assertEqual(vistas, [0, 10, 20, 30, 40, 50], ent)
        # 4. sin actividad reciente: nada mas alla del ultimo paquete + 60 s
        ultimo = self.T0 + 150 + 19 * 0.25
        tardias = [r for r in registro if r.get("entity_ip") == "10.10.20.27"
                   and epoch(r["window_end_utc"]) >= ultimo + 60]
        self.assertEqual(tardias, [])


class ResolucionPendientesUnidad(unittest.TestCase):
    """registro_cancelacion y los limites de la regla causal, sin el motor."""

    def test_limites_de_la_regla_de_registro(self):
        t = 1000.0  # en la reticula
        self.assertEqual(inc.anclas_con_contenido([t], [], PASO, float("-inf"), float("inf")),
                         [1000, 1010, 1020, 1030, 1040, 1050])
        t = 1000.001
        self.assertEqual(inc.anclas_con_contenido([t], [], PASO, float("-inf"), float("inf")),
                         [1010, 1020, 1030, 1040, 1050, 1060])
        p = type("P", (), {"timestamp": 1000.0})()
        self.assertTrue(inc.con_contenido([p], [], 1000))
        self.assertTrue(inc.con_contenido([p], [], 1050))
        self.assertFalse(inc.con_contenido([p], [], 1060))
        self.assertFalse(inc.con_contenido([p], [], 990))

    def test_registro_de_cancelacion_con_evidencia(self):
        rnd = random.Random(3)
        a = 2000
        obs = v2.attribute_packets(sorted([
            paquete(rnd, a - 20, "10.10.30.11", "10.10.20.22", sport=22, dport=42000, flags=0x18),
            paquete(rnd, a - 10, "10.10.30.11", "10.10.20.22", sport=22, dport=42000, flags=0x18)],
            key=lambda p: p.timestamp), RED)
        r = inc.registro_cancelacion(("10.10.20.22", inc.clave_ventana(a)), a, a - 230, obs, [], 1990.0,
                                     {"corte_incorporacion": a - 240, "obs_pcap_incorporacion": 2,
                                      "obs_eve_incorporacion": 0}, 1995.0, 1996.0)
        self.assertEqual(r["event"], "pendiente_cancelada")
        self.assertEqual((r["obs_pcap_propio"], r["obs_eve_propio"]), (0, 0))
        self.assertEqual(r["paquetes_atribuidos_a"], {"10.10.30.11": 2})
        self.assertEqual(r["corte_propio"], a - 230)


if __name__ == "__main__":
    unittest.main()
