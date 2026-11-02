"""Etapa 4: tráfico de ataque observado en el PCAP frente a las marcas del generador."""
from __future__ import annotations

import datetime as dt
import json
import struct
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ / "scripts" / "etapa4"))

import trafico_observado as to  # noqa: E402

KALI, SRV, DC1 = "10.10.20.30", "10.10.30.10", "10.10.10.20"
T0 = dt.datetime(2026, 11, 3, 10, 0, 0, tzinfo=dt.timezone.utc).timestamp()


def _ip(s):
    return bytes(int(x) for x in s.split("."))


def trama(src, dst, proto, dport, flags=0x02, vlan=0):
    eth = b"\x00" * 12
    for _ in range(vlan):
        eth += b"\x81\x00\x00\x3c"
    eth += b"\x08\x00"
    l4 = (struct.pack(">HHIIBBHHH", 40000, dport, 0, 0, 0x50, flags, 1024, 0, 0) if proto == 6
          else struct.pack(">HHHH", 40000, dport, 8, 0))
    ip = struct.pack(">BBHHHBBH4s4s", 0x45, 0, 20 + len(l4), 0, 0, 64, proto, 0, _ip(src), _ip(dst))
    return eth + ip + l4


def pcap(path: Path, paquetes, nano=False):
    magic = 0xA1B23C4D if nano else 0xA1B2C3D4
    out = struct.pack("<IHHiIII", magic, 2, 4, 0, 0, 262144, 1)
    for t, d in paquetes:
        frac = int(round((t % 1) * (1e9 if nano else 1e6)))
        out += struct.pack("<IIII", int(t), frac, len(d), len(d)) + d
    path.write_bytes(out + b"\x00\x01")      # cola truncada: se tolera


def marcas(path: Path, eps):
    ls = [{"evento": "campana_inicio", "orden": [e[0] for e in eps], "reloj": {"pared_utc": "x"}}]
    for eid, esc, dst, a, b in eps:
        ls.append({"evento": "inicio", "episodio_id": eid, "escenario": esc, "destino": dst,
                   "reloj": {"pared_utc": dt.datetime.fromtimestamp(a, dt.timezone.utc).isoformat()}})
        ls.append({"evento": "fin", "episodio_id": eid, "estado": "completo",
                   "reloj": {"pared_utc": dt.datetime.fromtimestamp(b, dt.timezone.utc).isoformat()}})
    path.write_text("\n".join(json.dumps(x) for x in ls) + "\n")


def test_lectura_vlan_nano_y_truncado(tmp_path):
    p = tmp_path / "live-1.pcap"
    pcap(p, [(T0 + 0.25, trama(KALI, SRV, 6, 22, vlan=1)), (T0 + 1, trama(KALI, DC1, 17, 53, vlan=2))], nano=True)
    r = list(to.leer_pcap(p))
    assert len(r) == 2 and r[0][1:] == (KALI, SRV, 6, 22, 0x02) and r[1][3:5] == (17, 53)
    assert abs(r[0][0] - (T0 + 0.25)) < 1e-6


def test_escaneo_usa_rafaga_de_syn_y_bucles_su_servicio(tmp_path):
    # escaneo breve: el proceso arranca en T0, nmap tarda 6 s en enviar el primer SYN
    paq = [(T0 + 6.0 + i * 0.01, trama(KALI, SRV, 6, 1 + i)) for i in range(100)]
    paq += [(T0 + 6.5, trama(KALI, SRV, 6, 80, flags=0x10))]           # ACK: no es SYN
    paq += [(T0 + 300 + i, trama(KALI, DC1, 17, 53)) for i in range(5)]  # dns en el episodio 2
    paq += [(T0 + 302, trama(KALI, SRV, 6, 80))]                        # al destino no previsto: 'otros'
    paq += [(T0 + 1000, trama(KALI, SRV, 6, 80))]                       # fuera de toda ventana
    paq += [(T0 + 1001, trama("10.10.20.20", SRV, 6, 80))]              # otro origen: ignorado
    d = tmp_path / "arch"
    d.mkdir()
    pcap(d / "live-20261103100000.pcap", sorted(paq))
    m = tmp_path / "marcas.jsonl"
    marcas(m, [("escaneo_breve-r1", "escaneo_breve", SRV, T0, T0 + 9), ("dns_inusual-r1", "dns_inusual", DC1,
                                                                     T0 + 299, T0 + 389)])
    cfg = tmp_path / "c.json"
    cfg.write_text(json.dumps({"origen": KALI, "lista_blanca_destinos": [DC1, SRV]}))
    out = tmp_path / "o.json"
    assert to.main(["--marcas", str(m), "--config", str(cfg), "--pcap-dir", str(d), "--salida", str(out)]) == 0
    r = json.loads(out.read_text(encoding="utf-8"))
    e1, e2 = r["episodios"]
    assert e1["paquetes_ataque"] == 100 and e1["puertos_distintos_syn"] == 100
    assert e1["retraso_primer_paquete_s"] == 6.0 and abs(e1["duracion_trafico_s"] - 0.99) < 1e-3
    assert e1["paquetes_origen_destino_otros"] == 1
    assert e2["paquetes_ataque"] == 5 and e2["paquetes_origen_destino_otros"] == 1
    assert r["fuera_de_episodio"]["paquetes"] == 1
    # la captura empieza después de T0−5: la ventana del primer episodio no queda cubierta
    assert e1["captura_cubre_ventana"] is False and "cotas" in e1["observacion"]


def test_episodio_sin_trafico_no_infiere_ausencia(tmp_path):
    eps = [{"episodio": "x-r1", "escenario": "inundacion_http", "destino": SRV, "t_proc_inicio": T0 + 10,
            "t_proc_fin": T0 + 20, "estado_generador": "completo"}]
    r = to.observar(eps, iter([(T0, KALI, DC1, 17, 53, None), (T0 + 100, KALI, DC1, 17, 53, None)]),
                    KALI, {SRV, DC1}, 5, 30)
    e = r["episodios"][0]
    assert e["paquetes_ataque"] == 0 and "NO se infiere" in e["observacion"]
