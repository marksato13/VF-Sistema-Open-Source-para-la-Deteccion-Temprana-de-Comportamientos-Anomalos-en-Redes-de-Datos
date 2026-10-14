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
import argparse, json, sys
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
    ap.add_argument("--fpr-antes", type=Path, help="evaluación pareada del actual sobre normal reservado")
    ap.add_argument("--fpr-despues", type=Path, help="evaluación pareada del candidato sobre EL MISMO normal")
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

    mismo_esquema = (g(A, "schema", "esquema") is not None
                    and g(A, "schema", "esquema") == g(B, "schema", "esquema")
                    and g(A, "n_features") == g(B, "n_features")
                    and A.get("features") == B.get("features"))
    misma_base = (A.get("entrada_sha256") is not None
                  and A.get("entrada_sha256") == B.get("entrada_sha256"))
    mismo_normal = False
    if a.fpr_antes and a.fpr_despues:
        FA, FB = leer(a.fpr_antes), leer(a.fpr_despues)
        mismo_normal = (FA.get("csv_sha256") is not None
                        and FA.get("csv_sha256") == FB.get("csv_sha256")
                        and FA.get("particion") == FB.get("particion")
                        and FA.get("tipo") == FB.get("tipo") == "normal"
                        and FA.get("features") == FB.get("features") == A.get("features"))
        fprt_A, fprt_B = FA.get("fpr"), FB.get("fpr")
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

    tprA = tprB = None
    mismo_ataque = False
    if a.tpr_antes and a.tpr_despues:
        TA, TB = leer(a.tpr_antes), leer(a.tpr_despues)
        tprA = g(TA, "tpr", "tpr_global", "tasa_deteccion")
        tprB = g(TB, "tpr", "tpr_global", "tasa_deteccion")
        mismo_ataque = (TA.get("csv_sha256") is not None and TA.get("csv_sha256") == TB.get("csv_sha256")
                       and TA.get("tipo") == TB.get("tipo") == "anomalias"
                       and TA.get("features") == TB.get("features") == A.get("features"))
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

    out.append("")
    out.append("**Comparabilidad:** mismo esquema/orden: %s; misma base de entrenamiento: %s; "
               "mismo normal reservado (SHA-256): %s; mismos ataques (SHA-256): %s." %
               ("sí" if mismo_esquema else "NO", "sí" if misma_base else "NO",
                "sí" if mismo_normal else "NO", "sí" if mismo_ataque else "NO"))
    out.append("**Criterio:** cobertura/TPR ≥ actual y FPR ≤ actual **sobre conjuntos comparables**. "
               "Un FPR de otro test es descriptivo, no prueba de mejora.")
    completo = (mismo_esquema and mismo_normal and mismo_ataque
                and fnum(fprt_A) is not None and fnum(fprt_B) is not None
                and fnum(tprA) is not None and fnum(tprB) is not None)
    if not completo:
        out.append("**Veredicto: EVALUACIÓN INCOMPLETA — NO PROMOVER.** Falta un conjunto común "
                   "o una métrica necesaria. Comparar ambos modelos sobre el mismo hold-out y los "
                   "mismos episodios antes de emitir un juicio de promoción.")
    elif fnum(fprt_B) <= fnum(fprt_A) + 1e-9 and fnum(tprB) >= fnum(tprA) - 1e-9:
        out.append("**Veredicto: candidato para revisión manual**, no despliegue automático. "
                   "Verificar además cobertura por familia y estabilidad.")
    else:
        out.append("**Veredicto: NO PROMOVER.** Empeora FPR o TPR en la comparación pareada.")

    texto = "\n".join(out) + "\n"
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    print(texto)
    if a.salida:
        a.salida.parent.mkdir(parents=True, exist_ok=True)
        a.salida.write_text(texto, encoding="utf-8")
        print("Guardado en %s" % a.salida)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
