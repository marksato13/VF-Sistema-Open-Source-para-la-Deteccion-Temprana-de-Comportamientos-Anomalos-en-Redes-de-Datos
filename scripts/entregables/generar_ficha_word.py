#!/usr/bin/env python3
"""Genera la Ficha de auditoría del producto de ingeniería en formato Word.

Mismo contenido que `docs/entregables/04-ficha-auditoria/`, con la
presentación formal del curso. Los subtotales y el puntaje final se **calculan
aquí**, no se escriben a mano, de modo que la ficha no puede quedar
descuadrada si cambia una puntuación.

Uso:
    .venv/bin/python3 scripts/entregables/generar_ficha_word.py
"""
from __future__ import annotations

from pathlib import Path

from docx import Document
from docx.enum.text import WD_ALIGN_PARAGRAPH, WD_BREAK
from docx.shared import Cm, Pt, RGBColor

import sys
sys.path.insert(0, str(Path(__file__).resolve().parent))
from generar_informe_word import (  # reutiliza el formato ya definido
    ACCENT, AMBER, DANGER, DIM, F_AMBER, F_DANGER, F_OK, INK, OK,
    caja, cell_text, figura, h1, h2, parrafo, shade, tabla, vineta,
)

REPO = Path(__file__).resolve().parents[2]
OUT = (REPO / "docs" / "entregables" / "04-ficha-auditoria"
       / "Ficha-auditoria-producto.docx")
LOGO = Path("/tmp/claude-1000/-home-m4rk-Documentos-pronteacomopepa-vf-sistema-final/"
            "dbe9d115-fcc7-401a-b5b5-92e1a041bbd5/scratchpad/logo-upeu.png")

# ------------------------------------------------------------- puntuaciones --
# (id, criterio, evidencia, puntaje)  ·  "N/A" se excluye del cálculo
CONFIABILIDAD = [
    ("1.1", "Alfa de Cronbach (consistencia interna)",
     "El producto no emplea cuestionarios ni escalas psicométricas; no hay ítems que correlacionar", "N/A"),
    ("1.2", "Kappa de Cohen (acuerdo inter-evaluador)",
     "No se realizó evaluación por jueces ni doble etiquetado independiente; las etiquetas provienen del diseño experimental", 0),
    ("1.3", "Validación cruzada",
     "No se aplicó sobre el modelo congelado. Existe leave-one-episode-out, pero solo sobre un pipeline descartado", 1),
    ("1.4", "Reproducibilidad de la medición",
     "Al reevaluar el modelo se obtuvieron exactamente las cifras originales (13/276 y 158/179)", 3),
    ("1.5", "Estabilidad entre repeticiones",
     "Dos pases completos de validación operativa con resultados equivalentes (25,8 % y 23,0 %)", 2),
    ("1.6", "Cuantificación de la incertidumbre",
     "Intervalos de confianza de Wilson 95 % sobre todas las proporciones; incorporados a posteriori", 2),
]
REPLICABILIDAD = [
    ("2.1", "Código disponible",
     "Repositorio público con 507 archivos versionados y 330 registros de cambios trazables", 3),
    ("2.2", "Datos disponibles",
     "Los datasets NO están publicados: excluidos del repositorio por tamaño. Impide reproducir el entrenamiento", 1),
    ("2.3", "Entorno documentado",
     "Versiones exactas fijadas, script de instalación idempotente y playbooks de Ansible", 3),
    ("2.4", "Determinismo y semillas",
     "10 semillas registradas, pero no cubren el modelo elegido; el determinismo no se declara como protocolo", 2),
    ("2.5", "Integridad verificable",
     "SHA-256 de datos, modelo y calibrador; repositorio verificado limpio antes y después", 3),
    ("2.6", "Instrucciones de reproducción",
     "Manual de operación y documentación por fases disponibles; falta el manual de implementación técnica", 2),
]
PERTINENCIA = [
    ("3.1", "Validación con usuarios reales",
     "No se realizó. Sin pruebas con analistas de seguridad ni medición de experiencia de uso del panel", 0),
    ("3.2", "Evaluación por expertos o jueces",
     "No se aplicó ningún instrumento de juicio experto (Delphi, SUS u otro)", 0),
    ("3.3", "Trazabilidad de requisitos",
     "Existe matriz de cumplimiento del jurado, pero 4 filas sin cerrar y con rutas desactualizadas", 1),
    ("3.4", "Validación en operación real",
     "Sistema medido desplegado y activo: 2 pases de 29 corridas con motor y bloqueo sobre tráfico real", 3),
    ("3.5", "Alineación con el problema",
     "Detecta y bloquea las 6 familias de ataque previstas, con métricas medidas por familia", 3),
    ("3.6", "Alcance y limitaciones declarados",
     "Limitaciones medidas, cuantificadas y publicadas, incluido el error operativo desfavorable (23–26 %)", 3),
]

NIVEL = {3: ("Completo", F_OK, OK), 2: ("Parcial", F_AMBER, AMBER),
         1: ("Insuficiente", F_DANGER, DANGER), 0: ("Ausente", F_DANGER, DANGER)}


def subtotal(items):
    vals = [p for *_, p in items if p != "N/A"]
    return sum(vals), len(vals) * 3


def bloque(doc, titulo, pregunta, items, lectura):
    h1(doc, titulo)
    parrafo(doc, pregunta, italic=True, color=DIM)
    filas = []
    for cid, crit, ev, p in items:
        if p == "N/A":
            celda = ("N/A", "EEF1F8")
        else:
            celda = (f"{p}", NIVEL[p][1])
        filas.append((cid, crit, ev, celda))
    tabla(doc, ["#", "Criterio", "Evidencia concreta en el proyecto", "Pts"],
          filas, widths=[1.0, 4.3, 9.5, 1.2])
    obt, mx = subtotal(items)
    p = doc.add_paragraph()
    p.paragraph_format.space_before = Pt(6)
    r = p.add_run(f"Subtotal: {obt} / {mx} puntos  =  {100*obt/mx:.1f} %")
    r.bold = True
    r.font.size = Pt(11.5)
    r.font.color.rgb = OK if obt/mx >= 0.7 else (AMBER if obt/mx >= 0.5 else DANGER)
    parrafo(doc, lectura)
    return obt, mx


def main() -> int:
    doc = Document()
    for s in doc.sections:
        s.top_margin = s.bottom_margin = Cm(1.9)
        s.left_margin = s.right_margin = Cm(1.8)
    doc.styles["Normal"].font.name = "Calibri"
    doc.styles["Normal"].font.size = Pt(9.5)

    # -------------------------------------------------------- CARÁTULA -----
    if LOGO.exists():
        doc.add_picture(str(LOGO), width=Cm(7.0))
        doc.paragraphs[-1].alignment = WD_ALIGN_PARAGRAPH.CENTER
    for txt, sz, col, bold in [("Universidad Peruana Unión", 12.5, INK, True),
                               ("Facultad de Ingeniería y Arquitectura", 10.5, DIM, False),
                               ("E.P. de Ingeniería de Sistemas", 10.5, DIM, False)]:
        p = doc.add_paragraph(); p.alignment = WD_ALIGN_PARAGRAPH.CENTER
        r = p.add_run(txt); r.bold = bold; r.font.size = Pt(sz); r.font.color.rgb = col

    doc.add_paragraph()
    p = doc.add_paragraph(); p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    r = p.add_run("FICHA DE AUDITORÍA\nDEL PRODUCTO DE INGENIERÍA VALIDADO")
    r.bold = True; r.font.size = Pt(19); r.font.color.rgb = ACCENT

    p = doc.add_paragraph(); p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p.paragraph_format.space_before = Pt(8)
    r = p.add_run("Detección temprana de comportamientos anómalos en redes de datos\n"
                  "mediante modelos predictivos y un mecanismo de control inline")
    r.italic = True; r.font.size = Pt(11); r.font.color.rgb = DIM

    doc.add_paragraph()
    tabla(doc, ["Campo", "Detalle"],
          [("Producto auditado", "Sistema de detección de anomalías de red con control inline, desplegado en laboratorio virtualizado (VM02)"),
           ("Curso", "Investigación V · Ciclo X"),
           ("Docente", "Ing. Nemias Saboya Ríos"),
           ("Integrantes", "Rubén Mark Salazar Tocas\nUziel Elias Sauñe Fernandez"),
           ("Fecha", "19 de agosto de 2026")],
          widths=[3.6, 12.4])

    doc.add_paragraph()
    caja(doc, "Nota sobre la rúbrica",
         "La escala y los ítems son una **reconstrucción razonada** del ejercicio propuesto, porque no se dispuso "
         "del formato exacto de la ficha proyectada en clase. La estructura de tres dimensiones —confiabilidad, "
         "replicabilidad y pertinencia— y el cálculo de puntaje final sí corresponden a la consigna. Si el formato "
         "oficial difiere, los puntajes por ítem se trasladan sin recalcular la evidencia.",
         fill="FDECD2", color_borde="B45309")

    doc.add_paragraph().add_run().add_break(WD_BREAK.PAGE)

    # ---------------------------------------------------------- ESCALA -----
    h1(doc, "Escala de valoración")
    tabla(doc, ["Puntos", "Nivel", "Significado"],
          [(("3", F_OK), "Completo", "Existe y es verificable por un tercero"),
           (("2", F_AMBER), "Parcial", "Existe pero con limitaciones declaradas"),
           (("1", F_DANGER), "Insuficiente", "Solo declarado, sin evidencia sólida"),
           (("0", F_DANGER), "Ausente", "No se abordó"),
           (("N/A", "EEF1F8"), "No aplica", "No corresponde al tipo de producto (se excluye del cálculo)")],
          widths=[1.8, 3.0, 11.2])

    doc.add_paragraph()
    a = bloque(doc, "1.  Evidencia de CONFIABILIDAD",
               "¿Los resultados son estables y consistentes al repetir la medición?", CONFIABILIDAD,
               "**Lectura.** Alta en **reproducibilidad técnica** —el resultado se vuelve a obtener exactamente— "
               "pero baja en **validación estadística**: falta validación cruzada sobre el modelo elegido y no hay "
               "acuerdo inter-evaluador porque el diseño no lo contempla.")

    doc.add_paragraph().add_run().add_break(WD_BREAK.PAGE)
    b = bloque(doc, "2.  Evidencia de REPLICABILIDAD",
               "¿Puede un tercero reconstruir el estudio y obtener lo mismo?", REPLICABILIDAD,
               "**Lectura.** Es la dimensión **más fuerte** del producto. La cadena de integridad (hashes, "
               "repositorio limpio, versiones fijadas) es superior a lo habitual. La brecha real es que **los datos "
               "no están publicados**, lo que impide replicar el entrenamiento de forma independiente.")

    doc.add_paragraph()
    c = bloque(doc, "3.  Evidencia de PERTINENCIA",
               "¿El producto responde al problema real y su utilidad está demostrada?", PERTINENCIA,
               "**Lectura.** El producto es **técnicamente pertinente** —resuelve el problema y se probó en "
               "operación real— pero carece de **validación con personas**: nadie externo al equipo lo ha usado ni "
               "evaluado. Para un producto cuya interfaz es un panel destinado a un analista, esa ausencia pesa.")

    # ---------------------------------------------------- PUNTAJE FINAL ----
    doc.add_paragraph().add_run().add_break(WD_BREAK.PAGE)
    h1(doc, "4.  Puntaje final")
    T, M = a[0] + b[0] + c[0], a[1] + b[1] + c[1]

    def nivel(pct):
        return ("Alto", F_OK) if pct >= 70 else (("Medio", F_AMBER) if pct >= 50 else ("Bajo", F_DANGER))

    filas = []
    for nombre, (o_, m_) in [("Confiabilidad", a), ("Replicabilidad", b), ("Pertinencia", c)]:
        pct = 100 * o_ / m_
        n, f = nivel(pct)
        filas.append((nombre, f"{o_}", f"{m_}", (f"{pct:.1f} %", f), (n, f)))
    pctT = 100 * T / M
    nT, fT = nivel(pctT)
    filas.append(("TOTAL", f"{T}", f"{M}", (f"{pctT:.1f} %", fT), (nT, fT)))
    tabla(doc, ["Dimensión", "Obtenido", "Máximo", "Porcentaje", "Nivel"], filas,
          widths=[4.4, 2.6, 2.4, 3.2, 3.4])

    doc.add_paragraph()
    caja(doc, f"Interpretación del {pctT:.1f} %",
         "Describe con precisión el estado del producto: **sólido como artefacto de ingeniería, incompleto como "
         "evidencia científica**. Lo que sostiene el puntaje es la **replicabilidad** (77,8 %): el trabajo es "
         "verificable, versionado y auditable. Lo que lo baja son dos ausencias distintas: **validación estadística** "
         "(sin validación cruzada del modelo elegido) y **validación humana** (ningún usuario o experto externo lo "
         "evaluó). Ninguna invalida los resultados; ambas **limitan el alcance de lo que puede afirmarse** con ellos.")

    # ------------------------------------------------------- ACCIONES -----
    doc.add_paragraph()
    h1(doc, "5.  Acciones para elevar el puntaje")
    parrafo(doc, "Ordenadas por costo. Las de horas y días **no requieren capturar datos nuevos**.")
    tabla(doc, ["Acción", "Sube", "De → a", "Tiempo"],
          [("Publicar los datasets (o un subconjunto) con enlace citable", "2.2", "1 → 3", ("Horas", F_OK)),
           ("Ejecutar validación cruzada sobre el modelo congelado", "1.3", "1 → 3", ("Horas", F_OK)),
           ("Cerrar y actualizar la matriz de trazabilidad de requisitos", "3.3", "1 → 3", ("Horas", F_OK)),
           ("Documentar semillas y determinismo como protocolo explícito", "2.4", "2 → 3", ("Horas", F_OK)),
           ("Completar el manual de implementación técnica", "2.6", "2 → 3", ("1 día", F_AMBER)),
           ("Aplicar un instrumento validado (SUS) con 5–8 evaluadores", "3.1 · 3.2", "0 → 2", ("3–5 días", F_AMBER)),
           ("Repetir la validación operativa para tener más de dos mediciones", "1.5", "2 → 3", ("Días", F_AMBER))],
          widths=[8.6, 2.2, 2.4, 2.8])

    proy = T + (3 - 1) + (3 - 1) + (3 - 1) + (3 - 2)
    doc.add_paragraph()
    caja(doc, "Proyección realista",
         f"Ejecutando solo las acciones de **horas**, el puntaje pasaría de **{T}/{M} ({pctT:.1f} %)** a "
         f"**{proy}/{M} ({100*proy/M:.1f} %)** sin experimentación nueva. Añadiendo el manual técnico y la "
         f"evaluación con usuarios, superaría el **85 %**.")

    # ----------------------------------------------------- CONCLUSIÓN -----
    doc.add_paragraph()
    h1(doc, "6.  Conclusión de la auditoría")
    parrafo(doc, "El producto **está validado como artefacto de ingeniería**: funciona, se midió en operación real "
                 "y sus resultados se pueden reproducir exactamente. Lo que la auditoría expone no son fallos del "
                 "sistema, sino **huecos en la evidencia que lo respalda**: falta validación cruzada, faltan los "
                 "datos publicados y falta que alguien ajeno al equipo lo haya usado.")
    parrafo(doc, "La ventaja es que **la mayor parte de esos huecos se cierra en horas**, porque el material ya "
                 "existe y solo requiere publicarse o ejecutarse. La excepción es la validación con usuarios, que "
                 "exige planificar una sesión con evaluadores externos.")

    OUT.parent.mkdir(parents=True, exist_ok=True)
    doc.save(OUT)
    print(f"Generado: {OUT.relative_to(REPO)}")
    print(f"  Confiabilidad {a[0]}/{a[1]} · Replicabilidad {b[0]}/{b[1]} · Pertinencia {c[0]}/{c[1]}")
    print(f"  TOTAL {T}/{M} = {pctT:.1f} %   (proyección tras acciones de horas: {100*proy/M:.1f} %)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
