# Servidor MCP de bibliografía

Ayuda a completar las referencias del PPI sin inventar ninguna.

## Antes que nada: qué NO es

**No hay una integración mágica con Mendeley.** La API de Mendeley exige
registrar una aplicación y autorizarla; no existe forma de leer tu biblioteca
sin que tú des ese paso. Por eso este servidor tiene **dos fuentes**, y la
recomendada no necesita credenciales.

## Vía recomendada: exportar la biblioteca

En Mendeley Reference Manager: seleccionar las referencias →
**File ▸ Export** → formato **BibTeX** → guardar como:

```
docs/entregables/05-ppi/biblioteca.bib
```

Con eso el servidor funciona. Sin red, sin OAuth, sin token. También acepta
**RIS** (`biblioteca.ris`).

> El archivo `.bib` **no se versiona**: es la biblioteca personal del autor y
> puede contener material con derechos. Está en `.gitignore`.

## Vía alternativa: la API

1. Registrar una aplicación en `dev.mendeley.com`.
2. Obtener un token de acceso.
3. Exportarlo antes de abrir la sesión:

```bash
export MENDELEY_TOKEN="…"
```

El servidor la usa solo si **no** encuentra un archivo exportado.

## Herramientas

| Herramienta | Qué hace |
|---|---|
| `biblio_estado` | Qué fuente hay disponible, cuántas entradas y cuántas con DOI |
| `biblio_buscar` | Busca por autor, título, año o palabra clave |
| `biblio_formatear_ieee` | Devuelve entradas en IEEE numerado, listas para pegar |
| `biblio_pendientes` | Cruza las citas sin resolver del PPI con la biblioteca |
| `biblio_verificar_doi` | Comprueba que un DOI **resuelve** y a qué artículo |

## La regla que gobierna el servidor

**Nada se inventa.**

- Una entrada sin DOI se marca con `⚠️ sin DOI en la fuente`, no se omite el
  campo como si no hiciera falta.
- Una cita sin correspondencia se marca `✘ sin correspondencia`, no se rellena
  con la referencia más parecida.
- `biblio_verificar_doi` sobre un DOI inexistente responde **«No usar esta
  referencia hasta comprobarla»**, no un error silencioso.

Es deliberado: en una bibliografía, una entrada plausible pero falsa hace más
daño que una ausencia declarada.

## Detalles de implementación

**El analizador de BibTeX cuenta llaves, no usa expresiones regulares.** Una
expresión regular falla con valores anidados como `{Sch{\"o}lkopf}` y con las
comas dentro de los títulos: la primera versión de este servidor se tragaba
`volume`, `number`, `pages` y `year` en un solo campo.

**Traduce las secuencias de LaTeX** que Mendeley exporta en los nombres
(`Sch{\"o}lkopf` → `Schölkopf`) y **conserva las iniciales compuestas**
(`Zhi-Hua` → `Z.-H.`), que es como las escribe IEEE.

## Comprobar que funciona

```bash
.venv/bin/python mcp-servers/mendeley/servidor.py   # arranca en stdio
```

En la sesión, la primera llamada útil es `biblio_estado`: dice si encuentra
biblioteca y, si no, qué falta.
