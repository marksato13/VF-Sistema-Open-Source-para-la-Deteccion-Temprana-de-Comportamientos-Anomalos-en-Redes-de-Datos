#!/usr/bin/env python3
"""Vista HTTP de los heurísticos (Etapa 3, punto 5). NO cambia las 28 entradas del IF.

Problema (3B, 1-nov): Suricata registra transacciones HTTP de flujos ya terminados
mucho después, cuando procesa su vencimiento, con la marca de tiempo del paquete que
está tratando en ese momento. Medido en el archivo del 3B:

- tras cada inundación o fuerza bruta, el EVE sigue registrando HTTP de la Kali durante
  unos 60 s después del fin, con 0 tramas TCP de ese origen y puerto en el cable;
- al empezar el episodio siguiente (sea DNS o escaneo), aparecen 100-976 peticiones
  más, también con 0 tramas en el cable. Son las «peticiones concurrentes» de
  escaneo_breve-r1 (C10 de la Etapa 2): no existieron durante el escaneo.

Esas transacciones hacían disparar brute_force y http_abuse fuera de su episodio. La
vista cuenta un evento HTTP solo si SU flujo (5-tupla, en cualquier sentido) tiene
alguna trama en el cable a <= ``tolerancia_s`` de la marca del evento; si no, lo
excluye como registro tardío y lo cuenta aparte. Es causal: usa solo tramas con marca
<= fin de ventana, que el motor ya tiene cuando decide la ventana.

Copias del espejo: mismo (flow_id, tx_id, url) cuenta una vez.
Campos con prefijo ``httph_`` (no son características del modelo).
"""
from __future__ import annotations

import bisect
import collections
import datetime as dt
import json

VERSION = "2026-11-02.1"
TOLERANCIA_S = 2.0
VENTANA_S = 60.0


def _ts(s: str) -> float:
    try:
        return dt.datetime.strptime(s[:26] + s[-5:], "%Y-%m-%dT%H:%M:%S.%f%z").timestamp()
    except ValueError:
        return dt.datetime.fromisoformat(s.replace("Z", "+00:00")).timestamp()


def clave_flujo(a: str, pa, b: str, pb) -> tuple:
    """5-tupla TCP sin sentido (el EVE da el flujo cliente->servidor; las tramas van en los dos)."""
    x, y = (a, int(pa or 0)), (b, int(pb or 0))
    return (x, y) if x <= y else (y, x)


class VistaHttp:
    def __init__(self, tolerancia_s: float = TOLERANCIA_S) -> None:
        self.tolerancia_s = float(tolerancia_s)
        self.eventos: list[tuple] = []        # (t, src, flujo, fallo_auth) ordenados por t
        self._vistos: dict[tuple, float] = {}

    def evento(self, e: dict) -> None:
        if e.get("event_type") != "http" or not e.get("timestamp"):
            return
        h = e.get("http") or {}
        k = (e.get("flow_id"), e.get("tx_id"), h.get("url"))
        t = _ts(e["timestamp"])
        if k in self._vistos:
            return
        self._vistos[k] = t
        try:
            estado = int(h.get("status") or 0)
        except (TypeError, ValueError):
            estado = 0
        fl = clave_flujo(e.get("src_ip") or "", e.get("src_port"), e.get("dest_ip") or "", e.get("dest_port"))
        bisect.insort(self.eventos, (t, e.get("src_ip") or "", fl, estado in (401, 403)))

    def linea(self, raw) -> None:
        if isinstance(raw, (bytes, bytearray)):
            if b'"http"' not in raw:
                return
        elif '"http"' not in raw:
            return
        try:
            self.evento(json.loads(raw))
        except (ValueError, KeyError, TypeError):
            return

    def podar(self, antes: float) -> None:
        i = bisect.bisect_left(self.eventos, (antes,))
        if i:
            del self.eventos[:i]
        for k in [k for k, v in self._vistos.items() if v < antes]:
            del self._vistos[k]

    def campos_por_entidad(self, fin: float, paquetes, ventana_s: float = VENTANA_S) -> dict[str, dict]:
        """Campos de (fin - ventana, fin] para cada origen con HTTP. ``paquetes``: tramas
        (atributos timestamp, src_ip, dst_ip, src_port, dst_port) del horizonte."""
        i0 = bisect.bisect_right(self.eventos, (fin - ventana_s, "￿"))
        i1 = bisect.bisect_right(self.eventos, (fin, "￿"))
        sel = self.eventos[i0:i1]
        if not sel:
            return {}
        necesarios = {e[2] for e in sel}
        tiempos: dict[tuple, list] = collections.defaultdict(list)
        # Causal: solo tramas <= fin (el motor solo garantiza los PCAP cerrados hasta la
        # ventana + 5 ms). Una transacción real tiene su petición antes de la marca del
        # evento, así que siempre hay una trama en [t - tolerancia, t].
        hasta = fin
        for p in paquetes:
            if p.timestamp > hasta or getattr(p, "protocol", 6) != 6:
                continue
            k = clave_flujo(p.src_ip, p.src_port, p.dst_ip, p.dst_port)
            if k in necesarios:
                tiempos[k].append(p.timestamp)
        for v in tiempos.values():
            v.sort()
        acc: dict[str, list] = collections.defaultdict(lambda: [0, 0, 0])
        for t, src, fl, fallo in sel:
            ts = tiempos.get(fl, ())
            j = bisect.bisect_left(ts, t - self.tolerancia_s)
            en_cable = j < len(ts) and ts[j] <= t + self.tolerancia_s
            a = acc[src]
            if en_cable:
                a[0] += 1
                a[1] += fallo
            else:
                a[2] += 1
        return {src: {"httph_peticiones_60s": n, "httph_fallo_auth_ratio_60s": f / n if n else 0.0,
                      "httph_tardios_excluidos_60s": x} for src, (n, f, x) in acc.items()}


CAMPOS_VACIOS = {"httph_peticiones_60s": 0, "httph_fallo_auth_ratio_60s": 0.0, "httph_tardios_excluidos_60s": 0}
