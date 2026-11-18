"""Cadena de respuesta v2 tal como la puede ver el panel del sensor (solo lectura).

Etapa 4A (4-nov-2026). Con el motor ec78ca5 y el publicador v2 (``--politica if_senal``)
la acción ya no se deduce de la decisión: la publica (o no) el publicador y deja traza.
Este módulo NO recalcula ninguna política. Indexa por ``decision_id`` lo que dejaron
las fuentes reales y dice, para cada decisión, en qué punto de la cadena está:

1. ``if``          señal del Isolation Forest (``senales-if.jsonl``): señal | sin_senal | sin_puntuar |
                   desconocido
2. ``regla``       regla heurística del propio registro del motor (``heuristicos``/``heuristico``)
3. ``decision``    decisión desplegada por el motor (ALERT/PERMIT), tal cual
4. ``medida``      lo que hizo el publicador v2 (``traza.jsonl``, campo ``nuevos``):
                   nueva | renovada | escalada | mantenida (publicadas) |
                   rechazada | sin_punto_de_aplicacion | no_publicada | desconocido
5. ``agente``      recepción/evaluación en el host: el sensor no tiene canal con la traza
                   del agente v2 -> «desconocido» (nunca se supone)
6. ``aplicacion``  en modo sombra: «no_ejecutada»; en otro modo sin evidencia: «desconocido»
7. ``efecto``      observado en el host: «sin_evidencia» (el sensor no lo mide)

Reglas de honestidad (requisito de la 4A):
- Una anomalía del IF NO es una medida: solo hay acción si el publicador la publicó.
- Si una fuente falta o no cubre la decisión, el estado es «desconocido», no «no».
- En sombra, una medida publicada es una PROPUESTA y su aplicación «no ejecutada».

Cierre complementario de la 4A (4-nov-2026): cobertura temporal DEMOSTRADA.
El publicador v2 lee el registro del motor cada ``--sondeo-segundos`` y escribe en la misma
iteración las señales (``senales-if.jsonl``, solo las que superan algún α) y, si toca, una
publicación en ``traza.jsonl`` (como mínimo cada ``--refresco-segundos`` = 20 s). Ninguno de los
dos ficheros declara hasta dónde leyó, así que la única cobertura demostrable es la de la traza:
de su primera publicación leída a la última (menos ``MARGEN_LECTURA_S``) y sin huecos de más de
``HUECO_TRAZA_S`` entre publicaciones consecutivas. La ausencia de un ``decision_id`` solo es
«sin señal» / «sin medida publicada» dentro de esa cobertura. Fuera de ella:
- posterior a la última publicación y traza fresca  -> ``pendiente`` (procesamiento pendiente);
- posterior a la última publicación y traza vieja    -> ``fuente_desactualizada``;
- fichero ausente o ilegible                         -> ``fuente_ausente``;
- anterior a la traza leída o en un hueco            -> ``desconocido``.
La aplicación es «no aplica» solo con ausencia de medida DEMOSTRADA (no publicada dentro de la
cobertura, rechazada o sin punto de aplicación); con medida desconocida, «desconocido».
El IF se muestra con dos fuentes que no se mezclan: ``if_motor`` (``decision_if`` y ``score`` del
propio registro del motor, umbral desplegado) e ``if`` (señal α de ``senales-if.jsonl``).
"""
from __future__ import annotations

import json
import threading
import time
from pathlib import Path

MEDIDAS_PUBLICADAS = ("nueva", "renovada", "escalada", "mantenida")
MEDIDAS_SIN_EFECTO = ("rechazada", "sin_punto_de_aplicacion")
SEVERIDAD = {"BLOCK": 2, "LIMIT": 1}
COLA_BYTES = 8 * 1024 * 1024          # cola leída de cada jsonl (las trazas crecen)
FUENTE_VIEJA_S = 60                   # el publicador escribe cada 10 s
REFRESCO_PUBLICADOR_S = 20.0          # --refresco-segundos del publicador v2 desplegado
HUECO_TRAZA_S = REFRESCO_PUBLICADOR_S + 10.0   # más separación entre publicaciones = hueco
TRAZA_FRESCA_S = REFRESCO_PUBLICADOR_S + 10.0  # última publicación más vieja = desactualizada
MARGEN_LECTURA_S = 2.0                # logged_at se fija antes de escribir la línea

# Cobertura de una decisión (resultado de IndiceV2.cobertura)
CUBIERTA, PENDIENTE, DESACTUALIZADA, AUSENTE, FUERA = (
    "cubierta", "pendiente", "fuente_desactualizada", "fuente_ausente", "desconocido")
SIN_MEDIDA_DEMOSTRADA = ("no_publicada",) + MEDIDAS_SIN_EFECTO

ETIQUETA_MEDIDA = {
    "nueva": "medida publicada (nueva)",
    "renovada": "medida publicada (renovada)",
    "escalada": "medida publicada (escalada)",
    "mantenida": "medida vigente mantenida",
    "rechazada": "regla rechazada por el publicador (sin efecto)",
    "sin_punto_de_aplicacion": "sin punto de aplicación (no se restringe)",
    "no_publicada": "sin medida publicada",
    "pendiente": "pendiente (posterior a la última publicación del publicador v2)",
    "fuente_desactualizada": "desconocido (la traza v2 está desactualizada)",
    "fuente_ausente": "desconocido (traza v2 ausente o ilegible)",
    "desconocido": "desconocido (la traza v2 no cubre esta decisión)",
}


def _cola_jsonl(ruta: Path, max_bytes: int = COLA_BYTES) -> list[dict]:
    with open(ruta, "rb") as fh:
        fh.seek(0, 2)
        tam = fh.tell()
        fh.seek(max(0, tam - max_bytes))
        datos = fh.read()
    if tam > max_bytes:
        datos = datos[datos.find(b"\n") + 1:]        # primera línea probablemente cortada
    out = []
    for linea in datos.splitlines():
        try:
            d = json.loads(linea)
        except ValueError:
            continue
        if isinstance(d, dict):
            out.append(d)
    return out


def _sello(ruta: Path):
    try:
        st = ruta.stat()
        return (st.st_mtime_ns, st.st_size)
    except OSError:
        return None


def reglas_de(d: dict) -> list[dict]:
    """Reglas heurísticas que el propio motor registró en la decisión (sin interpretar)."""
    lista = d.get("heuristicos")
    if not isinstance(lista, list):
        h = d.get("heuristico")
        lista = [h] if isinstance(h, dict) else []
    out = [{"regla": str(h.get("heuristico", "regla")), "accion": h.get("accion"),
            "motivo": str(h.get("motivo", ""))} for h in lista if isinstance(h, dict)]
    det = str(d.get("detector_name", ""))
    if d.get("decision") == "ALERT" and det.endswith("_heuristic"):
        out.append({"regla": det, "accion": "BLOCK", "motivo": det})
    return out


class IndiceV2:
    """Índice de las fuentes v2 por decision_id. Se recarga solo cuando cambian los ficheros.

    Si el directorio o sus ficheros faltan (al arrancar o durante la ejecución) el índice
    sigue existiendo: el panel conserva el modo v2 y lo declara como incidencia. Nunca se
    vuelve a la política v1 del panel por un fallo de las fuentes v2.
    """

    def __init__(self, directorio: Path, modo_respuesta: str = "sombra"):
        self.dir = Path(directorio)
        self.modo = modo_respuesta
        self._lock = threading.Lock()
        self._sellos: dict | None = None
        self.senales: dict[str, dict] = {}
        self.medidas: dict[str, list[dict]] = {}
        self.publicaciones = 0
        self.traza_desde: float | None = None
        self.traza_hasta: float | None = None
        self.huecos: list[tuple[float, float]] = []
        self.senales_desde: float | None = None
        self.politica: str | None = None
        self.feed: dict | None = None
        self.fuentes: dict[str, dict] = {}

    # ------------------------------------------------------------ carga
    def refrescar(self) -> None:
        rutas = {"senales_if": self.dir / "senales-if.jsonl", "traza": self.dir / "traza.jsonl",
                 "feed": self.dir / "feed.json"}
        sellos = {k: _sello(r) for k, r in rutas.items()}
        with self._lock:
            if sellos == self._sellos:
                return
            self._sellos = sellos
            self.fuentes = {}
            # 1) señales del IF
            senales: dict[str, dict] = {}
            desde = None
            try:
                for s in _cola_jsonl(rutas["senales_if"]):
                    if s.get("decision_id"):
                        senales[str(s["decision_id"])] = s
                        t = s.get("logged_at")
                        if isinstance(t, (int, float)) and (desde is None or t < desde):
                            desde = float(t)
                self.fuentes["senales_if"] = {"ok": True, "lineas": len(senales)}
            except OSError as exc:
                self.fuentes["senales_if"] = {"ok": False, "motivo": type(exc).__name__}
            self.senales, self.senales_desde = senales, desde
            # 2) traza del publicador
            medidas: dict[str, list[dict]] = {}
            tiempos: list[float] = []
            n = 0
            politica = None
            try:
                for p in _cola_jsonl(rutas["traza"]):
                    if p.get("evento") != "publicacion":
                        continue
                    n += 1
                    politica = p.get("politica", politica)
                    tp = p.get("publicado_en", p.get("generado"))
                    if isinstance(tp, (int, float)):
                        tiempos.append(float(tp))
                    for x in p.get("nuevos") or []:
                        if not isinstance(x, dict):
                            continue
                        clave = str(x.get("decision_id") or str(x.get("evento_id", "")).rsplit("|", 1)[0])
                        medidas.setdefault(clave, []).append(dict(x, secuencia=p.get("secuencia"),
                                                                  publicado_en=tp))
                self.fuentes["traza"] = {"ok": True, "publicaciones": n}
                if not tiempos:
                    self.fuentes["traza"] = {"ok": False, "motivo": "sin publicaciones legibles"}
            except OSError as exc:
                self.fuentes["traza"] = {"ok": False, "motivo": type(exc).__name__}
            tiempos.sort()
            self.medidas, self.publicaciones = medidas, n
            self.traza_desde = tiempos[0] if tiempos else None
            self.traza_hasta = tiempos[-1] if tiempos else None
            self.huecos = [(a, b) for a, b in zip(tiempos, tiempos[1:]) if b - a > HUECO_TRAZA_S]
            self.politica = politica
            # 3) feed v2 vigente
            try:
                self.feed = json.loads(rutas["feed"].read_text(encoding="utf-8"))
                self.fuentes["feed"] = {"ok": isinstance(self.feed, dict)}
                if not isinstance(self.feed, dict):
                    self.feed = None
            except (OSError, ValueError) as exc:
                self.feed = None
                self.fuentes["feed"] = {"ok": False, "motivo": type(exc).__name__}

    # ------------------------------------------------------------ cobertura
    def _ok(self, fuente: str) -> bool:
        return bool(self.fuentes.get(fuente, {}).get("ok"))

    def traza_fresca(self, ahora: float) -> bool:
        return self.traza_hasta is not None and ahora - self.traza_hasta <= TRAZA_FRESCA_S

    def cobertura(self, t: float | None, ahora: float) -> str:
        """Si la traza leída DEMUESTRA que el publicador procesó el instante t."""
        if not self._ok("traza"):
            return AUSENTE
        if t is None or self.traza_desde is None or self.traza_hasta is None or t < self.traza_desde:
            return FUERA
        if t > self.traza_hasta - MARGEN_LECTURA_S:
            return PENDIENTE if self.traza_fresca(ahora) else DESACTUALIZADA
        if any(a < t < b for a, b in self.huecos):
            return FUERA
        return CUBIERTA

    # ------------------------------------------------------------ por decisión
    def _cubre(self, t: float | None) -> bool:
        """Compatibilidad: la traza leída demuestra el procesamiento del instante t."""
        return self.cobertura(t, t if t is not None else 0.0) == CUBIERTA

    def cadena(self, d: dict, ahora: float | None = None) -> dict:
        ahora = time.time() if ahora is None else ahora
        did = d.get("decision_id") or "%s|%s" % (d.get("entity_ip"), d.get("window_end_utc"))
        t = d.get("logged_at") if isinstance(d.get("logged_at"), (int, float)) else None
        cob = self.cobertura(t, ahora)
        # 1a) IF según el propio motor (fuente explícita, no es la señal α del publicador)
        if_motor = {"fuente": "registro del motor (decision_if)", "decision_if": d.get("decision_if"),
                    "score": d.get("score"), "umbral": d.get("threshold")}
        # 1b) señal α publicada (senales-if.jsonl)
        s = self.senales.get(did)
        if s is not None:
            senal_if = {"estado": "senal", "score": s.get("score"),
                        "alfa_superados": s.get("alfa_superados") or []}
        elif d.get("score") is None:
            # Sin score el publicador no emite señal por construcción (senal_if() -> None).
            senal_if = {"estado": "sin_puntuar", "motivo": "el motor no puntuó la ventana (sin score)"}
        elif not self._ok("senales_if"):
            senal_if = {"estado": AUSENTE, "motivo": "senales-if.jsonl ausente o ilegible: "
                        + str(self.fuentes.get("senales_if", {}).get("motivo", "?"))}
        elif cob == CUBIERTA:
            senal_if = {"estado": "sin_senal", "motivo": "procesada por el publicador sin superar ningún α"}
        elif cob == AUSENTE:
            senal_if = {"estado": "desconocido", "motivo": "cobertura no demostrada: traza v2 ausente o ilegible"}
        else:
            senal_if = {"estado": cob, "motivo": _MOTIVO_COBERTURA[cob]}
        senal_if["fuente"] = "senales-if.jsonl"
        # 4) medida publicada
        items = self.medidas.get(did, [])
        if items:
            pub = [x for x in items if x.get("tipo") in MEDIDAS_PUBLICADAS]
            if pub:
                m = max(pub, key=lambda x: SEVERIDAD.get(str(x.get("accion")), 0))
                medida = {"estado": m.get("tipo"), "accion": m.get("accion"), "regla": m.get("regla"),
                          "id": m.get("id"), "hasta": m.get("hasta"), "secuencia": m.get("secuencia"),
                          "publicado_en": m.get("publicado_en"), "destino": m.get("destino")}
            else:
                m = items[-1]
                medida = {"estado": m.get("tipo"), "accion": None, "regla": m.get("regla"),
                          "motivo": m.get("motivo_rechazo") or m.get("objetivo"),
                          "secuencia": m.get("secuencia"), "publicado_en": m.get("publicado_en")}
        elif cob == CUBIERTA:
            medida = {"estado": "no_publicada", "accion": None}
        else:
            medida = {"estado": cob, "accion": None, "motivo": _MOTIVO_COBERTURA[cob]}
        publicada = medida["estado"] in MEDIDAS_PUBLICADAS
        if publicada:
            aplicacion = "no_ejecutada" if self.modo == "sombra" else "desconocido"
        elif medida["estado"] in SIN_MEDIDA_DEMOSTRADA:
            aplicacion = "no_aplica"
        else:
            aplicacion = "desconocido"
        return {
            "decision_id": did,
            "if_motor": if_motor,
            "if": senal_if,
            "reglas": reglas_de(d),
            "decision": d.get("decision"),
            "medida": medida,
            "cobertura": cob,
            "propuesta": publicada and self.modo == "sombra",
            "agente": "desconocido",
            "aplicacion": aplicacion,
            "efecto": "sin_evidencia",
            "modo": self.modo,
        }

    def anotar(self, decisiones: list[dict], ahora: float | None = None) -> None:
        self.refrescar()
        ahora = time.time() if ahora is None else ahora
        for d in decisiones:
            d["cadena_v2"] = self.cadena(d, ahora)

    # ------------------------------------------------------------ vistas
    def vigentes(self, ahora: float) -> list[dict]:
        """Medidas del feed v2 firmado con caducidad futura (en sombra: propuestas)."""
        self.refrescar()
        out = []
        for e in (self.feed or {}).get("entradas") or []:
            if not isinstance(e, dict) or not e.get("ip"):
                continue
            hasta = float(e.get("hasta") or 0)
            if hasta <= ahora:
                continue
            out.append({"ip": e["ip"], "accion": e.get("accion"), "motivo": e.get("motivo", ""),
                        "origen": e.get("detector", ""), "nivel": e.get("nivel"), "hasta": hasta,
                        "revisar_humano": bool(e.get("revisar_humano")), "fuente": "feed_v2",
                        "evento_id": e.get("evento_id"), "id": e.get("id"), "destino": e.get("destino"),
                        "publicada": True, "registrada": True,
                        "estado_respuesta": "propuesta (sombra)" if self.modo == "sombra" else "publicada",
                        "aplicacion": "no_ejecutada" if self.modo == "sombra" else "desconocido",
                        "expira_s": max(0, int(hasta - ahora))})
        out.sort(key=lambda v: (-SEVERIDAD.get(str(v["accion"]), 0), -v["hasta"]))
        return out

    def incidencias(self, ahora: float) -> list[str]:
        """Problemas de las fuentes v2, en palabras: el panel los muestra, no los oculta."""
        out = []
        if not self.dir.is_dir():
            out.append("directorio %s ausente" % self.dir)
        nombres = {"senales_if": "senales-if.jsonl", "traza": "traza.jsonl", "feed": "feed.json"}
        for k, nombre in nombres.items():
            f = self.fuentes.get(k, {})
            if not f.get("ok"):
                out.append("%s ausente o ilegible (%s)" % (nombre, f.get("motivo", "?")))
        if self._ok("traza") and not self.traza_fresca(ahora):
            out.append("traza v2 desactualizada: última publicación hace %d s" % int(ahora - self.traza_hasta))
        f = self.feed or {}
        gen = f.get("generado") if isinstance(f.get("generado"), (int, float)) else None
        if self._ok("feed") and (gen is None or ahora - gen > FUENTE_VIEJA_S):
            out.append("feed v2 atrasado")
        if self.huecos:
            out.append("%d hueco(s) de más de %d s en la traza leída" % (len(self.huecos), HUECO_TRAZA_S))
        return out

    def resumen(self, ahora: float) -> dict:
        self.refrescar()
        f = self.feed or {}
        gen = f.get("generado") if isinstance(f.get("generado"), (int, float)) else None
        inc = self.incidencias(ahora)
        return {
            "activa": True, "directorio": str(self.dir), "modo": self.modo,
            "estado": "incidencia" if inc else "ok", "incidencias": inc,
            "politica": self.politica, "publicaciones_leidas": self.publicaciones,
            "traza_desde": self.traza_desde, "traza_hasta": self.traza_hasta,
            "traza_fresca": self.traza_fresca(ahora), "huecos_traza": len(self.huecos),
            "cobertura_hasta": None if self.traza_hasta is None else self.traza_hasta - MARGEN_LECTURA_S,
            "feed_secuencia": f.get("secuencia"), "feed_generado": gen,
            "feed_edad_s": None if gen is None else round(ahora - gen, 1),
            "feed_atrasado": gen is None or ahora - gen > FUENTE_VIEJA_S,
            "feed_entradas": len(f.get("entradas") or []),
            "senales_if": len(self.senales) if self._ok("senales_if") else None,
            "decisiones_con_medida": len(self.medidas) if self._ok("traza") else None,
            "fuentes": self.fuentes,
            "agente": {"estado": "desconocido",
                       "motivo": "el sensor no recibe la traza del agente v2 (srv-dmz); se verifica en el host"},
            "aplicacion": "no_ejecutada (modo sombra)" if self.modo == "sombra" else "desconocido",
            "efecto": "sin_evidencia",
        }


_MOTIVO_COBERTURA = {
    PENDIENTE: "posterior a la última publicación del publicador v2 (procesamiento pendiente)",
    DESACTUALIZADA: "posterior a la última publicación y la traza v2 está desactualizada",
    AUSENTE: "traza v2 ausente o ilegible",
    FUERA: "fuera de la cobertura demostrada por la traza leída (anterior o en un hueco)",
}


def medida_como_accion(d: dict) -> tuple[str, str, str] | None:
    """(accion, motivo, origen) SOLO si el publicador v2 publicó una medida para la decisión."""
    c = d.get("cadena_v2")
    if not isinstance(c, dict):
        return None
    m = c.get("medida") or {}
    if m.get("estado") not in MEDIDAS_PUBLICADAS or m.get("accion") not in SEVERIDAD:
        return None
    etiqueta = ETIQUETA_MEDIDA.get(m["estado"], m["estado"])
    if c.get("propuesta"):
        etiqueta = "propuesta en sombra · " + etiqueta
    return (str(m["accion"]), etiqueta, str(m.get("regla") or "publicador_v2"))
