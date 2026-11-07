#!/usr/bin/env python3
"""S7 de E-carga v2 (= O7 de CRITERIOS-FIJADOS §4, regla de PREPARACION r1 §4.3). SOLO LECTURA. VERSION 2026-11-07.1.
Sustituye a la lectura manual de obs_p4_post.sh, cuyo `all()` da True con una lista vacía o con una sola lectura.
Misma ventana: entregas en [D, A), recepciones en [D, A + 5), muestras del publicador en [D − 60, A + 60].

  derivar_s7.py AGENTE.jsonl RELE.jsonl MUESTRAS.txt D A [--rc-agente N] [--rc-rele N]  -> JSON {"S7": {"valor", "motivo"}, …}

Tres comprobaciones, cada una true, false o null:
  entregas_aceptadas        hay entregas del relé y todas se aceptaron
  aceptadas_en_orden        secuencias aceptadas estrictamente crecientes, con al menos dos para poder comparar
  publicador_sin_retroceso  feed_seq no decrece, con al menos dos lecturas, sin ninguna lectura fallida y con cobertura
                            de <= 60 s (mismo criterio que derivar_bastion.py)
Valor de S7:
  false  algún incumplimiento observado: entregada sin aceptar, desorden o retroceso. Se conserva aunque falte otra
         evidencia: lo observado no desaparece porque otra lectura haya fallado.
  null   sin incumplimiento observado, pero alguna comprobación no se puede respaldar. Una lista vacía o una sola lectura
         no demuestran nada.
  true   solo si las tres son true.
rc: 0 JSON escrito, con cualquier valor; 2 uso.
"""
import argparse
import json
import re
import sys
from collections import Counter

VERSION = "derivar_s7 2026-11-07.1"
MARGEN = 60.0


def jsonl(ruta, rc):
    """-> (filas, problema). Se quitan los NUL de la traza del relé. Una fila ilegible invalida la lectura."""
    if rc not in (0, None):
        return [], f"copia fallida (rc {rc})"
    try:
        with open(ruta, "rb") as fh:
            crudo = fh.read().replace(b"\0", b"")
    except OSError as e:
        return [], f"no legible: {e.strerror}"
    filas, malas = [], 0
    for l in crudo.decode("utf-8", "replace").splitlines():
        if not l.strip():
            continue
        try:
            d = json.loads(l)
        except ValueError:
            malas += 1
            continue
        if isinstance(d, dict):
            filas.append(d)
        else:
            malas += 1
    if malas:
        return filas, f"{malas} línea(s) ilegibles"
    if not filas:
        return [], "vacía"
    return filas, None


def lecturas_feed(ruta, d, a):
    """-> (lecturas [(t, seq)], fallos [t], cobertura, problema)"""
    try:
        with open(ruta, encoding="utf-8", errors="replace") as fh:
            texto = fh.read()
    except OSError as e:
        return [], [], None, f"muestras no legibles: {e.strerror}"
    lec, fallos, ts = [], [], []
    for b in texto.split("### ")[1:]:
        cab, _, cuerpo = b.partition("\n")
        try:
            t = float(cab.split()[1])
        except (IndexError, ValueError):
            continue
        if not (d - MARGEN <= t <= a + MARGEN):
            continue
        ts.append(t)
        m = re.search(r"^S feed_seq=(\d+)$", cuerpo, re.M)
        if m:
            lec.append((t, int(m.group(1))))
        else:
            fallos.append(t)
    ts.sort()
    huecos = [y - x for x, y in zip(ts, ts[1:])]
    antes = [t for t in ts if t <= d]
    despues = [t for t in ts if t >= a]
    cob = {"muestras": len(ts), "antes_de_desde_s": round(d - max(antes), 1) if antes else None,
           "despues_de_hasta_s": round(min(despues) - a, 1) if despues else None,
           "hueco_max_s": round(max(huecos), 1) if huecos else None}
    cob["ok"] = cob["antes_de_desde_s"] is not None and cob["antes_de_desde_s"] <= MARGEN \
        and cob["despues_de_hasta_s"] is not None and cob["despues_de_hasta_s"] <= MARGEN \
        and (cob["hueco_max_s"] or 0) <= MARGEN
    return sorted(lec), fallos, cob, None


def derivar(agente, rele, muestras, d, a, rc_agente=None, rc_rele=None):
    ag, p_ag = jsonl(agente, rc_agente)
    re_, p_re = jsonl(rele, rc_rele)
    com = {}

    # entregas_aceptadas
    ent = sorted((r for r in re_ if r.get("evento") == "reenvio" and isinstance((r.get("destinos") or {}).get("srv-dmz"), dict)
                  and isinstance(r["destinos"]["srv-dmz"].get("entregado_en"), (int, float))
                  and d <= r["destinos"]["srv-dmz"]["entregado_en"] < a),
                 key=lambda r: r["destinos"]["srv-dmz"]["entregado_en"])
    seq_e = [r.get("secuencia") for r in ent]
    rec = sorted((x for x in ag if x.get("evento") == "recepcion" and isinstance(x.get("recibido_en"), (int, float))
                  and d <= x["recibido_en"] < a + 5), key=lambda x: x["recibido_en"])
    acep = [x.get("secuencia") for x in rec if x.get("estado") == "aceptado"]
    falt = sorted(set(s for s in seq_e if isinstance(s, int)) - set(s for s in acep if isinstance(s, int)))
    if p_re:
        c = {"valor": None, "motivo": f"traza del relé: {p_re}"}
    elif not seq_e:
        c = {"valor": None, "motivo": "ninguna entrega en la ventana"}
    elif not all(isinstance(s, int) for s in seq_e):
        c = {"valor": None, "motivo": "entrega sin secuencia"}
    elif p_ag:
        c = {"valor": None, "motivo": f"traza del agente: {p_ag}"}
    elif falt:
        c = {"valor": False, "motivo": f"{len(falt)} entregadas sin aceptar: {falt[:20]}"}
    else:
        c = {"valor": True, "motivo": None}
    c.update(entregas=len(seq_e), recepciones=len(rec), estados=dict(Counter(str(x.get("estado")) for x in rec)),
             no_aceptadas=len(falt), secuencia_ini_fin=[seq_e[0], seq_e[-1]] if seq_e else None)
    com["entregas_aceptadas"] = c

    # aceptadas_en_orden
    malas = [(x, y) for x, y in zip(acep, acep[1:]) if isinstance(x, int) and isinstance(y, int) and y <= x]
    if malas:
        c = {"valor": False, "motivo": f"secuencias aceptadas fuera de orden: {malas[:10]}"}
    elif p_ag:
        c = {"valor": None, "motivo": f"traza del agente: {p_ag}"}
    elif not all(isinstance(s, int) for s in acep):
        c = {"valor": None, "motivo": "recepción aceptada sin secuencia"}
    elif len(acep) < 2:
        c = {"valor": None, "motivo": f"{len(acep)} aceptada(s): no hay orden que comparar"}
    else:
        c = {"valor": True, "motivo": None}
    c.update(aceptadas=len(acep))
    com["aceptadas_en_orden"] = c

    # publicador_sin_retroceso
    lec, fallos, cob, p_mu = lecturas_feed(muestras, d, a)
    fseq = [s for _, s in lec]
    retro = [(x, y) for x, y in zip(fseq, fseq[1:]) if y < x]
    if retro:
        c = {"valor": False, "motivo": f"retroceso del publicador: {retro[:10]}"}
    elif p_mu:
        c = {"valor": None, "motivo": p_mu}
    elif not fseq:
        c = {"valor": None, "motivo": "ninguna lectura feed_seq en la ventana"}
    elif len(fseq) < 2:
        c = {"valor": None, "motivo": "una sola lectura feed_seq: no se puede comparar"}
    elif fallos:
        c = {"valor": None, "motivo": f"{len(fallos)} lectura(s) feed_seq fallidas, primera en {fallos[0]:.0f}"}
    elif not cob["ok"]:
        c = {"valor": None, "motivo": "cobertura de lecturas insuficiente (criterio <= 60 s)"}
    else:
        c = {"valor": True, "motivo": None}
    c.update(lecturas=len(fseq), lecturas_fallidas=len(fallos), secuencia_ini_fin=[fseq[0], fseq[-1]] if fseq else None,
             cobertura=cob)
    com["publicador_sin_retroceso"] = c

    vals = [c["valor"] for c in com.values()]
    mot = "; ".join(f"{k}: {c['motivo']}" for k, c in com.items() if c["motivo"] and c["valor"] is not True)
    valor = False if False in vals else (None if None in vals else True)
    if valor is False:
        mot = "; ".join(f"{k}: {c['motivo']}" for k, c in com.items() if c["valor"] is False)
    return {"version": VERSION, "periodo": [d, a], "comprobaciones": com, "S7": {"valor": valor, "motivo": mot or None}}


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("agente")
    ap.add_argument("rele")
    ap.add_argument("muestras")
    ap.add_argument("desde", type=float)
    ap.add_argument("hasta", type=float)
    ap.add_argument("--rc-agente", type=int)
    ap.add_argument("--rc-rele", type=int)
    a = ap.parse_args(argv)
    print(json.dumps(derivar(a.agente, a.rele, a.muestras, a.desde, a.hasta, a.rc_agente, a.rc_rele), ensure_ascii=False, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
