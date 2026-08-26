#!/usr/bin/env python3
"""Piezas de formato compartidas por los generadores de Word.

Existe para que los cuatro entregables se vean como una misma familia y para
no repetir en cada script el pie de pagina, los bordes de tabla y las
propiedades del documento.
"""
from __future__ import annotations
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Pt, RGBColor

GRIS_LINEA = "BFBFBF"
DIM = RGBColor(0x5B, 0x6B, 0x8C)
ACCENT = RGBColor(0x0F, 0x8A, 0x7D)


def bordes_tabla(tabla, color: str = GRIS_LINEA, grosor: int = 4) -> None:
    """Retícula fina. Sin bordes, las celdas sombreadas parecen flotar."""
    tblPr = tabla._tbl.tblPr
    for viejo in tblPr.findall(qn("w:tblBorders")):
        tblPr.remove(viejo)
    b = OxmlElement("w:tblBorders")
    for lado in ("top", "left", "bottom", "right", "insideH", "insideV"):
        e = OxmlElement(f"w:{lado}")
        e.set(qn("w:val"), "single")
        e.set(qn("w:sz"), str(grosor))
        e.set(qn("w:color"), color)
        b.append(e)
    tblPr.append(b)


def _campo(parrafo, instruccion: str, size: float, color: RGBColor):
    """Inserta un campo de Word (PAGE, NUMPAGES) que se recalcula al abrir."""
    r = parrafo.add_run()
    r.font.size = Pt(size)
    r.font.color.rgb = color
    ini = OxmlElement("w:fldChar")
    ini.set(qn("w:fldCharType"), "begin")
    txt = OxmlElement("w:instrText")
    txt.set(qn("xml:space"), "preserve")
    txt.text = f" {instruccion} "
    fin = OxmlElement("w:fldChar")
    fin.set(qn("w:fldCharType"), "end")
    for el in (ini, txt, fin):
        r._r.append(el)


def pie_con_pagina(doc, izquierda: str, size: float = 7.4) -> None:
    """Pie con identificacion a la izquierda y 'Pagina X de Y' a la derecha."""
    p = doc.sections[0].footer.paragraphs[0]
    p.text = ""
    p.alignment = WD_ALIGN_PARAGRAPH.LEFT
    # tabulador derecho al ancho util de la pagina
    s = doc.sections[0]
    ancho_emu = int(s.page_width) - int(s.left_margin) - int(s.right_margin)
    ancho_twips = ancho_emu // 635  # 1 twip = 635 EMU
    pPr = p._p.get_or_add_pPr()
    tabs = OxmlElement("w:tabs")
    tab = OxmlElement("w:tab")
    tab.set(qn("w:val"), "right")
    tab.set(qn("w:pos"), str(ancho_twips))
    tabs.append(tab)
    pPr.append(tabs)

    r = p.add_run(izquierda + "\t")
    r.font.size = Pt(size)
    r.font.color.rgb = DIM
    r = p.add_run("Página ")
    r.font.size = Pt(size)
    r.font.color.rgb = DIM
    _campo(p, "PAGE", size, DIM)
    r = p.add_run(" de ")
    r.font.size = Pt(size)
    r.font.color.rgb = DIM
    _campo(p, "NUMPAGES", size, DIM)


def encabezado(doc, texto: str, size: float = 7.4) -> None:
    """Encabezado discreto, con una linea inferior de separacion."""
    p = doc.sections[0].header.paragraphs[0]
    p.text = ""
    p.alignment = WD_ALIGN_PARAGRAPH.RIGHT
    r = p.add_run(texto)
    r.font.size = Pt(size)
    r.font.color.rgb = DIM
    r.font.italic = True
    pPr = p._p.get_or_add_pPr()
    bd = OxmlElement("w:pBdr")
    e = OxmlElement("w:bottom")
    e.set(qn("w:val"), "single")
    e.set(qn("w:sz"), "4")
    e.set(qn("w:color"), GRIS_LINEA)
    e.set(qn("w:space"), "3")
    bd.append(e)
    pPr.append(bd)


def propiedades(doc, titulo: str, asunto: str,
                autor: str = "Rubén Mark Salazar Tocas; Uziel Elias Sauñe Fernandez",
                palabras: str = "detección de anomalías; seguridad de redes; "
                                "aprendizaje no supervisado; OCSVM") -> None:
    """Metadatos del archivo. Un .docx sin titulo ni autor se ve improvisado
    en cuanto alguien abre las propiedades o lo indexa un gestor documental."""
    cp = doc.core_properties
    cp.title = titulo
    cp.subject = asunto
    cp.author = autor
    cp.last_modified_by = autor
    cp.keywords = palabras
    cp.category = "Investigación V · UPeU"
    cp.comments = ("Documento generado por script desde los artefactos del proyecto; "
                   "ninguna cifra se transcribe a mano.")


def rematar(doc, titulo: str, asunto: str, pie_izquierda: str, encabezado_txt: str) -> None:
    """Aplica de una vez todo el mobiliario del documento."""
    propiedades(doc, titulo, asunto)
    pie_con_pagina(doc, pie_izquierda)
    encabezado(doc, encabezado_txt)
    for t in doc.tables:
        bordes_tabla(t)
