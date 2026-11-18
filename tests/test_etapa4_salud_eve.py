"""salud_captura 2026-11-06.1: Suricata por EVE stats (pendiente P1 del cierre complementario 4A).

Datos reales: tests/datos/eve-stats-20261104-0200-0740.jsonl (Sensor1, 04-nov 02:00–07:40 UTC, eventos stats de
eve.json.1-2026110600.backup reducidos a timestamp + uptime + capture; sha256 de las 2551 líneas originales
cdfe4047bfe82834081b1003b7b317171d40b581d1bd27fd682d88970c00156f). Contiene el reinicio de Suricata del ensayo del
anillo (~06:16:55) y descartes reales (198 a las 02:08:27, 7 a las 03:05:47, …).
"""
from __future__ import annotations

import gzip
import json
import sys
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ / "scripts" / "etapa4"))
import salud_captura as sc  # noqa: E402

REAL = RAIZ / "tests" / "datos" / "eve-stats-20261104-0200-0740.jsonl"
ENSAYO = (1793773615.0, 1793777215.0)          # ventana oficial del ensayo ring-size 16384 (C3 histórico)
FIN_REAL = 1793777999.634698                    # última muestra del fichero real


def linea(t: float, up, pk, dr, *, capture=True) -> str:
    import datetime as dt
    ts = dt.datetime.fromtimestamp(t, dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%f+0000")
    cap = {}
    if pk is not None:
        cap["kernel_packets"] = pk
    if dr is not None:
        cap["kernel_drops"] = dr
    st = {"uptime": up}
    if up is None:
        st = {}
    if capture:
        st["capture"] = cap
    return json.dumps({"timestamp": ts, "event_type": "stats", "stats": st}, separators=(",", ":"))


def serie(t0=1000.0, n=50, paso=8.0, up0=500, pk0=10_000, dr0=3, dpk=100, drops_en=None):
    """Proceso único: uptime y paquetes crecen; descartes en los índices drops_en (dict i -> incremento)."""
    out, pk, dr = [], pk0, dr0
    for i in range(n):
        dr += (drops_en or {}).get(i, 0)
        out.append((t0 + i * paso, up0 + int(i * paso), pk, dr))
        pk += dpk
    return out


def escribir(tmp: Path, nombre: str, filas, extra: list[str] | None = None, final_nl=True, gz=False) -> Path:
    txt = "\n".join([linea(*f) if isinstance(f, tuple) else f for f in filas] + (extra or []))
    if final_nl:
        txt += "\n"
    p = tmp / nombre
    if gz:
        with gzip.open(p, "wt") as fh:
            fh.write(txt)
    else:
        p.write_text(txt)
    return p


def medir(rutas, desde, hasta, ahora=None):
    lect = sc.leer_eve_stats(rutas)
    return sc.medida_suricata_eve(lect, desde, hasta, ahora if ahora is not None else hasta + 5)


# ------------------------------------------------------------------------------------------------ datos reales

def test_real_ensayo_cero_explicito():
    r = medir([REAL], *ENSAYO)
    assert r["estado"] == "cero_explicito"
    assert r["descartes"] == 0 and r["paquetes"] == 1201704
    assert r["reinicios"] == [] and len(r["arranque_estimado"]) <= 2   # t − uptime con uptime entero


def test_real_descartes_medidos():
    r = medir([REAL], 1793757660.0, 1793761200.0)
    assert r["estado"] == "descartes" and r["descartes"] == 198
    r = medir([REAL], 1793761200.0, 1793764800.0)   # 03:00–04:00: 7 (03:05:47) + 13 (03:53:56)
    assert r["estado"] == "descartes" and r["descartes"] == 20


def test_real_reinicio_no_mezcla_procesos():
    r = medir([REAL], 1793772600.0, 1793773500.0)   # contiene el reinicio de ~06:16:55
    assert r["estado"] == "cobertura_insuficiente"
    assert any("reinicio" in m for m in r["motivos"])
    assert r["descartes"] is None                   # nunca el 0 del proceso nuevo restado del anterior


def test_real_i5_al_final_del_fichero():
    lect = sc.leer_eve_stats([REAL])
    r = sc.comprobar_i5(lect, FIN_REAL + 3)
    assert r["i5"] == "cumple" and r["medida"]["estado"] == "cero_explicito"
    r = sc.comprobar_i5(lect, FIN_REAL + 60)        # fuente sin muestras nuevas: no demostrable
    assert r["i5"] == "no_demostrable" and r["medida"]["estado"] == "desactualizada"


def test_real_lectura_por_cola_igual_que_entera(tmp_path):
    entera = sc.leer_eve_stats([REAL])
    cola = sc.leer_eve_stats([REAL], desde=ENSAYO[0], bloque=64 << 10)
    assert [m["t"] for m in cola["muestras"]] == [m["t"] for m in entera["muestras"]][-len(cola["muestras"]):]
    assert cola["muestras"][0]["t"] < ENSAYO[0] - sc.CRITERIOS_EVE["eve_max_hueco_s"]
    assert not cola["invalidas"]
    assert sc.medida_suricata_eve(cola, *ENSAYO, ENSAYO[1] + 5)["estado"] == "cero_explicito"


# ------------------------------------------------------------------------------------------------ sintéticos

def test_ceros_explicitos(tmp_path):
    p = escribir(tmp_path, "eve.json", serie())
    r = medir([p], 1040, 1300)
    assert r["estado"] == "cero_explicito" and r["descartes"] == 0 and r["paquetes"] > 0


def test_descartes_positivos(tmp_path):
    p = escribir(tmp_path, "eve.json", serie(drops_en={10: 4, 20: 1}))
    r = medir([p], 1040, 1300)
    assert r["estado"] == "descartes" and r["descartes"] == 5
    assert [x[2] for x in r["intervalos_con_descartes"]] == [4, 1]


def test_campo_ausente_no_es_cero(tmp_path):
    filas = serie()
    filas[15] = (filas[15][0], filas[15][1], filas[15][2], None)        # sin kernel_drops
    r = medir([escribir(tmp_path, "eve.json", filas)], 1040, 1300)
    assert r["estado"] == "ausente" and r["descartes"] is None
    filas = serie()
    t, up, pk, dr = filas[12]
    sin_capture = [linea(t, up, pk, dr, capture=False)]
    r = medir([escribir(tmp_path, "eve2.json", filas[:12] + sin_capture + filas[13:])], 1040, 1300)
    assert r["estado"] == "ausente"


def test_sin_eventos_stats(tmp_path):
    p = tmp_path / "eve.json"
    p.write_text('{"timestamp":"2026-11-06T00:00:00.000000+0000","event_type":"flow"}\n')
    assert medir([p], 1040, 1300)["estado"] == "ausente"


def test_fichero_no_legible(tmp_path):
    r = medir([tmp_path / "no-existe.json"], 1040, 1300)
    assert r["estado"] == "error_lectura" and r["descartes"] is None


def test_linea_corrupta_en_medio_es_error(tmp_path):
    filas = [linea(*f) for f in serie()]
    filas.insert(20, filas[20][:90])                      # stats truncado (tras "event_type") en mitad del fichero
    r = medir([escribir(tmp_path, "eve.json", filas)], 1040, 1300)
    assert r["estado"] == "error_lectura"


def test_linea_parcial_al_final_no_es_error(tmp_path):
    filas = [linea(*f) for f in serie()]
    p = escribir(tmp_path, "eve.json", filas + [filas[-1][:90]], final_nl=False)
    lect = sc.leer_eve_stats([p])
    assert lect["parciales"] == 1 and not lect["invalidas"]
    assert sc.medida_suricata_eve(lect, 1040, 1300, 1305)["estado"] == "cero_explicito"


def test_reinicio_dentro_del_periodo(tmp_path):
    a = serie(n=20, drops_en={5: 9})
    b = serie(t0=1000 + 20 * 8 + 3, n=20, up0=2, pk0=50, dr0=0)          # proceso nuevo: uptime y contadores bajan
    r = medir([escribir(tmp_path, "eve.json", a + b)], 1040, 1300)
    assert r["estado"] == "cobertura_insuficiente" and r["descartes"] is None
    assert len(r["reinicios"]) == 1


def test_reinicio_con_uptime_mayor_se_detecta_por_identidad(tmp_path):
    # proceso nuevo cuyo uptime ya supera al del viejo (p. ej. el viejo llevaba 10 s): t − uptime cambia
    a = serie(n=10, up0=10)
    b = serie(t0=1000 + 10 * 8 + 60, n=20, up0=500, pk0=20_000, dr0=0)
    r = medir([escribir(tmp_path, "eve.json", a + b)], 1040, 1200)
    assert r["estado"] == "cobertura_insuficiente" and r["reinicios"]


def test_periodo_entero_tras_reinicio_es_valido(tmp_path):
    a = serie(n=10)
    b = serie(t0=1100, n=40, up0=5, pk0=0, dr0=0)
    r = medir([escribir(tmp_path, "eve.json", a + b)], 1150, 1350)
    assert r["estado"] == "cero_explicito"                                # solo bloques del proceso nuevo


def test_contador_decrece_sin_reinicio_es_error(tmp_path):
    filas = serie()
    t, up, pk, dr = filas[20]
    filas[20] = (t, up, pk, dr - 1 if dr else 0)
    filas[19] = (filas[19][0], filas[19][1], filas[19][2], 5)
    r = medir([escribir(tmp_path, "eve.json", filas)], 1040, 1300)
    assert r["estado"] == "error_lectura"


def test_rotacion_con_copytruncate_y_repetidas(tmp_path):
    filas = serie(n=60, drops_en={40: 2})
    viejo = escribir(tmp_path, "eve.json.1.gz", filas[:35], gz=True)
    nuevo = escribir(tmp_path, "eve.json", filas[33:])                   # 2 muestras en los dos ficheros
    lect = sc.leer_eve_stats([nuevo, viejo])
    assert lect["repetidas"] == 2
    r = sc.medida_suricata_eve(lect, 1100, 1400, 1405)
    assert r["estado"] == "descartes" and r["descartes"] == 2
    # solo con el fichero actual, el inicio no está cubierto
    assert medir([nuevo], 1100, 1400)["estado"] == "cobertura_insuficiente"


def test_misma_hora_valores_distintos_es_error(tmp_path):
    filas = serie()
    t, up, pk, dr = filas[10]
    r = medir([escribir(tmp_path, "eve.json", filas + [(t, up, pk + 1, dr)])], 1040, 1300)
    assert r["estado"] == "error_lectura"


def test_fuente_congelada(tmp_path):
    filas = serie()
    filas = filas[:20] + [(f[0], filas[19][1], filas[19][2], filas[19][3]) for f in filas[20:]]
    r = medir([escribir(tmp_path, "eve.json", filas)], 1040, 1300)
    assert r["estado"] == "desactualizada"


def test_fuente_que_deja_de_escribir(tmp_path):
    p = escribir(tmp_path, "eve.json", serie(n=20))                      # última muestra en t = 1152
    r = medir([p], 1040, 1300, ahora=1400)
    assert r["estado"] == "desactualizada"
    r = medir([p], 1040, 1160, ahora=1158)                               # periodo aún no terminado
    assert r["estado"] == "cobertura_insuficiente"


def test_hueco_entre_muestras(tmp_path):
    filas = serie()
    filas = filas[:20] + filas[24:]                                      # 40 s sin stats
    r = medir([escribir(tmp_path, "eve.json", filas)], 1040, 1300)
    assert r["estado"] == "cobertura_insuficiente" and "hueco" in r["motivos"][0]


def test_extremos_sin_cobertura(tmp_path):
    p = escribir(tmp_path, "eve.json", serie(t0=1100, n=30))
    r = medir([p], 1040, 1300)
    assert r["estado"] == "cobertura_insuficiente" and "desde" in r["motivos"][0]
    p = escribir(tmp_path, "eve2.json", serie(n=30))                     # hasta 1232
    r = medir([p], 1040, 1300, ahora=1240)
    assert r["estado"] == "cobertura_insuficiente" and "hasta" in r["motivos"][-1]


def test_descartes_parciales_se_informan_aunque_falle_la_cobertura(tmp_path):
    filas = serie(drops_en={10: 3})
    filas = filas[:20] + filas[24:]
    r = medir([escribir(tmp_path, "eve.json", filas)], 1040, 1300)
    assert r["estado"] == "cobertura_insuficiente" and r["descartes_parciales"] == 3


@pytest.mark.parametrize("drops,esperado,rc", [({}, "cumple", 0), ({200: 1}, "no_cumple", 1)])
def test_i5_cli(tmp_path, drops, esperado, rc, capsys, monkeypatch):
    import time
    ahora = 1_800_000_000.0
    p = escribir(tmp_path, "eve.json", serie(t0=ahora - 1900, n=238, drops_en=drops))
    monkeypatch.setattr(time, "time", lambda: ahora)
    assert sc.main(["i5", "--eve", str(p)]) == rc
    assert json.loads(capsys.readouterr().out)["i5"] == esperado


def test_i5_no_demostrable_con_hueco(tmp_path):
    ahora = 1_800_000_000.0
    filas = serie(t0=ahora - 1900, n=238)
    filas = filas[:100] + filas[110:]
    lect = sc.leer_eve_stats([escribir(tmp_path, "eve.json", filas)])
    assert sc.comprobar_i5(lect, ahora)["i5"] == "no_demostrable"


# ------------------------------------------------------------------------------------------------ clasificar

def _incs_limpios(desde, hasta):
    base = {"reinicios": [], "anillo": {"ok": True, "salto_max_s": 5.0}}
    ts = [desde - 10 + 10 * i for i in range(int((hasta - desde) / 10) + 3)]
    return [dict(base, desde=a, hasta=b) for a, b in zip(ts, ts[1:])]


def _tcpdump(desde, hasta):
    return [{"t": t, "pid": 7, "capturados": 10, "recibidos_filtro": 10, "descartados_kernel": 0}
            for t in range(int(desde) - 30, int(hasta) + 31, 30)]


@pytest.mark.parametrize("estado,clase", [("cero_explicito", "C0"), ("descartes", "C1"), ("ausente", "C3"),
                                          ("desactualizada", "C3"), ("error_lectura", "C3"),
                                          ("cobertura_insuficiente", "C3")])
def test_clasificar_con_eve(estado, clase):
    d, h = 1000.0, 1300.0
    se = {"periodo": [d, h], "estado": estado, "motivos": ["x"], "paquetes": 10, "descartes": 2 if estado == "descartes" else 0}
    r = sc.clasificar(_incs_limpios(d, h), _tcpdump(d, h), d, h, dict(sc.CRITERIOS), suricata_eve=se)
    assert r["clase"] == clase
    assert r["info"]["suricata"]["fuente"] == "eve_stats"


def test_clasificar_eve_de_otro_periodo_es_c3():
    d, h = 1000.0, 1300.0
    se = {"periodo": [d, h + 60], "estado": "cero_explicito", "motivos": [], "paquetes": 1, "descartes": 0}
    r = sc.clasificar(_incs_limpios(d, h), _tcpdump(d, h), d, h, dict(sc.CRITERIOS), suricata_eve=se)
    assert r["clase"] == "C3"


def test_clasificar_sin_eve_conserva_lo_historico():
    """Sin --suricata-eve y sin stats en las muestras: C3 «Suricata sin medida completa» como en 2026-11-02.2."""
    d, h = 1000.0, 1300.0
    r = sc.clasificar(_incs_limpios(d, h), _tcpdump(d, h), d, h, dict(sc.CRITERIOS))
    assert r["clase"] == "C3" and "Suricata sin medida completa en el periodo" in r["motivos"]
    assert r["info"]["suricata"]["fuente"] == "stats.log"
