#!/usr/bin/env python3
"""Servidor MCP para bibliografia del PPI.

Dos fuentes, en este orden de preferencia:

  1. ARCHIVO EXPORTADO (BibTeX o RIS). No necesita credenciales, red ni
     autorizacion: funciona en cuanto exista el archivo. Es la via recomendada.
  2. API de Mendeley (api.mendeley.com) con OAuth2. Requiere registrar una
     aplicacion en dev.mendeley.com y autorizar una vez.

Herramientas expuestas:
  biblio_estado          que fuente esta disponible y cuantas entradas hay
  biblio_buscar          busca por autor, titulo, ano o palabra clave
  biblio_formatear_ieee  devuelve una o varias entradas en estilo IEEE
  biblio_pendientes      lee las citas sin resolver del PPI y las cruza
  biblio_verificar_doi   comprueba que un DOI resuelve y a que articulo

Nada se inventa: si una entrada no tiene DOI, se dice; si una cita no encuentra
correspondencia, se marca como no resuelta.
"""
from __future__ import annotations

import json
import os
import re
import sys
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any

from mcp.server.mcpserver import MCPServer

REPO = Path(__file__).resolve().parents[2]
EXPORT = Path(os.environ.get("MENDELEY_EXPORT", REPO / "docs/entregables/05-ppi/biblioteca.bib"))
API = "https://api.mendeley.com"
TOKEN = os.environ.get("MENDELEY_TOKEN", "")

app = MCPServer("mendeley-ppi",
                instructions="Bibliografía del PPI: biblioteca exportada de Mendeley "
                             "o API. Ninguna referencia se inventa; las que no tienen "
                             "DOI o correspondencia se marcan como tales.")


# --------------------------------------------------------------- BibTeX ----
ACENTOS = {'\\"a': "ä", '\\"e': "ë", '\\"i': "ï", '\\"o': "ö", '\\"u': "ü",
           "\\'a": "á", "\\'e": "é", "\\'i": "í", "\\'o": "ó", "\\'u": "ú",
           "\\`a": "à", "\\`e": "è", "\\~n": "ñ", "\\^a": "â", "\\^e": "ê",
           "\\c c": "ç", "\\ss": "ß"}


def _latex(t: str) -> str:
    """Traduce las secuencias de LaTeX que Mendeley exporta en los nombres."""
    for k, v in ACENTOS.items():
        t = t.replace("{" + k + "}", v).replace(k + "{}", v).replace(k, v)
    return t.replace("{", "").replace("}", "").replace("\\&", "&").strip()


def _campos(cuerpo: str) -> dict[str, str]:
    """Analizador con conteo de llaves.

    Una expresion regular no basta: los valores contienen llaves anidadas
    —{Sch{\\"o}lkopf}— y comas dentro de los titulos, asi que hay que recorrer
    el texto llevando la cuenta de profundidad.
    """
    campos: dict[str, str] = {}
    i, n = 0, len(cuerpo)
    while i < n:
        while i < n and cuerpo[i] in " \t\r\n,":
            i += 1
        j = i
        while j < n and (cuerpo[j].isalnum() or cuerpo[j] in "_-"):
            j += 1
        clave = cuerpo[i:j].strip().lower()
        while j < n and cuerpo[j] in " \t":
            j += 1
        if not clave or j >= n or cuerpo[j] != "=":
            break
        j += 1
        while j < n and cuerpo[j] in " \t\r\n":
            j += 1
        if j >= n:
            break
        if cuerpo[j] in "{\"":
            cierre = "}" if cuerpo[j] == "{" else "\""
            prof, k = 1, j + 1
            while k < n and prof:
                if cuerpo[k] == "{":
                    prof += 1
                elif cuerpo[k] == cierre or (cierre == "}" and cuerpo[k] == "}"):
                    prof -= 1
                    if not prof:
                        break
                k += 1
            valor, i = cuerpo[j + 1:k], k + 1
        else:                                    # valor sin delimitar
            k = j
            while k < n and cuerpo[k] not in ",\n":
                k += 1
            valor, i = cuerpo[j:k], k
        campos[clave] = _latex(" ".join(valor.split()))
    return campos


def leer_bibtex(ruta: Path) -> list[dict[str, Any]]:
    if not ruta.exists():
        return []
    texto = ruta.read_text(encoding="utf-8", errors="ignore")
    entradas = []
    for m in re.finditer(r'@(\w+)\s*\{\s*([^,]+),(.*?)\n\}', texto, re.S):
        c = _campos(m.group(3))
        c["_tipo"] = m.group(1).lower()
        c["_clave"] = m.group(2).strip()
        entradas.append(c)
    return entradas


def leer_ris(ruta: Path) -> list[dict[str, Any]]:
    if not ruta.exists():
        return []
    MAPA = {"TI": "title", "T1": "title", "AU": "author", "PY": "year",
            "Y1": "year", "JO": "journal", "T2": "journal", "JF": "journal",
            "VL": "volume", "IS": "number", "SP": "pages", "DO": "doi",
            "UR": "url", "TY": "_tipo"}
    entradas, actual = [], {}
    for linea in ruta.read_text(encoding="utf-8", errors="ignore").splitlines():
        m = re.match(r"^([A-Z][A-Z0-9])\s+-\s*(.*)$", linea)
        if not m:
            continue
        etq, val = m.group(1), m.group(2).strip()
        if etq == "ER":
            if actual:
                entradas.append(actual)
            actual = {}
            continue
        clave = MAPA.get(etq)
        if not clave:
            continue
        if clave == "author" and clave in actual:
            actual[clave] += " and " + val
        else:
            actual.setdefault(clave, val)
    if actual:
        entradas.append(actual)
    return entradas


def cargar() -> tuple[list[dict[str, Any]], str]:
    """Devuelve (entradas, descripcion de la fuente)."""
    for ruta in (EXPORT, EXPORT.with_suffix(".ris")):
        if ruta.exists():
            ent = leer_bibtex(ruta) if ruta.suffix == ".bib" else leer_ris(ruta)
            if ent:
                return ent, f"archivo exportado: {ruta.name} ({len(ent)} entradas)"
    if TOKEN:
        try:
            return desde_api(), "API de Mendeley"
        except Exception as exc:                                  # noqa: BLE001
            return [], f"API de Mendeley no disponible: {exc}"
    return [], "sin fuente: no hay export ni token"


def desde_api() -> list[dict[str, Any]]:
    req = urllib.request.Request(
        f"{API}/documents?limit=500&view=bib",
        headers={"Authorization": f"Bearer {TOKEN}",
                 "Accept": "application/vnd.mendeley-document.1+json"})
    with urllib.request.urlopen(req, timeout=25) as r:
        docs = json.load(r)
    out = []
    for d in docs:
        out.append({
            "title": d.get("title", ""),
            "author": " and ".join(
                f"{a.get('last_name','')}, {a.get('first_name','')}".strip(", ")
                for a in d.get("authors", [])),
            "year": str(d.get("year", "")),
            "journal": d.get("source", ""),
            "volume": str(d.get("volume", "")),
            "number": str(d.get("issue", "")),
            "pages": d.get("pages", ""),
            "doi": (d.get("identifiers") or {}).get("doi", ""),
            "_tipo": d.get("type", ""),
        })
    return out


# ------------------------------------------------------------------ IEEE ----
def iniciales(nombre: str) -> str:
    nombre = nombre.strip()
    if "," in nombre:
        apellido, resto = [x.strip() for x in nombre.split(",", 1)]
    else:
        partes = nombre.split()
        apellido, resto = (partes[-1], " ".join(partes[:-1])) if partes else ("", "")
    def inicial(parte: str) -> str:
        # los nombres compuestos con guion conservan ambas iniciales: Zhi-Hua -> Z.-H.
        return "-".join(f"{t[0]}." for t in parte.split("-") if t)

    ini = " ".join(inicial(p) for p in resto.split() if p)
    return f"{ini} {apellido}".strip()


def a_ieee(e: dict[str, Any], n: int | None = None) -> str:
    autores = [iniciales(a) for a in re.split(r"\s+and\s+", e.get("author", "")) if a.strip()]
    if len(autores) > 6:
        firma = ", ".join(autores[:6]) + " et al."
    elif len(autores) > 1:
        firma = ", ".join(autores[:-1]) + " y " + autores[-1]
    else:
        firma = autores[0] if autores else "[autor sin registrar]"
    partes = [firma, f"“{e.get('title','[título sin registrar]')}”"]
    if e.get("journal"):
        partes.append(e["journal"])
    if e.get("volume"):
        partes.append(f"vol. {e['volume']}")
    if e.get("number"):
        partes.append(f"n.º {e['number']}")
    if e.get("pages"):
        partes.append(f"pp. {e['pages'].replace('--', '–')}")
    if e.get("year"):
        partes.append(str(e["year"]))
    ref = ", ".join(partes) + "."
    if e.get("doi"):
        ref += f" doi: {e['doi']}"
    else:
        ref += "  ⚠️ sin DOI en la fuente"
    return f"[{n}] {ref}" if n else ref


# ------------------------------------------------------------ herramientas --
@app.tool(description="Indica qué fuente bibliográfica está disponible (archivo exportado de "
                      "Mendeley o API) y cuántas entradas contiene, con y sin DOI.")
def biblio_estado() -> str:
    entradas, fuente = cargar()
    con_doi = sum(1 for e in entradas if e.get("doi"))
    txt = (f"Fuente: {fuente}\n"
           f"Entradas: {len(entradas)}\n"
           f"Con DOI: {con_doi} · sin DOI: {len(entradas) - con_doi}")
    if not entradas:
        txt += ("\n\nPara usar un export: guarda la biblioteca de Mendeley como BibTeX en\n"
                f"  {EXPORT}\n"
                "Para usar la API: exporta MENDELEY_TOKEN con un token de dev.mendeley.com.")
    return txt


@app.tool(description="Busca entradas de la biblioteca por autor, título, año o palabra clave.")
def biblio_buscar(consulta: str) -> str:
    entradas, fuente = cargar()
    q = (consulta or "").lower()
    hits = [e for e in entradas if not q or q in json.dumps(e, ensure_ascii=False).lower()]
    if not hits:
        return f"Sin coincidencias para «{consulta}». Fuente: {fuente}"
    return "\n".join(
        f"· {e.get('author','?')[:45]} ({e.get('year','?')}) — {e.get('title','?')[:70]}"
        f"{'  [DOI]' if e.get('doi') else '  [sin DOI]'}" for e in hits[:40])


@app.tool(description="Devuelve entradas en estilo IEEE numerado, listas para pegar en el PPI. "
                      "Marca explícitamente las que no tienen DOI en vez de omitirlo.")
def biblio_formatear_ieee(consulta: str = "", desde: int = 1) -> str:
    entradas, fuente = cargar()
    q = (consulta or "").lower()
    hits = [e for e in entradas if not q or q in json.dumps(e, ensure_ascii=False).lower()]
    if not hits:
        return f"Sin coincidencias para «{consulta}». Fuente: {fuente}"
    return "\n\n".join(a_ieee(e, desde + i) for i, e in enumerate(hits))


@app.tool(description="Cruza las citas del PPI que siguen sin resolver con la biblioteca "
                      "disponible e indica cuáles tienen correspondencia y cuáles no.")
def biblio_pendientes() -> str:
    entradas, fuente = cargar()
    pend = ["Vempati", "Agyemang", "Smolen", "Benová", "Islam", "Ness",
            "Bryant", "Saiedian", "Roumani", "Peled"]
    lineas = [f"Fuente: {fuente}", ""]
    resueltas = 0
    for autor in pend:
        m = [e for e in entradas if autor.lower() in e.get("author", "").lower()]
        if m:
            resueltas += 1
            lineas.append(f"✔ {autor}: {a_ieee(m[0])}")
        else:
            lineas.append(f"✘ {autor}: sin correspondencia en la biblioteca")
    lineas += ["", f"Resueltas {resueltas} de {len(pend)}."]
    return "\n".join(lineas)


@app.tool(description="Comprueba que un DOI resuelve y devuelve el artículo al que apunta. "
                      "Usar SIEMPRE antes de incorporar una referencia.")
def biblio_verificar_doi(doi: str) -> str:
    doi = (doi or "").strip().replace("https://doi.org/", "")
    try:
        req = urllib.request.Request(
            f"https://doi.org/{urllib.parse.quote(doi)}",
            headers={"Accept": "application/vnd.citationstyles.csl+json"})
        with urllib.request.urlopen(req, timeout=20) as r:
            d = json.load(r)
        autores = ", ".join(f"{a.get('given','')} {a.get('family','')}".strip()
                            for a in d.get("author", []))
        año = (d.get("issued", {}).get("date-parts") or [[None]])[0][0]
        return (f"DOI válido: {doi}\n"
                f"Título : {d.get('title')}\n"
                f"Autores: {autores}\n"
                f"Fuente : {d.get('container-title')} ({año})\n"
                f"Páginas: {d.get('page','—')}  ·  vol. {d.get('volume','—')}")
    except Exception as exc:                                      # noqa: BLE001
        return (f"DOI NO verificado: {doi}\nMotivo: {exc}\n"
                "No usar esta referencia hasta comprobarla.")


if __name__ == "__main__":
    app.run(transport="stdio")
