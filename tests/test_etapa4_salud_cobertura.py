"""Etapa 4: cobertura de las estadísticas SIGUSR1 de tcpdump en salud_captura.clasificar (2026-11-02.2).

Regresiones del defecto de la versión 2026-11-02.1: bastaba una lectura <= desde y otra >= hasta de cualquier PID.
Para comprobar que FALLAN sobre la versión anterior:
    SALUD_CAPTURA_PY=<ruta a la versión .1> python -m pytest tests/test_etapa4_salud_cobertura.py
(las de "cobertura válida" pasan en las dos versiones; las de "regresión" solo en la corregida).
"""
from __future__ import annotations

import importlib.util
import os
import sys
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parents[1]
_ruta = Path(os.environ.get("SALUD_CAPTURA_PY", RAIZ / "scripts" / "etapa4" / "salud_captura.py"))
_spec = importlib.util.spec_from_file_location("salud_captura_bajo_prueba", _ruta)
sc = importlib.util.module_from_spec(_spec)
sys.modules[_spec.name] = sc
_spec.loader.exec_module(sc)

CRIT = dict(sc.CRITERIOS)


def _m(t, kp=None, kd=0):
    """Muestra de salud sana (Suricata sin descartes, unidad estable, anillo sin saltos)."""
    return {"t": t,
            "suricata": {"ok": True, "t": t - 1, "uptime_s": 1000 + t, "kernel_packets": 100 * t if kp is None else kp,
                         "kernel_drops": kd},
            "unidades": {"ppi-motor-capture": {"ok": True, "pid": 7, "nrestarts": 0, "activo": "active",
                                               "arranque_mono_us": 7}},
            "anillo": {"ok": True, "salto_max_s": 5.0}}


INCS = sc.incrementos([_m(t) for t in range(-60, 200, 10)])  # muestras de salud cada 10 s, sanas


def _td(t, d=0, pid=1375, c=None, r=None):
    c = 1000 + int(t) * 10 if c is None else c
    return {"t": t, "pid": pid, "capturados": c, "recibidos_filtro": c + d if r is None else r,
            "descartados_kernel": d}


def clase(td, desde, hasta):
    return sc.clasificar(INCS, td, desde, hasta, CRIT)


# ------------------------------------------------------------------ regresiones (fallan en .1)

def test_regresion_caso_reproducido_dos_lecturas_lejanas():
    """Caso del encargo: muestras cada 10 s, SIGUSR1 solo en t=0 y t=120, periodo [10, 110] -> NO C0."""
    r = clase([_td(0), _td(120)], 10, 110)
    assert r["clase"] == "C3", r
    assert any("hueco" in m for m in r["motivos"])


def test_regresion_extremo_inicial_lejano():
    # lecturas cada 30 s dentro, pero la que acota el inicio está 60 s antes
    r = clase([_td(-50), _td(40), _td(70), _td(100), _td(130)], 10, 110)
    assert r["clase"] == "C3" and any("inicio" in m or "hueco" in m for m in r["motivos"])


def test_regresion_extremo_final_lejano():
    r = clase([_td(0), _td(30), _td(60), _td(90), _td(180)], 10, 110)
    assert r["clase"] == "C3" and any("fin" in m or "hueco" in m for m in r["motivos"])


def test_regresion_hueco_interior():
    # extremos bien, pero falta una lectura en medio (60 s entre 30 y 90)
    r = clase([_td(0), _td(30), _td(90), _td(120)], 10, 110)
    assert r["clase"] == "C3" and any("hueco" in m for m in r["motivos"])


def test_regresion_cambio_de_pid_dentro():
    # tcpdump reinició a mitad: el PID 1375 acota el inicio y el 2000 el fin
    td = [_td(0), _td(30), _td(60, pid=2000, c=5), _td(90, pid=2000, c=6), _td(120, pid=2000, c=7)]
    r = clase(td, 10, 110)
    assert r["clase"] == "C3" and any("PID" in m for m in r["motivos"])


def test_regresion_fuentes_mezcladas():
    # anillo (PID 1375) y vía rápida (PID 4242) en el mismo log: la vía no puede tapar el hueco del anillo
    td = [_td(0), _td(120)] + [_td(t, pid=4242) for t in (0, 30, 60, 90, 120)]
    assert clase(td, 10, 110)["clase"] == "C3"


def test_regresion_contador_que_decrece():
    td = [_td(0, c=500), _td(30, c=400), _td(60, c=600), _td(90, c=700), _td(120, c=800)]
    r = clase(td, 10, 110)
    assert r["clase"] == "C3" and any("decrece" in m for m in r["motivos"])


def test_regresion_contador_invalido():
    td = [_td(0), _td(30, c=900, r=10), _td(60), _td(90), _td(120)]
    r = clase(td, 10, 110)
    assert r["clase"] == "C3" and any("inválid" in m for m in r["motivos"])


# ------------------------------------------------------------------ cobertura válida (pasan en las dos)

def test_cobertura_valida_c0():
    td = [_td(t) for t in (0, 30, 60, 90, 120)]
    assert clase(td, 10, 110)["clase"] == "C0"


def test_cobertura_valida_con_tolerancia_declarada():
    # disparos con AccuracySec=1s y escritura: huecos de 31,6 s (> 30, <= 32) y extremo inicial a 31 s -> C0
    td = [_td(t) for t in (-21.0, 10.6, 42.2, 73.8, 105.4, 137.0)]
    assert clase(td, 10, 110)["clase"] == "C0"


def test_cobertura_valida_c2_con_descartes():
    td = [_td(0, d=0), _td(30, d=1), _td(60, d=3), _td(90, d=3), _td(120, d=5)]
    r = clase(td, 10, 110)
    assert r["clase"] == "C2"
    if hasattr(sc, "cobertura_tcpdump"):
        assert r["info"]["tcpdump"]["descartados_kernel"] == 5


def test_lectura_exacta_en_los_extremos():
    td = [_td(t) for t in (10, 40, 70, 100, 110)]
    assert clase(td, 10, 110)["clase"] == "C0"


# ------------------------------------------------------------------ más allá de la tolerancia y sin medida

def test_hueco_justo_por_encima_de_la_tolerancia():
    lim = CRIT["tcpdump_periodo_s"] + CRIT["tcpdump_tolerancia_s"]
    td = [_td(0), _td(30), _td(30 + lim + 0.1), _td(130)]
    assert clase(td, 10, 110)["clase"] == "C3"


def test_sin_lecturas_no_es_c0():
    assert clase([], 10, 110)["clase"] == "C3"


def test_lecturas_sin_hora_no_cuentan():
    td = [dict(_td(t), t=None) for t in (0, 30, 60, 90, 120)]
    r = clase(td, 10, 110)
    assert r["clase"] == "C3"


def test_cli_journal_ilegible_para(tmp_path, capsys):
    inc = tmp_path / "i.jsonl"
    inc.write_text("")
    if not hasattr(sc, "cobertura_tcpdump"):
        pytest.skip("comportamiento nuevo de la CLI (2026-11-02.2)")
    rc = sc.main(["clasificar", "--incrementos", str(inc), "--tcpdump-log", str(tmp_path / "no.txt"),
                  "--desde", "10", "--hasta", "110"])
    assert rc == 2


def test_cli_separa_anillo_y_via(tmp_path):
    """Dos ejecuciones con dos journals: la vía bien cubierta no arregla el anillo con hueco."""
    if not hasattr(sc, "cobertura_tcpdump"):
        pytest.skip("comportamiento nuevo")
    import json
    inc = tmp_path / "i.jsonl"
    inc.write_text("".join(json.dumps(x) + "\n" for x in INCS))

    def journal(nombre, pid, ts):
        p = tmp_path / nombre
        p.write_text("".join(
            f"2026-11-02T19:{int(t) // 60:02d}:{int(t) % 60:02d}.000000+00:00 sensor1 tcpdump[{pid}]: "
            f"{1000 + int(t)} packets captured, {1000 + int(t)} packets received by filter, 0 packets dropped by kernel\n"
            for t in ts))
        return p
    base = 1793646000  # 2026-11-02T19:00:00Z
    an = journal("anillo.txt", 1375, (0, 120))
    via = journal("via.txt", 4242, (0, 30, 60, 90, 120))
    out = []
    for j in (an, via):
        incs = [dict(x, desde=x["desde"] + base, hasta=x["hasta"] + base) for x in INCS]
        r = sc.clasificar(incs, sc.leer_tcpdump_log(j), base + 10, base + 110, CRIT)
        out.append(r["clase"])
    assert out == ["C3", "C0"]
