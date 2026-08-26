#!/usr/bin/env python3
"""Word del informe de evaluacion critica (Sesion 01, momento CREA).

El .md de la carpeta es la fuente DETALLADA. Este Word es la version PRECISA
para el docente, con la estructura exacta que pide la consigna y dentro del
limite de 2-4 paginas.

    python3 scripts/entregables/generar_evaluacion_critica_word.py
"""
from __future__ import annotations
from pathlib import Path
from docx import Document
from docx.enum.table import WD_TABLE_ALIGNMENT
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Cm, Pt, RGBColor

REPO = Path(__file__).resolve().parents[2]
LOGO = REPO / "docs/entregables/assets/logo-upeu.png"
GRAF = REPO / "docs/entregables/graficas"
OUT = REPO / "docs/entregables/01-evaluacion-critica/Informe-evaluacion-critica.docx"

INK, DIM = RGBColor(0x13, 0x1B, 0x2E), RGBColor(0x5B, 0x6B, 0x8C)
ACCENT, WHITE = RGBColor(0x0F, 0x8A, 0x7D), RGBColor(0xFF, 0xFF, 0xFF)
F_HEAD, F_ZEBRA, F_OK, F_AMBER, F_RED = "0F8A7D", "F4F6FB", "E0F3E6", "FDECD2", "FBE3E1"


def shade(cell, hx):
    el = OxmlElement("w:shd"); el.set(qn("w:val"), "clear"); el.set(qn("w:fill"), hx)
    cell._tc.get_or_add_tcPr().append(el)


def h1(doc, n, txt):
    p = doc.add_paragraph()
    p.paragraph_format.space_before = Pt(11); p.paragraph_format.space_after = Pt(4)
    r = p.add_run(f"{n}  {txt}")
    r.font.size = Pt(12.5); r.font.bold = True; r.font.color.rgb = ACCENT
    return p


def par(doc, txt, size=9.2, italic=False, color=INK, after=5, align=WD_ALIGN_PARAGRAPH.JUSTIFY):
    p = doc.add_paragraph()
    p.paragraph_format.space_after = Pt(after); p.alignment = align
    for i, t in enumerate(txt.split("**")):
        r = p.add_run(t)
        r.font.size = Pt(size); r.font.color.rgb = color
        r.font.italic = italic; r.font.bold = i % 2 == 1
    return p


def tabla(doc, cab, filas, anchos, fondos=None):
    t = doc.add_table(rows=1, cols=len(cab))
    t.alignment = WD_TABLE_ALIGNMENT.CENTER; t.autofit = False
    for c, (txt, w) in enumerate(zip(cab, anchos)):
        cell = t.rows[0].cells[c]; cell.width = Cm(w); cell.text = ""
        r = cell.paragraphs[0].add_run(txt)
        r.font.bold = True; r.font.size = Pt(8.4); r.font.color.rgb = WHITE
        shade(cell, F_HEAD)
    for i, fila in enumerate(filas):
        row = t.add_row()
        for c, txt in enumerate(fila):
            cell = row.cells[c]; cell.width = Cm(anchos[c]); cell.text = ""
            p = cell.paragraphs[0]; p.paragraph_format.space_after = Pt(1)
            for k, tr in enumerate(str(txt).split("**")):
                r = p.add_run(tr)
                r.font.size = Pt(8.2); r.font.bold = k % 2 == 1; r.font.color.rgb = INK
            if fondos and fondos[i]:
                shade(cell, fondos[i])
            elif i % 2 == 0:
                shade(cell, F_ZEBRA)
    doc.add_paragraph().paragraph_format.space_after = Pt(2)


def figura(doc, nombre, pie, ancho=13.0):
    f = GRAF / nombre
    if not f.exists():
        raise SystemExit(f"falta la figura: {f}")
    doc.add_picture(str(f), width=Cm(ancho))
    doc.paragraphs[-1].alignment = WD_ALIGN_PARAGRAPH.CENTER
    doc.paragraphs[-1].paragraph_format.space_after = Pt(1)
    par(doc, pie, size=7.8, italic=True, color=DIM, after=7, align=WD_ALIGN_PARAGRAPH.CENTER)


def main() -> None:
    if not LOGO.exists():
        raise SystemExit(f"falta el logo: {LOGO}")
    doc = Document()
    s = doc.sections[0]
    s.top_margin = s.bottom_margin = Cm(1.4); s.left_margin = s.right_margin = Cm(1.8)
    doc.styles["Normal"].font.name = "Calibri"

    doc.add_picture(str(LOGO), width=Cm(4.6))
    doc.paragraphs[-1].alignment = WD_ALIGN_PARAGRAPH.CENTER
    for txt, sz, col, b in [("Universidad Peruana Unión", 10, INK, True),
                            ("Facultad de Ingeniería y Arquitectura · E.P. de Ingeniería de Sistemas", 8.4, DIM, False),
                            ("Investigación V · Sesión 01", 8.4, DIM, False)]:
        p = doc.add_paragraph(); p.alignment = WD_ALIGN_PARAGRAPH.CENTER
        p.paragraph_format.space_after = Pt(1)
        r = p.add_run(txt); r.font.size = Pt(sz); r.font.color.rgb = col; r.font.bold = b

    p = doc.add_paragraph(); p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p.paragraph_format.space_before = Pt(7); p.paragraph_format.space_after = Pt(2)
    r = p.add_run("INFORME DE EVALUACIÓN CRÍTICA DE RESULTADOS")
    r.font.size = Pt(14.5); r.font.bold = True; r.font.color.rgb = ACCENT
    par(doc, "Sistema open source para la detección temprana de comportamientos anómalos "
             "en redes de datos\nRubén Mark Salazar Tocas · Uziel Elias Sauñe Fernandez",
        size=9, color=DIM, after=9, align=WD_ALIGN_PARAGRAPH.CENTER)

    # ---------------------------------------------------------------- 1
    h1(doc, "1 ·", "Qué se abordó de manera objetiva")
    par(doc, "El producto es un sistema desplegado que detecta comportamiento anómalo y "
             "**bloquea la IP ofensora en el propio router**, validado sobre tráfico real de "
             "laboratorio. Toda cifra procede de artefactos verificables; ninguna se transcribe "
             "a mano.")
    tabla(doc, ["Criterio evaluado", "Resultado obtenido", "Cómo se verificó"], [
        ["**Capacidad discriminante**", "**ROC-AUC 0,974**", "Re-puntuando el modelo congelado"],
        ["**Detección de ataques genuinos**", "**88,8 %** [83,0 – 92,8]", "Evaluación bloqueada de un solo paso, con intervalo de Wilson"],
        ["**Respuesta en tiempo real**", "Bloqueo en mediana de **8,0 s** (p95 8,7 s)", "58 corridas con el motor activo"],
        ["**Disponibilidad**", "**Cero caídas registradas**; 55 de 58 corridas con verificación explícita", "Registro de servicios antes y después de cada corrida"],
        ["**Aporte de las variables multicapa**", "De **66,5 % a 88,8 %** de detección, p < 0,001", "Ablación por capas con McNemar exacto"],
        ["**Superioridad del modelo elegido**", "Las **6 comparaciones** del OCSVM son significativas", "McNemar + corrección de Holm sobre 21 pares"],
        ["**Reproducibilidad**", "Dataset, manifiesto y **los 7 modelos** publicados y verificables", "sha256sum -c · licencias MIT y CC BY 4.0"],
    ], [4.4, 5.4, 7.6])
    figura(doc, "A1-curva-roc.png",
           "Figura 1. Curva ROC del modelo congelado. El AUC de 0,974 se calculó en esta evaluación: "
           "el trabajo original nunca lo computó.", ancho=9.6)

    # ---------------------------------------------------------------- 2
    h1(doc, "2 ·", "Qué está faltando")
    par(doc, "Las debilidades se ordenan por gravedad y **todas están medidas**, no supuestas.")
    tabla(doc, ["Debilidad", "Evidencia", "Gravedad"], [
        ["**El falso positivo de laboratorio no se sostiene en operación**", "4,71 % [2,8–7,9] frente a 22,97 % [14,9–33,7]. **Los intervalos no se solapan.** Una transferencia legítima de 200 Mbit/s bloqueó a un cliente real 120 s", "Crítica"],
        ["**El modelo se eligió observando el conjunto de prueba**", "El manifiesto designaba otro modelo como conclusión y a este como comparador. El 88,3 % es el máximo sobre 7 candidatos", "Crítica"],
        ["**Ninguna validación con usuarios reales**", "No se midió la experiencia de uso del panel ni se aplicó instrumento alguno", "Alta"],
        ["**La partición mide repetición, no generalización**", "Los 44 perfiles aparecen en las tres particiones; no existe jornada de holdout externa", "Alta"],
        ["**Sin validación cruzada ni banda para el umbral**", "El umbral 1,8126 se reporta como valor puntual, sin variabilidad", "Media"],
        ["**Las 8 variables L7 nuevas no aportan detección**", "La ablación las midió: p = 1,000 y **5 falsos positivos adicionales**", "Media"],
    ], [5.0, 9.2, 2.2], fondos=[F_RED, F_RED, F_AMBER, F_AMBER, F_ZEBRA, F_ZEBRA])
    figura(doc, "C1-fpr-offline-vs-operativo.png",
           "Figura 2. El hallazgo más importante: el error sobre tráfico legítimo medido en "
           "laboratorio no se reproduce en operación real.", ancho=11.0)

    # ---------------------------------------------------------------- 3
    h1(doc, "3 ·", "Cómo se está abordando lo que falta")
    par(doc, "**Ya resuelto**, sin capturar datos nuevos ni reentrenar el modelo congelado:")
    tabla(doc, ["Acción ejecutada", "Qué cerró"], [
        ["Intervalos de Wilson en toda proporción y **McNemar con corrección de Holm** sobre 21 comparaciones", "Ausencia de medidas de incertidumbre y de pruebas de significancia"],
        ["**Ablación por capas y comparación 14 vs 28**, con la configuración completa reproduciendo el modelo congelado bit a bit", "Requisito explícito del jurado, antes sin ejecutar"],
        ["**Diccionario científico de las 28 variables**, generado desde el extractor congelado", "Requisito explícito del jurado"],
        ["Dataset, manifiesto y **7 modelos publicados** con checksums y licencias", "Imposibilidad de replicar desde un clon"],
        ["*Datasheet*, *model card* y *system card*", "Ausencia de documentación canónica"],
        ["**Declaración explícita de la selección posterior** del modelo", "Objeción metodológica principal, ahora declarada"],
    ], [8.6, 7.8], fondos=[F_OK] * 6)
    par(doc, "**Pendiente, con plazo realista.** El orden responde a coste, no a comodidad:")
    tabla(doc, ["Plazo", "Acción", "Por qué en ese orden"], [
        ["**Horas**", "Validación cruzada por episodio · banda del umbral por remuestreo · cerrar la matriz de requisitos", "No dependen de nadie más y usan el dataset ya publicado"],
        ["**Días**", "**Validación con usuarios: SUS con 5–8 evaluadores**", "Es el único cero absoluto que queda; una sesión lo convierte en evidencia"],
        ["**Semanas**", "Recalibrar incluyendo tráfico legítimo pesado y repetir la validación operativa", "Única solución real al falso positivo del 23–26 %. Se declara como límite, no se simula"],
    ], [2.2, 7.4, 6.8])

    # ---------------------------------------------------------------- 4
    h1(doc, "4 ·", "Conclusión")
    par(doc, "Se demostró con evidencia que el sistema **detecta y bloquea en tiempo real** sobre "
             "una red enrutada, con ROC-AUC de 0,974, detección del 88,8 % sobre ataques genuinos "
             "y bloqueo en una mediana de 8 segundos, sin ninguna caída de servicio registrada.")
    par(doc, "**No se demostró** que lo haga con una tasa de falsos positivos aceptable sobre "
             "tráfico legítimo pesado: en esa condición el sistema todavía no es apto para "
             "operación desatendida.")
    par(doc, "Delimitar esa frontera con medición —y no ocultarla— es el resultado de esta "
             "evaluación. Un hallazgo negativo verificado vale más que una conclusión favorable "
             "sin respaldo.", italic=True, color=DIM)
    par(doc, "Detalle completo, con las 11 figuras y la trazabilidad de cada cifra, en "
             "informe-evaluacion-critica.md del repositorio del proyecto.",
        size=7.8, italic=True, color=DIM)

    doc.save(OUT)
    print(f"Generado: {OUT.relative_to(REPO)}")


if __name__ == "__main__":
    main()
