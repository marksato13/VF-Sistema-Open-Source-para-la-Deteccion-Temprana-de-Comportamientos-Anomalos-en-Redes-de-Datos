#!/usr/bin/env python3
"""Matriz de decision de revistas (Sesion 04).

Cada celda lleva su fuente y su estado de verificacion. Los puntajes se
calculan; no se escriben a mano. Un dato sin fuente primaria se marca como
pendiente en vez de presentarse como verificado.

Formula del complemento:  aporte = puntaje x peso / 10   (total sobre 100)

    python3 scripts/entregables/generar_matriz_revistas.py
"""
from __future__ import annotations
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
OUT_MD = REPO / "docs/entregables/09-matriz-revistas/matriz-decision-revistas.md"
FECHA = "26 de agosto de 2026"

# (clave, nombre, peso, regla de puntuacion)
CRITERIOS = [
    ("pertinencia", "Pertinencia temática", 30,
     "Coincidencia entre el alcance editorial declarado y el problema, método y dominio del artículo"),
    ("visibilidad", "Visibilidad bibliométrica", 25,
     "CiteScore, percentil y cuartil SJR identificados por separado, con su fuente"),
    ("viabilidad", "Viabilidad editorial", 20,
     "Tipo de revisión, tiempo declarado, periodicidad y capacidad de publicación"),
    ("costo", "Costo y accesibilidad", 15,
     "APC vigente, cargos por página y acceso abierto"),
    ("formato", "Compatibilidad formal", 10,
     "Plantilla, límite de páginas y requisitos de envío"),
]

# ✔ = verificado en fuente primaria · ~ = fuente secundaria · ? = pendiente
CANDIDATAS = [
    {
        "nombre": "Bulletin of Electrical Engineering and Informatics (BEEI)",
        "corto": "BEEI", "editor": "IAES · Indonesia", "issn": "2089-3191",
        "scopus": "https://www.scopus.com/sourceid/21100826382",
        "filtro": ("Supera", "ISSN confirmado, ficha activa en Scopus, política de revisión por pares "
                             "publicada, archivo de números con DOI, APC transparente y editor "
                             "identificable. Fuera de la lista de revistas depredadoras consultada"),
        "datos": {
            "CiteScore 2025": ("4,2 · percentil 65 en Computer Networks and Communications", "✔"),
            "Cuartil SJR": ("Q3 · la revista declara además Q1 por CiteScore", "~"),
            "Revisión": ("Single-blind, ≥2 revisores; 8–12 semanas declaradas", "✔"),
            "Periodicidad": ("Bimestral · 76 artículos en el número de agosto de 2026", "✔"),
            "APC": ("USD 415 hasta 8 páginas · USD 50 por página adicional · USD 830 si es autor único", "✔"),
            "Plantilla": ("DOCX oficial disponible", "✔"),
        },
        "puntajes": {
            "pertinencia": (9, "Su alcance declara explícitamente redes de comunicaciones, seguridad de "
                               "redes, aprendizaje automático y ciberseguridad: los cuatro ejes del artículo"),
            "visibilidad": (8, "CiteScore 4,2 y percentil 65, el más alto de las candidatas verificadas"),
            "viabilidad": (9, "Bimestral con 76 artículos por número: alta capacidad y ciclo declarado corto"),
            "costo": (8, "USD 415 con coautoría, el más bajo de las candidatas con APC"),
            "formato": (7, "Plantilla disponible, pero el límite base de 8 páginas obliga a comprimir o "
                           "a pagar por página adicional"),
        },
    },
    {
        "nombre": "International Journal of Safety and Security Engineering (IJSSE)",
        "corto": "IJSSE", "editor": "IIETA · Canadá", "issn": "2041-904X",
        "scopus": "https://www.scopus.com/sourceid/21100785501",
        "filtro": ("Supera", "ISSN confirmado, ficha activa en Scopus, revisión double-blind declarada, "
                             "archivo de números con DOI y página oficial de APC. Fuera de la lista de "
                             "revistas depredadoras consultada"),
        "datos": {
            "CiteScore 2025": ("2,8 · percentil 60 en Safety, Risk, Reliability and Quality", "✔"),
            "Cuartil SJR": ("Q3", "~"),
            "Revisión": ("Double-blind, ≥2 expertos independientes; ~2 meses", "✔"),
            "Periodicidad": ("12 números regulares al año · 20 artículos en el número de julio de 2026", "✔"),
            "APC": ("USD 850 por artículo aceptado, sin cargo por página", "✔"),
            "Plantilla": ("DOCX oficial disponible", "✔"),
        },
        "puntajes": {
            "pertinencia": (9, "Declara seguridad informática, evaluación de amenazas, ciberseguridad y "
                               "protección de infraestructura crítica; publica de forma habitual detección "
                               "de intrusiones con aprendizaje automático"),
            "visibilidad": (6, "CiteScore 2,8 y percentil 60: por debajo de BEEI en ambos indicadores"),
            "viabilidad": (9, "Doce números al año y revisión double-blind de unos dos meses"),
            "costo": (5, "USD 850, el doble que BEEI"),
            "formato": (8, "Plantilla disponible y sin límite estrecho de páginas declarado"),
        },
    },
    {
        "nombre": "Information Security Journal: A Global Perspective",
        "corto": "ISJ", "editor": "Taylor & Francis · Reino Unido", "issn": "1939-3555",
        "scopus": "https://www.scopus.com/sourceid/19700187807",
        "filtro": ("Supera", "Editorial de trayectoria reconocida, ficha activa en Scopus e indexación "
                             "adicional en ESCI. Fuera de la lista de revistas depredadoras consultada"),
        "datos": {
            "CiteScore 2025": ("pendiente de verificar en la ficha de Scopus", "?"),
            "Cuartil SJR": ("Q2 como mejor cuartil · SJR 0,489 · h-index 33", "~"),
            "Revisión": ("pendiente de verificar en las instrucciones para autores", "?"),
            "Periodicidad": ("6 números al año · 21 artículos en el volumen 34 (2025)", "~"),
            "APC": ("Híbrida: publicar por la vía de suscripción no exige APC", "~"),
            "Plantilla": ("pendiente de verificar", "?"),
        },
        "puntajes": {
            "pertinencia": (9, "Su alcance nombra seguridad de redes y control de acceso; publica trabajos "
                               "sobre ataques SSH y denegación de servicio HTTP, las mismas familias del corpus"),
            "visibilidad": (8, "Mejor cuartil Q2 y h-index 33, el más alto tras Emerald"),
            "viabilidad": (4, "Solo 21 artículos en el volumen 34: capacidad muy limitada y, por tanto, "
                              "probabilidad de aceptación baja"),
            "costo": (10, "Sin APC obligatorio por la vía de suscripción"),
            "formato": (7, "Editorial mayor con formato estándar; requisitos concretos sin verificar"),
        },
    },
    {
        "nombre": "Information and Computer Security",
        "corto": "ICS", "editor": "Emerald · Reino Unido", "issn": "2056-4961",
        "scopus": "https://www.scopus.com/sourceid/21100421900",
        "filtro": ("Supera", "Editorial de trayectoria reconocida y ficha activa en Scopus. Fuera de la "
                             "lista de revistas depredadoras consultada"),
        "datos": {
            "CiteScore 2025": ("pendiente de verificar en la ficha de Scopus", "?"),
            "Cuartil SJR": ("Q2 como mejor cuartil · Q3 en Computer Networks and Communications, "
                            "Information Systems y Software · h-index 60", "~"),
            "Revisión": ("pendiente de verificar", "?"),
            "Periodicidad": ("pendiente de verificar", "?"),
            "APC": ("Híbrida: no exige APC por la vía de suscripción", "~"),
            "Plantilla": ("pendiente de verificar", "?"),
        },
        "puntajes": {
            "pertinencia": (6, "Cubre la categoría de redes, pero su centro editorial se inclina a factores "
                               "humanos, concienciación y cumplimiento de políticas: un artículo puramente "
                               "técnico corre riesgo de quedar fuera de foco"),
            "visibilidad": (9, "h-index 60, el más alto de todas las candidatas"),
            "viabilidad": (5, "Sin datos verificados de tiempo ni periodicidad"),
            "costo": (10, "Sin APC obligatorio por la vía de suscripción"),
            "formato": (6, "Requisitos sin verificar"),
        },
    },
    {
        "nombre": "International Journal of Advanced Computer Science and Applications (IJACSA)",
        "corto": "IJACSA", "editor": "TheSAI · Reino Unido", "issn": "2158-107X",
        "scopus": "https://www.scopus.com/sourceid/21100867241",
        "filtro": ("Supera con reserva", "Ficha activa en Scopus e indexación en WoS ESCI, y fuera de la "
                                         "lista de depredadoras consultada. Se registra que su reputación "
                                         "editorial es más discutida que la de las demás candidatas"),
        "datos": {
            "CiteScore 2025": ("3,4", "~"),
            "Cuartil SJR": ("Q3", "~"),
            "Revisión": ("Doble ciego con al menos tres revisores; decisión en unas 3 semanas", "~"),
            "Periodicidad": ("Mensual, con fecha de cierre fija cada mes", "~"),
            "APC": ("GBP 800 · GBP 750 para estudiantes y revisores", "~"),
            "Plantilla": ("Plantilla propia obligatoria", "~"),
        },
        "puntajes": {
            "pertinencia": (6, "Declara cubrir «todas las ramas de las ciencias de la computación»: alcance "
                               "amplio y por tanto menos específico que las tres primeras"),
            "visibilidad": (8, "CiteScore 3,4 y doble indexación en Scopus y WoS ESCI"),
            "viabilidad": (10, "Mensual y con decisión declarada en unas tres semanas: la más rápida"),
            "costo": (3, "GBP 800, el más alto de todas las candidatas"),
            "formato": (7, "Plantilla propia obligatoria, que exige reformatear"),
        },
    },
]


def total(c) -> float:
    return sum(c["puntajes"][k][0] * peso / 10 for k, _, peso, _ in CRITERIOS)


def completitud(c) -> tuple[int, int]:
    marcas = [m for _, m in c["datos"].values()]
    return marcas.count("✔"), len(marcas)


def main() -> None:
    orden = sorted(CANDIDATAS, key=total, reverse=True)
    L, a = [], lambda s: L.append(s)

    a("# Matriz de decisión de revistas científicas\n\n")
    a(f"**Proyecto:** Sistema open source para la detección temprana de comportamientos "
      f"anómalos en redes de datos\n"
      f"**Autores:** Rubén Mark Salazar Tocas · Uziel Elias Sauñe Fernandez\n"
      f"**Curso:** Investigación V · Sesión 04\n"
      f"**Fecha de consulta de todos los datos:** {FECHA}\n\n")
    a("> **Generada**, no redactada a mano: `scripts/entregables/generar_matriz_revistas.py`.\n"
      "> Los puntajes ponderados se calculan; ninguno se transcribe.\n\n---\n\n")

    a("## 1 · El artículo que se quiere publicar\n\n")
    a("Antes de puntuar hay que saber qué se compara contra cada alcance editorial.\n\n")
    a("| Elemento | En este proyecto |\n|---|---|\n")
    for k, v in [("Problema", "Detección temprana de comportamientos anómalos en redes de datos"),
                 ("Método", "Aprendizaje no supervisado (OCSVM) sobre 28 variables multicapa L3/L4/L7 "
                            "extraídas de telemetría causal"),
                 ("Sistema", "Control inline: bloqueo automático con nftables en el router del laboratorio"),
                 ("Dominio", "Redes, ciberseguridad y protección de infraestructura"),
                 ("Contribución", "Validación de un sistema desplegado, con la brecha medida entre el "
                                  "error de laboratorio (4,71 %) y el de operación (23–26 %)")]:
        a(f"| **{k}** | {v} |\n")

    a("\n---\n\n## 2 · Filtro de legitimidad\n\n")
    a("**La legitimidad no se pondera: es un filtro de entrada.** Una candidata que no lo "
      "supera sale de la matriz por completo, sin importar cuánto puntúe en lo demás.\n\n")
    a("| Revista | Resultado | Evidencia |\n|---|---|---|\n")
    for c in CANDIDATAS:
        a(f"| **{c['corto']}** | {c['filtro'][0]} | {c['filtro'][1]} |\n")
    a("\n### Descartadas por el filtro\n\n")
    a("| Revista | Motivo |\n|---|---|\n")
    for n, m in [("International Journal of Communication Networks and Information Security (IJCNIS)",
                  "**Descontinuada de Scopus desde 2022** y presente en la lista de revistas depredadoras consultada"),
                 ("Indonesian Journal of Electrical Engineering and Computer Science (IJEECS)",
                  "**Descontinuada de Scopus en 2025**"),
                 ("Journal of Cyber Security and Mobility", "Q4 con APC de 1 300 EUR: no compite en ningún criterio"),
                 ("International Journal of Information Security and Privacy", "Q4")]:
        a(f"| {n} | {m} |\n")
    a("\n> Sobre la condición de depredadora: no se afirma una certificación absoluta. Se "
      "declara que cada candidata **supera los filtros documentales aplicados** —ISSN, ficha "
      "de Scopus, política de revisión, archivo con DOI, APC transparente y editor "
      "identificable— y que debe reverificarse antes del envío.\n")

    a("\n---\n\n## 3 · Criterios y pesos\n\n")
    a("| Criterio | Peso | Regla de puntuación |\n|---|---:|---|\n")
    for _, nom, peso, regla in CRITERIOS:
        a(f"| {nom} | {peso} % | {regla} |\n")
    a(f"| **Total** | **{sum(p for _,_,p,_ in CRITERIOS)} %** | |\n")
    a("\n**Fórmula:** `aporte = puntaje × peso / 10`, con puntajes de 0 a 10 y total sobre 100.\n\n")
    a("Ningún criterio supera el 30 %, por debajo del techo del 35–40 % recomendado. La "
      "pertinencia temática pesa más que la visibilidad **a propósito**: un mal encaje "
      "produce rechazo de escritorio por muy alto que sea el cuartil.\n")

    a("\n---\n\n## 4 · Matriz\n\n")
    cab = " | ".join(c["corto"] for c in orden)
    a(f"| Criterio (peso) | {cab} |\n|---|" + "---:|" * len(orden) + "\n")
    for k, nom, peso, _ in CRITERIOS:
        fila = " | ".join(str(c["puntajes"][k][0]) for c in orden)
        a(f"| {nom} ({peso} %) | {fila} |\n")
    a("| **PUNTAJE PONDERADO** | " + " | ".join(f"**{total(c):.1f}**" for c in orden) + " |\n")
    a("| Datos con fuente primaria | " + " | ".join(
        f"{completitud(c)[0]}/{completitud(c)[1]}" for c in orden) + " |\n")

    a("\n---\n\n## 5 · Ficha por candidata\n\n")
    for i, c in enumerate(orden, 1):
        a(f"### {i}. {c['nombre']} — {total(c):.1f} puntos\n\n")
        a(f"`{c['editor']}` · ISSN {c['issn']} · [ficha en Scopus]({c['scopus']})\n\n")
        a("| Dato | Valor | |\n|---|---|:--:|\n")
        for k, (v, m) in c["datos"].items():
            a(f"| {k} | {v} | {m} |\n")
        a("\n| Criterio | Puntaje | Justificación |\n|---|:--:|---|\n")
        for k, nom, _, _ in CRITERIOS:
            p, just = c["puntajes"][k]
            a(f"| {nom} | **{p}** | {just} |\n")
        a("\n")
    a("> `✔` verificado en fuente primaria · `~` fuente secundaria · `?` pendiente\n")

    a("\n---\n\n## 6 · Plan A, B y C\n\n")
    a("> **El orden por debajo del Plan A es provisional.** Solo BEEI e IJSSE tienen sus "
      "datos sensibles verificados en fuente primaria; las otras tres se puntuaron con "
      "fuentes secundarias. Una verificación completa **puede reordenar las posiciones 2 a "
      "5**, y por eso la sección 8 enumera lo que falta comprobar antes del envío.\n>\n"
      "> Se presenta igual, con el orden y sus lagunas a la vista, porque ocultar la "
      "diferencia de verificación entre candidatas sería el error más grave de esta matriz.\n\n")
    for etq, c in zip(("Plan A", "Plan B", "Plan C"), orden[:3]):
        a(f"**{etq} — {c['corto']} ({total(c):.1f})**\n\n")
    a("| | Revista | Puntaje | Por qué en esa posición |\n|---|---|---:|---|\n")
    razones = {
        "BEEI": "Gana en tres de los cinco criterios y es la que más datos tiene **verificados "
                "en fuente primaria** (5 de 6). Mejor combinación de encaje temático, "
                "visibilidad y coste.",
        "ISJ": "Empata en pertinencia con las mejores y **no exige APC**, pero publica solo "
               "21 artículos al año: su bajo puntaje de viabilidad refleja una probabilidad "
               "de aceptación mucho menor.",
        "IJSSE": "Encaje temático idéntico al de BEEI y ciclo editorial rápido, pero pierde "
                 "en visibilidad (CiteScore 2,8 frente a 4,2) y su APC duplica al de BEEI.",
        "ICS": "El mayor prestigio de la lista (h-index 60), pero su centro editorial se "
               "inclina a factores humanos y buena parte de sus datos sigue sin verificar.",
        "IJACSA": "La más rápida de todas, pero de alcance genérico y con el APC más alto.",
    }
    for etq, c in zip(("**Plan A**", "**Plan B**", "**Plan C**", "4.º", "5.º"), orden):
        a(f"| {etq} | {c['corto']} | {total(c):.1f} | {razones[c['corto']]} |\n")

    a("\n---\n\n## 7 · Justificación\n\n")
    p, s_, t_ = orden[0], orden[1], orden[2]
    v, n = completitud(p)
    a(f"**{p['corto']} es el Plan A** porque obtiene el puntaje ponderado más alto "
      f"({total(p):.1f} sobre 100) y, sobre todo, porque es la candidata con más datos "
      f"verificados en fuente primaria ({v} de {n}). Su alcance editorial nombra de "
      "forma explícita los cuatro ejes del artículo —redes de comunicaciones, seguridad de "
      "redes, aprendizaje automático y ciberseguridad—, presenta el CiteScore y el percentil "
      "más altos del conjunto (4,2 y 65) y su APC de USD 415 con coautoría es el más bajo "
      "entre las revistas que cobran.\n\n")
    a(f"**No se eligió {s_['corto']}** pese a no exigir APC: publica solo 21 artículos al "
      "año, de modo que su capacidad —y por tanto la probabilidad de aceptación— es "
      "sustancialmente menor. Se conserva como Plan B precisamente porque su coste nulo la "
      "hace la mejor alternativa si el presupuesto desaparece.\n\n")
    a(f"**No se eligió {t_['corto']}** aunque su encaje temático es equivalente: pierde en "
      "visibilidad bibliométrica y su APC duplica al del Plan A, sin ofrecer a cambio una "
      "ventaja editorial que lo compense.\n\n")
    a("La decisión **no se tomó por cuartil**. Si la visibilidad hubiera pesado el 70 %, como "
      "es habitual, el orden habría sido otro y se habría perseguido prestigio a costa del "
      "encaje y del plazo. Aquí la pertinencia temática pesa más que la visibilidad porque un "
      "mal encaje produce rechazo de escritorio antes de llegar a revisión.\n")

    a("\n---\n\n## 8 · Pendientes antes del envío\n\n")
    a("Esta matriz **no debe usarse tal cual el día del envío**. Falta:\n\n")
    for x in ["Verificar el **cuartil SJR** de las cinco candidatas en Scimago. Aquí figura "
              "como fuente secundaria: **el percentil de Scopus no es el cuartil SJR**, y "
              "confundirlos invalidaría el criterio de visibilidad.",
              "Completar en fuente primaria los datos marcados con `?` en ISJ, ICS e IJACSA: "
              "CiteScore, tipo y tiempo de revisión, periodicidad y plantilla.",
              "Reverificar el APC de las cinco: cambia sin aviso. El de IJSSE ya pasó de "
              "USD 700 a USD 850 entre dos consultas.",
              "Confirmar por escrito con la coordinación académica el requisito exacto de "
              "cuartil o índice del programa: es un **filtro**, no un criterio ponderado.",
              "Comprobar que la extensión del artículo cabe en el límite base de 8 páginas de "
              "BEEI, o presupuestar el coste por página adicional."]:
        a(f"- {x}\n")

    OUT_MD.parent.mkdir(parents=True, exist_ok=True)
    OUT_MD.write_text("".join(L), encoding="utf-8")
    print(f"Generado: {OUT_MD.relative_to(REPO)}")
    for c in orden:
        v, n = completitud(c)
        print(f"  {c['corto']:8} {total(c):5.1f}   datos primarios {v}/{n}")


# ================================================================= WORD =====
def generar_word() -> None:
    """Version PRECISA para el docente: matriz + justificacion, ~3 paginas."""
    import sys
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    from _docx_estilo import rematar, bloque_enlaces
    from docx import Document
    from docx.enum.table import WD_TABLE_ALIGNMENT
    from docx.enum.text import WD_ALIGN_PARAGRAPH
    from docx.oxml import OxmlElement
    from docx.oxml.ns import qn
    from docx.shared import Cm, Pt, RGBColor

    OUT = REPO / "docs/entregables/09-matriz-revistas/Matriz-decision-revistas.docx"
    LOGO = REPO / "docs/entregables/assets/logo-upeu.png"
    if not LOGO.exists():
        raise SystemExit(f"falta el logo: {LOGO}")
    INK, DIM = RGBColor(0x13, 0x1B, 0x2E), RGBColor(0x5B, 0x6B, 0x8C)
    AZUL, WHITE = RGBColor(0x1F, 0x4E, 0x79), RGBColor(0xFF, 0xFF, 0xFF)
    F_HEAD, F_ZEBRA, F_OK, F_AMBER = "1F4E79", "EEF3FA", "E0F3E6", "FDECD2"

    def shade(c, h):
        e = OxmlElement("w:shd"); e.set(qn("w:val"), "clear"); e.set(qn("w:fill"), h)
        c._tc.get_or_add_tcPr().append(e)

    doc = Document()
    s = doc.sections[0]
    s.top_margin = s.bottom_margin = Cm(1.4); s.left_margin = s.right_margin = Cm(1.6)
    doc.styles["Normal"].font.name = "Calibri"

    def par(txt, size=8.8, bold=False, italic=False, color=INK, after=4,
            align=WD_ALIGN_PARAGRAPH.JUSTIFY):
        p = doc.add_paragraph(); p.alignment = align
        p.paragraph_format.space_after = Pt(after)
        for i, t in enumerate(txt.split("**")):
            r = p.add_run(t); r.font.size = Pt(size); r.font.color.rgb = color
            r.font.italic = italic; r.font.bold = bold or i % 2 == 1
        return p

    def h1(txt):
        p = doc.add_paragraph()
        p.paragraph_format.space_before = Pt(9); p.paragraph_format.space_after = Pt(3)
        r = p.add_run(txt); r.font.size = Pt(11.5); r.font.bold = True; r.font.color.rgb = AZUL

    def tabla(cab, filas, anchos, fondos=None):
        t = doc.add_table(rows=1, cols=len(cab)); t.alignment = WD_TABLE_ALIGNMENT.CENTER
        t.autofit = False
        for c, (txt, w) in enumerate(zip(cab, anchos)):
            cell = t.rows[0].cells[c]; cell.width = Cm(w); cell.text = ""
            r = cell.paragraphs[0].add_run(txt)
            r.font.bold = True; r.font.size = Pt(8); r.font.color.rgb = WHITE
            shade(cell, F_HEAD)
        for i, fila in enumerate(filas):
            row = t.add_row()
            for c, txt in enumerate(fila):
                cell = row.cells[c]; cell.width = Cm(anchos[c]); cell.text = ""
                p = cell.paragraphs[0]; p.paragraph_format.space_after = Pt(1)
                for k, tr in enumerate(str(txt).split("**")):
                    r = p.add_run(tr); r.font.size = Pt(7.8); r.font.bold = k % 2 == 1
                    r.font.color.rgb = INK
            if fondos and i < len(fondos) and fondos[i]:
                for cell in row.cells: shade(cell, fondos[i])
            elif i % 2 == 0:
                for cell in row.cells: shade(cell, F_ZEBRA)
        doc.add_paragraph().paragraph_format.space_after = Pt(2)

    doc.add_picture(str(LOGO), width=Cm(4.4))
    doc.paragraphs[-1].alignment = WD_ALIGN_PARAGRAPH.CENTER
    for txt, sz, col, b in [("Universidad Peruana Unión", 10, INK, True),
                            ("E.P. de Ingeniería de Sistemas · Investigación V · Sesión 04", 8.2, DIM, False)]:
        p = doc.add_paragraph(); p.alignment = WD_ALIGN_PARAGRAPH.CENTER
        p.paragraph_format.space_after = Pt(1)
        r = p.add_run(txt); r.font.size = Pt(sz); r.font.color.rgb = col; r.font.bold = b
    p = doc.add_paragraph(); p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p.paragraph_format.space_before = Pt(6); p.paragraph_format.space_after = Pt(2)
    r = p.add_run("MI DECISIÓN FINAL: REVISTA OBJETIVO Y PLAN DE RESPALDO")
    r.font.size = Pt(13.5); r.font.bold = True; r.font.color.rgb = AZUL
    par("Rubén Mark Salazar Tocas · Uziel Elias Sauñe Fernandez  ·  Datos consultados el "
        + FECHA, size=8.4, color=DIM, after=8, align=WD_ALIGN_PARAGRAPH.CENTER)

    h1("1 · Filtro de legitimidad, aplicado antes de puntuar")
    par("La legitimidad **no se pondera: es un filtro de entrada**. Una candidata que no lo "
        "supera sale de la matriz por completo, sin importar cuánto puntúe en lo demás.")
    tabla(["Revista", "Resultado", "Evidencia documental"],
          [[c["corto"], c["filtro"][0], c["filtro"][1]] for c in CANDIDATAS],
          [2.4, 3.0, 12.4])
    par("**Descartadas por el filtro:** IJCNIS, descontinuada de Scopus desde 2022 y presente "
        "en la lista de revistas depredadoras consultada; IJEECS, descontinuada de Scopus en "
        "2025; y dos revistas Q4 que no compiten en ningún criterio.", size=8.2, italic=True,
        color=DIM)

    h1("2 · Criterios y pesos")
    tabla(["Criterio", "Peso", "Regla de puntuación"],
          [[n, f"{p} %", r] for _, n, p, r in CRITERIOS], [4.0, 1.6, 12.2])
    par("**Fórmula:** aporte = puntaje × peso / 10, con puntajes de 0 a 10 y total sobre 100. "
        "Ningún criterio supera el 30 %, por debajo del techo del 35–40 % recomendado. La "
        "pertinencia pesa más que la visibilidad **a propósito**: un mal encaje temático "
        "produce rechazo de escritorio por muy alto que sea el cuartil.", size=8.2)

    h1("3 · Matriz de decisión")
    orden = sorted(CANDIDATAS, key=total, reverse=True)
    filas = [[f"{n} ({p} %)"] + [str(c["puntajes"][k][0]) for c in orden]
             for k, n, p, _ in CRITERIOS]
    filas.append(["PUNTAJE PONDERADO"] + [f"**{total(c):.1f}**" for c in orden])
    filas.append(["Datos con fuente primaria"] + [f"{completitud(c)[0]}/{completitud(c)[1]}"
                                                  for c in orden])
    tabla(["Criterio (peso)"] + [c["corto"] for c in orden], filas,
          [5.4] + [2.5] * len(orden),
          fondos=[None] * len(CRITERIOS) + [F_OK, F_AMBER])

    h1("4 · Plan A, B y C")
    razones = {
        "BEEI": "Gana en tres de los cinco criterios y es la que más datos tiene verificados en "
                "fuente primaria. Mejor combinación de encaje, visibilidad y coste.",
        "ISJ": "Empata en pertinencia y **no exige APC**, pero publica solo 21 artículos al año: "
               "capacidad y probabilidad de aceptación mucho menores.",
        "IJSSE": "Encaje idéntico al de BEEI y ciclo rápido, pero menor visibilidad (CiteScore "
                 "2,8 frente a 4,2) y APC del doble.",
        "ICS": "El mayor prestigio (h-index 60), pero su centro editorial se inclina a factores "
               "humanos y sus datos siguen sin verificar.",
        "IJACSA": "La más rápida, pero de alcance genérico y con el APC más alto.",
    }
    tabla(["", "Revista", "Puntaje", "Por qué en esa posición"],
          [[e, c["corto"], f"{total(c):.1f}", razones[c["corto"]]]
           for e, c in zip(("Plan A", "Plan B", "Plan C", "4.º", "5.º"), orden)],
          [1.8, 2.4, 1.8, 11.8], fondos=[F_OK, None, None, None, None])
    par("**El orden por debajo del Plan A es provisional.** Solo BEEI e IJSSE tienen sus datos "
        "sensibles verificados en fuente primaria; las otras tres se puntuaron con fuentes "
        "secundarias, y una verificación completa puede reordenar las posiciones 2 a 5.",
        size=8.2, italic=True, color=DIM)

    h1("5 · Justificación")
    v, n = completitud(orden[0])
    par(f"**BEEI es el Plan A** porque obtiene el puntaje ponderado más alto ({total(orden[0]):.1f} "
        f"sobre 100) y porque es la candidata con más datos verificados en fuente primaria "
        f"({v} de {n}). Su alcance editorial nombra de forma explícita los cuatro ejes del "
        "artículo —redes de comunicaciones, seguridad de redes, aprendizaje automático y "
        "ciberseguridad—, presenta el CiteScore y el percentil más altos del conjunto (4,2 y "
        "65) y su APC de USD 415 con coautoría es el más bajo entre las revistas que cobran.")
    par("**No se eligió ISJ** pese a no exigir APC: publica solo 21 artículos al año, de modo "
        "que su probabilidad de aceptación es sustancialmente menor. Se conserva como Plan B "
        "porque su coste nulo la vuelve la mejor alternativa si desaparece el presupuesto. "
        "**No se eligió IJSSE** aunque su encaje temático es equivalente: pierde en visibilidad "
        "y su APC duplica al del Plan A, sin una ventaja editorial que lo compense.")
    par("La decisión **no se tomó por cuartil**. Si la visibilidad hubiera pesado el 70 %, como "
        "es habitual, el orden habría sido otro y se habría perseguido prestigio a costa del "
        "encaje y del plazo.", italic=True)

    h1("6 · Pendientes antes del envío")
    par("Verificar el **cuartil SJR** de las cinco en Scimago: aquí figura como fuente "
        "secundaria, y **el percentil de Scopus no es el cuartil SJR**. · Completar en fuente "
        "primaria los datos de ISJ, ICS e IJACSA. · Reverificar el APC de las cinco: el de "
        "IJSSE pasó de USD 700 a USD 850 entre dos consultas. · Confirmar por escrito con la "
        "coordinación académica el requisito de cuartil del programa, que es un **filtro** y no "
        "un criterio ponderado. · Comprobar que el artículo cabe en el límite base de 8 páginas "
        "de BEEI.", size=8.2)

    bloque_enlaces(doc, "Evidencia en el repositorio", [
        ("Matriz detallada, con la ficha completa de cada candidata",
         "docs/entregables/09-matriz-revistas/matriz-decision-revistas.md"),
        ("Mapeo por secciones de 10 artículos de las dos primeras candidatas",
         "docs/articulo/README.md"),
    ])
    rematar(doc, "Matriz de decisión de revistas",
            "Investigación V · Sesión 04 · Revista objetivo y plan de respaldo",
            "Matriz de decisión de revistas · Salazar Tocas & Sauñe Fernandez",
            "Investigación V · Sesión 04 · UPeU")
    doc.save(OUT)
    print(f"Generado: {OUT.relative_to(REPO)}")


if __name__ == "__main__":
    main()
    generar_word()
