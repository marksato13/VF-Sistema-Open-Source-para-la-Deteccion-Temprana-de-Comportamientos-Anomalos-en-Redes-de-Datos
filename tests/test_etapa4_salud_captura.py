"""Etapa 4: muestreador de salud de la captura (solo lectura) y su clasificación conservadora."""
from __future__ import annotations

import json
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ / "scripts" / "etapa4"))

import salud_captura as sc  # noqa: E402

BLOQUE = """------------------------------------------------------------------------------------
Date: 11/2/2026 -- 19:10:{ss:02d} (uptime: 2d, 23h 14m {up:02d}s)
------------------------------------------------------------------------------------
Counter                                       | TM Name                   | Value
------------------------------------------------------------------------------------
capture.kernel_packets                        | Total                     | {kp}
capture.kernel_drops                          | Total                     | {kd}
decoder.pkts                                  | Total                     | {kp}
"""


def stats(tmp: Path, bloques, incompleto=False) -> Path:
    p = tmp / "stats.log"
    txt = "".join(BLOQUE.format(**b) for b in bloques)
    if incompleto:
        txt += "Date: 11/2/2026 -- 19:10:59 (uptime: 2d, 23h 14m 59s)\n----\ncapture.kernel_packets | Total | 1\n"
    p.write_text(txt)
    return p


def test_stats_toma_ultimo_bloque_completo(tmp_path):
    p = stats(tmp_path, [dict(ss=1, up=1, kp=100, kd=1), dict(ss=9, up=9, kp=200, kd=3)], incompleto=True)
    r = sc.leer_stats_suricata(p)
    assert r["ok"] and r["kernel_packets"] == 200 and r["kernel_drops"] == 3
    assert r["uptime_s"] == 2 * 86400 + 23 * 3600 + 14 * 60 + 9
    assert r["fecha_utc"].startswith("2026-11-02T19:10:09")


def test_stats_ausente_no_es_cero(tmp_path):
    r = sc.leer_stats_suricata(tmp_path / "no.log")
    assert r["ok"] is False and "kernel_drops" not in r


def test_interfaz_parcial(tmp_path):
    d = tmp_path / "ens37" / "statistics"
    d.mkdir(parents=True)
    (d / "rx_packets").write_text("10\n")
    (d / "rx_dropped").write_text("2\n")
    r = sc.leer_interfaz("ens37", tmp_path)
    assert r["rx_packets"] == 10 and r["rx_dropped"] == 2 and r["rx_missed_errors"] is None
    assert sc.leer_interfaz("nada", tmp_path)["ok"] is False


def test_anillo_y_saltos(tmp_path):
    for n in ("live-20261102191000.pcap", "live-20261102191005.pcap", "live-20261102191020.pcap", "otro.txt"):
        (tmp_path / n).write_bytes(b"")
    r = sc.leer_anillo(tmp_path)
    assert r["ficheros"] == 3 and r["salto_max_s"] == 15.0 and r["mas_nuevo"].endswith("191020.pcap")


def test_archivador_cuenta_fallos(tmp_path):
    (tmp_path / "ESTADO.txt").write_text("vistos=3 archivados=2\n")
    (tmp_path / "archivar.log").write_text(
        "2026-11-02T19:00:00Z OK a.pcap\n2026-11-02T19:00:05Z FALLO b.pcap PERDIDO\n2026-11-02T19:00:10Z OK c\n")
    r = sc.leer_archivador(tmp_path)
    assert (r["lineas_ok"], r["lineas_fallo"], r["perdidos"]) == (2, 1, 1)


def test_via_rapida_y_motor(tmp_path):
    vr = tmp_path / "res.jsonl"
    vr.write_text(json.dumps({"bloque_hasta": 100.0, "paquetes_tcp": 5, "bytes_pendientes": 40, "cpu_s": 1}) + "\n{roto")
    r = sc.leer_via_rapida(vr, 101.5)
    assert r["paquetes_tcp"] == 5 and r["antiguedad_s"] == 1.5
    ci = tmp_path / "ciclos.jsonl"
    ci.write_text(json.dumps({"event": "ciclo", "inicio_ciclo": 50.0, "marca_pcap": 44.0, "fin_ciclo": 51.0,
                              "duracion_s": 1.0, "ventanas_pendientes": 2}) + "\n")
    m = sc.leer_motor(ci, 53.0)
    assert m["retraso_pcap_s"] == 6.0 and m["antiguedad_s"] == 2.0
    assert sc.leer_motor(tmp_path / "x", 1)["ok"] is False


def test_tcpdump_log(tmp_path):
    p = tmp_path / "j.txt"
    p.write_text("2026-11-02T19:10:00.123456+00:00 sensor1 tcpdump[1375]: 26236100 packets captured\n"
                 "2026-11-02T19:10:00.123456+00:00 sensor1 tcpdump[1375]: 26236100 packets captured, "
                 "26236105 packets received by filter, 7 packets dropped by kernel\n")
    r = sc.leer_tcpdump_log(p)
    assert len(r) == 1 and r[0]["pid"] == 1375 and r[0]["descartados_kernel"] == 7
    assert abs(r[0]["t"] - 1793646600.123456) < 1e-3


def _m(t, kp, kd, up, pid=1, nr=0, salto=5.0, vr=None, ok_s=True):
    m = {"t": t,
         "suricata": ({"ok": True, "t": t - 1, "uptime_s": up, "kernel_packets": kp, "kernel_drops": kd}
                      if ok_s else {"ok": False, "motivo": "x"}),
         "unidades": {"ppi-motor-capture": {"ok": True, "pid": pid, "nrestarts": nr, "activo": "active",
                                            "arranque_mono_us": pid}},
         "anillo": {"ok": True, "salto_max_s": salto}}
    if vr is not None:
        m["via_rapida"] = {"ok": True, "paquetes_tcp": vr, "antiguedad_s": 0.1, "bytes_pendientes": 0}
    return m


def test_incrementos_y_reinicios():
    ms = [_m(0, 100, 0, 10), _m(10, 200, 2, 20, vr=5), _m(20, 50, 0, 3, vr=1), _m(30, 80, 0, 13, pid=2, nr=1)]
    incs = sc.incrementos(ms)
    assert incs[0]["suricata"]["paquetes"] == 100 and incs[0]["suricata"]["descartes"] == 2
    assert incs[1]["suricata"]["ok"] is False and "suricata" in incs[1]["reinicios"]
    assert "via_rapida" in incs[1]["reinicios"]
    assert "ppi-motor-capture" in incs[2]["reinicios"]


def _td(t, d, pid=1375):
    return {"t": t, "pid": pid, "capturados": 0, "recibidos_filtro": 0, "descartados_kernel": d}


def test_clasificar_c0_c1_c2_c3():
    # 2026-11-02.2: las lecturas SIGUSR1 van cada 30 s, como el timer. La versión .1 de esta prueba usaba solo
    # t=0 y t=65 y esperaba C0: era justo el defecto (faltaban las lecturas intermedias).
    crit = dict(sc.CRITERIOS)
    ms = [_m(t, 100 * t, 0, t) for t in range(0, 70, 10)]
    incs = sc.incrementos(ms)
    td = [_td(0, 0), _td(30, 0), _td(60, 0)]
    assert sc.clasificar(incs, td, 5, 55, crit)["clase"] == "C0"
    ms1 = [_m(t, 100 * t, (1 if t >= 30 else 0), t) for t in range(0, 70, 10)]
    assert sc.clasificar(sc.incrementos(ms1), td, 5, 55, crit)["clase"] == "C1"
    assert sc.clasificar(incs, [_td(0, 0), _td(30, 2), _td(60, 4)], 5, 55, crit)["clase"] == "C2"
    # sin lecturas de tcpdump que acoten el periodo: no se presume C0
    r = sc.clasificar(incs, [_td(10, 0), _td(40, 0), _td(65, 0)], 5, 55, crit)
    assert r["clase"] == "C3" and any("tcpdump" in x for x in r["motivos"])
    # hueco en el anillo
    ms2 = [_m(t, 100 * t, 0, t, salto=(20.0 if t == 40 else 5.0)) for t in range(0, 70, 10)]
    assert sc.clasificar(sc.incrementos(ms2), td, 5, 55, crit)["clase"] == "C3"


def test_clasificar_insuficiente_y_hueco_de_muestras():
    crit = dict(sc.CRITERIOS)
    incs = sc.incrementos([_m(t, 100 * t, 0, t) for t in (10, 20, 80)])
    assert sc.clasificar(incs, [], 5, 15, crit)["clase"] == "insuficiente"
    r = sc.clasificar(incs, [_td(0, 0), _td(90, 0)], 12, 70, crit)
    assert r["clase"] == "C3" and any("sin muestra" in x for x in r["motivos"])


def test_cli_intervalos(tmp_path):
    mu = tmp_path / "m.jsonl"
    mu.write_text("\n".join(json.dumps(_m(t, 100 * t, 0, t)) for t in (0, 10, 20)) + "\n")
    out = tmp_path / "i.jsonl"
    assert sc.main(["intervalos", str(mu), str(out)]) == 0
    assert len(out.read_text().splitlines()) == 2
