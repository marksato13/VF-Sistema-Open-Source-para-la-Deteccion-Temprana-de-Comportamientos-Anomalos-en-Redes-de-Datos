"""Pruebas de la Etapa 2: feed v2, publicador if_senal, agente v2, helper y rele.

Sin red y sin tocar el host: el helper se sustituye por uno falso salvo en las
pruebas marcadas `nft_real`, que solo corren como root con nft disponible (banco
Docker con --network none y NET_ADMIN en su propio espacio de red).
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ / "scripts" / "engine"))
sys.path.insert(0, str(RAIZ / "scripts" / "enforce"))
sys.path.insert(0, str(RAIZ / "deploy" / "enforcement"))

import feed  # noqa: E402
import publicar_feed_v2 as pub  # noqa: E402
import agente_enforce_v2 as ag  # noqa: E402
import cf_nft_helper as helper  # noqa: E402
import relay_eventos as rele  # noqa: E402

T0 = 1_800_000_000.0
HAY_OPENSSL = shutil.which("openssl") is not None
NFT_REAL = hasattr(os, "geteuid") and os.geteuid() == 0 and shutil.which("nft") is not None


def entrada(ip="10.10.20.30", destino="srv-dmz", alcance="todo", accion="BLOCK", hasta=T0 + 300, ev="e1"):
    e = {"ip": ip, "destino": destino, "alcance": alcance, "accion": accion, "hasta": hasta, "evento_id": ev}
    e["id"] = feed.id_entrada(ip, destino, alcance, accion, ev)
    return e


def feed_v2(entradas, seq=1, ahora=T0, vig=60):
    return feed.construir_v2(entradas, seq, ahora, vig)


# --- contrato v2 ------------------------------------------------------------

def test_v2_acepta_solo_su_destino_y_cuenta_ajenas():
    f = feed_v2([entrada(), entrada(destino="dc1", alcance="dns", accion="LIMIT", ev="e2")])
    v = feed.validar_v2(f, "srv-dmz", T0 + 1, None, set())
    assert v["estado"] == "aceptado" and [e["destino"] for e in v["entradas"]] == ["srv-dmz"] and v["ajenas"] == 1
    v = feed.validar_v2(f, "dc1", T0 + 1, None, set())
    assert [e["alcance"] for e in v["entradas"]] == ["dns"]


def test_v2_misma_ip_dos_destinos_simultaneos():
    f = feed_v2([entrada(), entrada(destino="dc1", alcance="dns", accion="LIMIT", ev="e2")])
    assert len(f["entradas"]) == 2
    assert {e["destino"] for e in f["entradas"]} == {"srv-dmz", "dc1"}


@pytest.mark.parametrize("version", [1, None, "2", 3])
def test_v2_rechaza_version(version):
    f = feed_v2([entrada()]); f["version"] = version
    assert feed.validar_v2(f, "srv-dmz", T0, None, set())["motivo"] == "version_no_soportada"


def test_v2_rechaza_feed_v1_desplegado():
    f1 = feed.construir([{"ip": "10.10.20.30", "accion": "BLOCK", "hasta": T0 + 300, "alcance": "all"}], ahora=T0)
    assert feed.validar_v2(f1, "srv-dmz", T0, None, set())["estado"] == "rechazado"


def test_v2_caducado_futuro_y_secuencias():
    f = feed_v2([entrada()], seq=5)
    assert feed.validar_v2(f, "srv-dmz", T0 + 61, None, set())["motivo"] == "feed_caducado"
    assert feed.validar_v2(f, "srv-dmz", T0 - 100, None, set())["motivo"] == "feed_del_futuro"
    assert feed.validar_v2(f, "srv-dmz", T0, 6, set())["motivo"] == "secuencia_anterior"
    assert feed.validar_v2(f, "srv-dmz", T0, 5, set())["estado"] == "repetido"
    assert feed.validar_v2(f, "srv-dmz", T0, 4, set())["estado"] == "aceptado"


@pytest.mark.parametrize("cambio,motivo", [
    ({"destino": "srv-web"}, "destino_desconocido"),
    ({"alcance": "all"}, "alcance_no_permitido"),       # entrada antigua v1
    ({"alcance": "dns"}, "alcance_no_permitido"),       # DNS en srv-dmz
    ({"alcance": None}, "alcance_desconocido"),
    ({"accion": "DROP"}, "accion_desconocida"),
    ({"ip": "10.10.20.300"}, "ip_invalida"),
    ({"ip": "10.10.10.21"}, "nunca_bloquear"),
    ({"hasta": T0 - 1}, "entrada_caducada"),
    ({"hasta": T0 + 99999}, "hasta_excesivo"),
    ({"hasta": "x"}, "hasta_invalido"),
])
def test_v2_rechazos_por_entrada(cambio, motivo):
    e = entrada(); e.update(cambio)
    if "hasta" not in cambio and "ip" not in cambio and motivo not in ("destino_desconocido",):
        pass
    f = feed_v2([e])
    v = feed.validar_v2(f, "srv-dmz", T0, None, {"10.10.10.21"})
    assert v["estado"] == "aceptado" and v["entradas"] == []
    assert v["rechazadas"][0]["motivo"] == motivo


def test_v2_dns_en_dc1_rechaza_todo():
    f = feed_v2([entrada(destino="dc1", alcance="todo")])
    v = feed.validar_v2(f, "dc1", T0, None, set())
    assert v["rechazadas"][0]["motivo"] == "alcance_no_permitido"


def test_v2_id_incoherente_y_duplicado():
    e = entrada(); e2 = dict(e); e3 = dict(e); e3["hasta"] = T0 + 100
    e4 = entrada(ev="otro"); e4["id"] = "deadbeefdeadbeef"
    v = feed.validar_v2(feed_v2([e, e2, e4]), "srv-dmz", T0, None, set())
    assert sorted(r["motivo"] for r in v["rechazadas"]) == ["id_duplicado", "id_incoherente"]


@pytest.mark.skipif(not HAY_OPENSSL, reason="sin openssl")
def test_v2_firma_cubre_destino_y_alcance(tmp_path):
    priv, pubk = tmp_path / "p.pem", tmp_path / "pub.pem"
    feed.generar_claves(str(priv), str(pubk))
    datos = feed.serializar(feed_v2([entrada(destino="dc1", alcance="dns", accion="LIMIT")]))
    firma = feed.firmar(datos, str(priv))
    assert feed.verificar(datos, firma, str(pubk))
    for a, b in ((b'"dc1"', b'"srv-dmz"'), (b'"dns"', b'"todo"'), (b'"secuencia":1', b'"secuencia":9')):
        assert not feed.verificar(datos.replace(a, b), firma, str(pubk))


# --- publicador candidato -----------------------------------------------------

def decision(ip="10.10.20.30", w="2026-11-01T08:47:30+00:00", t=T0, det="if_limpio_2026_10", dec="PERMIT",
             score=-0.4, heur=None):
    d = {"event": "decision", "entity_ip": ip, "window_end_utc": w, "logged_at": t, "decidido_en": t - 0.1,
         "detector_name": det, "decision": dec, "score": score, "decision_id": "%s|%s" % (ip, w)}
    if heur is not None:
        d["heuristicos"] = heur
        d["heuristico"] = heur[0] if heur else None
    return d


H_DNS = {"heuristico": "dns_entropy", "accion": "LIMIT", "motivo": "x"}
H_SCAN = {"heuristico": "port_scan", "accion": "BLOCK", "motivo": "y"}


def test_if_senal_alert_if_no_restringe():
    st = {}
    pub.incorporar([decision(dec="ALERT", score=-0.7)], st, pub.NUNCA_BLOQUEAR_V2, "if_senal")
    assert pub.entradas_vigentes(st, T0) == []
    st = {}
    pub.incorporar([decision(dec="ALERT", score=-0.7)], st, pub.NUNCA_BLOQUEAR_V2, "actual")
    assert [e["accion"] for e in pub.entradas_vigentes(st, T0)] == ["LIMIT"]


def test_senal_if_alfas():
    s = pub.senal_if(decision(score=-0.60))
    assert s["alfa_superados"] == ["0.05", "0.03"]
    assert pub.senal_if(decision(score=-0.5))["alfa_superados"] == []
    assert pub.senal_if(decision(score=-0.7))["alfa_superados"] == ["0.05", "0.03", "0.01"]


def test_destinos_separados_misma_ventana():
    st = {}
    pub.incorporar([decision(heur=[H_SCAN, H_DNS])], st, pub.NUNCA_BLOQUEAR_V2)
    v = sorted((e["destino"], e["alcance"], e["accion"]) for e in pub.entradas_vigentes(st, T0))
    assert v == [("dc1", "dns", "LIMIT"), ("srv-dmz", "todo", "BLOCK")]


def test_reprocesar_mismo_evento_no_renueva():
    st = {}
    d = decision(heur=[H_SCAN])
    pub.incorporar([d], st, pub.NUNCA_BLOQUEAR_V2)
    hasta = pub.entradas_vigentes(st, T0)[0]["hasta"]
    for _ in range(5):  # el publicador relee la misma decision (ventana de 120 s)
        assert pub.incorporar([d], st, pub.NUNCA_BLOQUEAR_V2) == []
    e = pub.entradas_vigentes(st, T0 + 200)[0]
    assert e["hasta"] == hasta == round(T0 + 300) and e["nivel"] == 1


def test_evento_nuevo_amplia_y_escala_por_destino():
    st = {}
    pub.incorporar([decision(heur=[H_SCAN])], st, pub.NUNCA_BLOQUEAR_V2)
    pub.incorporar([decision(w="2026-11-01T08:47:40+00:00", t=T0 + 10, heur=[H_SCAN])], st, pub.NUNCA_BLOQUEAR_V2)
    e = pub.entradas_vigentes(st, T0 + 11)[0]
    assert e["hasta"] == round(T0 + 310) and e["nivel"] == 1  # mismo episodio (<120 s): no escala
    pub.incorporar([decision(w="2026-11-01T09:00:00+00:00", t=T0 + 1000, heur=[H_SCAN])], st, pub.NUNCA_BLOQUEAR_V2)
    e = pub.entradas_vigentes(st, T0 + 1001)[0]
    assert e["nivel"] == 2 and e["hasta"] == round(T0 + 1000 + 1800)
    # La escalera de dc1 es independiente de la de srv-dmz.
    pub.incorporar([decision(w="2026-11-01T09:00:10+00:00", t=T0 + 1010, heur=[H_DNS])], st, pub.NUNCA_BLOQUEAR_V2)
    dns = [x for x in pub.entradas_vigentes(st, T0 + 1011) if x["destino"] == "dc1"][0]
    assert dns["accion"] == "LIMIT" and dns["hasta"] == round(T0 + 1010 + 300)


def test_limit_no_degrada_block_vigente_en_publicador():
    st = {}
    pub.incorporar([decision(heur=[H_SCAN])], st, pub.NUNCA_BLOQUEAR_V2)
    h_http = {"heuristico": "http_abuse", "accion": "LIMIT", "motivo": "z"}
    pub.incorporar([decision(w="2026-11-01T08:47:40+00:00", t=T0 + 10, heur=[h_http])], st, pub.NUNCA_BLOQUEAR_V2)
    assert [e["accion"] for e in pub.entradas_vigentes(st, T0 + 11)] == ["BLOCK"]


def test_dc2_en_nunca_bloquear_pero_su_senal_se_registra():
    st = {}
    d = decision(ip="10.10.10.21", dec="ALERT", score=-0.7, heur=[H_DNS])
    pub.incorporar([d], st, pub.NUNCA_BLOQUEAR_V2)
    assert pub.entradas_vigentes(st, T0) == []
    assert pub.senal_if(d)["alfa_superados"]  # la evaluacion no se excluye


def test_registro_sin_heuristicos_lista_usa_heuristico():
    d = decision(); d["heuristico"] = H_DNS
    assert [a["destino"] for a in pub.acciones_de(d)] == ["dc1"]


def test_legacy_auth_failure_heuristic_es_block_srv_dmz():
    a = pub.acciones_de(decision(det="auth_failure_heuristic", dec="ALERT"))
    assert [(x["destino"], x["accion"]) for x in a] == [("srv-dmz", "BLOCK")]


@pytest.mark.skipif(not HAY_OPENSSL, reason="sin openssl")
def test_publicador_seguir_publica_por_evento_y_traza(tmp_path):
    priv, pubk = tmp_path / "p.pem", tmp_path / "pub.pem"
    feed.generar_claves(str(priv), str(pubk))
    log = tmp_path / "motor.log"
    reloj = iter([T0 + i * 0.25 for i in range(1000)]).__next__
    log.write_text(json.dumps(decision(t=T0, heur=[H_SCAN])) + "\n", encoding="utf-8")
    args = ["--log", str(log), "--estado", str(tmp_path / "st.json"), "--clave-privada", str(priv),
            "--salida-feed", str(tmp_path / "feed.json"), "--salida-firma", str(tmp_path / "feed.sig"),
            "--traza", str(tmp_path / "traza.jsonl"), "--seguir", "--max-iteraciones", "3"]
    assert pub.main(args, reloj=reloj, dormir=lambda s: None) == 0
    traza = [json.loads(x) for x in (tmp_path / "traza.jsonl").read_text().splitlines()]
    assert len(traza) == 1 and traza[0]["nuevos"][0]["decision_id"].startswith("10.10.20.30|")
    datos = (tmp_path / "feed.json").read_bytes()
    assert feed.verificar(datos, (tmp_path / "feed.sig").read_bytes(), str(pubk))
    # Reinicio del publicador: el estado conserva los eventos y no renueva.
    assert pub.main(args, reloj=reloj, dormir=lambda s: None) == 0
    traza = [json.loads(x) for x in (tmp_path / "traza.jsonl").read_text().splitlines()]
    assert traza[-1]["nuevos"] == [] and traza[-1]["secuencia"] == 2
    f2 = json.loads((tmp_path / "feed.json").read_text())
    assert f2["entradas"][0]["hasta"] == round(T0 + 300)


# --- agente v2 con helper falso ---------------------------------------------

class HelperFalso:
    def __init__(self, reloj):
        self.sets = {"bloqueados": {}, "limitados": {}}
        self.reloj = reloj
        self.llamadas = []
        self.fallar = False

    def __call__(self, ops):
        self.llamadas.append(ops)
        if self.fallar:
            return {"ok": False, "error_nft": "simulado"}
        try:
            helper.validar({"perfil": "dns", "operaciones": ops})
        except helper.Rechazo as exc:
            return {"ok": False, "rechazo": str(exc)}
        for o in ops:
            if o["op"] == "anadir":
                self.sets[o["set"]][o["ip"]] = self.reloj() + o["timeout"]
            elif o["op"] == "quitar":
                self.sets[o["set"]].pop(o["ip"], None)
        return {"ok": True}

    def listar(self):
        ahora = self.reloj()
        return {"sets": {s: {ip: {"expira_s": int(h - ahora), "paquetes": 0}
                             for ip, h in d.items() if h > ahora} for s, d in self.sets.items()}}


class Reloj:
    def __init__(self, t):
        self.t = t

    def __call__(self):
        return self.t


@pytest.fixture
def claves(tmp_path):
    if not HAY_OPENSSL:
        pytest.skip("sin openssl")
    priv, pubk = tmp_path / "p.pem", tmp_path / "pub.pem"
    feed.generar_claves(str(priv), str(pubk))
    return priv, pubk


def agente(tmp_path, pubk, perfil="dns", reloj=None):
    reloj = reloj or Reloj(T0)
    a = argparse.Namespace(perfil=perfil, clave_publica=pubk, estado=tmp_path / ("st-%s.json" % perfil),
                           traza=tmp_path / ("traza-%s.jsonl" % perfil), helper="x", aplicar=True)
    h = HelperFalso(reloj)
    return ag.Agente(a, helper=h, reloj=reloj), h, reloj


def firmado(priv, obj):
    d = feed.serializar(obj)
    return d, feed.firmar(d, str(priv))


def test_agente_dns_aplica_solo_lo_suyo(tmp_path, claves):
    priv, pubk = claves
    a, h, _ = agente(tmp_path, pubk, "dns")
    f = feed_v2([entrada(), entrada(destino="dc1", alcance="dns", accion="LIMIT", ev="e2")])
    r = a.procesar(*firmado(priv, f))
    assert r["estado"] == "aceptado" and r["ajenas"] == 1
    assert h.sets["limitados"].keys() == {"10.10.20.30"} and h.sets["bloqueados"] == {}
    ev = [json.loads(x)["evento"] for x in a.a.traza.read_text().splitlines()]
    assert ev == ["recepcion", "aplicacion", "confirmacion"]


def test_agente_firma_invalida_no_toca_nada(tmp_path, claves):
    priv, pubk = claves
    a, h, _ = agente(tmp_path, pubk)
    d, s = firmado(priv, feed_v2([entrada(destino="dc1", alcance="dns", accion="LIMIT")]))
    r = a.procesar(d.replace(b"LIMIT", b"BLOCK"), s)
    assert r["motivo"] == "firma_invalida" and h.llamadas == []


def test_agente_duplicado_fuera_de_orden_y_caducado(tmp_path, claves):
    priv, pubk = claves
    a, h, reloj = agente(tmp_path, pubk)
    e = entrada(destino="dc1", alcance="dns", accion="LIMIT")
    assert a.procesar(*firmado(priv, feed_v2([e], seq=3)))["estado"] == "aceptado"
    n = len(h.llamadas)
    assert a.procesar(*firmado(priv, feed_v2([e], seq=3)))["estado"] == "repetido"
    assert a.procesar(*firmado(priv, feed_v2([e], seq=2)))["motivo"] == "secuencia_anterior"
    reloj.t = T0 + 120
    assert a.procesar(*firmado(priv, feed_v2([e], seq=4)))["motivo"] == "feed_caducado"
    assert len(h.llamadas) == n


def test_agente_releer_mismo_id_no_renueva(tmp_path, claves):
    priv, pubk = claves
    a, h, reloj = agente(tmp_path, pubk)
    e = entrada(destino="dc1", alcance="dns", accion="LIMIT", hasta=T0 + 300)
    a.procesar(*firmado(priv, feed_v2([e], seq=1)))
    hasta = h.sets["limitados"]["10.10.20.30"]
    reloj.t = T0 + 50
    a.procesar(*firmado(priv, feed_v2([e], seq=2, ahora=T0 + 50)))
    assert h.sets["limitados"]["10.10.20.30"] == hasta
    assert all(o["op"] != "anadir" for o in h.llamadas[-1]) if len(h.llamadas) > 2 else True


def test_agente_block_saca_de_limit_y_limit_no_degrada(tmp_path, claves):
    priv, pubk = claves
    a, h, reloj = agente(tmp_path, pubk, "dmz")
    a.procesar(*firmado(priv, feed_v2([entrada(accion="LIMIT", ev="a")], seq=1)))
    a.procesar(*firmado(priv, feed_v2([entrada(accion="BLOCK", ev="b")], seq=2)))
    assert "10.10.20.30" in h.sets["bloqueados"] and "10.10.20.30" not in h.sets["limitados"]
    a.procesar(*firmado(priv, feed_v2([entrada(accion="LIMIT", ev="c", hasta=T0 + 900)], seq=3)))
    assert "10.10.20.30" not in h.sets["limitados"]


def test_agente_fallo_helper_no_avanza_secuencia(tmp_path, claves):
    priv, pubk = claves
    a, h, _ = agente(tmp_path, pubk)
    h.fallar = True
    e = entrada(destino="dc1", alcance="dns", accion="LIMIT")
    assert a.procesar(*firmado(priv, feed_v2([e], seq=1)))["estado"] == "error_aplicacion"
    h.fallar = False
    assert a.procesar(*firmado(priv, feed_v2([e], seq=1)))["estado"] == "aceptado"


def test_agente_reinicio_conserva_secuencia_y_no_acorta(tmp_path, claves):
    priv, pubk = claves
    a, h, reloj = agente(tmp_path, pubk)
    e = entrada(destino="dc1", alcance="dns", accion="LIMIT", hasta=T0 + 300)
    a.procesar(*firmado(priv, feed_v2([e], seq=7)))
    b = ag.Agente(a.a, helper=h, reloj=reloj)  # mismo estado en disco, mismo nft
    assert b.procesar(*firmado(priv, feed_v2([e], seq=7)))["estado"] == "repetido"
    assert b.procesar(*firmado(priv, feed_v2([e], seq=6)))["motivo"] == "secuencia_anterior"


def test_agente_observa_retirada(tmp_path, claves):
    priv, pubk = claves
    a, h, reloj = agente(tmp_path, pubk)
    a.procesar(*firmado(priv, feed_v2([entrada(destino="dc1", alcance="dns", accion="LIMIT", hasta=T0 + 30)])))
    reloj.t = T0 + 31
    a.observar()
    ev = [json.loads(x) for x in a.a.traza.read_text().splitlines()]
    assert ev[-1]["evento"] == "retirada" and ev[-1]["ip"] == "10.10.20.30"


def test_agente_sin_feed_v1(tmp_path, claves):
    priv, pubk = claves
    a, h, _ = agente(tmp_path, pubk, "dmz")
    f1 = feed.construir([{"ip": "10.10.20.30", "accion": "BLOCK", "hasta": T0 + 300, "alcance": "all"}], ahora=T0)
    assert a.procesar(*firmado(priv, f1))["motivo"] == "version_no_soportada" and h.llamadas == []


# --- helper: validacion (sin root) ------------------------------------------

@pytest.mark.parametrize("pet,motivo", [
    ({"perfil": "dns"}, "peticion_mal_formada"),
    ({"perfil": "x", "operaciones": [{"op": "asegurar"}]}, "perfil_desconocido"),
    ({"perfil": "dns", "operaciones": [{"op": "flush"}]}, "op_desconocida"),
    ({"perfil": "dns", "operaciones": [{"op": "anadir", "set": "limitados", "ip": "10.10.20.30"}]},
     "campos_invalidos:anadir"),
    ({"perfil": "dns", "operaciones": [{"op": "anadir", "set": "x; flush ruleset", "ip": "10.10.20.30",
                                         "timeout": 5}]}, "set_desconocido"),
    ({"perfil": "dns", "operaciones": [{"op": "anadir", "set": "limitados", "ip": "10.10.20.30 }; flush ruleset",
                                         "timeout": 5}]}, "ip_invalida"),
    ({"perfil": "dns", "operaciones": [{"op": "anadir", "set": "limitados", "ip": "10.10.20.030", "timeout": 5}]},
     "ip_invalida"),
    ({"perfil": "dns", "operaciones": [{"op": "anadir", "set": "limitados", "ip": "127.0.0.1", "timeout": 5}]},
     "ip_especial"),
    ({"perfil": "dns", "operaciones": [{"op": "anadir", "set": "limitados", "ip": "10.10.10.21", "timeout": 5}]},
     "ip_nunca_bloquear"),
    ({"perfil": "dns", "operaciones": [{"op": "anadir", "set": "limitados", "ip": "10.10.20.30", "timeout": 0}]},
     "timeout_fuera_de_rango"),
    ({"perfil": "dns", "operaciones": [{"op": "anadir", "set": "limitados", "ip": "10.10.20.30",
                                         "timeout": 99999}]}, "timeout_fuera_de_rango"),
    ({"perfil": "dns", "operaciones": [{"op": "anadir", "set": "limitados", "ip": "10.10.20.30",
                                         "timeout": True}]}, "timeout_fuera_de_rango"),
    ({"perfil": "dns", "operaciones": [{"op": "listar"}, {"op": "asegurar"}]}, "listar_y_desinstalar_van_solos"),
    ({"perfil": "dns", "operaciones": []}, "operaciones_invalidas"),
    ({"perfil": "dns", "operaciones": [{"op": "asegurar"}] * 513}, "operaciones_invalidas"),
    ({"perfil": "dns", "operaciones": [{"op": "asegurar", "tabla": "filter"}]}, "campos_invalidos:asegurar"),
])
def test_helper_rechaza(pet, motivo):
    r = helper.ejecutar(pet, nft="/no/existe/nft")
    assert r == {"ok": False, "rechazo": motivo}


def test_helper_una_invalida_rechaza_todo_el_lote():
    pet = {"perfil": "dmz", "operaciones": [
        {"op": "anadir", "set": "bloqueados", "ip": "10.10.20.30", "timeout": 60},
        {"op": "anadir", "set": "bloqueados", "ip": "10.10.60.11", "timeout": 60}]}
    assert helper.ejecutar(pet, nft="/no/existe")["rechazo"] == "ip_nunca_bloquear"


def test_helper_texto_solo_su_tabla():
    t = helper.texto("dns", [{"op": "asegurar"}, {"op": "anadir", "set": "limitados", "ip": "10.10.20.30",
                                                   "timeout": 60}])
    tablas = {l.split()[3] for l in t.splitlines() if l.startswith(("add ", "flush "))
              and l.split()[2] == "inet" or l.split()[1] in ("set", "chain", "rule", "element")}
    assert all(" inet cyberflow_dns " in l + " " for l in t.splitlines() if l)
    assert "th dport 53" in t and "flush ruleset" not in t
    assert helper.texto("dmz", [{"op": "desinstalar"}]) == "destroy table inet cyberflow_dmz\n"
    assert tablas  # se genero algo


def test_helper_cli_sin_argumentos():
    r = subprocess.run([sys.executable, str(RAIZ / "scripts/enforce/cf_nft_helper.py"), "--x"],
                       capture_output=True, text=True, stdin=subprocess.DEVNULL)
    assert r.returncode == 2 and "sin_argumentos" in r.stdout


@pytest.mark.skipif(not NFT_REAL, reason="requiere root y nft (banco Docker)")
def test_helper_nft_real_ciclo_completo():
    nft = shutil.which("nft")
    subprocess.run([nft, "destroy", "table", "inet", "cyberflow_dns"], capture_output=True)
    ops = [{"op": "asegurar"}, {"op": "anadir", "set": "limitados", "ip": "10.10.20.30", "timeout": 120},
           {"op": "anadir", "set": "bloqueados", "ip": "10.10.20.31", "timeout": 2}]
    assert helper.ejecutar({"perfil": "dns", "operaciones": ops}, nft=nft)["ok"]
    est = helper.ejecutar({"perfil": "dns", "operaciones": [{"op": "listar"}]}, nft=nft)["estado"]
    assert set(est["sets"]["limitados"]) == {"10.10.20.30"} and len(est["reglas"]) == 2
    # Reaplicar 'asegurar' no duplica reglas ni vacia sets.
    assert helper.ejecutar({"perfil": "dns", "operaciones": [{"op": "asegurar"}]}, nft=nft)["ok"]
    est = helper.ejecutar({"perfil": "dns", "operaciones": [{"op": "listar"}]}, nft=nft)["estado"]
    assert len(est["reglas"]) == 2 and "10.10.20.30" in est["sets"]["limitados"]
    import time as _t
    _t.sleep(3)  # caducidad nativa
    est = helper.ejecutar({"perfil": "dns", "operaciones": [{"op": "listar"}]}, nft=nft)["estado"]
    assert "10.10.20.31" not in est["sets"]["bloqueados"]
    assert helper.ejecutar({"perfil": "dns", "operaciones": [{"op": "retirar_origen", "ip": "10.10.20.30"}]},
                           nft=nft)["ok"]
    est = helper.ejecutar({"perfil": "dns", "operaciones": [{"op": "listar"}]}, nft=nft)["estado"]
    assert est["sets"]["limitados"] == {}
    assert helper.ejecutar({"perfil": "dns", "operaciones": [{"op": "desinstalar"}]}, nft=nft)["ok"]
    r = subprocess.run([nft, "list", "tables"], capture_output=True, text=True)
    assert "cyberflow_dns" not in r.stdout


# --- rele por eventos ---------------------------------------------------------

def test_rele_reenvia_solo_cambios_y_reintenta(tmp_path):
    origen, d1, d2 = tmp_path / "o", tmp_path / "d1", tmp_path / "d2"
    for d in (origen, d1):
        d.mkdir()
    (origen / "feed.json").write_bytes(b'{"secuencia": 1}\n'); (origen / "feed.sig").write_bytes(b"s1")
    r = rele.Rele({"dir": str(origen), "host": None, "identidad": None},
                  [{"nombre": "srv-dmz", "dir": str(d1)}, {"nombre": "dc1", "dir": str(d2)}],
                  rele.TransporteLocal(), tmp_path / "t.jsonl")
    reg = r.paso()
    assert reg["secuencia"] == 1 and "entregado_en" in reg["destinos"]["srv-dmz"]
    assert "error" in reg["destinos"]["dc1"]  # d2 no existe: fallo de comunicacion
    assert (d1 / "feed.json").read_bytes() == b'{"secuencia": 1}\n'
    d2.mkdir()
    reg = r.paso()
    assert list(reg["destinos"]) == ["dc1"]  # reintento solo donde fallo
    assert r.paso() is None  # sin cambios, nada que reenviar
    (origen / "feed.json").write_bytes(b'{"secuencia": 2}\n'); (origen / "feed.sig").write_bytes(b"s2")
    reg = r.paso()
    assert reg["secuencia"] == 2 and set(reg["destinos"]) == {"srv-dmz", "dc1"}
    assert (d2 / "feed.sig").read_bytes() == b"s2"


def test_rele_parsea_destinos():
    d = rele.parsear_destino("dc1=adminctl@10.10.10.20:/home/x/enforce,~/.ssh/k")
    assert d == {"nombre": "dc1", "host": "adminctl@10.10.10.20", "dir": "/home/x/enforce", "identidad": "~/.ssh/k"}


# --- limpieza D5 en seco -------------------------------------------------------

import limpiar_origen as limpiar  # noqa: E402


def _estado_mixto():
    st = {"10.10.20.30": {"bloqueos": 2, "ultimo_visto": T0}, "10.10.20.40": {"bloqueos": 1, "ultimo_visto": T0}}
    pub.incorporar([decision(heur=[H_SCAN, H_DNS]), decision(ip="10.10.20.40", heur=[H_SCAN])], st,
                   pub.NUNCA_BLOQUEAR_V2)
    return st


def test_limpieza_en_seco_no_toca_original(tmp_path):
    est = tmp_path / "estado.json"
    est.write_text(json.dumps(_estado_mixto()), encoding="utf-8")
    antes = est.read_bytes()
    rc = limpiar.main(["--ip", "10.10.20.30", "--estado-publicador", str(est), "--respaldo", str(tmp_path / "r"),
                       "--informe", str(tmp_path / "inf.json")])
    inf = json.loads((tmp_path / "inf.json").read_text())
    assert rc == 0 and est.read_bytes() == antes and inf["original_intacto"]
    seco = json.loads((tmp_path / "r" / "estado.json.seco").read_text())
    assert not limpiar.presente(seco, "10.10.20.30") and limpiar.presente(seco, "10.10.20.40")
    q = inf["pasos"]["2_3_publicador_y_escalada"]["quitado"]
    assert q["v1"] == ["10.10.20.30"] and len(q["vigentes"]) == 2 and sorted(q["escalada"]) == [
        "10.10.20.30@dc1", "10.10.20.30@srv-dmz"]


def test_limpieza_rechaza_infraestructura(tmp_path):
    est = tmp_path / "estado.json"; est.write_text("{}")
    with pytest.raises(SystemExit):
        limpiar.main(["--ip", "10.10.10.21", "--estado-publicador", str(est), "--respaldo", str(tmp_path / "r"),
                      "--informe", str(tmp_path / "i.json")])


@pytest.mark.skipif(not NFT_REAL, reason="requiere root y nft (banco Docker)")
def test_limpieza_con_helper_real(tmp_path):
    nft = shutil.which("nft")
    for perfil in ("dmz", "dns"):
        assert helper.ejecutar({"perfil": perfil, "operaciones": [
            {"op": "asegurar"}, {"op": "anadir", "set": "bloqueados", "ip": "10.10.20.30", "timeout": 300},
            {"op": "anadir", "set": "limitados", "ip": "10.10.20.40", "timeout": 300}]}, nft=nft)["ok"]
    est = tmp_path / "estado.json"
    est.write_text(json.dumps(_estado_mixto()), encoding="utf-8")
    rc = limpiar.main(["--ip", "10.10.20.30", "--estado-publicador", str(est), "--respaldo", str(tmp_path / "r"),
                       "--informe", str(tmp_path / "inf.json"),
                       "--helper-orden", "%s %s" % (sys.executable, RAIZ / "scripts/enforce/cf_nft_helper.py")])
    assert rc == 0
    for perfil in ("dmz", "dns"):
        e = helper.ejecutar({"perfil": perfil, "operaciones": [{"op": "listar"}]}, nft=nft)["estado"]["sets"]
        assert "10.10.20.30" not in e["bloqueados"] and "10.10.20.40" in e["limitados"]
        helper.ejecutar({"perfil": perfil, "operaciones": [{"op": "desinstalar"}]}, nft=nft)


# --- comando forzado de las llaves del rele ---------------------------------------

@pytest.mark.skipif(shutil.which("sh") is None or os.name == "nt", reason="requiere sh POSIX")
def test_comando_forzado_rele(tmp_path):
    sc = str(RAIZ / "deploy/enforcement/candidato-etapa2/cf-feed-ssh.sh")
    d = str(tmp_path)
    (tmp_path / "feed.json").write_bytes(b"F")

    def correr(modo, orden, entrada=b""):
        env = dict(os.environ, SSH_ORIGINAL_COMMAND=orden)
        return subprocess.run(["sh", sc, modo, d], input=entrada, capture_output=True, env=env)

    assert correr("servir", "cat %s/feed.json" % d).stdout == b"F"
    r = correr("recibir", "cat > %s/.feed.sig.tmp && mv -f %s/.feed.sig.tmp %s/feed.sig" % (d, d, d), b"S")
    assert r.returncode == 0 and (tmp_path / "feed.sig").read_bytes() == b"S"
    for malo in ("cat /etc/shadow", "cat %s/feed.json; id" % d, "rm -rf %s" % d, ""):
        assert correr("servir", malo).returncode != 0
    assert correr("recibir", "cat > /tmp/x && mv -f /tmp/x %s/feed.json" % d, b"X").returncode != 0
    assert (tmp_path / "feed.json").read_bytes() == b"F"


@pytest.mark.skipif(not NFT_REAL, reason="requiere root y nft (banco Docker)")
def test_helper_dmz_no_toca_la_tabla_del_v1():
    nft = shutil.which("nft")
    v1 = ("add table inet cyberflow\n"
          "add set inet cyberflow cyberflow_bloqueados { type ipv4_addr; flags timeout; }\n"
          "add chain inet cyberflow entrada { type filter hook input priority -10; policy accept; }\n"
          "add rule inet cyberflow entrada ip saddr @cyberflow_bloqueados drop\n"
          "add element inet cyberflow cyberflow_bloqueados { 10.10.20.50 timeout 300s }\n")
    subprocess.run([nft, "-f", "-"], input=v1, text=True, check=True)
    antes = subprocess.run([nft, "list", "table", "inet", "cyberflow"], capture_output=True, text=True).stdout
    assert helper.ejecutar({"perfil": "dmz", "operaciones": [
        {"op": "asegurar"}, {"op": "anadir", "set": "bloqueados", "ip": "10.10.20.30", "timeout": 60}]}, nft=nft)["ok"]
    assert helper.ejecutar({"perfil": "dmz", "operaciones": [{"op": "desinstalar"}]}, nft=nft)["ok"]
    despues = subprocess.run([nft, "list", "table", "inet", "cyberflow"], capture_output=True, text=True).stdout
    quitar_exp = lambda s: "\n".join(l for l in s.splitlines() if "expires" not in l)  # noqa: E731
    assert quitar_exp(antes) == quitar_exp(despues) and "10.10.20.50" in despues
    subprocess.run([nft, "destroy", "table", "inet", "cyberflow"], check=True)
