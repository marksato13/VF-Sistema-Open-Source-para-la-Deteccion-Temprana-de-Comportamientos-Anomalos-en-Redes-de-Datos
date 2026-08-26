#!/usr/bin/env python3
"""Calcula el puntaje SUS y las metricas de tarea desde respuestas-sus.csv.

Calcula; NO interpreta. El umbral aceptable (SUS >= 68, tasa de exito >= 80 %)
esta declarado de antemano en el README de la carpeta, antes de aplicar el
instrumento.

    python3 scripts/entregables/calcular_sus.py [ruta.csv]
"""
from __future__ import annotations
import csv, statistics, sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
CSV = REPO / "docs/entregables/08-validacion-usuarios/respuestas-sus.csv"
OUT = REPO / "docs/entregables/08-validacion-usuarios/resultados-sus.md"
IMPARES = (1, 3, 5, 7, 9)
UMBRAL_SUS, UMBRAL_TAREA = 68.0, 80.0
TAREAS = {"t1": "Identificar la IP bloqueada", "t2": "Leer la expiración del bloqueo",
          "t3": "Distinguir modelo de heurístico", "t4": "Verificar los servicios"}


def es(x: float, d: int = 1) -> str:
    return f"{x:.{d}f}".replace(".", ",")


def sus(fila: dict) -> float:
    total = 0
    for i in range(1, 11):
        v = int(fila[f"i{i}"])
        if not 1 <= v <= 5:
            raise SystemExit(f"{fila['participante']}: el ítem i{i} vale {v}; debe estar entre 1 y 5")
        total += (v - 1) if i in IMPARES else (5 - v)
    return total * 2.5


def ic_media(xs: list[float]) -> tuple[float, float]:
    """IC 95 % de la media con t de Student; con n pequeno es lo correcto."""
    n = len(xs)
    if n < 2:
        return (float("nan"), float("nan"))
    m, s = statistics.mean(xs), statistics.stdev(xs)
    # valor critico de t al 95 % para gl = n-1, tabla hasta n=10
    t = {1: 12.706, 2: 4.303, 3: 3.182, 4: 2.776, 5: 2.571, 6: 2.447,
         7: 2.365, 8: 2.306, 9: 2.262}.get(n - 1, 2.228)
    e = t * s / (n ** 0.5)
    return (m - e, m + e)


def main() -> None:
    ruta = Path(sys.argv[1]) if len(sys.argv) > 1 else CSV
    filas = [r for r in csv.DictReader(ruta.open(encoding="utf-8")) if r.get("participante")]
    if not filas:
        raise SystemExit(f"{ruta.name} no tiene respuestas todavía. "
                         "Aplica el instrumento y vuelca los datos antes de calcular.")

    puntajes = [(r["participante"], r.get("perfil", "—"), sus(r)) for r in filas]
    vals = [p for _, _, p in puntajes]
    m = statistics.mean(vals)
    lo, hi = ic_media(vals)

    L = [f"# Resultados de la validación con usuarios\n\n",
         f"**{len(filas)} participantes.** Generado por `scripts/entregables/calcular_sus.py`.\n\n",
         "## Puntaje SUS\n\n| Participante | Perfil | SUS |\n|---|---|---:|\n"]
    for nom, perf, p in puntajes:
        L.append(f"| {nom} | {perf} | {es(p)} |\n")
    L.append(f"| **Media** | | **{es(m)}** |\n")
    if len(vals) > 1:
        L.append(f"\nDesviación típica {es(statistics.stdev(vals))} · "
                 f"IC 95 % de la media **[{es(lo)} – {es(hi)}]**\n")
    veredicto = ("≥ 80: excelente" if m >= 80 else
                 "entre 68 y 79: por encima de la media de referencia" if m >= UMBRAL_SUS else
                 "**por debajo de 68**: el umbral declarado no se alcanza")
    L.append(f"\n**Frente al umbral declarado ({es(UMBRAL_SUS,0)}):** {veredicto}.\n")
    if len(vals) < 5:
        L.append("\n> Menos de 5 participantes: el intervalo es demasiado ancho para "
                 "sostener una conclusión. Se reporta igual, declarando la limitación.\n")

    L.append("\n## Tareas observadas\n\n| Tarea | Éxito sin ayuda | Tiempo mediano |\n|---|---|---:|\n")
    for k, nombre in TAREAS.items():
        oks = [r[f"{k}_ok"].strip().lower() in ("si", "sí", "1", "true", "ok") for r in filas]
        segs = [float(r[f"{k}_seg"]) for r in filas if r.get(f"{k}_seg")]
        tasa = sum(oks) / len(oks) * 100
        marca = "" if tasa >= UMBRAL_TAREA else "  ⚠️"
        med = es(statistics.median(segs)) + " s" if segs else "—"
        L.append(f"| {nombre} | {sum(oks)}/{len(oks)} = **{es(tasa,0)} %**{marca} | {med} |\n")
    L.append(f"\n**Umbral declarado por tarea: {es(UMBRAL_TAREA,0)} % de éxito sin ayuda.** "
             "Las marcadas con ⚠️ no lo alcanzan y su elemento del panel se rediseña.\n")

    OUT.write_text("".join(L), encoding="utf-8")
    print(f"Generado: {OUT.relative_to(REPO)}")
    print(f"  SUS medio: {es(m)}  (umbral {es(UMBRAL_SUS,0)})")


if __name__ == "__main__":
    main()
