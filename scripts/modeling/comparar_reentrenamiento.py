#!/usr/bin/env python3
"""Compara el modelo ANTES vs DESPUES de un reentrenamiento (ensayo en seco).

Responde a la pregunta del jurado/profesor: "cuando reentrenas, ¿QUE CAMBIA?".
Toma dos informes de `entrenar_preliminar.py` (o un manifest con los mismos
campos) y muestra una tabla antes/despues con las variaciones, mas -opcional- la
deteccion (TPR) si se le pasan los informes de `puntuar_deteccion.py`.

NO toca produccion: solo lee JSON y escribe una tabla. El modelo desplegado no se
modifica; esto demuestra el MECANISMO del reentrenamiento, no lo despliega.

    python3 comparar_reentrenamiento.py \\
        --antes   artifacts/model/if_recalibrado_desplegable.json \\
        --despues artifacts/preliminar/if-v3.json \\
        [--tpr-antes det-v2.json --tpr-despues det-v3.json] \\
        [--salida artifacts/preliminar/comparacion-reentrenamiento.md]
"""
from __future__ import annotations
import argparse, json
from pathlib import Path


def leer(p: Path) -> dict:
    return json.loads(Path(p).read_text(encoding="utf-8"))


def g(d: dict, *claves, defecto=None):
    """Primer valor presente entre varias claves posibles (tolerante a formatos)."""
    for k in claves:
        if k in d and d[k] is not None:
            return d[k]
    return defecto


def fnum(v):
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def pct(v):
    v = fnum(v)
    return "—" if v is None else "%.2f %%" % (v * 100.0)


def delta(a, b, mejor="menor"):
    a, b = fnum(a), fnum(b)
    if a is None or b is None:
        return "—"
    d = b - a
    flecha = "▼" if d < 0 else ("▲" if d > 0 else "=")
    bueno = (d < 0 and mejor == "menor") or (d > 0 and mejor == "mayor") or d == 0
    marca = " ✅" if bueno else " ⚠️"
    return "%s %+.2f pp%s" % (flecha, d * 100.0, marca)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--antes", type=Path, required=True, help="informe del modelo actual (congelado)")
    ap.add_argument("--despues", type=Path, required=True, help="informe del modelo reentrenado")
    ap.add_argument("--tpr-antes", type=Path, help="informe de puntuar_deteccion del modelo actual")
    ap.add_argument("--tpr-despues", type=Path, help="informe de puntuar_deteccion del reentrenado")
    ap.add_argument("--salida", type=Path, help="guardar la tabla en Markdown")
    a = ap.parse_args()

    A, B = leer(a.antes), leer(a.despues)

    filA = g(A, "filas", defecto={}) or {}
    filB = g(B, "filas", defecto={}) or {}
    fprv_A = g(A, "fpr_validacion", "fpr_val")
    fprv_B = g(B, "fpr_validacion", "fpr_val")
    fprt_A = g(A, "fpr_test", "fpr")
    fprt_B = g(B, "fpr_test", "fpr")
    umb_A = g(A, "umbral_decision_function", "umbral")
    umb_B = g(B, "umbral_decision_function", "umbral")

    filas = [
        ("Esquema (features)", g(A, "schema", "esquema", defecto="—"), g(B, "schema", "esquema", defecto="—"), "—"),
        ("Nº de features", g(A, "n_features", defecto="—"), g(B, "n_features", defecto="—"), "—"),
        ("Filas train/val/test",
         "%s / %s / %s" % (filA.get("train", "—"), filA.get("validation", "—"), filA.get("test", "—")),
         "%s / %s / %s" % (filB.get("train", "—"), filB.get("validation", "—"), filB.get("test", "—")), "—"),
        ("Umbral (decision_function)",
         "%.6f" % fnum(umb_A) if fnum(umb_A) is not None else "—",
         "%.6f" % fnum(umb_B) if fnum(umb_B) is not None else "—", "—"),
        ("FPR validación", pct(fprv_A), pct(fprv_B), delta(fprv_A, fprv_B, "menor")),
        ("FPR test (ciego)", pct(fprt_A), pct(fprt_B), delta(fprt_A, fprt_B, "menor")),
    ]

    if a.tpr_antes and a.tpr_despues:
        TA, TB = leer(a.tpr_antes), leer(a.tpr_despues)
        tprA = g(TA, "tpr", "tpr_global", "deteccion")
        tprB = g(TB, "tpr", "tpr_global", "deteccion")
        filas.append(("TPR (detección)", pct(tprA), pct(tprB), delta(tprA, tprB, "mayor")))

    anchos = [max(len(str(r[i])) for r in [("Métrica", "ANTES", "DESPUÉS", "Δ (después−antes)")] + filas) for i in range(4)]
    def fila(r):
        return "| " + " | ".join(str(r[i]).ljust(anchos[i]) for i in range(4)) + " |"
    sep = "|" + "|".join("-" * (anchos[i] + 2) for i in range(4)) + "|"

    out = []
    out.append("# Reentrenamiento — comparación ANTES vs DESPUÉS (ensayo en seco)\n")
    out.append("> No despliega nada; demuestra el mecanismo y el efecto del reentrenamiento.\n")
    out.append(fila(("Métrica", "ANTES", "DESPUÉS", "Δ (después−antes)")))
    out.append(sep)
    for r in filas:
        out.append(fila(r))

    # criterio de aceptación (del PLAN-REENTRENAMIENTO)
    acepta = None
    if fnum(fprt_A) is not None and fnum(fprt_B) is not None:
        acepta = fnum(fprt_B) <= fnum(fprt_A) + 1e-9
    out.append("")
    out.append("**Criterio (PLAN-REENTRENAMIENTO):** desplegar solo si el reentrenado "
               "iguala o mejora cobertura y NO empeora el FPR.")
    if acepta is not None:
        out.append("**FPR:** %s" % ("✅ no empeora → candidato a desplegar (revisar también cobertura/ARP/DNS)."
                                    if acepta else "⚠️ empeora el FPR → NO desplegar; quedarse con el modelo actual."))

    texto = "\n".join(out) + "\n"
    print(texto)
    if a.salida:
        a.salida.parent.mkdir(parents=True, exist_ok=True)
        a.salida.write_text(texto, encoding="utf-8")
        print("Guardado en %s" % a.salida)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
