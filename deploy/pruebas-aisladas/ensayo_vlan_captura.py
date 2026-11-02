#!/usr/bin/env python3
"""Cierre de la Etapa 3, hallazgo 3: el filtro de captura de la vía rápida frente a las VLAN.

SOLO banco Docker como root, sin red del laboratorio:

  docker run --rm --privileged --network none -v <repo>:/src:ro -v <seg>:/seg:ro -v <out>:/out \\
    cyberflow-etapa3-banco:1 bash -c 'cp -a /src /w && cd /w && \\
      python3 deploy/pruebas-aisladas/ensayo_vlan_captura.py /seg /out'

La unidad ppi-via-rapida@ captura con ``tcpdump ... -w - tcp``. El espejo del laboratorio
entrega tramas 802.1Q y el ensayo de la batería las reinyectaba SIN etiqueta
(``--enet-vlan=del``), así que no comprobaba el filtro con VLAN. Aquí, para cada escaneo
grabado del archivo del 3B, en su forma ORIGINAL (etiquetada) y sin etiqueta:

1. Fuera de línea: ``tcpdump -r`` con cada filtro candidato; tramas, SYN, SYN-ACK y RST
   que pasan, frente al total TCP de la muestra.
2. En vivo: la tubería COMPLETA de la unidad (tcpdump -i vB -n -U --immediate-mode -s 128
   -w - <filtro> | detector_rapido.py --flujo), con tee para guardar lo que entrega
   tcpdump, mientras tcpreplay-edit reproduce la muestra por la veth vA -> vB (solo se
   reescribe la MAC de destino; la etiqueta se conserva en la variante etiquetada).
   Se cuentan SYN, SYN-ACK y RST entregados, si conservan la etiqueta, las copias del
   espejo que la deduplicación descarta y los disparos.
3. Referencia: el detector sobre la muestra leída directamente (sin tcpdump).

Filtros: ``tcp`` (unidad 585da7b), ``tcp or (vlan and tcp)`` (candidato) y sin filtro.
No se toca ninguna interfaz, switch ni offload del laboratorio: solo la veth del
contenedor.
"""
from __future__ import annotations

import json
import os
import signal
import struct
import subprocess
import sys
import time
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RAIZ / "scripts" / "engine"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import detector_rapido as dr  # noqa: E402
import escaneo_temprano as et  # noqa: E402
from ensayo_via_rapida import red  # noqa: E402

PY = sys.executable
FILTROS = {"tcp": "tcp", "tcp_o_vlan_tcp": "tcp or (vlan and tcp)", "sin_filtro": ""}
SYN, ACK, RST = 0x02, 0x10, 0x04


def sh(*a, **kw):
    return subprocess.run(list(a), capture_output=True, text=True, **kw)


def tramas(ruta: Path):
    with ruta.open("rb") as fh:
        lp = dr.LectorPcap(fh)
        while (x := lp.siguiente()) is not None:
            yield x


def clasificar(frame: bytes):
    """(etiquetas, ip_tcp, flags) de una trama Ethernet."""
    if len(frame) < 14:
        return 0, False, 0
    off, et_, n = 14, (frame[12] << 8) | frame[13], 0
    while et_ in (0x8100, 0x88A8) and len(frame) >= off + 4:
        et_ = (frame[off + 2] << 8) | frame[off + 3]
        off += 4
        n += 1
    if et_ != 0x0800 or len(frame) < off + 20 or frame[off + 9] != 6:
        return n, False, 0
    tr = off + (frame[off] & 0x0F) * 4
    return n, True, (frame[tr + 13] if len(frame) > tr + 13 else 0)


def contar(ruta: Path) -> dict:
    c = {"tramas": 0, "etiquetadas": 0, "doble_etiqueta": 0, "tcp": 0, "syn": 0, "syn_ack": 0, "rst": 0}
    if not ruta.exists() or ruta.stat().st_size < 24:
        return c
    for _, fr in tramas(ruta):
        n, es_tcp, fl = clasificar(fr)
        c["tramas"] += 1
        c["etiquetadas"] += n >= 1
        c["doble_etiqueta"] += n >= 2
        if es_tcp:
            c["tcp"] += 1
            c["syn"] += bool(fl & SYN and not fl & ACK)
            c["syn_ack"] += bool(fl & SYN and fl & ACK)
            c["rst"] += bool(fl & RST)
    return c


def detector_sobre(ruta: Path) -> dict:
    d = et.DetectorEscaneoTemprano("10.10.0.0/16", frozenset(x for x in dr.EXCLUIDOS_POR_OMISION.split(",") if x))
    disparos = []
    if ruta.exists() and ruta.stat().st_size >= 24:
        for t, fr in tramas(ruta):
            tcp = dr.tcp_de_trama(fr)
            if tcp is not None:
                disparos += d.observar(t, *tcp)
        disparos += d.avanzar(d.t)
    return {"paquetes_syn_rst": d.paquetes, "copias_span": d.copias_span, "retransmisiones": d.retransmisiones,
            "disparos": [(x["origen"], x["destino"], x["puertos_fallidos"]) for x in disparos]}


def sin_etiqueta(src: Path, dst: Path) -> None:
    r = sh("tcprewrite", "--enet-vlan=del", "-i", str(src), "-o", str(dst))
    if r.returncode:
        raise SystemExit(r.stderr)


def fuera_de_linea(muestra: Path, tmp: Path) -> dict:
    out = {}
    for nombre, f in FILTROS.items():
        o = tmp / ("off-%s.pcap" % nombre)
        r = sh("tcpdump", "-r", str(muestra), "-w", str(o), *([f] if f else []))
        out[nombre] = dict(contar(o), rc=r.returncode)
    return out


def en_vivo(muestra: Path, tmp: Path, etiqueta: str) -> dict:
    mac = red()
    procs = {}
    for nombre, f in FILTROS.items():
        cap, sal, res = (tmp / ("vivo-%s-%s.%s" % (etiqueta, nombre, x)) for x in ("pcap", "jsonl", "res"))
        for p in (cap, sal, res):
            p.unlink(missing_ok=True)
        filtro = (" '%s'" % f) if f else ""
        # Comando de la unidad (sin User=m4rk: aquí root), con tee para conservar lo entregado.
        cmd = ("set -o pipefail; /usr/bin/tcpdump -i vB -n -U --immediate-mode -s 128 -w -%s "
               "| tee %s | %s scripts/engine/detector_rapido.py --flujo --salida %s --resumen %s"
               % (filtro, cap, PY, sal, res))
        procs[nombre] = (subprocess.Popen(["bash", "-c", cmd], cwd=str(RAIZ), stderr=subprocess.PIPE,
                                          start_new_session=True), cap, sal)
    time.sleep(2.0)
    r = sh("tcpreplay-edit", "--enet-dmac=%s" % mac, "-i", "vA", str(muestra))
    time.sleep(2.0)
    out = {"tcpreplay_rc": r.returncode, "tcpreplay": r.stdout.strip().splitlines()[-6:]}
    for nombre, (p, cap, sal) in procs.items():
        sh("pkill", "-INT", "-f", "tcpdump -i vB")
        try:
            _, err = p.communicate(timeout=10)
        except subprocess.TimeoutExpired:
            os.killpg(p.pid, signal.SIGKILL)
            _, err = p.communicate()
        senales = [json.loads(x) for x in sal.read_text().splitlines()] if sal.exists() else []
        out[nombre] = dict(contar(cap), deteccion=detector_sobre(cap),
                           senales=[(s["origen"], s["destino"], s["puertos_fallidos"]) for s in senales],
                           tcpdump_resumen=[x for x in err.decode(errors="replace").splitlines()
                                            if "packets" in x])
    return out


def main(argv=None) -> int:
    argv = argv or sys.argv[1:]
    seg, out = Path(argv[0]), Path(argv[1])
    out.mkdir(parents=True, exist_ok=True)
    tmp = Path("/tmp/vlan")
    tmp.mkdir(exist_ok=True)
    ver = sh("tcpdump", "--version")
    res = {"tcpdump_version": (ver.stdout + ver.stderr).strip().splitlines(),
           "kernel": sh("uname", "-r").stdout.strip(), "filtros": FILTROS, "muestras": {}}
    for m in sorted(seg.glob("escaneo_breve-r*.pcap")):
        plano = tmp / (m.stem + "-sin-vlan.pcap")
        sin_etiqueta(m, plano)
        r = {}
        for etiqueta, ruta in (("etiquetada", m), ("sin_etiqueta", plano)):
            r[etiqueta] = {"muestra": contar(ruta), "referencia": detector_sobre(ruta),
                           "fuera_de_linea": fuera_de_linea(ruta, tmp),
                           "en_vivo": en_vivo(ruta, tmp, etiqueta)}
            print(m.name, etiqueta, json.dumps({k: (v["syn"], v["syn_ack"], v["rst"], len(v["senales"]))
                                                for k, v in r[etiqueta]["en_vivo"].items()
                                                if isinstance(v, dict)}), flush=True)
        res["muestras"][m.name] = r
    (out / "ensayo-vlan.json").write_text(json.dumps(res, indent=1, sort_keys=True), encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main())
