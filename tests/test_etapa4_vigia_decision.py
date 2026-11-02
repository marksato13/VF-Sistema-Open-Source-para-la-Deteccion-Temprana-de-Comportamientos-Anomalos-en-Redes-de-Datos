"""Etapa 4: decisión del vigía de la 4C (scripts/etapa4/vigia_4c.py), P1–P5 y X1–X3, offline y con fallo cerrado."""
from __future__ import annotations

import json
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ / "scripts" / "etapa4"))
import vigia_4c as vg  # noqa: E402

CRIT = dict(vg.CRIT)
T0 = 1_793_646_000.0


def sensor(t, nr=0, arr=T0 - 3600, activo="active", salto=5.0, fallo=0, perdido=0, d=0, pid=1375, td_edad=10.0,
           fuera=None, ok=True):
    u = {"ok": True, "activo": activo, "nrestarts": nr, "arranque_epoch": arr, "pid": 1}
    return {"ok": ok, "unidades": {k: dict(u) for k in vg.UNIDADES},
            "tcpdump": {"ok": True, "lecturas": [{"t": t - td_edad - 30, "pid": pid, "descartados_kernel": 0},
                                                 {"t": t - td_edad, "pid": pid, "descartados_kernel": d}]},
            "anillo": {"ok": True, "salto_max_s": salto},
            "archivador": {"ok": True, "lineas_fallo": fallo, "perdidos": perdido},
            "eve": {"ok": True, "fuera": fuera or []}}


def obs(t, srv=0, **kw):
    o = {"sensor": sensor(t, **kw), "desfases": {"sensor": {"desfase_s": 0.05, "cota_s": 0.1}}}
    if srv is not None:
        o["srvdmz"] = {"rc": srv, "resumen": "x"}
    return o


def nuevo():
    return vg.estado_inicial(25)


def test_sano_continua():
    st = nuevo()
    assert vg.decidir(st, obs(T0), T0, CRIT)["estado"] == "continuar"


def test_p1_reinicio_pausa_y_reanuda_tras_300_s_y_230_s_de_motor():
    st = nuevo()
    vg.decidir(st, obs(T0), T0, CRIT)
    # el motor reinicia en T0+50
    d = vg.decidir(st, obs(T0 + 60, srv=None, nr=1, arr=T0 + 50), T0 + 60, CRIT)
    assert d["estado"] == "pausa" and any(c.startswith("P1") for c in d["causas"])
    # limpio pero < 300 s desde la última condición
    d = vg.decidir(st, obs(T0 + 200, nr=1, arr=T0 + 50), T0 + 200, CRIT)
    assert d["estado"] == "pausa" and "reanudación" in d["causas"][0]
    # 301 s después de la condición -> continúa (motor con 311 s de historia)
    assert vg.decidir(st, obs(T0 + 361, nr=1, arr=T0 + 50), T0 + 361, CRIT)["estado"] == "continuar"


def test_historia_del_motor_menor_de_230_s_retiene():
    st = nuevo()
    d = vg.decidir(st, obs(T0, arr=T0 - 100), T0, CRIT)
    assert d["estado"] == "pausa" and "historia del motor" in d["causas"][0]


def test_p1_unidad_inactiva_y_no_legible():
    st = nuevo()
    assert vg.decidir(st, obs(T0, activo="activating"), T0, CRIT)["estado"] == "pausa"
    o = obs(T0)
    o["sensor"]["unidades"]["suricata"] = {"ok": False, "motivo": "systemctl rc=1"}
    assert vg.decidir(nuevo(), o, T0, CRIT)["estado"] == "pausa"


def test_p2_desfase_y_cota():
    o = obs(T0)
    o["desfases"]["kali"] = {"desfase_s": 1.4, "cota_s": 0.1}
    d = vg.decidir(nuevo(), o, T0, CRIT)
    assert d["estado"] == "pausa" and "P2" in d["causas"][0]
    o["desfases"]["kali"] = {"desfase_s": 0.0, "cota_s": float("inf")}
    assert vg.decidir(nuevo(), o, T0, CRIT)["estado"] == "pausa"


def test_p3_salto_y_archivador():
    assert vg.decidir(nuevo(), obs(T0, salto=10.0), T0, CRIT)["estado"] == "pausa"
    st = nuevo()
    vg.decidir(st, obs(T0, fallo=0), T0, CRIT)
    d = vg.decidir(st, obs(T0 + 60, fallo=1, perdido=1), T0 + 60, CRIT)
    assert d["estado"] == "pausa" and any("P3 archivador" in c for c in d["causas"])


def test_p4_descartes_y_sin_sigusr1():
    d = vg.decidir(nuevo(), obs(T0, d=3), T0, CRIT)
    assert d["estado"] == "pausa" and any("P4 descartes" in c for c in d["causas"])
    d = vg.decidir(nuevo(), obs(T0, td_edad=95), T0, CRIT)
    assert d["estado"] == "pausa" and any("SIGUSR1" in c for c in d["causas"])
    o = obs(T0)
    o["sensor"]["tcpdump"] = {"ok": False, "motivo": "journalctl rc=1"}
    assert vg.decidir(nuevo(), o, T0, CRIT)["estado"] == "pausa"


def test_sin_lectura_del_sensor_es_pausa():
    o = obs(T0)
    o["sensor"] = {"ok": False, "motivo": "ssh rc=255"}
    assert vg.decidir(nuevo(), o, T0, CRIT)["estado"] == "pausa"


def test_srvdmz_rc2_pausa_rc1_cancela_y_es_definitivo():
    d = vg.decidir(nuevo(), obs(T0, srv=2), T0, CRIT)
    assert d["estado"] == "pausa" and any("srv-dmz" in c for c in d["causas"])
    d = vg.decidir(nuevo(), obs(T0, srv=None), T0, CRIT)        # nunca leído
    assert d["estado"] == "pausa"
    st = nuevo()
    assert vg.decidir(st, obs(T0, srv=1), T0, CRIT)["estado"] == "cancelar"
    assert vg.decidir(st, obs(T0 + 60, srv=0), T0 + 60, CRIT)["estado"] == "cancelar"


def test_p5_tres_c1_seguidos_exige_diagnostico():
    st = nuevo()
    st["orden_fin"] = ["a", "b", "c"]
    o = obs(T0)
    o["clases"] = {"a": {"clase": "C1"}, "b": {"clase": "C1"}, "c": {"clase": "C1"}}
    d = vg.decidir(st, o, T0, CRIT)
    assert d["estado"] == "pausa" and any(c.startswith("P5") for c in d["causas"])
    assert vg.decidir(st, obs(T0 + 400), T0 + 400, CRIT)["estado"] == "pausa"    # sin diagnóstico no reanuda
    o = obs(T0 + 460)
    o["diagnostico_p5_epoch"] = T0 + 450
    assert vg.decidir(st, o, T0 + 460, CRIT)["estado"] == "pausa"                 # diagnóstico, faltan 300 s
    o = obs(T0 + 761)
    o["diagnostico_p5_epoch"] = T0 + 450
    assert vg.decidir(st, o, T0 + 761, CRIT)["estado"] == "continuar"


def test_x1_solo_cuando_es_seguro():
    st = nuevo()
    st["orden_fin"] = [f"e{i}" for i in range(6)]
    o = obs(T0)
    o["clases"] = {f"e{i}": {"clase": "C3"} for i in range(5)}         # 5 de 25 = 20 %: aún no
    assert vg.decidir(st, o, T0, CRIT)["estado"] == "continuar"
    o = obs(T0 + 60)
    o["clases"] = {"e5": {"clase": "C2"}}                                # 6 de 25 > 20 %: seguro
    d = vg.decidir(st, o, T0 + 60, CRIT)
    assert d["estado"] == "cancelar" and d["causas"][0].startswith("X1")


def test_x3_dentro_de_episodio_cancela_fuera_informa():
    st = nuevo()
    iso = "2026-11-02T19:00:30.000000+0000"         # T0 + 30
    f = [{"ts": iso, "dest_ip": "10.10.10.99", "dest_port": 22, "event_type": "flow"}]
    assert vg.decidir(st, obs(T0 + 60, fuera=f), T0 + 60, CRIT)["estado"] == "continuar"   # sin episodio
    # la marca del episodio llega DESPUÉS del evento de EVE: se reevalúa y cancela
    vg.asimilar_marcas(st, [{"evento": "inicio", "episodio_id": "x-r1",
                             "reloj": {"pared_utc": "2026-11-02T19:00:20.000000+00:00"}}])
    d = vg.decidir(st, obs(T0 + 120), T0 + 120, CRIT)
    assert d["estado"] == "cancelar" and d["causas"][0].startswith("X3")


def test_eve_cursor_rotacion_y_limite(tmp_path):
    eve = tmp_path / "eve.json"
    l1 = json.dumps({"timestamp": "2026-11-02T19:00:01.0+0000", "src_ip": "10.10.20.30", "dest_ip": "10.10.30.10"},
                    separators=(",", ":"))
    l2 = json.dumps({"timestamp": "2026-11-02T19:00:02.0+0000", "src_ip": "10.10.20.30", "dest_ip": "8.8.8.8",
                     "flow": {"start": "2026-11-02T19:00:00.5+0000"}}, separators=(",", ":"))
    eve.write_text(l1 + "\n")
    r = vg.eve_fuera_lista(eve, -1, "10.10.20.30", {"10.10.30.10"}, 1 << 20)
    assert r["cursor"] == eve.stat().st_size and r["fuera"] == []
    with eve.open("a") as fh:
        fh.write(l2 + "\n" + l1[:20])                       # última línea a medio escribir
    r2 = vg.eve_fuera_lista(eve, r["cursor"], "10.10.20.30", {"10.10.30.10"}, 1 << 20)
    assert [f["dest_ip"] for f in r2["fuera"]] == ["8.8.8.8"] and r2["fuera"][0]["ts"].startswith("2026-11-02T19:00:00.5")
    assert r2["cursor"] == eve.stat().st_size - 20
    eve.write_text(l1 + "\n")                               # rotación
    assert vg.eve_fuera_lista(eve, r2["cursor"], "10.10.20.30", {"10.10.30.10"}, 1 << 20)["rotado"] is True
    assert vg.eve_fuera_lista(eve, 0, "10.10.20.30", set(), 5)["ok"] is False
    assert vg.eve_fuera_lista(tmp_path / "no", 0, "x", set(), 5)["ok"] is False


def test_obs_sensor_con_falsos(tmp_path):
    """Suborden sensor: systemctl y journalctl falsos, anillo, archivador, EVE y clasificación de un episodio."""
    import os
    import pytest
    if os.name == "nt":
        pytest.skip("necesita /proc/uptime y ejecutables falsos de Linux (banco Docker)")
    sc_ = tmp_path / "systemctl"
    sc_.write_text("#!/bin/sh\nprintf 'MainPID=7\\nNRestarts=0\\nActiveState=active\\n"
                   "ExecMainStartTimestampMonotonic=1000000\\n'\n")
    jc = tmp_path / "journalctl"
    jc.write_text("#!/bin/sh\necho '2026-11-02T19:00:00.000000+00:00 s tcpdump[1375]: 10 packets captured, "
                  "10 packets received by filter, 0 packets dropped by kernel'\n")
    for f in (sc_, jc):
        f.chmod(0o755)
    an = tmp_path / "anillo"
    an.mkdir()
    for n in ("live-20261102190000.pcap", "live-20261102190005.pcap", "live-20261102190015.pcap"):
        (an / n).write_bytes(b"")
    ar = tmp_path / "arch"
    ar.mkdir()
    (ar / "ESTADO.txt").write_text("OK\n")
    (ar / "archivar.log").write_text("2026-11-02T19:00:00Z OK a\n")
    eve = tmp_path / "eve.json"
    eve.write_text('{"src_ip":"10.10.20.30","dest_ip":"10.10.99.9","timestamp":"2026-11-02T19:00:01.0+0000"}\n')
    mu = tmp_path / "m.jsonl"
    mu.write_text("")
    a = vg.argparse.Namespace(systemctl=str(sc_), journalctl=str(jc), ventana_tcpdump=150.0, anillo=str(an),
                              anillo_ultimos=12, archivador=str(ar), eve=str(eve), eve_cursor=0, origen="10.10.20.30",
                              lista_blanca="10.10.30.10", eve_max_bytes=1 << 20, muestras=str(mu),
                              clasificar=["x-r1:1793646000:1793646100"])
    r = vg.obs_sensor(a)
    assert r["unidades"]["ppi-motor"]["activo"] == "active" and "arranque_epoch" in r["unidades"]["ppi-motor"]
    assert r["tcpdump"]["ok"] and r["tcpdump"]["lecturas"][0]["pid"] == 1375
    assert r["anillo"]["salto_max_s"] == 10.0 and r["archivador"]["lineas_ok"] == 1
    assert r["eve"]["fuera"][0]["dest_ip"] == "10.10.99.9"
    assert r["clases"]["x-r1"]["clase"] in ("C3", "insuficiente")      # sin muestras: nunca C0
    jc.write_text("#!/bin/sh\necho 'Failed to open journal' >&2; exit 1\n")
    r = vg.obs_sensor(a)
    assert r["tcpdump"]["ok"] is False and r["clases"]["x-r1"]["clase"] == "C3"
