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

import collections
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
    """Mantiene el resultado de ``deduplicar_espejo`` sobre un anillo que cambia por los bordes."""

    def __init__(self, deduplicar: Callable) -> None:
        self._deduplicar = deduplicar
        self._clave: dict[int, tuple] = {}            # id(contexto) -> clave
        self._grupo: dict[tuple, dict[int, object]] = {}  # clave -> {id: contexto}
        self._descartadas: set[int] = set()            # id(contexto) descartados
        self._presentes: set[int] = set()

    def actualizar(self, utiles: list, orden_llegada: dict[int, int]) -> tuple[list, int]:
        """``utiles`` en el orden del anillo; devuelve (paquetes conservados en orden, descartados)."""
        actuales = {id(c): c for c in utiles}
        ids = set(actuales)
        nuevos = ids - self._presentes
        salientes = self._presentes - ids
        tocadas = set()
        for i in salientes:
            k = self._clave.pop(i)
            grupo = self._grupo[k]
            del grupo[i]
            if not grupo:
                del self._grupo[k]
            self._descartadas.discard(i)
            tocadas.add(k)
        for i in nuevos:
            c = actuales[i]
            k = clave_espejo(c)
            self._clave[i] = k
            self._grupo.setdefault(k, {})[i] = c
            tocadas.add(k)
        if tocadas:
            # Una sola llamada con todas las tramas de los grupos tocados: la
            # funcion congelada separa los grupos por su clave internamente.
            # Entrada en orden (timestamp, llegada), el mismo orden relativo que
            # tienen esas tramas dentro de la llamada global.
            lote = [c for k in tocadas if k in self._grupo for c in self._grupo[k].values()]
            lote.sort(key=lambda c: (c.packet.timestamp, orden_llegada[id(c)]))
            conservados, _ = self._deduplicar(lote)
            vivos = {id(p) for p in conservados}
            for c in lote:
                if id(c.packet) in vivos:
                    self._descartadas.discard(id(c))
                else:
                    self._descartadas.add(id(c))
        self._presentes = ids
        orden = sorted(utiles, key=lambda c: (c.packet.timestamp, orden_llegada[id(c)]))
        descartadas = self._descartadas
        return [c.packet for c in orden if id(c) not in descartadas], len(descartadas)


# --- Atribucion de flujos ----------------------------------------------------

class Atribuidor:
    """Mantiene el resultado de ``attribute_packets`` recalculando solo los flujos que cambian."""

    def __init__(self, atribuir: Callable, clave_flujo: Callable) -> None:
        self._atribuir = atribuir
        self._clave_flujo = clave_flujo
        self._flujo: dict[int, tuple] = {}                 # id(paquete) -> clave de flujo
        self._miembros: dict[tuple, dict[int, object]] = {}  # flujo -> {id: paquete}
        self._obs: dict[int, tuple] = {}                   # id(paquete) -> (paquete, observacion)
        self._presentes: set[int] = set()
        self.flujos_recalculados = 0
        self.paquetes_recalculados = 0

    def actualizar(self, paquetes: list, red, orden: Callable[[object], tuple]) -> list:
        """``paquetes`` ya en el orden de ``attribute_packets``; devuelve la misma lista de observaciones."""
        actuales = {id(p): p for p in paquetes}
        ids = set(actuales)
        nuevos = ids - self._presentes
        salientes = self._presentes - ids
        tocados = set()
        for i in salientes:
            f = self._flujo.pop(i)
            miembros = self._miembros[f]
            del miembros[i]
            if not miembros:
                del self._miembros[f]
            self._obs.pop(i, None)
            tocados.add(f)
        for i in nuevos:
            p = actuales[i]
            f = self._clave_flujo(p)
            self._flujo[i] = f
            self._miembros.setdefault(f, {})[i] = p
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
        self._presentes = ids
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
