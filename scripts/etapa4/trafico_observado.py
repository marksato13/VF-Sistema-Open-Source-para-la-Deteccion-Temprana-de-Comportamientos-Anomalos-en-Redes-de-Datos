#!/usr/bin/env python3
"""Inicio y fin del tráfico de ataque OBSERVADO en la captura, por episodio (Etapa 4, campaña A).

Separa dos cosas que hasta el 3B se confundían:

  proceso del generador   ``inicio``/``fin`` de marcas.jsonl (reloj de pared de la Kali): cuándo arrancó
                          y terminó el comando (nmap espera, resuelve, etc. antes del primer paquete).
  tráfico observado       primer y último paquete del origen hacia el destino y servicio del escenario
                          en el PCAP archivado del Sensor1 (reloj del Sensor1).

Para los escaneos la referencia es la ráfaga real: primer y último SYN sin ACK del origen al destino
(distintos puertos), no la espera inicial de nmap. Para los bucles (DNS, HTTP, fuerza bruta) es el primer
y el último paquete hacia el servicio. Los paquetes del origen hacia los destinos que caen FUERA de toda
ventana de episodio se cuentan aparte (posible contaminación o restos de un episodio).

Solo lee: PCAP clásico (tcpdump -w, microsegundos o nanosegundos, ambos órdenes de bytes), Ethernet con
0, 1 o 2 etiquetas VLAN (0x8100 / 0x88a8). No necesita dependencias.

Uso:
  python trafico_observado.py --marcas marcas.jsonl --config escenarios-4c.json \
      --pcap-dir archivo/ --salida trafico-observado.json [--margen-antes 5] [--margen-despues 30]
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import struct
import sys
from pathlib import Path

VERSION = "2026-11-02.1"

# Qué cuenta como tráfico de ataque de cada escenario (protocolo, puerto destino o None = cualquiera,
# solo SYN sin ACK). Coincide con escenarios.json (servicio) y con FICHAS-ESCENARIOS.md.
FILTROS = {
    "dns_inusual": {"proto": 17, "dport": 53, "solo_syn": False},
    "inundacion_http": {"proto": 6, "dport": 80, "solo_syn": False},
    "escaneo_breve": {"proto": 6, "dport": None, "solo_syn": True},
    "escaneo_sostenido": {"proto": 6, "dport": None, "solo_syn": True},
    "fuerza_bruta_http": {"proto": 6, "dport": 18081, "solo_syn": False},
}

_MAGIC = {b"\xd4\xc3\xb2\xa1": ("<", 1e-6), b"\xa1\xb2\xc3\xd4": (">", 1e-6),
          b"\x4d\x3c\xb2\xa1": ("<", 1e-9), b"\xa1\xb2\x3c\x4d": (">", 1e-9)}


def leer_pcap(path: Path):
    """Genera (t, ip_src, ip_dst, proto, dport, flags_tcp) de cada paquete IPv4. Tolera un final truncado."""
    with path.open("rb") as fh:
        cab = fh.read(24)
        if len(cab) < 24 or cab[:4] not in _MAGIC:
            raise ValueError(f"{path.name}: no es PCAP clásico")
        orden, escala = _MAGIC[cab[:4]]
        enlace = struct.unpack(orden + "I", cab[20:24])[0] & 0xFFFF
        if enlace != 1:
            raise ValueError(f"{path.name}: enlace {enlace} no soportado (se espera Ethernet)")
        rec = struct.Struct(orden + "IIII")
        while True:
            h = fh.read(16)
            if len(h) < 16:
                return
            seg, frac, incl, _orig = rec.unpack(h)
            datos = fh.read(incl)
            if len(datos) < incl:
                return                       # registro a medio escribir: fin del fichero
            p = _analizar(datos)
            if p is not None:
                yield (seg + frac * escala,) + p


def _analizar(d: bytes):
    if len(d) < 14:
        return None
    off = 12
    eth = int.from_bytes(d[off:off + 2], "big")
    while eth in (0x8100, 0x88A8) and len(d) >= off + 6:
        off += 4
        eth = int.from_bytes(d[off:off + 2], "big")
    off += 2
    if eth != 0x0800 or len(d) < off + 20:
        return None
    ihl = (d[off] & 0x0F) * 4
    proto = d[off + 9]
    src = ".".join(str(b) for b in d[off + 12:off + 16])
    dst = ".".join(str(b) for b in d[off + 16:off + 20])
    frag = int.from_bytes(d[off + 6:off + 8], "big") & 0x1FFF
    l4 = off + ihl
    dport, flags = None, None
    if frag == 0 and proto in (6, 17) and len(d) >= l4 + 4:
        dport = int.from_bytes(d[l4 + 2:l4 + 4], "big")
        if proto == 6 and len(d) >= l4 + 14:
            flags = d[l4 + 13]
    return src, dst, proto, dport, flags


def _ts(iso: str) -> float:
    return dt.datetime.fromisoformat(iso.replace("Z", "+00:00")).timestamp()


def _iso(t):
    return None if t is None else dt.datetime.fromtimestamp(t, dt.timezone.utc).isoformat()


def episodios(marcas: Path) -> list[dict]:
    ini, fin, orden = {}, {}, None
    for l in marcas.read_text(encoding="utf-8").splitlines():
        if not l.strip():
            continue
        r = json.loads(l)
        if r.get("evento") == "inicio":
            ini[r["episodio_id"]] = r
        elif r.get("evento") == "fin":
            fin[r["episodio_id"]] = r
        elif r.get("evento") == "campana_inicio":
            orden = r.get("orden")
    eps = []
    for e in sorted(ini, key=lambda k: _ts(ini[k]["reloj"]["pared_utc"])):
        f = fin.get(e)
        eps.append({"episodio": e, "escenario": ini[e]["escenario"], "destino": ini[e]["destino"],
                    "t_proc_inicio": _ts(ini[e]["reloj"]["pared_utc"]),
                    "t_proc_fin": _ts(f["reloj"]["pared_utc"]) if f else None,
                    "estado_generador": f.get("estado") if f else "sin_fin"})
    return eps, orden


def observar(eps: list[dict], paquetes, origen: str, destinos: set, antes: float, despues: float) -> dict:
    # ventana de asignación de cada episodio: [inicio − antes, fin + después], sin solapar con el siguiente
    vent = []
    for i, e in enumerate(eps):
        a = e["t_proc_inicio"] - antes
        b = (e["t_proc_fin"] if e["t_proc_fin"] is not None else e["t_proc_inicio"]) + despues
        if i + 1 < len(eps):
            b = min(b, eps[i + 1]["t_proc_inicio"] - antes)
        vent.append((a, b))
    acc = {e["episodio"]: {"n": 0, "primero": None, "ultimo": None, "puertos": set(), "otros": 0} for e in eps}
    fuera, t_min, t_max, total = [], None, None, 0
    for t, src, dst, proto, dport, flags in paquetes:
        total += 1
        t_min = t if t_min is None else min(t_min, t)
        t_max = t if t_max is None else max(t_max, t)
        if src != origen or dst not in destinos:
            continue
        idx = next((i for i, (a, b) in enumerate(vent) if a <= t <= b), None)
        if idx is None:
            fuera.append(t)
            continue
        e = eps[idx]
        f = FILTROS.get(e["escenario"])
        x = acc[e["episodio"]]
        if f is None or dst != e["destino"] or proto != f["proto"] \
                or (f["dport"] is not None and dport != f["dport"]) \
                or (f["solo_syn"] and (flags is None or (flags & 0x12) != 0x02)):
            x["otros"] += 1
            continue
        x["n"] += 1
        x["primero"] = t if x["primero"] is None else min(x["primero"], t)
        x["ultimo"] = t if x["ultimo"] is None else max(x["ultimo"], t)
        if f["solo_syn"]:
            x["puertos"].add(dport)
    out = []
    for e, (a, b) in zip(eps, vent):
        x = acc[e["episodio"]]
        cubierta = t_min is not None and t_min <= a and t_max >= b
        r = {**{k: e[k] for k in ("episodio", "escenario", "destino", "estado_generador")},
             "t_proc_inicio_utc": _iso(e["t_proc_inicio"]), "t_proc_fin_utc": _iso(e["t_proc_fin"]),
             "ventana_asignacion_utc": [_iso(a), _iso(b)], "captura_cubre_ventana": cubierta,
             "criterio": FILTROS.get(e["escenario"], {"motivo": "escenario sin filtro definido"}),
             "paquetes_ataque": x["n"], "paquetes_origen_destino_otros": x["otros"],
             "t_trafico_inicio_utc": _iso(x["primero"]), "t_trafico_fin_utc": _iso(x["ultimo"]),
             "duracion_trafico_s": round(x["ultimo"] - x["primero"], 3) if x["n"] else None,
             "retraso_primer_paquete_s": round(x["primero"] - e["t_proc_inicio"], 3) if x["n"] else None,
             "cola_tras_fin_proceso_s": (round(x["ultimo"] - e["t_proc_fin"], 3)
                                         if x["n"] and e["t_proc_fin"] is not None else None)}
        if FILTROS.get(e["escenario"], {}).get("solo_syn"):
            r["puertos_distintos_syn"] = len(x["puertos"])
        if not cubierta:
            r["observacion"] = "la captura leída no cubre toda la ventana: el inicio/fin observados son cotas"
        elif x["n"] == 0:
            r["observacion"] = "sin tráfico de ataque en la captura: NO se infiere ausencia de ataque"
        out.append(r)
    return {"version": VERSION, "origen": origen, "destinos": sorted(destinos),
            "margenes_s": {"antes": antes, "despues": despues}, "paquetes_leidos": total,
            "captura_utc": [_iso(t_min), _iso(t_max)],
            "fuera_de_episodio": {"paquetes": len(fuera), "primero_utc": _iso(min(fuera)) if fuera else None,
                                  "ultimo_utc": _iso(max(fuera)) if fuera else None},
            "episodios": out,
            "nota_relojes": ("t_proc_* es el reloj de la Kali; t_trafico_* el del Sensor1. La diferencia solo es "
                             "interpretable con el desfase medido (comprobar_relojes.sh; criterio |desfase| <= 1 s).")}


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--marcas", type=Path, required=True)
    p.add_argument("--config", type=Path, required=True)
    p.add_argument("--pcap-dir", type=Path, required=True)
    p.add_argument("--patron", default="live-*.pcap")
    p.add_argument("--salida", type=Path, required=True)
    p.add_argument("--margen-antes", type=float, default=5.0)
    p.add_argument("--margen-despues", type=float, default=30.0)
    a = p.parse_args(argv)
    cfg = json.loads(a.config.read_text(encoding="utf-8"))
    eps, orden = episodios(a.marcas)
    if not eps:
        print("marcas sin episodios", file=sys.stderr)
        return 2
    ficheros = sorted(a.pcap_dir.glob(a.patron))
    if not ficheros:
        print("sin PCAP en --pcap-dir", file=sys.stderr)
        return 2
    errores = []

    def todos():
        for f in ficheros:
            try:
                yield from leer_pcap(f)
            except (OSError, ValueError) as e:
                errores.append(f"{f.name}: {e}")

    res = observar(eps, todos(), cfg["origen"], set(cfg["lista_blanca_destinos"]),
                   a.margen_antes, a.margen_despues)
    res["orden_publicado"] = orden
    res["ficheros_pcap"] = len(ficheros)
    res["errores_lectura"] = errores
    a.salida.write_text(json.dumps(res, indent=1, ensure_ascii=False), encoding="utf-8")
    sin = [e["episodio"] for e in res["episodios"] if not e["paquetes_ataque"]]
    print(f"{len(res['episodios'])} episodios; sin tráfico observado: {len(sin)}; fuera de episodio: "
          f"{res['fuera_de_episodio']['paquetes']} paquetes; errores de lectura: {len(errores)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
