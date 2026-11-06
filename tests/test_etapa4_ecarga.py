"""E-carga v2: clase de captura (clasificador vigente, sin cambios), veredicto en cuatro dimensiones separadas, K4a/K4b
del generador y obs_pcap.py 2026-11-06.2 (fin comprobado y en seco).

Las clases se obtienen con ``salud_captura.clasificar`` tal cual (precedencia C3 > C2 > C1 > C0; el periodo toma la
peor y ``no_evaluable`` domina). Nada de este fichero cambia el clasificador.
"""
from __future__ import annotations

import datetime as dt
import gzip
import importlib.util
import json
import struct
import sys
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ / "scripts" / "etapa4"))
import salud_captura as sc  # noqa: E402


def _cargar(nombre):
    spec = importlib.util.spec_from_file_location(nombre, RAIZ / "deploy" / "etapa4" / "sensor1" / f"{nombre}.py")
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


ev = _cargar("evaluar_ecarga")
op = _cargar("obs_pcap")

# ------------------------------------------------------------------ 1. clase de captura con el clasificador vigente
D, H = 1000.0, 1300.0


def _incs(reinicio=False, salto=5.0):
    ts = [D - 10 + 10 * i for i in range(int((H - D) / 10) + 3)]
    return [{"desde": a, "hasta": b, "reinicios": ["suricata"] if reinicio and i == 5 else [],
             "anillo": {"ok": True, "salto_max_s": salto}} for i, (a, b) in enumerate(zip(ts, ts[1:]))]


def _td(descartes=0):
    return [{"t": t, "pid": 7, "capturados": 10, "recibidos_filtro": 10,
             "descartados_kernel": descartes if t > D + 100 else 0} for t in range(int(D) - 30, int(H) + 31, 30)]


def _se(estado, descartes=0, paquetes=600_000, periodo=(D, H)):
    return {"periodo": list(periodo), "estado": estado, "motivos": [estado], "paquetes": paquetes,
            "descartes": descartes}


def _clase(**kw):
    return sc.clasificar(_incs(kw.get("reinicio", False), kw.get("salto", 5.0)), _td(kw.get("td", 0)), D, H,
                         dict(sc.CRITERIOS), suricata_eve=kw["se"])


def test_cero_descartes_es_c0():
    r = _clase(se=_se("cero_explicito"))
    assert r["clase"] == "C0" and r["motivos"] == []


def test_descartes_con_medicion_completa_es_c1():
    r = _clase(se=_se("descartes", descartes=5))
    assert r["clase"] == "C1"
    assert r["motivos"] == ["Suricata (EVE): 5 descartes de 600000 paquetes"]


@pytest.mark.parametrize("estado", ["ausente", "desactualizada", "error_lectura", "cobertura_insuficiente"])
def test_evidencia_insuficiente_de_suricata_es_c3(estado):
    assert _clase(se=_se(estado))["clase"] == "C3"


def test_sin_muestras_que_acoten_es_insuficiente():
    r = sc.clasificar(_incs()[3:], _td(), D, H, dict(sc.CRITERIOS), suricata_eve=_se("cero_explicito"))
    assert r["clase"] == "insuficiente"   # clasificar_periodo lo convierte en no_evaluable


@pytest.mark.parametrize("kw,clase,motivos", [
    ({"se": _se("descartes", 5), "reinicio": True}, "C3", 2),        # descartes + reinicio: manda C3
    ({"se": _se("descartes", 5), "salto": 30.0}, "C3", 2),            # descartes + hueco del anillo: C3
    ({"se": _se("descartes", 5), "td": 4}, "C2", 2),                  # descartes Suricata + tcpdump: C2
    ({"se": _se("cero_explicito"), "td": 4, "reinicio": True}, "C3", 2),  # tcpdump + reinicio: C3
    ({"se": _se("ausente"), "td": 4}, "C3", 2),                       # sin medida de Suricata + tcpdump: C3
])
def test_concurrencia_de_motivos_respeta_la_precedencia(kw, clase, motivos):
    r = _clase(**kw)
    assert r["clase"] == clase
    assert len(r["motivos"]) == motivos          # se informan TODOS los motivos, no solo el que decide


# ------------------------------------------------------------------ 2. veredicto: cuatro dimensiones separadas
def _entrada(clase="C0", dpm=0.0, k=None, s=None):
    kk = {x: True for x in ev.K}
    ss = {x: True for x in ev.S}
    kk.update(k or {})
    ss.update(s or {})
    return {"K": kk, "S": ss, "clasificacion": {"clase_periodo": clase, "motivos": []}, "descartes_por_millon": dpm}


def test_estable_c0():
    r = ev.veredicto(_entrada())
    assert r["estabilidad_tecnica"] == "estable con carga suficiente"
    assert r["clase_captura"] == "C0" and r["limitaciones"] == []
    assert r["i5"].startswith("no evaluado")
    assert "condición (3)" in r["habilita"]


def test_estable_c1_conserva_la_limitacion_y_no_es_c0_ni_i5():
    r = ev.veredicto(_entrada("C1", 3.2))
    assert r["estabilidad_tecnica"] == "estable con carga suficiente"   # S13: 3,2 < 14,95
    assert r["clase_captura"] == "C1"
    assert "NO apta para la población principal" in r["poblacion_principal"]
    assert "No es captura sin pérdidas" in r["poblacion_principal"]
    assert any("no demuestra C0 ni I5" in x for x in r["limitaciones"])
    assert any("clase C1" in x for x in r["limitaciones"])
    assert r["i5"].startswith("no evaluado")


def test_s13_superado_es_no_estable():
    r = ev.veredicto(_entrada("C1", 20.0, s={"S13": False}))
    assert r["estabilidad_tecnica"] == "no estable" and r["S_no_cumplen"] == ["S13"]
    assert r["habilita"].startswith("nada")


def test_carga_insuficiente_domina_pero_conserva_hallazgos():
    r = ev.veredicto(_entrada(k={"K2": False}, s={"S1": False}))
    assert r["estabilidad_tecnica"] == "carga insuficiente"
    assert r["hallazgos_S_aunque_carga_insuficiente"] == ["S1"]


def test_lectura_que_falta_es_no_demostrable():
    assert ev.veredicto(_entrada(s={"S4": None}))["estabilidad_tecnica"] == "no demostrable"
    assert ev.veredicto(_entrada(k={"K5": None}))["estabilidad_tecnica"] == "no demostrable"


def test_c3_estable_no_es_admisible():
    r = ev.veredicto(_entrada("C3"))
    assert r["poblacion_principal"].startswith("NO apta: C3")


def test_incoherencia_clase_descartes_no_da_estable():
    assert ev.veredicto(_entrada("C0", 2.0))["estabilidad_tecnica"] == "no demostrable"
    assert ev.veredicto(_entrada("C1", 0.0))["estabilidad_tecnica"] == "no demostrable"


def test_entrada_incompleta_o_clase_desconocida_es_error():
    e = _entrada()
    del e["S"]["S7"]
    with pytest.raises(ValueError):
        ev.veredicto(e)
    with pytest.raises(ValueError):
        ev.veredicto(_entrada("C9"))


# ------------------------------------------------------------------ 3. K4a / K4b
T0 = 1794194100.0      # inicio de la ventana propuesta (09-nov 03:15:00Z); solo como número de prueba
T1 = T0 + 3600


def _flow(ip, t, proto="TCP"):
    s = dt.datetime.fromtimestamp(t, dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%f+0000")
    fin = dt.datetime.fromtimestamp(t + 2, dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%f+0000")
    return json.dumps({"timestamp": fin, "event_type": "flow", "src_ip": ip, "dest_ip": "10.10.30.10",
                       "proto": proto, "flow": {"start": s, "end": fin, "pkts_toserver": 5, "pkts_toclient": 5}})


def _eve(tmp, filas, nombre="eve.json", gz=False):
    p = tmp / nombre
    txt = "\n".join(filas) + "\n"
    if gz:
        with gzip.open(p, "wt") as f:
            f.write(txt)
    else:
        p.write_text(txt)
    return str(p)


def _todos_presentes():
    return [_flow(ip, T0 + 30 + 600 * i) for ip in ev.PERFILES.values() for i in range(6)]


def test_k4a_seis_perfiles_en_cada_tramo(tmp_path):
    p = _eve(tmp_path, _todos_presentes())
    r = ev.k4a(ev.flujos([p], set(ev.PERFILES.values()), T0, T1), ev.PERFILES, T0, T1)
    assert r["cumple"] and r["tramos"] == 6


def test_k4a_un_tramo_sin_un_perfil_no_cumple(tmp_path):
    filas = [f for f in _todos_presentes() if not ('"10.10.20.25"' in f and _ts(f) >= T0 + 3000)]
    r = ev.k4a(ev.flujos([_eve(tmp_path, filas)], set(ev.PERFILES.values()), T0, T1), ev.PERFILES, T0, T1)
    assert not r["cumple"] and r["perfiles"]["ligero"]["tramos_sin_flujos"] == [5]


def _ts(f):
    return ev.ts(json.loads(f)["flow"]["start"])


def test_flujo_se_asigna_por_inicio_no_por_emision(tmp_path):
    """Un flujo que empieza antes de la ventana y se emite dentro no cuenta; uno que empieza dentro sí."""
    filas = [_flow("10.10.20.26", T0 - 5), _flow("10.10.20.26", T1 - 1), _flow("10.10.20.26", T1)]
    r = ev.flujos([_eve(tmp_path, filas)], {"10.10.20.26"}, T0, T1)
    assert r["10.10.20.26"] == [T1 - 1]


def test_eve_ilegible_o_corrupto_es_error_no_ausencia(tmp_path):
    p = tmp_path / "eve.json.gz"
    p.write_bytes(b"\x1f\x8b\x08\x00basura")
    with pytest.raises(ev.ErrorLectura):
        ev.flujos([str(p)], {"10.10.20.26"}, T0, T1)
    q = _eve(tmp_path, ['{"event_type": "flow", "src_ip": "10.10.20.26", '], "rota.json")
    with pytest.raises(ev.ErrorLectura):
        ev.flujos([q], {"10.10.20.26"}, T0, T1)
    assert ev.main(["perfiles", "--eve", str(p), "--desde", str(T0), "--hasta", str(T1)]) == 2


def _k4b(starts):
    return ev.k4b(starts, T0, T1, 0.12, 5.0)


def test_k4b_ausencia_de_trafico():
    r = _k4b([])
    assert r["estado"] == "sin_trafico" and r["intervalos"] == 450 and r["mediana_por_intervalo"] == 0


def test_k4b_actividad_aislada_no_es_rafaga():
    """8 flujos en un mismo intervalo de 8 s (p. ej. varias conexiones de una acción) y nada alrededor."""
    r = _k4b([T0 + 800 + 0.5 * i for i in range(8)])
    assert r["max_suma_40s"] == 8 and r["estado"] == "sin_rafaga_detectable"


def test_k4b_trafico_estable_no_es_rafaga():
    """Un flujo por intervalo durante toda la hora: media 1, umbral 15 en 40 s, máximo 5."""
    r = _k4b([T0 + 8 * i + 1 for i in range(450)])
    assert r["lambda_ref"] == 1.0 and r["umbral_suma_40s"] == 15
    assert r["estado"] == "sin_rafaga_detectable"


def test_k4b_ritmo_nocturno_del_diseno_no_es_rafaga():
    """Ritmo base del generador de noche (un flujo cada ≈ 41,7 s), sin ráfaga: mediana 0, nunca detectada."""
    r = _k4b([T0 + 41.7 * i for i in range(86)])
    assert r["mediana_por_intervalo"] == 0 and r["estado"] == "sin_rafaga_detectable"


def test_k4b_rafaga_clara_con_mediana_cero():
    """Fondo nocturno + ráfaga de 60 s a 6× (un flujo cada ≈ 6,9 s): detectada aunque la mediana sea 0."""
    fondo = [T0 + 41.7 * i for i in range(86)]
    rafaga = [T0 + 1800 + 6.9 * i for i in range(9)]
    r = _k4b(sorted(fondo + rafaga))
    assert r["mediana_por_intervalo"] == 0
    assert r["umbral_suma_40s"] == 6           # max(6, ceil(3 × 0,192 × 5)) con la media < λ_diseño
    assert r["estado"] == "rafaga_detectada" and len(r["episodios"]) == 1
    assert T0 + 1760 <= r["episodios"][0]["desde"] <= T0 + 1800


def test_k4b_no_cuenta_otros_perfiles(tmp_path):
    filas = [_flow("10.10.20.22", T0 + 1800 + i) for i in range(40)]
    rr = ev.flujos([_eve(tmp_path, filas)], {"10.10.20.26", "10.10.20.22"}, T0, T1)
    assert _k4b(rr["10.10.20.26"])["estado"] == "sin_trafico"


def test_cli_perfiles_k4a_decide_rc_y_k4b_es_informativo(tmp_path, capsys):
    p = _eve(tmp_path, _todos_presentes(), gz=True, nombre="eve.json.1.gz")
    assert ev.main(["perfiles", "--eve", p, "--desde", str(T0), "--hasta", str(T1)]) == 0
    r = json.loads(capsys.readouterr().out)
    assert r["K4a"]["cumple"] and r["K4b"]["informativo"] is True
    assert r["K4b"]["estado"] == "sin_rafaga_detectable"


# ------------------------------------------------------------------ 4. obs_pcap.py: fin comprobado y en seco
def test_fin_epoch_e_iso_deben_coincidir():
    assert op.fin_comprobado(1794197760, "2026-11-09T04:16:00Z") == 1794197760.0
    with pytest.raises(ValueError):
        op.fin_comprobado(1793945490, "2026-11-06T05:51:30Z")   # el error real del 06-nov (= 06:11:30Z)
    with pytest.raises(ValueError):
        op.fin_comprobado(1794197760, "2026-11-09T04:16:00")    # sin Z: no se acepta hora local


def test_en_seco_no_lee_el_anillo(tmp_path, capsys):
    d = tmp_path / "anillo"
    d.mkdir()
    rc = op.main(["--dir", str(d), "--salida", str(tmp_path / "o"), "--hasta-epoch", "1794197760",
                  "--hasta-iso", "2026-11-09T04:16:00Z", "--en-seco"], reloj=lambda: 1794190000.0)
    r = json.loads(capsys.readouterr().out)
    assert rc == 0 and r["fin_utc"] == "2026-11-09T04:16:00Z" and r["fin_peru"].startswith("2026-11-08 23:16:00")
    assert r["faltan_s"] == 7760.0
    assert not (tmp_path / "o").exists()
    assert op.main(["--dir", str(tmp_path / "x"), "--salida", str(tmp_path / "o"), "--hasta-epoch", "1794197760",
                    "--hasta-iso", "2026-11-09T04:16:00Z", "--en-seco"]) == 2
    assert op.main(["--dir", str(d), "--salida", str(tmp_path / "o"), "--hasta-epoch", "1793945490",
                    "--hasta-iso", "2026-11-06T05:51:30Z", "--en-seco"]) == 2


def _pcap(p, n):
    b = struct.pack("<IHHiIII", 0xa1b2c3d4, 2, 4, 0, 0, 65535, 1)
    for i in range(n):
        b += struct.pack("<IIII", 1794194100 + i, 0, 4, 4) + b"abcd"
    p.write_bytes(b)


def test_lee_cerrados_y_para_en_el_fin(tmp_path):
    d = tmp_path / "anillo"
    d.mkdir()
    for i, n in enumerate((3, 2, 1)):
        _pcap(d / f"live-2026110903150{i}.pcap", n)
    (d / "live-20261109031500.pcap").write_bytes((d / "live-20261109031500.pcap").read_bytes()[:-2])
    reloj = iter([1794197000.0, 1794197900.0, 1794197901.0, 1794197902.0])
    rc = op.main(["--dir", str(d), "--salida", str(tmp_path / "o"), "--hasta-epoch", "1794197760",
                  "--hasta-iso", "2026-11-09T04:16:00Z"], reloj=lambda: next(reloj), dormir=lambda s: None)
    lineas = [json.loads(l) for l in (tmp_path / "o" / "pcap.jsonl").read_text().splitlines()]
    assert rc == 0 and [l["fichero"] for l in lineas] == ["live-20261109031500.pcap", "live-20261109031501.pcap"]
    assert lineas[0]["error"].startswith("registro incompleto") and lineas[1]["registros"] == 2
