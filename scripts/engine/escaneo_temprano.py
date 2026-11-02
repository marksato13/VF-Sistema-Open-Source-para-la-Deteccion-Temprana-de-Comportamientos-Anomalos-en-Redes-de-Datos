#!/usr/bin/env python3
"""Vía rápida de detección de escaneo (Etapa 3): componente heurístico ADICIONAL.

No toca el IF ni sus 28 características ni las ventanas de 10 s del motor. Lee paquetes
(de ficheros PCAP cortos ya cerrados o de un flujo continuo) y dispara por par
origen→destino cuando, con la información disponible hasta el instante evaluado, hay
al menos ``K`` puertos destino DISTINTOS cuyos intentos de conexión TCP han fallado
dentro de los últimos ``W`` segundos.

Un intento (SYN sin ACK) "ha fallado" en el instante t si:
- el destino respondió con RST antes de t, o
- han pasado ``g`` segundos desde el SYN sin SYN-ACK del destino (puerto filtrado:
  srv-dmz descarta en silencio los puertos cerrados, así que no hay RST).
Un SYN-ACK que llega después de ``g`` retira el intento del conteo desde ese momento.

Tratamientos:
- Copias del espejo SPAN: la misma trama (5-tupla, flags, seq, longitud) en < 5 ms se
  cuenta una vez.
- Retransmisiones: mismo (origen, puerto origen, destino, puerto destino, seq) = un
  intento. Un segundo SYN al mismo puerto con otro puerto de origen es otro intento,
  pero el conteo es de puertos DISTINTOS, así que no infla.
- Tráfico legítimo confundible: muchas conexiones a pocos puertos (HTTP, inundaciones,
  fuerza bruta) no suman puertos distintos; las conexiones completadas no cuentan.
- Causalidad: ``avanzar(t)`` solo usa paquetes con marca <= t. Los vencimientos de
  ``g`` se resuelven en el instante exacto t_syn + g (o en la primera evaluación
  posterior), no con información futura.

Cada disparo lleva identificador estable y evidencia: puertos, primeros instantes,
intentos y completados en la ventana, parámetros y versión.
"""
from __future__ import annotations

import hashlib
import heapq
from collections import deque
import ipaddress
from dataclasses import dataclass, field

VERSION = "2026-11-02.1"
SYN, ACK, RST = 0x02, 0x10, 0x04

# Parámetros por omisión. Justificación y sensibilidad: etapa3 / ESCANEO-BREVE.md.
PARAMETROS_POR_OMISION = {"K": 10, "W": 2.0, "g": 0.1, "refractario_s": 60.0}


@dataclass
class _Par:
    vivos: dict = field(default_factory=dict)        # id_intento -> puerto (fallo vigente)
    cuenta: dict = field(default_factory=dict)       # puerto -> n fallos vigentes
    por_syn: list = field(default_factory=list)      # heap (t_syn, id)
    por_fin: list = field(default_factory=list)      # heap (t_fin_vigencia, id)
    ultimo_disparo: float = -1e18
    intentos_ventana: deque = field(default_factory=deque)  # (t_syn, puerto) de los últimos W s
    completados: int = 0


class DetectorEscaneoTemprano:
    def __init__(self, red: str = "10.10.0.0/16", excluidos: set | frozenset = frozenset(),
                 K: int | None = None, W: float | None = None, g: float | None = None,
                 refractario_s: float | None = None) -> None:
        p = PARAMETROS_POR_OMISION
        self.K = int(K if K is not None else p["K"])
        self.W = float(W if W is not None else p["W"])
        self.g = float(g if g is not None else p["g"])
        self.refractario_s = float(refractario_s if refractario_s is not None else p["refractario_s"])
        self.red = ipaddress.ip_network(red)
        self.excluidos = frozenset(excluidos)
        self._en_red: dict[str, bool] = {}
        self._copias: dict[tuple, float] = {}
        self._vistos: dict[tuple, float] = {}           # (src,sport,dst,dport,seq) -> t
        self._abiertos: dict[tuple, tuple] = {}         # (src,sport,dst,dport) -> (id, t_syn, puerto, par)
        self._pendientes: list = []                     # heap (t_syn + g, id)
        self._intento: dict[int, tuple] = {}            # id -> (par, t_syn, puerto, estado)
        self._pares: dict[tuple, _Par] = {}
        self._n = 0
        self.t = float("-inf")
        self.paquetes = 0
        self.copias_span = 0
        self.retransmisiones = 0

    # --- utilidades ------------------------------------------------------------
    def _dentro(self, ip: str) -> bool:
        r = self._en_red.get(ip)
        if r is None:
            r = self._en_red[ip] = ipaddress.ip_address(ip) in self.red
        return r

    def _par(self, k: tuple) -> _Par:
        p = self._pares.get(k)
        if p is None:
            p = self._pares[k] = _Par()
        return p

    def _quitar(self, par: _Par, i: int) -> None:
        pu = par.vivos.pop(i, None)
        if pu is not None:
            par.cuenta[pu] -= 1
            if not par.cuenta[pu]:
                del par.cuenta[pu]

    def _marcar_fallo(self, i: int, t: float, disparos: list) -> None:
        par_k, t_syn, puerto, estado = self._intento[i]
        if estado != "abierto":
            return
        self._intento[i] = (par_k, t_syn, puerto, "fallido")
        par = self._par(par_k)
        par.vivos[i] = puerto
        par.cuenta[puerto] = par.cuenta.get(puerto, 0) + 1
        heapq.heappush(par.por_syn, (t_syn, i))
        self._evaluar(par_k, par, t, disparos)

    def _expirar(self, par: _Par, t: float) -> None:
        lim = t - self.W
        while par.por_syn and par.por_syn[0][0] <= lim:
            self._quitar(par, heapq.heappop(par.por_syn)[1])
        while par.por_fin and par.por_fin[0][0] <= t:
            self._quitar(par, heapq.heappop(par.por_fin)[1])
        while par.intentos_ventana and par.intentos_ventana[0][0] <= lim:
            par.intentos_ventana.popleft()

    def _evaluar(self, par_k: tuple, par: _Par, t: float, disparos: list) -> None:
        self._expirar(par, t)
        n = len(par.cuenta)
        if n >= self.K and t - par.ultimo_disparo >= self.refractario_s:
            par.ultimo_disparo = t
            src, dst = par_k
            puertos = sorted(par.cuenta)
            ident = hashlib.sha256(("%s>%s|%.6f|%s" % (src, dst, t, VERSION)).encode()).hexdigest()[:16]
            disparos.append({
                "event": "senal_rapida", "regla": "port_scan_temprano", "version": VERSION,
                "id": ident, "origen": src, "destino": dst, "t_evidencia": round(t, 6),
                "puertos_fallidos": n, "muestra_puertos": puertos[:25],
                "intentos_en_ventana": len(par.intentos_ventana),
                "primer_intento_ventana": round(min(x[0] for x in par.intentos_ventana), 6)
                if par.intentos_ventana else None,
                "parametros": {"K": self.K, "W": self.W, "g": self.g},
            })

    # --- API ---------------------------------------------------------------------
    def avanzar(self, t: float) -> list[dict]:
        """Resuelve los vencimientos de g hasta t (sin paquetes nuevos). Devuelve disparos."""
        disparos: list[dict] = []
        while self._pendientes and self._pendientes[0][0] <= t:
            t_v, i = heapq.heappop(self._pendientes)
            if i in self._intento:
                self._marcar_fallo(i, t_v, disparos)
        if t > self.t:
            self.t = t
        return disparos

    def observar(self, t: float, src: str, dst: str, sport: int, dport: int, flags: int,
                 seq: int, iplen: int) -> list[dict]:
        """Incorpora un paquete TCP (en orden de marca). Devuelve los disparos que provoca."""
        disparos = self.avanzar(t)
        self.paquetes += 1
        kc = (src, dst, sport, dport, flags, seq, iplen)
        t0 = self._copias.get(kc)
        self._copias[kc] = t
        if t0 is not None and t - t0 < 0.005:
            self.copias_span += 1
            return disparos
        if flags & SYN and not flags & ACK:
            if src in self.excluidos or not self._dentro(src):
                return disparos
            k = (src, sport, dst, dport, seq)
            if k in self._vistos:
                self.retransmisiones += 1
                return disparos
            self._vistos[k] = t
            self._n += 1
            i = self._n
            par_k = (src, dst)
            self._intento[i] = (par_k, t, dport, "abierto")
            self._abiertos[(src, sport, dst, dport)] = (i,)
            heapq.heappush(self._pendientes, (t + self.g, i))
            par = self._par(par_k)
            par.intentos_ventana.append((t, dport))
            return disparos
        # respuesta del destino a un intento: viene de dst->src
        ab = self._abiertos.get((dst, dport, src, sport))
        if ab is None or ab[0] not in self._intento:
            return disparos
        i = ab[0]
        par_k, t_syn, puerto, estado = self._intento[i]
        if flags & SYN and flags & ACK:
            par = self._par(par_k)
            par.completados += 1
            if estado == "abierto":
                self._intento[i] = (par_k, t_syn, puerto, "completado")
            elif estado == "fallido":   # SA tardío: deja de contar desde ahora
                self._intento[i] = (par_k, t_syn, puerto, "completado")
                self._quitar(par, i)
        elif flags & RST and estado == "abierto":
            self._marcar_fallo(i, t, disparos)
        return disparos

    def podar(self, t: float, retencion_s: float = 120.0) -> None:
        """Higiene de memoria: olvida intentos y copias más viejos que la retención."""
        lim = t - retencion_s
        self._copias = {k: v for k, v in self._copias.items() if v >= t - 1.0}
        self._vistos = {k: v for k, v in self._vistos.items() if v >= lim}
        viejos = [i for i, x in self._intento.items() if x[1] < lim]
        for i in viejos:
            del self._intento[i]
        self._abiertos = {k: v for k, v in self._abiertos.items() if v[0] in self._intento}
        for k in [k for k, p in self._pares.items() if not p.vivos and (not p.intentos_ventana)
                  and p.ultimo_disparo < lim]:
            del self._pares[k]
