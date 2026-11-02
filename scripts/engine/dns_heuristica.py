#!/usr/bin/env python3
"""Vista DNS de los heurísticos (Etapa 3, punto 4). NO cambia las 28 entradas del IF.

Problema (3B, 1-nov): ``dns_entropy`` disparaba en 382-385 ventanas sobre DC1
(10.10.10.20). El 98,8 % de las consultas que salen de DC1 (2 946 de 2 981) son
REENVÍOS de consultas de clientes: DC1 pregunta a su servidor superior, recibe
NXDOMAIN y contesta NOERROR al cliente. La NXDOMAIN la «veía» DC1, no el cliente.
Además, el espejo SPAN entrega cada consulta dos veces (VLAN de origen y de destino),
lo que duplica la cuenta: un cliente legítimo con subdominios hexadecimales
(10.10.20.22, 19 consultas/60 s reales) pasaba del umbral de 20.

Esta vista calcula, por (entidad, fin de ventana), las magnitudes que usa la regla:

- deduplica las copias del espejo (misma consulta/respuesta en < ``copia_s``);
- en un RESOLVEDOR interno, separa las consultas que reenvía (un cliente preguntó el
  mismo nombre y tipo a un resolvedor en los ``delta_s`` anteriores) de las PROPIAS, y
  la regla solo cuenta las propias. El resolvedor NO se excluye: sus consultas propias
  siguen contando y sus filas del IF no cambian;
- la NXDOMAIN se atribuye a quien preguntó en ESE flujo (como el extractor), ya sin
  copias.

Es causal: un reenvío siempre es posterior a la consulta del cliente y todo lo
usado tiene marca <= fin de ventana.

Los campos van con prefijo ``dnsh_`` para que nadie los confunda con las
características del modelo (que siguen saliendo del extractor, con copias incluidas).
"""
from __future__ import annotations

import bisect
import collections
import datetime as dt
import itertools
import json

VERSION = "2026-11-02.1"
RESOLVEDORES = frozenset({"10.10.10.20", "10.10.10.21"})
DELTA_REENVIO_S = 2.0
COPIA_S = 0.005
VENTANA_S = 60.0


def _ts(s: str) -> float:
    try:
        return dt.datetime.strptime(s[:26] + s[-5:], "%Y-%m-%dT%H:%M:%S.%f%z").timestamp()
    except ValueError:
        return dt.datetime.fromisoformat(s.replace("Z", "+00:00")).timestamp()


def _nombre_tipo(d: dict) -> tuple[str, str]:
    n, t = d.get("rrname"), d.get("rrtype")
    if not n:
        q = d.get("queries")
        if isinstance(q, list) and q and isinstance(q[0], dict):
            n, t = q[0].get("rrname"), q[0].get("rrtype")
    return (n or "").lower(), t or ""


class VistaDns:
    def __init__(self, resolvedores=RESOLVEDORES, delta_s: float = DELTA_REENVIO_S,
                 copia_s: float = COPIA_S, prefijo_red: str | None = None) -> None:
        self.resolvedores = frozenset(resolvedores)
        self.delta_s = float(delta_s)
        self.copia_s = float(copia_s)
        self.prefijo_red = prefijo_red
        # por origen: lista ordenada de (t, secuencia, nombre, clave_flujo, es_reenvio)
        self.consultas: dict[str, list] = collections.defaultdict(list)
        self.nx: dict[tuple, float] = {}                       # clave_flujo -> t
        self.cliente_a_resolvedor: dict[tuple, list] = collections.defaultdict(list)  # (nombre,tipo) -> [t]
        self._ultima: dict[tuple, float] = {}                  # deduplicación de copias
        self.copias = 0
        self._seq = itertools.count()

    # --- entrada -------------------------------------------------------------------
    def evento(self, e: dict) -> None:
        if e.get("event_type") != "dns":
            return
        d = e.get("dns") or {}
        tipo_ev = d.get("type")
        if tipo_ev not in ("query", "answer"):
            return
        ts = e.get("timestamp")
        if not ts:
            return
        t = _ts(ts)
        src, dst = e.get("src_ip") or "", e.get("dest_ip") or ""
        nombre, tipo = _nombre_tipo(d)
        flujo = (src, e.get("src_port"), dst, d.get("id"), nombre)
        clave = (tipo_ev, flujo, tipo, d.get("rcode"))
        prev = self._ultima.get(clave)
        if prev is not None and abs(t - prev) < self.copia_s:
            self.copias += 1
            return
        self._ultima[clave] = t
        if tipo_ev == "answer":
            if d.get("rcode") == "NXDOMAIN":
                self.nx[flujo] = t
            return
        reenvio = False
        if src in self.resolvedores:
            if dst not in self.resolvedores:
                lst = self.cliente_a_resolvedor.get((nombre, tipo), ())
                i = bisect.bisect_right(lst, t)
                reenvio = i > 0 and t - lst[i - 1] <= self.delta_s
        elif dst in self.resolvedores:
            bisect.insort(self.cliente_a_resolvedor[(nombre, tipo)], t)
        bisect.insort(self.consultas[src], (t, next(self._seq), nombre, flujo, reenvio))

    def linea(self, raw) -> None:
        # Filtro barato (la decisión real la toma event_type tras parsear).
        if isinstance(raw, (bytes, bytearray)):
            if b'"dns"' not in raw:
                return
        elif '"dns"' not in raw:
            return
        try:
            self.evento(json.loads(raw))
        except (ValueError, KeyError, TypeError):
            return

    def podar(self, antes: float) -> None:
        for src in list(self.consultas):
            lst = self.consultas[src]
            i = bisect.bisect_left(lst, (antes, -1))
            if i:
                del lst[:i]
            if not lst:
                del self.consultas[src]
        for k in list(self.cliente_a_resolvedor):
            lst = self.cliente_a_resolvedor[k]
            i = bisect.bisect_left(lst, antes - self.delta_s)
            if i:
                del lst[:i]
            if not lst:
                del self.cliente_a_resolvedor[k]
        for dic in (self.nx, self._ultima):
            for k in [k for k, v in dic.items() if v < antes - 1.0]:
                del dic[k]

    # --- salida --------------------------------------------------------------------
    def campos(self, entidad: str, fin: float, ventana_s: float = VENTANA_S) -> dict:
        lst = self.consultas.get(entidad, ())
        i0 = bisect.bisect_right(lst, (fin - ventana_s, float("inf")))
        i1 = bisect.bisect_right(lst, (fin, float("inf")))
        sel = lst[i0:i1]
        propias = [x for x in sel if not x[4]]
        n = len(propias)
        nx = sum(1 for x in propias if x[3] in self.nx and self.nx[x[3]] <= fin)
        return {
            "dnsh_consultas_60s": n,
            "dnsh_nxdomain_ratio_60s": nx / n if n else 0.0,
            "dnsh_nombres_unicos_ratio_60s": len({x[2] for x in propias}) / n if n else 0.0,
            "dnsh_reenvios_excluidos_60s": len(sel) - n,
        }
