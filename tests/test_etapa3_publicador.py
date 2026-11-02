"""Etapa 3: integración de la vía rápida en el publicador v2 y renovación por evidencia reciente."""
from __future__ import annotations

import datetime as dt
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ / "scripts" / "engine"))

import publicar_feed_v2 as pub  # noqa: E402

ATK, SRV = "10.10.20.30", "10.10.30.10"


def t_(hms: str) -> float:
    return dt.datetime.fromisoformat("2026-11-01T%s+00:00" % hms).timestamp()


def ventana(w: str, t: float, heur: list, ip=ATK, score=None):
    return {"event": "decision", "entity_ip": ip, "window_end_utc": "2026-11-01T%s+00:00" % w, "logged_at": t,
            "decidido_en": t - 0.1, "detector_name": "if_limpio_2026_10", "decision": "PERMIT", "score": score,
            "decision_id": "%s|2026-11-01T%s+00:00" % (ip, w), "heuristicos": heur}


def senal(t_ev: float, destino=SRV, ident="a1", origen=ATK):
    return {"event": "senal_rapida", "regla": "port_scan_temprano", "id": ident, "origen": origen,
            "destino": destino, "t_evidencia": t_ev, "primer_intento_ventana": t_ev - 0.1,
            "puertos_fallidos": 10, "parametros": {"K": 10, "W": 2.0, "g": 0.1},
            "disponible_en": t_ev + 0.01, "emitido_en": t_ev + 0.02}


SCAN = [{"heuristico": "port_scan", "accion": "BLOCK", "motivo": "y"}]
HTTP = [{"heuristico": "http_abuse", "accion": "LIMIT", "motivo": "z"}]


def test_senal_rapida_bloquea_en_el_punto_que_protege_al_escaneado():
    st = {}
    n = pub.incorporar([pub.decision_de_senal_rapida(senal(t_("09:38:38.209")))], st, pub.NUNCA_BLOQUEAR_V2)
    assert [(x["tipo"], x["destino"], x["accion"], x["regla"]) for x in n] == [
        ("nueva", "srv-dmz", "BLOCK", "port_scan_temprano")]
    v = pub.entradas_vigentes(st, t_("09:38:39"))
    assert [(e["ip"], e["destino"], e["alcance"], e["accion"], e["nivel"]) for e in v] == [
        (ATK, "srv-dmz", "todo", "BLOCK", 1)]
    assert n[0]["senal_rapida"]["id"] == "a1"


def test_escaneo_a_un_host_sin_agente_no_restringe_en_otro_sitio():
    st = {}
    n = pub.incorporar([pub.decision_de_senal_rapida(senal(t_("09:38:38.209"), destino="10.10.10.20"))],
                       st, pub.NUNCA_BLOQUEAR_V2)
    assert [x["tipo"] for x in n] == ["sin_punto_de_aplicacion"]
    assert pub.entradas_vigentes(st, t_("09:38:39")) == []


def test_via_rapida_y_ventanas_del_mismo_escaneo_una_restriccion_un_peldano():
    st = {}
    pub.incorporar([pub.decision_de_senal_rapida(senal(t_("09:38:38.209")))], st, pub.NUNCA_BLOQUEAR_V2)
    hasta = pub.entradas_vigentes(st, t_("09:38:39"))[0]["hasta"]
    # las ventanas 09:38:40 y 09:38:50 (retrospectiva 30 s) contienen el mismo escaneo
    n = pub.incorporar([ventana("09:38:40", t_("09:38:42"), SCAN), ventana("09:38:50", t_("09:38:52"), SCAN)],
                       st, pub.NUNCA_BLOQUEAR_V2)
    assert [x["tipo"] for x in n] == ["mantenida", "mantenida"]
    v = pub.entradas_vigentes(st, t_("09:38:53"))
    assert len(v) == 1 and v[0]["hasta"] == hasta and v[0]["nivel"] == 1
    assert st["escalada"]["%s@srv-dmz" % ATK]["bloqueos"] == 1


def test_releer_ventanas_antiguas_no_extiende_indefinidamente():
    st = {}
    pub.incorporar([ventana("09:38:40", t_("09:38:42"), SCAN)], st, pub.NUNCA_BLOQUEAR_V2)
    h0 = pub.entradas_vigentes(st, t_("09:38:43"))[0]["hasta"]
    # ventanas posteriores que solo repiten la actividad de la primera: se mantienen
    for k, w in enumerate(("09:38:50", "09:39:00")):
        pub.incorporar([ventana(w, t_(w) + 2, SCAN)], st, pub.NUNCA_BLOQUEAR_V2)
    assert pub.entradas_vigentes(st, t_("09:39:05"))[0]["hasta"] == h0


def test_renovacion_heuristica_sin_score_del_if():
    """La renovación no depende de score != None: evidencia nueva sin score renueva."""
    st = {}
    pub.incorporar([ventana("09:00:00", t_("09:00:02"), HTTP, score=None)], st, pub.NUNCA_BLOQUEAR_V2)
    n = pub.incorporar([ventana("09:01:00", t_("09:01:02"), HTTP, score=None)], st, pub.NUNCA_BLOQUEAR_V2)
    assert [x["tipo"] for x in n] == ["renovada"]
    assert pub.entradas_vigentes(st, t_("09:01:03"))[0]["hasta"] == round(t_("09:01:02") + 300)


def test_escalada_limit_a_block_y_block_no_degradado():
    st = {}
    pub.incorporar([ventana("09:00:00", t_("09:00:02"), HTTP)], st, pub.NUNCA_BLOQUEAR_V2)
    n = pub.incorporar([ventana("09:00:10", t_("09:00:12"), SCAN)], st, pub.NUNCA_BLOQUEAR_V2)
    assert [x["tipo"] for x in n] == ["escalada"]
    n = pub.incorporar([ventana("09:00:20", t_("09:00:22"), HTTP)], st, pub.NUNCA_BLOQUEAR_V2)
    assert [(x["tipo"], x["motivo_mantenida"]) for x in n] == [("mantenida", "accion menos severa que la vigente")]
    assert [e["accion"] for e in pub.entradas_vigentes(st, t_("09:00:23"))] == ["BLOCK"]


def test_reglas_secundarias_quedan_en_la_traza():
    st = {}
    d = ventana("09:00:00", t_("09:00:02"), SCAN + HTTP)
    n = pub.incorporar([d], st, pub.NUNCA_BLOQUEAR_V2)
    assert sorted((x["regla"], x["tipo"]) for x in n) == [("http_abuse", "mantenida"), ("port_scan", "nueva")]


def test_releer_la_misma_senal_rapida_no_hace_nada():
    st = {}
    s = pub.decision_de_senal_rapida(senal(t_("09:38:38.209")))
    pub.incorporar([s], st, pub.NUNCA_BLOQUEAR_V2)
    assert pub.incorporar([s], st, pub.NUNCA_BLOQUEAR_V2) == []
