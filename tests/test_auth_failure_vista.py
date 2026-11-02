"""Cierre de la Etapa 3, hallazgo 2: auth_failure_heuristic y los registros HTTP tardíos.

En 585da7b el motor convertía PERMIT en ALERT con las columnas http_* del IF, que cuentan
también las transacciones que Suricata registra tarde (sin tramas de su flujo), y el
publicador convertía cualquier ALERT ``*_heuristic`` en BLOCK. Así una entidad con 0
peticiones válidas en la vista HTTP podía acabar bloqueada.

Ahora la condición histórica se registra (auth_failure.historico) pero solo la vista
autoriza la respuesta (auth_failure.autoriza), y el publicador lo vuelve a exigir.
El modelo, el escalador, las 28 características y los 3 α no cambian.
"""
from __future__ import annotations

import datetime as dt
import json
import random
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ / "scripts" / "engine"))
sys.path.insert(0, str(RAIZ / "scripts" / "features"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import publicar_feed_v2 as pub  # noqa: E402

T0 = 1_800_000_000.0
ATK = "10.10.20.30"


def decision(ip=ATK, t=T0, dec="PERMIT", det="if_limpio_2026_10", score=-0.3, heur=None,
             http_vista=None, auth_failure=None, w=None):
    w = w or dt.datetime.fromtimestamp(t - 2, dt.timezone.utc).isoformat()
    d = {"event": "decision", "entity_ip": ip, "window_end_utc": w, "logged_at": t, "decidido_en": t - 0.1,
         "detector_name": det, "decision": dec, "score": score, "decision_id": "%s|%s" % (ip, w),
         "heuristicos": heur or []}
    if http_vista is not None:
        d["http_vista"] = http_vista
    if auth_failure is not None:
        d["auth_failure"] = auth_failure
    return d


def vista(validas, ratio, tardias):
    return {"httph_peticiones_60s": validas, "httph_fallo_auth_ratio_60s": ratio,
            "httph_tardios_excluidos_60s": tardias}


BF = [{"heuristico": "brute_force", "accion": "BLOCK", "motivo": "x"}]


class Publicador(unittest.TestCase):
    def test_solo_http_tardio_ni_nueva_ni_renovacion(self):
        # Registro del motor 585da7b: ALERT por auth_failure con 0 peticiones validas.
        st = {}
        n = pub.incorporar([decision(dec="ALERT", det="auth_failure_heuristic", score=None,
                                     http_vista=vista(0, 0.0, 40))], st, pub.NUNCA_BLOQUEAR_V2)
        self.assertEqual([x["tipo"] for x in n], ["rechazada"])
        self.assertEqual(pub.entradas_vigentes(st, T0), [])
        # Con una restriccion vigente por evidencia valida, el tardio posterior no la renueva.
        st = {}
        pub.incorporar([decision(t=T0, dec="ALERT", det="auth_failure_heuristic", score=None,
                                 http_vista=vista(8, 1.0, 0))], st, pub.NUNCA_BLOQUEAR_V2)
        (antes,) = pub.entradas_vigentes(st, T0 + 1)
        n = pub.incorporar([decision(t=T0 + 90, dec="ALERT", det="auth_failure_heuristic", score=None,
                                     http_vista=vista(0, 0.0, 300))], st, pub.NUNCA_BLOQUEAR_V2)
        self.assertEqual([x["tipo"] for x in n], ["rechazada"])
        (despues,) = pub.entradas_vigentes(st, T0 + 91)
        self.assertEqual((despues["id"], despues["hasta"]), (antes["id"], antes["hasta"]))
        # Motor corregido: el mismo caso ya llega como PERMIT con la senal historica anotada.
        st = {}
        n = pub.incorporar([decision(auth_failure={"historico": True, "vista": False, "autoriza": False},
                                     http_vista=vista(0, 0.0, 40))], st, pub.NUNCA_BLOQUEAR_V2)
        self.assertEqual(n, [])
        self.assertEqual(pub.entradas_vigentes(st, T0), [])

    def test_fuerza_bruta_vigente_con_evidencia_valida_se_conserva(self):
        st = {}
        n = pub.incorporar([decision(dec="ALERT", det="auth_failure_heuristic", score=None, heur=BF,
                                     http_vista=vista(12, 1.0, 0),
                                     auth_failure={"historico": True, "vista": True, "autoriza": True})],
                           st, pub.NUNCA_BLOQUEAR_V2)
        self.assertEqual([(x["tipo"], x["regla"], x["accion"]) for x in n],
                         [("nueva", "auth_failure_heuristic", "BLOCK"), ("mantenida", "brute_force", "BLOCK")])
        v = pub.entradas_vigentes(st, T0 + 1)
        self.assertEqual([(e["ip"], e["destino"], e["accion"]) for e in v], [(ATK, "srv-dmz", "BLOCK")])

    def test_http_legitimo_con_anomalia_exclusiva_del_if_respeta_if_senal(self):
        d = decision(dec="ALERT", score=-0.7, http_vista=vista(30, 0.0, 0))
        st = {}
        self.assertEqual(pub.incorporar([d], st, pub.NUNCA_BLOQUEAR_V2, "if_senal"), [])
        self.assertEqual(pub.entradas_vigentes(st, T0), [])
        s = pub.senal_if(d)
        self.assertEqual(s["alfa_superados"], ["0.05", "0.03", "0.01"])  # la senal del IF se conserva
        st = {}
        pub.incorporar([d], st, pub.NUNCA_BLOQUEAR_V2, "actual")
        self.assertEqual([e["accion"] for e in pub.entradas_vigentes(st, T0)], ["LIMIT"])

    def test_valida_y_tardia_mezcladas_solo_la_valida_justifica(self):
        # 3 validas (bajo el minimo de 5) + 200 tardias: no hay accion.
        st = {}
        rech = []
        d = decision(dec="ALERT", det="auth_failure_heuristic", score=None, http_vista=vista(3, 1.0, 200))
        self.assertEqual(pub.acciones_de(d, rechazadas=rech), [])
        self.assertIn("3 peticiones validas, 200 tardias", rech[0]["motivo_rechazo"])
        pub.incorporar([d], st, pub.NUNCA_BLOQUEAR_V2)
        self.assertEqual(pub.entradas_vigentes(st, T0), [])
        # 6 validas, todas fallidas, + 200 tardias: la evidencia valida basta por si sola.
        d = decision(dec="ALERT", det="auth_failure_heuristic", score=None, http_vista=vista(6, 1.0, 200))
        self.assertEqual([a["accion"] for a in pub.acciones_de(d)], ["BLOCK"])
        # validas con ratio de fallo bajo (las tardias eran los 401): no hay accion.
        d = decision(dec="ALERT", det="auth_failure_heuristic", score=None, http_vista=vista(20, 0.1, 200))
        self.assertEqual(pub.acciones_de(d), [])


# --- recorrido completo: motor real (replay) -> registro -> publicador -> feed firmado --------

SRV = "10.10.30.10"
A_VALIDA, B_TARDIA, C_POCAS, D_MEZCLA = "10.10.20.30", "10.10.20.31", "10.10.20.32", "10.10.20.33"


def _escenario(tmp: Path, t0: int):
    import extract_multilayer_v2 as v2
    from test_motor_incremental import _trama, _escribir_pcap
    rnd = random.Random(11)
    capt = tmp / "pcap"
    capt.mkdir()
    tramas, eventos = [], []
    fid = [1000]

    def iso(t):
        return dt.datetime.fromtimestamp(t, dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%f+0000")

    def tcp(t, s, d, sp, dp, fl, seq, pay=b""):
        p = v2.ParsedPacket(timestamp=t, src_ip=s, dst_ip=d, ip_length=40 + len(pay), protocol=6, ttl=64,
                            src_port=sp, dst_port=dp, tcp_flags=fl, tcp_seq=seq, tcp_payload_length=len(pay))
        tramas.append((t, _trama(p, 20, rnd.randint(1, 60000), pay)))

    def http(t, src, sp, estado, con_tramas):
        if con_tramas:
            tcp(t - 0.05, src, SRV, sp, 80, 0x02, 1)
            tcp(t - 0.04, SRV, src, 80, sp, 0x12, 9)
            tcp(t - 0.03, src, SRV, sp, 80, 0x18, 2, b"P" * 60)
            tcp(t + 0.01, SRV, src, 80, sp, 0x18, 10, b"R" * 60)
        fid[0] += 1
        eventos.append({"timestamp": iso(t), "event_type": "http", "src_ip": src, "src_port": sp,
                        "dest_ip": SRV, "dest_port": 80, "flow_id": fid[0], "tx_id": 0,
                        "http": {"status": estado, "http_method": "POST", "url": "/login"}})

    for k in range(0, 150):
        t = t0 + k + 0.5
        # B: trafico TCP propio (a 443) pero sus 401 no tienen ninguna trama del flujo.
        if k % 5 == 0:
            for who in (B_TARDIA, C_POCAS):
                tcp(t + 0.2, who, SRV, 30000 + k, 443, 0x02, 1)
                tcp(t + 0.21, SRV, who, 443, 30000 + k, 0x12, 1)
        if k % 3 == 0:
            http(t, A_VALIDA, 50000 + k, 401, True)          # A: fuerza bruta con tramas
        if k % 2 == 0:
            http(t + 0.1, B_TARDIA, 51000 + k, 401, False)   # B: solo tardios
            http(t + 0.1, C_POCAS, 52000 + k, 401, False)    # C: tardios ...
            http(t + 0.1, D_MEZCLA, 53000 + k, 401, False)   # D: tardios ...
        if k % 20 == 0:
            http(t + 0.3, C_POCAS, 54000 + k, 401, True)      # ... + 3 validas por minuto
        if k % 8 == 0:
            http(t + 0.3, D_MEZCLA, 55000 + k, 401, True)     # ... + 7-8 validas por minuto
    tramas.sort(key=lambda x: x[0])
    for i in range(11):
        s, f = t0 + 15 * i, t0 + 15 * (i + 1)
        nombre = dt.datetime.fromtimestamp(s, dt.timezone.utc).strftime("live-%Y%m%d%H%M%S.pcap")
        _escribir_pcap(capt / nombre, [x for x in tramas if s <= x[0] < f])
    eventos.sort(key=lambda e: e["timestamp"])
    eve = tmp / "eve.json"
    eve.write_bytes("".join(json.dumps(e) + "\n" for e in eventos).encode("utf-8"))
    return capt, eve


class RecorridoCompleto(unittest.TestCase):
    def test_del_registro_del_motor_a_las_entradas_del_feed(self):
        try:
            import joblib
            import numpy as np
            from sklearn.ensemble import IsolationForest
            from sklearn.pipeline import make_pipeline
            from sklearn.preprocessing import StandardScaler
        except ImportError:  # pragma: no cover
            self.skipTest("sin scikit-learn")
        if shutil.which("openssl") is None:
            self.skipTest("sin openssl")
        import feed
        import replay_motor
        t0 = 1_793_260_800
        with tempfile.TemporaryDirectory() as d:
            tmp = Path(d)
            capt, eve = _escenario(tmp, t0)
            pipe = make_pipeline(StandardScaler(), IsolationForest(n_estimators=20, random_state=0))
            pipe.fit(np.random.default_rng(1).normal(size=(300, 28)))
            modelo = tmp / "m" / "modelo.joblib"
            modelo.parent.mkdir()
            joblib.dump(pipe, modelo)
            # Umbral inalcanzable: el IF nunca da ALERT, asi toda ALERT es del heuristico y el
            # caso no depende del modelo de prueba.
            (tmp / "m" / "manifest.json").write_text(json.dumps({"detectors": {"if_prueba": {"calibration": {
                "comparison": "score < threshold", "threshold": -10.0}}}}), encoding="utf-8")
            salida = tmp / "salida"
            argv = sys.argv
            try:
                sys.argv = ["replay_motor.py", "--motor", str(RAIZ / "scripts/engine/motor_decision.py"),
                            "--pcap-dir", str(capt), "--eve", str(eve), "--desde", str(t0 + 10),
                            "--hasta", str(t0 + 165), "--salida", str(salida), "--",
                            "--model-path", str(modelo), "--manifest-path", str(tmp / "m" / "manifest.json"),
                            "--detector-name", "if_prueba", "--entity-network", "10.10.0.0/16",
                            "--excluir", "10.10.60.11/32", "--excluir-protocolos", "112,240",
                            "--step-seconds", "10", "--history-seconds", "90"]
                self.assertEqual(replay_motor.main(), 0)
            finally:
                sys.argv = argv
            log = salida / "motor_decision.log"
            registro = [json.loads(x) for x in log.read_text(encoding="utf-8").splitlines()]
            dec = [r for r in registro if r["event"] == "decision"]
            por = {ip: [r for r in dec if r["entity_ip"] == ip] for ip in (A_VALIDA, B_TARDIA, C_POCAS, D_MEZCLA)}

            # Motor: la senal historica se registra; solo la vista autoriza.
            for ip in (B_TARDIA, C_POCAS):
                self.assertTrue(por[ip], ip)
                self.assertTrue(any(r["auth_failure"] and r["auth_failure"]["historico"] for r in por[ip]), ip)
                self.assertFalse(any(r["decision"] == "ALERT" for r in por[ip]), ip)
                self.assertFalse(any(r["auth_failure"] and r["auth_failure"]["autoriza"] for r in por[ip]), ip)
                self.assertFalse(any(h["heuristico"] == "brute_force" for r in por[ip] for h in r["heuristicos"]), ip)
            self.assertTrue(any((r["http_vista"] or {}).get("httph_peticiones_60s") == 3 for r in por[C_POCAS]))
            for ip in (A_VALIDA, D_MEZCLA):
                alert = [r for r in por[ip] if r["detector_name"] == "auth_failure_heuristic"]
                self.assertTrue(alert, ip)
                for r in alert:
                    # cambio de decision final por la heuristica, separado de la del IF
                    self.assertEqual((r["decision"], r["decision_if"]), ("ALERT", "PERMIT"))
                    self.assertTrue(r["auth_failure"]["vista"] and r["auth_failure"]["autoriza"])
                    self.assertGreaterEqual(r["http_vista"]["httph_peticiones_60s"], 5)
            self.assertTrue(any(r["http_vista"]["httph_tardios_excluidos_60s"] > 0
                                for r in por[D_MEZCLA] if r["http_vista"]))

            # Publicador sobre ESE registro -> feed firmado.
            priv, pubk = tmp / "p.pem", tmp / "pub.pem"
            feed.generar_claves(str(priv), str(pubk))
            ahora = max(r["logged_at"] for r in dec) + 1
            args = ["--log", str(log), "--estado", str(tmp / "st.json"), "--clave-privada", str(priv),
                    "--salida-feed", str(tmp / "feed.json"), "--salida-firma", str(tmp / "feed.sig"),
                    "--traza", str(tmp / "traza.jsonl"), "--ventana-segundos", "100000"]
            self.assertEqual(pub.main(args, reloj=lambda: ahora), 0)
            datos = (tmp / "feed.json").read_bytes()
            self.assertTrue(feed.verificar(datos, (tmp / "feed.sig").read_bytes(), str(pubk)))
            entradas = json.loads(datos)["entradas"]
            self.assertEqual(sorted({e["ip"] for e in entradas}), [A_VALIDA, D_MEZCLA])
            self.assertTrue(all(e["accion"] == "BLOCK" and e["destino"] == "srv-dmz" for e in entradas))
            traza = [json.loads(x) for x in (tmp / "traza.jsonl").read_text(encoding="utf-8").splitlines()]
            nuevos = [x for t in traza for x in t["nuevos"]]
            self.assertFalse(any(x["ip"] in (B_TARDIA, C_POCAS) for x in nuevos))


if __name__ == "__main__":
    unittest.main()
