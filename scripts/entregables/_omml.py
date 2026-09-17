#!/usr/bin/env python3
"""Constructor minimo de ecuaciones OMML para python-docx.

Word representa las ecuaciones en OMML, no como texto ni como imagen. Sustituir
una ecuacion por texto plano se nota; por eso se generan en el mismo formato.
Solo se cubre lo necesario: runs, fracciones, subindices, superindices y
sumatorios.
"""
from __future__ import annotations
from docx.oxml import OxmlElement
from docx.oxml.ns import qn

M = "http://schemas.openxmlformats.org/officeDocument/2006/math"


def _e(tag: str):
    el = OxmlElement(f"m:{tag}")
    return el


def r(texto: str):
    """Run matematico."""
    run = _e("r")
    t = _e("t")
    t.set(qn("xml:space"), "preserve")
    t.text = texto
    run.append(t)
    return run


def sub(base, indice):
    """base con subindice."""
    s = _e("sSub")
    e1, e2 = _e("e"), _e("sub")
    e1.append(base); e2.append(indice)
    s.append(e1); s.append(e2)
    return s


def sup(base, exponente):
    """base con superindice."""
    s = _e("sSup")
    e1, e2 = _e("e"), _e("sup")
    e1.append(base); e2.append(exponente)
    s.append(e1); s.append(e2)
    return s


def frac(num, den):
    """Fraccion."""
    f = _e("f")
    n, d = _e("num"), _e("den")
    n.append(num); d.append(den)
    f.append(n); f.append(d)
    return f


def nary(op: str, desde, hasta, cuerpo):
    """Operador n-ario: sumatorio, producto..."""
    n = _e("nary")
    pr = _e("naryPr")
    ch = _e("chr"); ch.set(qn("m:val"), op)
    lim = _e("limLoc"); lim.set(qn("m:val"), "undOvr")
    pr.append(ch); pr.append(lim)
    n.append(pr)
    for tag, cont in (("sub", desde), ("sup", hasta), ("e", cuerpo)):
        el = _e(tag)
        if cont is not None:
            el.append(cont)
        n.append(el)
    return n


def ecuacion(parrafo, *elementos):
    """Sustituye el contenido de un parrafo por una ecuacion centrada."""
    p = parrafo._p
    for hijo in list(p):
        if not hijo.tag.endswith("}pPr"):
            p.remove(hijo)
    om = _e("oMathPara")
    pr = _e("oMathParaPr")
    jc = _e("jc"); jc.set(qn("m:val"), "center")
    pr.append(jc); om.append(pr)
    math = _e("oMath")
    for el in elementos:
        math.append(el)
    om.append(math)
    p.append(om)
    return parrafo
