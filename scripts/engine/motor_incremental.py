"""Procesamiento incremental del motor: mismas funciones congeladas, menos trabajo repetido.

El motor 7b275b8 recalcula en cada ciclo, sobre toda la historia de
``history_seconds`` (230 s en Sensor1), la deduplicacion del espejo, la
atribucion de flujos, la lectura de las observaciones L7 de eve.json y las
filas de TODAS las ventanas de TODAS las entidades, aunque casi todo sale igual
que en el ciclo anterior y casi todas las ventanas ya estan decididas. Con la
inundacion HTTP de la campana A (2026-10-29) eso llevo el ciclo a 45 s.

Este modulo NO reimplementa ninguna formula ni ninguna regla: llama a las
mismas funciones congeladas (``extract_multilayer_v2`` y
``extract_multilayer_v3``) con un subconjunto de la entrada, y solo cuando se
puede demostrar que el resultado coincide con el de la llamada global:

1. ``deduplicar_espejo`` decide cada trama mirando solo las tramas anteriores
   con su misma clave (``guardados`` y ``descartados`` se indexan por clave).
   Las claves son independientes: basta con volver a deduplicar las claves que
   ganaron o perdieron tramas en este ciclo y conservar las decisiones del
   resto.
2. ``attribute_packets`` lleva todo su estado por flujo canonico
   (propietario, inicio, secuencias vistas por sentido, que pertenecen a un
   unico flujo canonico). Un flujo cuya lista de paquetes no cambio produce
   las mismas observaciones; solo se vuelven a atribuir los flujos que
   ganaron o perdieron paquetes. El propietario es el mismo para todos los
   paquetes de un flujo, asi que un flujo esta entero dentro o entero fuera
   de la red de entidades.
3. ``load_app_observations`` trata cada linea por separado. Se aplica una vez
   a cada linea nueva de eve.json, en vez de a toda la historia en cada ciclo.
4. ``build_rows`` calcula la fila de la ventana W con las observaciones de la
   entidad en (W-30, W] (paquetes) y (W-60, W] (L7), el ``capture_start``
   global y el rango de anclas de la entidad (de su primera a su ultima
   observacion). Las ventanas anteriores a la primera ancla no puntuada de la
   entidad ya estan en ``scored_windows`` y el motor las salta. Se construyen
   solo las ventanas desde esa ancla, con las observaciones necesarias mas la
   primera y la ultima de la entidad (que fijan el mismo rango de anclas).

El orden del resultado global se reconstruye exactamente: la ordenacion
estable por timestamp de las funciones congeladas equivale a ordenar por
(timestamp, orden de llegada al anillo).
"""

from __future__ import annotations

import bisect
import collections
import heapq
import io
import math
from datetime import datetime, timezone
from typing import Callable, Iterable


# --- EVE ---------------------------------------------------------------------

class _LineaEnMemoria:
    """Objeto con ``open()`` como un Path, para pasar UNA linea a load_app_observations sin disco."""

    __slots__ = ("texto",)

    def __init__(self, texto: str) -> None:
        self.texto = texto

    def open(self, *_args, **_kwargs):
        return io.StringIO(self.texto)


def observaciones_de_linea(extractor, linea: str, red) -> list:
    """Observaciones L7 de una linea de eve.json con la funcion congelada.

    El motor original vuelca el buffer con ``raw_line + "\\n"`` y lo relee con
    ``load_app_observations``, que procesa cada linea por separado. Las lineas
    del buffer ya pasaron ``json.loads``, asi que no pueden contener saltos de
    linea crudos: cada una vuelve a ser exactamente una linea al releerla.
    """
    return extractor.load_app_observations(_LineaEnMemoria(linea + "\n"), red)


# --- Deduplicacion del espejo -----------------------------------------------

def clave_espejo(contexto) -> tuple:
    """Particion de las tramas para deduplicar por grupos.

    Son los mismos campos de la clave de ``deduplicar_espejo``. Si esa clave
    cambiara, esta particion seguiria siendo valida mientras no sea MAS FINA que
    la congelada (agrupar de mas solo cuesta tiempo; agrupar de menos rompería la
    equivalencia). La prueba de propiedad de tests/test_motor_incremental.py lo
    vigila con tramas que colisionan a proposito.
    """
    p = contexto.packet
    return (p.protocol, p.src_ip, p.dst_ip, p.src_port, p.dst_port, contexto.ip_id,
            p.ip_length, p.tcp_seq, p.icmp_type, p.icmp_id)


class Deduplicador:
    """Mantiene el resultado de ``deduplicar_espejo`` sobre un anillo que cambia por los bordes.

    Dos entradas con el mismo resultado:

    - ``actualizar(utiles)``: el conjunto completo; los cambios se obtienen por diferencia.
    - ``deslizar(corte, llegados)``: el horizonte solo avanza ([corte, ...]) y solo entran los
      contextos llegados desde la llamada anterior. Los que salen son el prefijo de los
      presentes con timestamp < corte (estan en orden (timestamp, llegada)). Evita recorrer
      todo el horizonte para saber que cambio (pendiente 2 de la Etapa 2).

    ``deslizar`` devuelve ademas que paquetes entran y salen del conjunto conservado (para
    ``Atribuidor.deslizar``), incluidos los que cambian de estado en los grupos tocados.
    """

    def __init__(self, deduplicar: Callable) -> None:
        self._deduplicar = deduplicar
        self._clave: dict[int, tuple] = {}            # id(contexto) -> clave
        self._grupo: dict[tuple, dict[int, object]] = {}  # clave -> {id: contexto}
        self._descartadas: set[int] = set()            # id(contexto) descartados
        self._presentes: set[int] = set()
        # Los presentes en orden (timestamp, llegada).
        self._orden: list = []

    def _aplicar(self, entran: list, salen: list, orden_llegada: dict[int, int]) -> tuple[list, list]:
        """Aplica los cambios; devuelve (paquetes que entran, paquetes que salen) del conjunto conservado."""
        def clave(c):
            return c.packet.timestamp, orden_llegada[id(c)]
        conservado_antes: dict[int, bool] = {}
        tocadas = set()
        sale_p, entra_p = [], []
        for c in salen:
            i = id(c)
            if i not in self._descartadas:
                sale_p.append(c.packet)
            k = self._clave.pop(i)
            grupo = self._grupo[k]
            del grupo[i]
            if not grupo:
                del self._grupo[k]
            self._descartadas.discard(i)
            self._presentes.discard(i)
            tocadas.add(k)
        nuevos = set()
        for c in entran:
            i = id(c)
            k = clave_espejo(c)
            self._clave[i] = k
            self._grupo.setdefault(k, {})[i] = c
            self._presentes.add(i)
            nuevos.add(i)
            tocadas.add(k)
        if tocadas:
            # Una sola llamada con todas las tramas de los grupos tocados: la
            # funcion congelada separa los grupos por su clave internamente.
            # Entrada en orden (timestamp, llegada), el mismo orden relativo que
            # tienen esas tramas dentro de la llamada global.
            lote = [c for k in tocadas if k in self._grupo for c in self._grupo[k].values()]
            lote.sort(key=clave)
            for c in lote:
                if id(c) not in nuevos:
                    conservado_antes[id(c)] = id(c) not in self._descartadas
            conservados, _ = self._deduplicar(lote)
            vivos = {id(p) for p in conservados}
            for c in lote:
                i = id(c)
                ahora = id(c.packet) in vivos
                if ahora:
                    self._descartadas.discard(i)
                else:
                    self._descartadas.add(i)
                antes = conservado_antes.get(i, False)
                if ahora and not antes:
                    entra_p.append(c.packet)
                elif antes and not ahora:
                    sale_p.append(c.packet)
        # Orden: quitar los que salen e intercalar los que entran (clave unica por contexto).
        if salen:
            fuera = {id(c) for c in salen}
            self._orden = [c for c in self._orden if id(c) not in fuera]
        if entran:
            nuevos_ord = sorted(entran, key=clave)
            if self._orden and clave(nuevos_ord[0]) < clave(self._orden[-1]):
                self._orden = list(heapq.merge(self._orden, nuevos_ord, key=clave))
            else:
                self._orden.extend(nuevos_ord)
        return entra_p, sale_p

    def _resultado(self) -> tuple[list, int]:
        descartadas = self._descartadas
        return [c.packet for c in self._orden if id(c) not in descartadas], len(descartadas)

    def actualizar(self, utiles: list, orden_llegada: dict[int, int]) -> tuple[list, int]:
        """``utiles`` en el orden del anillo; devuelve (paquetes conservados en orden, descartados)."""
        actuales = {id(c): c for c in utiles}
        ids = set(actuales)
        entran = [actuales[i] for i in ids - self._presentes]
        salen = [c for c in self._orden if id(c) not in ids]
        self._aplicar(entran, salen, orden_llegada)
        return self._resultado()

    def deslizar(self, corte: float, llegados: list, orden_llegada: dict[int, int]) -> tuple[list, int, list, list]:
        """Horizonte [corte, ...]: salen los presentes con timestamp < corte y entran los
        ``llegados`` con timestamp >= corte. Devuelve (conservados en orden, descartados,
        paquetes que entran, paquetes que salen del conjunto conservado)."""
        j = bisect.bisect_left(self._orden, corte, key=lambda c: c.packet.timestamp)
        salen = self._orden[:j]
        entran = [c for c in llegados if c.packet.timestamp >= corte and id(c) not in self._presentes]
        entra_p, sale_p = self._aplicar(entran, salen, orden_llegada)
        paq, n = self._resultado()
        return paq, n, entra_p, sale_p


# --- Atribucion de flujos ----------------------------------------------------

class Atribuidor:
    """Mantiene el resultado de ``attribute_packets`` recalculando solo los flujos que cambian.

    ``actualizar(paquetes)`` obtiene los cambios por diferencia de conjuntos;
    ``deslizar(paquetes, entran, salen)`` los recibe de ``Deduplicador.deslizar``.
    """

    def __init__(self, atribuir: Callable, clave_flujo: Callable) -> None:
        self._atribuir = atribuir
        self._clave_flujo = clave_flujo
        self._flujo: dict[int, tuple] = {}                 # id(paquete) -> clave de flujo
        self._miembros: dict[tuple, dict[int, object]] = {}  # flujo -> {id: paquete}
        self._obs: dict[int, tuple] = {}                   # id(paquete) -> (paquete, observacion)
        self._presentes: set[int] = set()
        self.flujos_recalculados = 0
        self.paquetes_recalculados = 0

    def _aplicar(self, entran: list, salen: list, red, orden: Callable[[object], tuple]) -> None:
        tocados = set()
        for p in salen:
            i = id(p)
            f = self._flujo.pop(i)
            miembros = self._miembros[f]
            del miembros[i]
            if not miembros:
                del self._miembros[f]
            self._obs.pop(i, None)
            self._presentes.discard(i)
            tocados.add(f)
        for p in entran:
            i = id(p)
            f = self._clave_flujo(p)
            self._flujo[i] = f
            self._miembros.setdefault(f, {})[i] = p
            self._presentes.add(i)
            tocados.add(f)
        self.flujos_recalculados = 0
        self.paquetes_recalculados = 0
        for f in tocados:
            miembros = self._miembros.get(f)
            if not miembros:
                continue
            lista = sorted(miembros.values(), key=orden)
            obs = self._atribuir(lista, red)
            self.flujos_recalculados += 1
            self.paquetes_recalculados += len(lista)
            if not obs:
                for p in lista:
                    self._obs.pop(id(p), None)
            elif len(obs) == len(lista):
                for p, o in zip(lista, obs):
                    self._obs[id(p)] = (p, o)
            else:  # imposible si el propietario es unico por flujo: se falla en voz alta
                raise RuntimeError(f"atribucion parcial de un flujo: {len(obs)} de {len(lista)} paquetes")

    def actualizar(self, paquetes: list, red, orden: Callable[[object], tuple]) -> list:
        """``paquetes`` ya en el orden de ``attribute_packets``; devuelve la misma lista de observaciones."""
        actuales = {id(p): p for p in paquetes}
        ids = set(actuales)
        entran = [actuales[i] for i in ids - self._presentes]
        salen = [self._miembros[self._flujo[i]][i] for i in self._presentes - ids]
        self._aplicar(entran, salen, red, orden)
        res = self._obs
        return [res[id(p)][1] for p in paquetes if id(p) in res]

    def deslizar(self, paquetes: list, entran: list, salen: list, red, orden: Callable[[object], tuple]) -> list:
        """Como ``actualizar`` con los cambios ya conocidos (``entran``/``salen`` del conjunto)."""
        self._aplicar(entran, salen, red, orden)
        res = self._obs
        return [res[id(p)][1] for p in paquetes if id(p) in res]


# --- Filas solo de las ventanas pendientes -----------------------------------

def clave_ventana(anchor: float) -> str:
    """window_end_utc tal como lo escribe build_rows."""
    return datetime.fromtimestamp(anchor, timezone.utc).isoformat()


def rango_anclas(timestamps: Iterable[float], paso: int) -> tuple[int, int]:
    """Primera y ultima ancla de una entidad, con la misma aritmetica que build_rows."""
    ts = list(timestamps)
    return (math.floor(min(ts) / paso) + 1) * paso, math.ceil(max(ts) / paso) * paso


def primera_ancla_no_puntuada(entidad: str, primera: int, ultima: int, paso: int,
                              puntuadas) -> int | None:
    ancla = primera
    while ancla <= ultima:
        if (entidad, clave_ventana(ancla)) not in puntuadas:
            return ancla
        ancla += paso
    return None


def anclas_sin_puntuar(entidad: str, lp: list, la: list, paso: int, puntuadas) -> list[int]:
    """Anclas del rango de una entidad excluida que el motor original marcaria (sin construir filas).

    El original construye todas sus filas y, para cada ventana no puntuada,
    suma una exclusion y la marca como puntuada. Solo usa la clave de la fila.
    """
    ts = [p.timestamp for p in lp] + [a.timestamp for a in la]
    primera, ultima = rango_anclas(ts, paso)
    a_min = primera_ancla_no_puntuada(entidad, primera, ultima, paso, puntuadas)
    if a_min is None:
        return []
    return [a for a in range(a_min, ultima + 1, paso) if (entidad, clave_ventana(a)) not in puntuadas]


def agrupar_por_entidad(paquetes: list, apps: list) -> tuple[dict, dict]:
    pp: dict[str, list] = collections.defaultdict(list)
    pa: dict[str, list] = collections.defaultdict(list)
    for p in paquetes:
        pp[p.entity_ip].append(p)
    for a in apps:
        pa[a.entity_ip].append(a)
    return pp, pa


def comprobar_equivalencia(extractor, v3, inicio_ciclo, utiles, sin_deduplicar, paquetes, packets, apps,
                           eve_buffer, ruta_volcado, red, paso, observation_timestamps, capture_epoch,
                           items, puntuadas, excluida, puntuar=None, feature_names=()) -> dict:
    """Recalcula el ciclo por la via global congelada (la del motor 7b275b8) y la compara con la incremental.

    Se llama ANTES del bucle de decisiones, con ``puntuadas`` (scored_windows)
    todavia intacto: «filas necesarias» son las filas globales cuya clave no
    esta puntuada, exactamente las que el bucle original habria tratado.
    """
    r: dict[str, object] = {"inicio_ciclo": inicio_ciclo}
    dif: list = []
    # 1. deduplicacion
    if sin_deduplicar:
        ref_paq = [pk.packet for pk in utiles]
        r["ok_dedup"] = True
    else:
        ref_paq, _ = v3.deduplicar_espejo(utiles)
        r["ok_dedup"] = len(ref_paq) == len(paquetes) and all(a is b for a, b in zip(ref_paq, paquetes))
    # 2. atribucion
    ref_obs = extractor.attribute_packets(ref_paq, red) if ref_paq else []
    r["ok_atribucion"] = ref_obs == packets
    # 3. EVE: el volcado y la relectura del original
    if eve_buffer:
        with ruta_volcado.open("w", encoding="utf-8") as fh:
            for _, linea, _ in eve_buffer:
                fh.write(linea + "\n")
        ref_apps = extractor.load_app_observations(ruta_volcado, red)
    else:
        ref_apps = []
    r["ok_eve"] = ref_apps == apps
    # 4. filas
    ref_ts = [x.timestamp for x in ref_obs] + [x.timestamp for x in ref_apps]
    ref_filas = (extractor.build_rows("motor-live", ref_obs, ref_apps, step_seconds=paso,
                                      capture_start=min(capture_epoch, min(ref_ts))) if ref_ts else [])
    por_ent: dict[str, list] = collections.defaultdict(list)
    for f in ref_filas:
        por_ent[f["entity_ip"]].append(f)
    ok_filas = ok_cob = True
    n_necesarias = n_cand = 0
    cand_por_ent: dict[str, tuple] = {}
    for it in items:
        if it[0] == "excluida":
            cand_por_ent[it[1]] = ("excluida", [clave_ventana(a) for a in it[2]])
        elif it[1]:
            cand_por_ent[it[1][0]["entity_ip"]] = ("filas", it[1])
    for ent in sorted(set(por_ent) | set(cand_por_ent)):
        ref = por_ent.get(ent, [])
        necesarias = [f["window_end_utc"] for f in ref if (ent, f["window_end_utc"]) not in puntuadas]
        n_necesarias += len(necesarias)
        tipo, cand = cand_por_ent.get(ent, ("filas", []))
        if tipo == "excluida" or excluida(ent):
            claves = cand if tipo == "excluida" else []
            n_cand += len(claves)
            if claves != necesarias:
                ok_cob = False
                dif.append({"entidad": ent, "tipo": "excluida", "necesarias": necesarias[:4], "cand": claves[:4]})
            continue
        n_cand += len(cand)
        if cand:
            esperado = [f for f in ref if f["window_end_utc"] >= cand[0]["window_end_utc"]]
            if cand != esperado:
                ok_filas = False
                dif.append({"entidad": ent, "tipo": "filas", "n_cand": len(cand), "n_ref": len(esperado)})
        claves_cand = {f["window_end_utc"] for f in cand}
        faltan = [w for w in necesarias if w not in claves_cand]
        if faltan:
            ok_cob = False
            dif.append({"entidad": ent, "tipo": "cobertura", "faltan": faltan[:4]})
    r.update({"ok_filas": ok_filas, "ok_cobertura": ok_cob, "filas_globales": len(ref_filas),
              "filas_necesarias": n_necesarias, "filas_candidatas": n_cand,
              "paquetes": len(ref_paq), "observaciones": len(ref_obs), "observaciones_l7": len(ref_apps)})
    # 5. puntuacion por lotes frente a una llamada por fila
    if puntuar is not None:
        filas = [f for it in items if it[0] == "filas" for f in it[1]
                 if f["packet_count_10s"] != 0 and (f["entity_ip"], f["window_end_utc"]) not in puntuadas]
        if filas:
            X = [[float(f[n]) for n in feature_names] for f in filas]
            lote = [float(v) for v in puntuar(X)]
            una = [float(puntuar([x])[0]) for x in X]
            r["ok_puntuacion_lote"] = lote == una
            r["puntuadas"] = len(filas)
        else:
            r["ok_puntuacion_lote"] = True
            r["puntuadas"] = 0
    r["ok"] = all(v for k, v in r.items() if k.startswith("ok_"))
    if dif:
        r["diferencias"] = dif[:6]
    return r


def filas_pendientes(build_rows: Callable, entidad: str, lp: list, la: list, paso: int,
                     capture_start: float, puntuadas) -> tuple[list, int | None]:
    """Filas de ``entidad`` desde su primera ancla no puntuada, identicas a las de la llamada global.

    Devuelve (filas, ancla minima). Sin anclas pendientes devuelve ([], None).
    """
    ts = [p.timestamp for p in lp] + [a.timestamp for a in la]
    primera, ultima = rango_anclas(ts, paso)
    a_min = primera_ancla_no_puntuada(entidad, primera, ultima, paso, puntuadas)
    if a_min is None:
        return [], None
    if a_min == primera:
        rp, ra = lp, la
    else:
        t_lo, t_hi = min(ts), max(ts)
        # La primera y la ultima observacion fijan el mismo rango de anclas;
        # quedan fuera de toda ventana >= a_min salvo que ya entren por tiempo.
        rp = [p for p in lp if p.timestamp > a_min - 30 or p.timestamp == t_lo or p.timestamp == t_hi]
        ra = [a for a in la if a.timestamp > a_min - 60 or a.timestamp == t_lo or a.timestamp == t_hi]
    filas = build_rows("motor-live", rp, ra, step_seconds=paso, capture_start=capture_start)
    corte = clave_ventana(a_min)
    # window_end_utc en ISO con el mismo formato y zona: el orden de texto es el de tiempo.
    return [f for f in filas if f["window_end_utc"] >= corte], a_min


# --- Horizonte de entrada fijado por ventana (Etapa 2, cierre) -----------------
#
# Hasta 2be5335 el anillo se podaba a ``history_seconds`` desde el paquete MAS
# NUEVO leido. El inicio de cada flujo, su propietario, si un paquete cuenta
# como ``flow_attempt`` y las secuencias ya vistas los fija ``attribute_packets``
# sobre el conjunto que recibe, asi que la fila de una ventana dependia de
# CUANDO se decidia (rotacion de 5 o 15 s, disponibilidad, retraso): r2 frente a
# r4 dio 215 vectores distintos. Ahora la ventana W se calcula siempre con la
# entrada [W - history_seconds, ...]: misma funcion congelada, misma formula, un
# horizonte que solo depende de W. ``attribute_packets`` es causal (procesa por
# timestamp y solo mira atras), asi que los paquetes posteriores a W que ya
# esten en el buffer no cambian ninguna observacion de (W-60, W].

MARGEN_DEDUP_S = 0.005  # ventana de deduplicar_espejo: la copia de W puede llegar 5 ms despues
# Una ventana (E, A) se registra si E tiene algun paquete o evento L7 en (A-60, A]. Los
# paquetes de (A-60, A-30] no entran en ningun conteo de A (p10/p30): solo hacen que se
# registre la ventana que sigue al ultimo paquete (vacia en 10/30 s, PERMIT), como hacia
# el motor en vivo, y que los analisis que exigen la rejilla hasta fin+60 la encuentren.
REGISTRO_S = 60


def anclas_con_contenido(ts_paquetes: Iterable[float], ts_apps: Iterable[float], paso: int,
                         desde_excl: float, hasta_incl: float) -> list[int]:
    """Anclas A en (desde, hasta] con algun paquete o evento L7 en (A-60, A] (REGISTRO_S).

    Son las ventanas registrables: con contenido en 10/30/60 s, o vacias en 10/30 s pero
    con paquetes de la entidad en los 60 s previos. Las demas no se generan.
    """
    k = set()
    for t in ts_paquetes:
        if t > desde_excl - REGISTRO_S:
            k.add((math.ceil(t / paso), REGISTRO_S))
    for t in ts_apps:
        if t > desde_excl - 60:
            k.add((math.ceil(t / paso), 60))
    anclas = set()
    for c, w in k:
        # t en (A-w, A]  <=>  A en [t, t+w): con A = c*paso >= t, las anclas c..c+w/paso-1
        # cubren [t, t+w) salvo cuando t cae justo en la reticula (entonces c*paso == t).
        for j in range(w // paso):
            a = (c + j) * paso
            if desde_excl < a <= hasta_incl:
                anclas.add(a)
    return sorted(anclas)


def con_contenido(lp: list, la: list, ancla: float) -> bool:
    """Ventana registrable (ver REGISTRO_S)."""
    return (any(ancla - REGISTRO_S < p.timestamp <= ancla for p in lp)
            or any(ancla - 60 < a.timestamp <= ancla for a in la))


def registro_cancelacion(window_key: tuple[str, str], ancla: float, corte: float, packets: list, apps: list,
                         visto: float, origen: dict, inicio_ciclo: float, ahora: float) -> dict:
    """Registro de una pendiente cancelada: la entidad no tiene contenido en (A-60, A] con el
    horizonte propio de la ventana. Deja la evidencia (horizontes, observaciones y a que
    entidades atribuye ese horizonte los paquetes de/hacia la entidad en (A-60, A])."""
    ent = window_key[0]
    propietarios: dict[str, int] = collections.Counter(
        x.entity_ip for x in packets
        if ancla - REGISTRO_S < x.timestamp <= ancla and x.peer_ip == ent and x.entity_ip != ent)
    return {
        "event": "pendiente_cancelada",
        "motivo": "sin_contenido_en_su_horizonte",
        "decidido_en": ahora,
        "entity_ip": ent,
        "window_end_utc": window_key[1],
        "pendiente_desde": visto,
        "corte_incorporacion": origen.get("corte_incorporacion"),
        "obs_pcap_incorporacion": origen.get("obs_pcap_incorporacion"),
        "obs_eve_incorporacion": origen.get("obs_eve_incorporacion"),
        "corte_propio": corte,
        "obs_pcap_propio": sum(1 for x in packets
                               if x.entity_ip == ent and ancla - REGISTRO_S < x.timestamp <= ancla),
        "obs_eve_propio": sum(1 for x in apps if x.entity_ip == ent and ancla - 60 < x.timestamp <= ancla),
        "paquetes_atribuidos_a": dict(sorted(propietarios.items())),
        "inicio_ciclo": inicio_ciclo,
    }


def fila_de_ancla(build_rows: Callable, lp: list, la: list, ancla: int, paso: int,
                  capture_start: float, reemplazar: Callable, primera=None,
                  buscar_anterior: Callable | None = None) -> dict | None:
    """La fila de ``build_rows`` para la ventana que termina en ``ancla``, o None si no existe.

    La ventana es registrable si la entidad tiene paquetes o L7 en (A-60, A] (REGISTRO_S).
    La fila A de ``build_rows`` solo lee los paquetes de (A-30, A] (p10 y p30), los
    eventos L7 de (A-60, A], la ancla y ``capture_start``: el resto de observaciones solo
    fija el rango de anclas que ``build_rows`` recorre. Por eso se le pasan solo esas, en
    su orden (mismos conteos, mismas sumas y mismo orden de flujos que la llamada global).

    Rango de anclas: la global sobre el horizonte genera A si la observacion mas antigua
    de la entidad (``primera``) es anterior a A. Si ninguna de las pasadas lo es, se
    antepone una copia de ``primera`` con marca A-30 (paquete) o A-60 (L7): fuera de
    todo conteo de A (las ventanas son (A-w, A]) y no anterior a ``capture_start``. Si
    ninguna llega a (A-paso, A], se anade una copia de la ultima con marca A+paso/2, que
    solo extiende el rango. Asi ``build_rows`` recorre a lo sumo las anclas de (A-60, A]
    en lugar de todas las del horizonte (hasta 23 con 230 s), con listas de 30 s y no de
    60 s: la fila A es identica (``tests/test_motor_incremental.py``).
    """
    if not any(ancla - REGISTRO_S < p.timestamp <= ancla for p in lp) and \
            not any(ancla - 60 < a.timestamp <= ancla for a in la):
        return None
    # ``base``: una observacion de la entidad anterior a A en su horizonte, si existe.
    # ``primera`` (la mas antigua del horizonte) o, en el motor, la mas antigua de
    # (A-60, A] y, solo si todo cae justo en A, ``buscar_anterior()`` sobre el horizonte.
    base = primera
    if base is None:
        base = min((x for x in list(lp) + list(la) if ancla - REGISTRO_S < x.timestamp <= ancla),
                   key=lambda x: x.timestamp)
        if base.timestamp >= ancla and buscar_anterior is not None:
            base = buscar_anterior() or base
    if base.timestamp >= ancla:
        return None  # la global empieza su rango en A+paso: no hay ventana A
    rp = [p for p in lp if ancla - 30 < p.timestamp <= ancla]
    ra = [a for a in la if ancla - 60 < a.timestamp <= ancla]
    if min((x.timestamp for x in rp + ra), default=math.inf) >= ancla:
        if hasattr(base, "kind"):
            ra = [reemplazar(base, timestamp=ancla - 60)] + ra
        else:
            rp = [reemplazar(base, timestamp=ancla - 30)] + rp
    ultima_p = max(rp, key=lambda x: x.timestamp) if rp else None
    ultima_a = max(ra, key=lambda x: x.timestamp) if ra else None
    t_max = max(x.timestamp for x in (ultima_p, ultima_a) if x is not None)
    if t_max <= ancla - paso:
        if ultima_p is not None:
            rp = rp + [reemplazar(ultima_p, timestamp=ancla + paso / 2)]
        else:
            ra = ra + [reemplazar(ultima_a, timestamp=ancla + paso / 2)]
    clave = clave_ventana(ancla)
    for f in build_rows("motor-live", rp, ra, step_seconds=paso, capture_start=capture_start):
        if f["window_end_utc"] == clave:
            return f
    raise RuntimeError("build_rows no genero la ventana %s" % clave)


def comprobar_ancla(extractor, v3, ancla, horizonte, utiles, sin_deduplicar, paquetes, packets, apps,
                    lineas_eve, ruta_volcado, red, paso, capture_start, filas, excluidas,
                    puntuar=None, feature_names=()) -> dict:
    """Recalcula la ventana ``ancla`` por la via global congelada y la compara con la incremental.

    Referencia: deduplicar_espejo + attribute_packets sobre TODO el horizonte del
    buffer, load_app_observations sobre el volcado de sus lineas EVE y build_rows
    sobre TODAS las observaciones de la entidad en el horizonte (con la misma
    extension de rango si la entidad no llega a la ancla). ``filas`` es
    {"filas": {entidad: fila}, "excluidas": {entidad, ...}}.
    """
    from dataclasses import replace
    r: dict[str, object] = {"ancla": clave_ventana(ancla), "horizonte_s": horizonte}
    if sin_deduplicar:
        ref_paq = [pk.packet for pk in utiles]
        r["ok_dedup"] = True
    else:
        ref_paq, _ = v3.deduplicar_espejo(utiles)
        r["ok_dedup"] = len(ref_paq) == len(paquetes) and all(a is b for a, b in zip(ref_paq, paquetes))
    ref_obs = extractor.attribute_packets(ref_paq, red) if ref_paq else []
    r["ok_atribucion"] = ref_obs == packets
    if lineas_eve:
        with ruta_volcado.open("w", encoding="utf-8") as fh:
            for linea in lineas_eve:
                fh.write(linea + "\n")
        ref_apps = extractor.load_app_observations(ruta_volcado, red)
    else:
        ref_apps = []
    r["ok_eve"] = ref_apps == apps
    pp, pa = agrupar_por_entidad(ref_obs, ref_apps)
    ok_filas = ok_cob = True
    n_ref = 0
    dif = []
    for ent in sorted(set(pp) | set(pa)):
        lp, la = pp.get(ent, []), pa.get(ent, [])
        if not con_contenido(lp, la, ancla):
            continue
        n_ref += 1
        if excluidas(ent):
            if ent not in filas.get("excluidas", ()):
                ok_cob = False
                dif.append({"entidad": ent, "tipo": "excluida"})
            continue
        rp, ra = list(lp), list(la)
        if max(x.timestamp for x in rp + ra) <= ancla - paso:
            ult = max(rp + ra, key=lambda x: x.timestamp)
            (rp if any(ult is x for x in rp) else ra).append(replace(ult, timestamp=ancla + paso / 2))
        ref = [f for f in extractor.build_rows("motor-live", rp, ra, step_seconds=paso,
                                               capture_start=capture_start)
               if f["window_end_utc"] == clave_ventana(ancla)]
        cand = filas.get("filas", {}).get(ent)
        if not ref:
            n_ref -= 1
            if cand is not None:
                ok_cob = False
                dif.append({"entidad": ent, "tipo": "cobertura", "ref": False, "cand": True})
            continue
        if cand is None:
            ok_cob = False
            dif.append({"entidad": ent, "tipo": "cobertura", "ref": bool(ref), "cand": cand is not None})
        elif ref[0] != cand:
            ok_filas = False
            dif.append({"entidad": ent, "tipo": "filas",
                        "distintas": sorted(k for k in ref[0] if ref[0][k] != cand.get(k))[:6]})
    n_cand = len(filas.get("filas", {})) + len(filas.get("excluidas", ()))
    if n_cand != n_ref:
        ok_cob = False
    r.update({"ok_filas": ok_filas, "ok_cobertura": ok_cob, "entidades_ref": n_ref, "entidades_cand": n_cand,
              "paquetes": len(ref_paq), "observaciones": len(ref_obs), "observaciones_l7": len(ref_apps)})
    if puntuar is not None:
        lista = [f for f in filas.get("filas", {}).values() if f["packet_count_10s"] != 0]
        if lista:
            X = [[float(f[n]) for n in feature_names] for f in lista]
            r["ok_puntuacion_lote"] = [float(v) for v in puntuar(X)] == [float(puntuar([x])[0]) for x in X]
        else:
            r["ok_puntuacion_lote"] = True
    r["ok"] = all(v for k, v in r.items() if k.startswith("ok_"))
    if dif:
        r["diferencias"] = dif[:6]
    return r
