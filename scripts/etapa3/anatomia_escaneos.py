#!/usr/bin/env python3
"""Etapa 3: anatomía de los escaneos breves a partir de los paquetes realmente capturados.

Para cada episodio (marcas inicio/fin del orquestador) lee el PCAP archivado del 3B
(rotación original) y, sin el motor, obtiene para el par origen→destino del escaneo:

- descubrimiento inicial (ICMP/ARP/TCP 80/443 previos a la ráfaga de nmap -sT)
- ráfaga efectiva: SYN a puertos distintos (deduplicando las copias del espejo SPAN)
- último intento (último SYN nuevo) y fin del proceso (marca 'fin')
- curva acumulada de puertos distintos y de SYN por instante

Copias SPAN: dos tramas idénticas (mismos campos IP/TCP salvo TTL ±1) en < 5 ms se
cuentan una vez. Retransmisiones: mismo (sport, dport, seq) => no es un intento nuevo.

Uso: python anatomia_escaneos.py marcas.jsonl dir-pcap salida.json [--tcpdump-like]
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "features"))
import extract_multilayer_v2 as v2  # noqa: E402

SYN, ACK, RST = 0x02, 0x10, 0x04


def ts(s: str) -> float:
    return dt.datetime.fromisoformat(s.replace("Z", "+00:00")).timestamp()


def iso(t: float | None) -> str | None:
    if t is None:
        return None
    return dt.datetime.fromtimestamp(t, dt.timezone.utc).strftime("%H:%M:%S.%f")[:-3]


def episodios(marcas: Path, prefijo: str) -> list[dict]:
    ini, fin = {}, {}
    for linea in marcas.open(encoding="utf-8"):
        r = json.loads(linea)
        e = r.get("episodio_id", "")
        if not e.startswith(prefijo):
            continue
        if r.get("evento") == "inicio":
            ini[e] = r
        elif r.get("evento") == "fin":
            fin[e] = r
    out = []
    for e, r in ini.items():
        out.append({"episodio": e, "destino": r.get("destino"), "comando": r.get("comando"),
                    "inicio": ts(r["reloj"]["pared_utc"]),
                    "fin": ts(fin[e]["reloj"]["pared_utc"]) if e in fin else None})
    return sorted(out, key=lambda x: x["inicio"])


def leer(pcap_dir: Path, desde: float, hasta: float) -> list:
    paq = []
    for f in sorted(pcap_dir.glob("live-*.pcap")):
        st = dt.datetime.strptime(f.stem[5:], "%Y%m%d%H%M%S").replace(tzinfo=dt.timezone.utc).timestamp()
        if st > hasta or st < desde - 900:
            continue
        for t, frame in v2.iter_pcap_frames(f):
            if desde <= t <= hasta:
                p = v2.parse_ethernet_ipv4(t, frame)
                if p is not None:
                    paq.append(p)
    paq.sort(key=lambda p: p.timestamp)
    return paq


def sin_copias_span(paq: list, ventana: float = 0.005) -> list:
    """Quita la segunda copia del espejo: misma 5-tupla, flags, seq y longitud en < 5 ms."""
    vistos: dict[tuple, float] = {}
    out = []
    for p in paq:
        k = (p.src_ip, p.dst_ip, p.protocol, p.src_port, p.dst_port, p.tcp_flags, p.tcp_seq, p.ip_length, p.icmp_id)
        t0 = vistos.get(k)
        if t0 is not None and p.timestamp - t0 < ventana:
            continue
        vistos[k] = p.timestamp
        out.append(p)
    return out


def anatomia(ep: dict, paq: list) -> dict:
    dst = ep["destino"]
    alrededor = [p for p in paq if dst in (p.src_ip, p.dst_ip)]
    # origen del escaneo: quien más SYN puros manda a dst durante el episodio
    cuenta: dict[str, int] = {}
    for p in alrededor:
        if (p.dst_ip == dst and p.protocol == 6 and p.tcp_flags & SYN and not p.tcp_flags & ACK
                and ep["inicio"] - 1 <= p.timestamp <= (ep["fin"] or p.timestamp) + 1):
            cuenta[p.src_ip] = cuenta.get(p.src_ip, 0) + 1
    if not cuenta:
        return {"episodio": ep["episodio"], "error": "sin SYN hacia el destino"}
    src = max(cuenta, key=cuenta.get)
    par = [p for p in alrededor if {p.src_ip, p.dst_ip} == {src, dst}]
    paq_todos_origen = sin_copias_span([p for p in paq if p.src_ip == src])
    crudo = len(par)
    par = sin_copias_span(par)
    syn = [p for p in par if p.src_ip == src and p.protocol == 6 and p.tcp_flags & SYN and not p.tcp_flags & ACK]
    vistos, nuevos, retrans = set(), [], 0
    for p in syn:
        k = (p.src_port, p.dst_port, p.tcp_seq)
        if k in vistos:
            retrans += 1
            continue
        vistos.add(k)
        nuevos.append(p)
    puertos_t: dict[int, float] = {}
    for p in nuevos:
        puertos_t.setdefault(p.dst_port, p.timestamp)
    orden = sorted(puertos_t.values())
    synack = [p for p in par if p.src_ip == dst and p.protocol == 6 and p.tcp_flags & SYN and p.tcp_flags & ACK]
    rst_dst = [p for p in par if p.src_ip == dst and p.protocol == 6 and p.tcp_flags & RST]
    previos = [p for p in par if p.src_ip == src and p.timestamp < (orden[0] if orden else 0)]
    icmp = [p for p in par if p.protocol == 1 and p.src_ip == src]

    # Fases. Descubrimiento: lo que el origen manda al destino antes de la ráfaga (nmap: ICMP
    # echo/timestamp, SYN 443, ACK 80). Resolución inversa: tráfico DNS del origen entre el
    # descubrimiento y la ráfaga. Ráfaga efectiva: primer instante t con >= 10 puertos
    # distintos NUEVOS en [t, t+1 s] (definición fijada antes de mirar los umbrales).
    import bisect as _b
    inicio_rafaga = None
    for i, t in enumerate(orden):
        if _b.bisect_right(orden, t + 1.0) - i >= 10:
            inicio_rafaga = t
            break
    desc = [p for p in par if p.src_ip == src and p.timestamp < (inicio_rafaga or 0)]
    dns_origen = [p for p in paq_todos_origen if p.protocol == 17 and p.dst_port == 53
                  and (desc[0].timestamp if desc else 0) <= p.timestamp < (inicio_rafaga or 0)]
    if inicio_rafaga is not None:
        orden_r = [t for t in orden if t >= inicio_rafaga]
    else:
        orden_r = []

    def instante_n(n: int):
        return orden[n - 1] if len(orden) >= n else None

    def rel_n(n: int):
        return round(orden_r[n - 1] - inicio_rafaga, 3) if len(orden_r) >= n else None

    fases = {
        "descubrimiento_inicio": iso(desc[0].timestamp) if desc else None,
        "descubrimiento_tramas": len(desc),
        "descubrimiento_detalle": sorted({(p.protocol, p.dst_port, p.tcp_flags, p.icmp_type) for p in desc}),
        "resolucion_inversa_consultas": len(dns_origen),
        "resolucion_inversa_servidores": sorted({p.dst_ip for p in dns_origen}),
        "rafaga_inicio": iso(inicio_rafaga),
        "rafaga_ultimo_syn": iso(orden_r[-1]) if orden_r else None,
        "rafaga_duracion_s": round(orden_r[-1] - inicio_rafaga, 3) if orden_r else None,
        "rafaga_puertos": len(orden_r),
        "fin_proceso": iso(ep["fin"]),
        "s_rafaga_a_fin_proceso": round(ep["fin"] - inicio_rafaga, 3) if inicio_rafaga and ep["fin"] else None,
        "s_desde_rafaga_hasta_n_puertos": {n: rel_n(n) for n in (5, 10, 15, 20, 30, 50, 100, 200, 500, 900)},
        "puertos_en_s_desde_rafaga": {d: sum(1 for t in orden_r if t <= inicio_rafaga + d)
                                       for d in (0.1, 0.25, 0.5, 1.0, 1.5, 2.0, 3.0, 4.0)} if inicio_rafaga else {},
    }

    # Ráfaga efectiva: del primer SYN nuevo hasta el instante en que se alcanza el 95 % de los puertos
    p95 = instante_n(max(1, int(0.95 * len(orden)))) if orden else None
    curva = []
    if orden:
        t0 = orden[0]
        for dt_ in (0.1, 0.25, 0.5, 1.0, 1.5, 2.0, 3.0, 4.0, 5.0, 7.5, 10.0):
            curva.append({"t_desde_primer_syn_s": dt_, "puertos_distintos": sum(1 for t in orden if t <= t0 + dt_)})
    return {
        "episodio": ep["episodio"], "comando": ep["comando"], "origen": src, "destino": dst,
        "marca_inicio": iso(ep["inicio"]), "marca_fin": iso(ep["fin"]),
        "duracion_proceso_s": round(ep["fin"] - ep["inicio"], 3) if ep["fin"] else None,
        "tramas_par_crudas": crudo, "tramas_par_sin_copias_span": len(par),
        "descubrimiento": {
            "primera_trama_origen": iso(previos[0].timestamp) if previos else None,
            "tramas_previas_a_la_rafaga": len(previos),
            "icmp_del_origen": len(icmp),
            "puertos_previos": sorted({p.dst_port for p in previos if p.protocol == 6}),
        },
        "rafaga": {
            "primer_syn_nuevo": iso(orden[0]) if orden else None,
            "syn_nuevos": len(nuevos), "retransmisiones_syn": retrans,
            "puertos_distintos": len(orden),
            "instante_10_puertos": iso(instante_n(10)), "instante_20_puertos": iso(instante_n(20)),
            "instante_50_puertos": iso(instante_n(50)), "instante_100_puertos": iso(instante_n(100)),
            "instante_95pct_puertos": iso(p95),
            "duracion_efectiva_s": round(p95 - orden[0], 3) if orden and p95 else None,
            "ultimo_syn_nuevo": iso(orden[-1]) if orden else None,
            "syn_ack_del_destino": len(synack), "rst_del_destino": len(rst_dst),
            "puertos_abiertos": sorted({p.src_port for p in synack}),
        },
        "fin_actividad_red": iso(max(p.timestamp for p in par)) if par else None,
        "s_desde_inicio_marca": {
            "primer_syn": round(orden[0] - ep["inicio"], 3) if orden else None,
            "ultimo_syn": round(orden[-1] - ep["inicio"], 3) if orden else None,
            "fin_proceso": round(ep["fin"] - ep["inicio"], 3) if ep["fin"] else None,
        },
        "curva": curva,
        "fases": fases,
        "_t": {"inicio": ep["inicio"], "fin": ep["fin"], "primer_syn": orden[0] if orden else None,
               "inicio_rafaga": inicio_rafaga,
               "ultimo_syn": orden[-1] if orden else None, "p95": p95,
               "puertos_t": orden},
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("marcas", type=Path)
    ap.add_argument("pcap_dir", type=Path)
    ap.add_argument("salida", type=Path)
    ap.add_argument("--prefijo", default="escaneo_breve")
    a = ap.parse_args()
    res = []
    for ep in episodios(a.marcas, a.prefijo):
        paq = leer(a.pcap_dir, ep["inicio"] - 30, (ep["fin"] or ep["inicio"]) + 30)
        r = anatomia(ep, paq)
        res.append(r)
        rf = r.get("rafaga", {})
        print(json.dumps(r.get("fases"), ensure_ascii=False))
        print(r["episodio"], r.get("origen"), "proceso", r.get("duracion_proceso_s"), "s | 1er SYN +",
              r.get("s_desde_inicio_marca", {}).get("primer_syn"), "| ultimo SYN +",
              r.get("s_desde_inicio_marca", {}).get("ultimo_syn"), "| puertos", rf.get("puertos_distintos"),
              "| efectiva", rf.get("duracion_efectiva_s"), "s | retrans", rf.get("retransmisiones_syn"),
              "| abiertos", rf.get("puertos_abiertos"))
    a.salida.write_text(json.dumps(res, indent=1, ensure_ascii=False), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
