"""Cadena de respuesta v2 tal como la puede ver el panel del sensor (solo lectura).

Etapa 4A (4-nov-2026). Con el motor ec78ca5 y el publicador v2 (``--politica if_senal``)
la acción ya no se deduce de la decisión: la publica (o no) el publicador y deja traza.
Este módulo NO recalcula ninguna política. Indexa por ``decision_id`` lo que dejaron
las fuentes reales y dice, para cada decisión, en qué punto de la cadena está:

1. ``if``          señal del Isolation Forest (``senales-if.jsonl``): señal | sin_senal | desconocido
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
"""
from __future__ import annotations

import json
import threading
from pathlib import Path

MEDIDAS_PUBLICADAS = ("nueva", "renovada", "escalada", "mantenida")
MEDIDAS_SIN_EFECTO = ("rechazada", "sin_punto_de_aplicacion")
SEVERIDAD = {"BLOCK": 2, "LIMIT": 1}
COLA_BYTES = 8 * 1024 * 1024          # cola leída de cada jsonl (las trazas crecen)
FUENTE_VIEJA_S = 60                   # el publicador escribe cada 10 s

ETIQUETA_MEDIDA = {
    "nueva": "medida publicada (nueva)",
    "renovada": "medida publicada (renovada)",
    "escalada": "medida publicada (escalada)",
    "mantenida": "medida vigente mantenida",
    "rechazada": "regla rechazada por el publicador (sin efecto)",
    "sin_punto_de_aplicacion": "sin punto de aplicación (no se restringe)",
    "no_publicada": "sin medida publicada",
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
    """Índice de las fuentes v2 por decision_id. Se recarga solo cuando cambian los ficheros."""

    def __init__(self, directorio: Path, modo_respuesta: str = "sombra"):
        self.dir = Path(directorio)
        self.modo = modo_respuesta
        self._lock = threading.Lock()
        self._sellos: dict = {}
        self.senales: dict[str, dict] = {}
        self.medidas: dict[str, list[dict]] = {}
        self.publicaciones = 0
        self.traza_desde: float | None = None
        self.traza_hasta: float | None = None
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
            t0 = t1 = None
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
                        t0 = tp if t0 is None else min(t0, tp)
                        t1 = tp if t1 is None else max(t1, tp)
                    for x in p.get("nuevos") or []:
                        if not isinstance(x, dict):
                            continue
                        clave = str(x.get("decision_id") or str(x.get("evento_id", "")).rsplit("|", 1)[0])
                        medidas.setdefault(clave, []).append(dict(x, secuencia=p.get("secuencia"),
                                                                  publicado_en=tp))
                self.fuentes["traza"] = {"ok": True, "publicaciones": n}
            except OSError as exc:
                self.fuentes["traza"] = {"ok": False, "motivo": type(exc).__name__}
            self.medidas, self.publicaciones = medidas, n
            self.traza_desde, self.traza_hasta, self.politica = t0, t1, politica
            # 3) feed v2 vigente
            try:
                self.feed = json.loads(rutas["feed"].read_text(encoding="utf-8"))
                self.fuentes["feed"] = {"ok": isinstance(self.feed, dict)}
            except (OSError, ValueError) as exc:
                self.feed = None
                self.fuentes["feed"] = {"ok": False, "motivo": type(exc).__name__}

    # ------------------------------------------------------------ por decisión
    def _cubre(self, t: float | None) -> bool:
        """La traza leída abarca el instante t (ni anterior a ella ni posterior a la última)."""
        if t is None or self.traza_desde is None or self.traza_hasta is None:
            return False
        return self.traza_desde <= t <= self.traza_hasta

    def cadena(self, d: dict) -> dict:
        did = d.get("decision_id") or "%s|%s" % (d.get("entity_ip"), d.get("window_end_utc"))
        t = d.get("logged_at") if isinstance(d.get("logged_at"), (int, float)) else None
        # 1) IF
        s = self.senales.get(did)
        if s is not None:
            senal_if = {"estado": "senal", "score": s.get("score"),
                        "alfa_superados": s.get("alfa_superados") or []}
        elif self.fuentes.get("senales_if", {}).get("ok") and self.senales_desde is not None \
                and t is not None and t >= self.senales_desde and d.get("score") is not None:
            senal_if = {"estado": "sin_senal"}
        else:
            senal_if = {"estado": "desconocido"}
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
        elif self.fuentes.get("traza", {}).get("ok") and self._cubre(t):
            medida = {"estado": "no_publicada", "accion": None}
        else:
            medida = {"estado": "desconocido", "accion": None}
        publicada = medida["estado"] in MEDIDAS_PUBLICADAS
        if publicada:
            aplicacion = "no_ejecutada" if self.modo == "sombra" else "desconocido"
        else:
            aplicacion = "no_aplica"
        return {
            "decision_id": did,
            "if": senal_if,
            "reglas": reglas_de(d),
            "decision": d.get("decision"),
            "medida": medida,
            "propuesta": publicada and self.modo == "sombra",
            "agente": "desconocido",
            "aplicacion": aplicacion,
            "efecto": "sin_evidencia",
            "modo": self.modo,
        }

    def anotar(self, decisiones: list[dict]) -> None:
        self.refrescar()
        for d in decisiones:
            d["cadena_v2"] = self.cadena(d)

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

    def resumen(self, ahora: float) -> dict:
        self.refrescar()
        f = self.feed or {}
        gen = f.get("generado") if isinstance(f.get("generado"), (int, float)) else None
        return {
            "activa": True, "directorio": str(self.dir), "modo": self.modo,
            "politica": self.politica, "publicaciones_leidas": self.publicaciones,
            "traza_desde": self.traza_desde, "traza_hasta": self.traza_hasta,
            "feed_secuencia": f.get("secuencia"), "feed_generado": gen,
            "feed_edad_s": None if gen is None else round(ahora - gen, 1),
            "feed_atrasado": gen is None or ahora - gen > FUENTE_VIEJA_S,
            "feed_entradas": len(f.get("entradas") or []),
            "senales_if": len(self.senales), "decisiones_con_medida": len(self.medidas),
            "fuentes": self.fuentes,
            "agente": {"estado": "desconocido",
                       "motivo": "el sensor no recibe la traza del agente v2 (srv-dmz); se verifica en el host"},
            "aplicacion": "no_ejecutada (modo sombra)" if self.modo == "sombra" else "desconocido",
            "efecto": "sin_evidencia",
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
