"""Etapa 2: disparo del motor por cierre de PCAP y troceador de anillos."""
from __future__ import annotations

import argparse
import os
import struct
import sys
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ / "scripts" / "engine"))

import motor_decision as md  # noqa: E402
import trocear_pcap as tp  # noqa: E402

CAB = struct.pack("<IHHiIII", 0xA1B2C3D4, 2, 4, 0, 0, 65535, 1)


def pcap(ruta: Path, sellos, truncar=False):
    datos = bytearray(CAB)
    for t in sellos:
        trama = b"\x00" * 60
        datos += struct.pack("<IIII", int(t), int((t % 1) * 1e6), len(trama), len(trama)) + trama
    if truncar:
        datos = datos[:-10]
    ruta.write_bytes(bytes(datos))


class Reloj:
    def __init__(self, t):
        self.t = t
        self.dormido = []

    def time(self):
        return self.t

    def sleep(self, s):
        self.dormido.append(s)
        self.t += s


def args(d: Path, disparo="eventos"):
    return argparse.Namespace(capture_dir=d, capture_glob="live-*.pcap", history_seconds=230,
                              disparo=disparo, step_seconds=10, sondeo_segundos=0.25)


def test_fichero_abierto_no_dispara(tmp_path, monkeypatch):
    r = Reloj(1000.0)
    monkeypatch.setattr(md, "time", r)
    pcap(tmp_path / "live-20261101084000.pcap", [1000.0])
    os.utime(tmp_path / "live-20261101084000.pcap", (1000, 1000))
    # Un solo fichero: es el que tcpdump esta escribiendo -> no hay cerrado nuevo.
    assert not md.hay_pcap_cerrado_nuevo(args(tmp_path), set(), 1000.0)
    pcap(tmp_path / "live-20261101084005.pcap", [1005.0])
    os.utime(tmp_path / "live-20261101084005.pcap", (1000, 1000))
    assert md.hay_pcap_cerrado_nuevo(args(tmp_path), set(), 1000.0)
    assert not md.hay_pcap_cerrado_nuevo(args(tmp_path), {"live-20261101084000.pcap"}, 1000.0)


def test_esperar_eventos_dispara_al_cerrar(tmp_path, monkeypatch):
    r = Reloj(1000.0)
    monkeypatch.setattr(md, "time", r)
    pcap(tmp_path / "live-20261101084000.pcap", [1000.0])
    llamadas = {"n": 0}
    real = md.hay_pcap_cerrado_nuevo

    def falso(a, leidos, ahora):
        llamadas["n"] += 1
        if llamadas["n"] == 3:  # tercer sondeo: aparece el siguiente fichero
            pcap(tmp_path / "live-20261101084005.pcap", [1005.0])
        return real(a, leidos, ahora)

    monkeypatch.setattr(md, "hay_pcap_cerrado_nuevo", falso)
    for f in tmp_path.iterdir():
        os.utime(f, (1000, 1000))
    motivo = md.esperar_siguiente_ciclo(args(tmp_path), 1000.0, set())
    assert motivo == "pcap_cerrado" and r.t == pytest.approx(1000.75)


def test_esperar_eventos_plazo_sin_captura(tmp_path, monkeypatch):
    r = Reloj(1000.0)
    monkeypatch.setattr(md, "time", r)
    assert md.esperar_siguiente_ciclo(args(tmp_path), 1000.0, set()) == "plazo"
    assert r.t == pytest.approx(1010.0)


def test_esperar_periodico_como_desplegado(tmp_path, monkeypatch):
    r = Reloj(1003.0)
    monkeypatch.setattr(md, "time", r)
    assert md.esperar_siguiente_ciclo(args(tmp_path, "periodico"), 1000.0, set()) == "periodo"
    assert r.dormido == [7.0]
    r = Reloj(1012.0)
    monkeypatch.setattr(md, "time", r)
    md.esperar_siguiente_ciclo(args(tmp_path, "periodico"), 1000.0, set())
    assert r.dormido == [0.5]


def test_motor_args_por_omision_es_periodico(monkeypatch):
    monkeypatch.setattr(sys, "argv", ["m", "--model-path", "x", "--log-path", "y"])
    a = md.parse_args()
    assert a.disparo == "periodico" and a.volcar_caracteristicas is None


# --- troceador -----------------------------------------------------------------

def test_trocear_conserva_registros_y_rota(tmp_path):
    o, d = tmp_path / "o", tmp_path / "d"
    o.mkdir()
    base = 1793522400  # 2026-11-01T08:40:00Z
    pcap(o / tp.nombre_de(base), [base + 0.1 * i for i in range(150)])        # 0..14.9 s
    pcap(o / tp.nombre_de(base + 15), [base + 15 + 0.1 * i for i in range(150)])
    r = tp.trocear(sorted(o.iterdir()), d, 5)
    nuevos = sorted(d.iterdir())
    assert r["paquetes"] == 300 and len(nuevos) == 6
    assert [tp.t_fichero(p.name) - base for p in nuevos] == [0, 5, 10, 15, 20, 25]
    _, sha_o = tp.asignacion(sorted(o.iterdir()))
    _, sha_n = tp.asignacion(nuevos)
    assert sha_o == sha_n


def test_trocear_vacio_e_incompleto(tmp_path):
    o, d = tmp_path / "o", tmp_path / "d"
    o.mkdir()
    base = 1793522400
    pcap(o / tp.nombre_de(base), [base + 1, base + 2])
    (o / tp.nombre_de(base + 15)).write_bytes(b"")                     # vacio (0 bytes)
    (o / tp.nombre_de(base + 30)).write_bytes(CAB)                     # solo cabecera
    pcap(o / tp.nombre_de(base + 45), [base + 45, base + 46], truncar=True)  # ultimo registro cortado
    r = tp.trocear(sorted(o.iterdir()), d, 5)
    assert r["paquetes"] == 3  # 2 + 0 + 0 + 1 (el truncado se ignora)


def test_trocear_rotacion_solo_al_llegar_paquete(tmp_path):
    o, d = tmp_path / "o", tmp_path / "d"
    o.mkdir()
    base = 1793522400
    pcap(o / tp.nombre_de(base), [base + 1, base + 23])  # 22 s sin trafico
    tp.trocear(sorted(o.iterdir()), d, 5)
    assert [tp.t_fichero(p.name) - base for p in sorted(d.iterdir())] == [0, 23]


def test_motor_lee_pcap_vacio_y_truncado(tmp_path):
    pcap(tmp_path / "a.pcap", [1000.0, 1000.5], truncar=True)
    (tmp_path / "b.pcap").write_bytes(CAB)
    # Tramas de ceros: no son IPv4 -> el parser congelado las descarta, sin excepcion.
    assert md.parse_pcap_to_packets(tmp_path / "b.pcap") == []
    # Comportamiento documentado (extractor congelado, no se cambia): un fichero con
    # el ultimo registro cortado lanza ValueError y el motor lo cuenta en
    # pcaps_ilegibles, perdiendo TAMBIEN sus paquetes completos. Por eso el motor
    # nunca lee el fichero abierto (list_closed_pcap_files) y el disparo por eventos
    # usa el mismo criterio de cierre.
    with pytest.raises(ValueError, match="truncado"):
        md.parse_pcap_to_packets(tmp_path / "a.pcap")
    (tmp_path / "c.pcap").write_bytes(b"")
    with pytest.raises(ValueError):
        md.parse_pcap_to_packets(tmp_path / "c.pcap")
