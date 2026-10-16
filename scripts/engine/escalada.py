#!/usr/bin/env python3
"""Escalera de caducidad y reincidencia (ver DISENO-ENFORCEMENT.md §9).

Principio: el coste de equivocarse (falso positivo) está acotado en el tiempo; el
coste de ser un atacante reincidente crece. Nunca `∞` automático.

- LIMIT      -> 300 s (plano; no escala; reversible)
- BLOCK 1º   -> 300 s
- BLOCK 2º   (< ventana) -> 1800 s
- BLOCK 3º+  (< ventana) -> 3600 s (tope automático) + marca de revisión humana
- ∞          -> nunca aquí; lo decide una persona sobre la cola de revisión

Decaimiento: si una IP no reincide en `ventana_s` (24 h por defecto), su contador
se reinicia y la próxima ofensa vuelve a 300 s.

El estado es un dict serializable {ip: {"bloqueos": int, "ultimo_visto": epoch}},
para poder persistirlo en disco entre ejecuciones.
"""
from __future__ import annotations

TIMEOUT_LIMIT_S = 300
ESCALERA_BLOCK_S = {1: 300, 2: 1800, 3: 3600}   # 3 = tope; 3+ usa 3600
REVISION_HUMANA_DESDE = 3
VENTANA_DECAIMIENTO_S = 24 * 3600
SEPARACION_EPISODIO_S = 120


def procesar(estado: dict, ip: str, accion: str, ahora: float,
             ventana_s: int = VENTANA_DECAIMIENTO_S,
             evento_ts: float | None = None,
             separacion_episodio_s: int = SEPARACION_EPISODIO_S) -> dict:
    """Actualiza `estado[ip]` y devuelve el veredicto con su caducidad.

    accion: "LIMIT" o "BLOCK". Devuelve
    {accion, timeout_s, nivel, revisar_humano}.
    """
    st = estado.get(ip)
    # Decaimiento: si lleva más de la ventana sin reincidir, se reinicia.
    if st and (ahora - st.get("ultimo_visto", 0)) > ventana_s:
        st = None

    # Solo hay tres niveles efectivos. Acotar también migra estados históricos
    # inflados por republicar la misma decisión en cada ciclo del timer.
    bloqueos = min(int(st.get("bloqueos", 0)), 3) if st else 0

    if accion == "BLOCK":
        ultimo_evento = float(st.get("ultimo_evento_block", 0)) if st else 0
        mismo_episodio = (
            evento_ts is not None
            and ultimo_evento > 0
            and evento_ts <= ultimo_evento + separacion_episodio_s
        )
        if not mismo_episodio:
            bloqueos = min(bloqueos + 1, 3)
        nivel = min(bloqueos, 3)
        timeout = ESCALERA_BLOCK_S[nivel]
        revisar = bloqueos >= REVISION_HUMANA_DESDE
    elif accion == "LIMIT":
        # LIMIT no incrementa el contador de bloqueos (es la entrada suave),
        # pero mantiene la IP "viva" para que no decaiga entre un LIMIT y un
        # BLOCK posterior cercano.
        timeout = TIMEOUT_LIMIT_S
        revisar = False
    else:
        raise ValueError("accion invalida: %r (usa LIMIT o BLOCK)" % accion)

    nuevo_estado = {"bloqueos": bloqueos, "ultimo_visto": ahora}
    if st and "ultimo_evento_block" in st:
        nuevo_estado["ultimo_evento_block"] = st["ultimo_evento_block"]
    if accion == "BLOCK" and evento_ts is not None:
        nuevo_estado["ultimo_evento_block"] = max(ultimo_evento, evento_ts)
    estado[ip] = nuevo_estado
    return {"accion": accion, "timeout_s": timeout, "nivel": bloqueos,
            "revisar_humano": revisar}


def podar(estado: dict, ahora: float, ventana_s: int = VENTANA_DECAIMIENTO_S) -> int:
    """Quita del estado las IPs que ya decayeron (higiene). Devuelve cuántas."""
    viejas = [ip for ip, st in estado.items()
              if (ahora - st.get("ultimo_visto", 0)) > ventana_s]
    for ip in viejas:
        del estado[ip]
    return len(viejas)
