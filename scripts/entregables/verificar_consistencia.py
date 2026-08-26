#!/usr/bin/env python3
"""Busca inconsistencias entre los documentos y los artefactos congelados.

Dos comprobaciones:
  1. RASTROS OBSOLETOS: afirmaciones de versiones anteriores del sistema que ya
     son falsas (Isolation Forest como modelo desplegado, umbrales del MVP,
     iptables, cifras de auditoria superadas...).
  2. CIFRAS CLAVE: que los numeros citados coincidan con el manifiesto y el
     dataset. Ninguna se compara contra otro documento: siempre contra el
     artefacto.

    python3 scripts/entregables/verificar_consistencia.py
"""
from __future__ import annotations
import csv, json, re, sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
MANIFEST = json.loads((REPO / "artifacts/model/manifest.json").read_text(encoding="utf-8"))
AUDIT = json.loads((REPO / "artifacts/dataset/multilayer-v2-audit-report.json").read_text(encoding="utf-8"))

# Documentos vivos. Se excluyen los historicos: una campana de julio DEBE
# seguir diciendo lo que decia, y reescribirla falsearia el registro.
AMBITO = ["docs/entregables", "docs/dataset", "docs/requisitos-jurado", "docs/articulo",
          "docs/fase02-features-multicapa", "docs/fase04-modelado",
          "docs/fase05-motor-tiempo-real", "docs/fase06-dashboard",
          "docs/fase07-validacion-final", "docs/07-mejoras-futuras", "README.md", "CLAUDE.md"]
EXCLUIR = ("docs/revisiones-claude", "docs/fase03-dataset", "docs/fase00", "docs/fase01")

# (etiqueta, patron, por que es un rastro obsoleto)
OBSOLETOS = [
    ("umbral del MVP", r"-0[.,]4459|-0[.,]6027|\bτ1\b|\bτ2\b",
     "umbrales del sistema anterior; el vigente es 1,8126"),
    ("iptables/ipset como mecanismo", r"(?<!de )\b(iptables|ipset)\b(?!\.netfilter)",
     "el sistema usa nftables; solo vale como cita ajena o bibliografia"),
    ("14 variables como contrato vigente", r"\b14 (features|variables|caracter[ií]sticas) (del modelo|actuales|vigentes)",
     "el contrato vigente tiene 28 definidas y 27 efectivas"),
    ("IF como modelo desplegado", r"(modelo|detector) (final |congelado )?(es|será) (un )?Isolation Forest",
     "el modelo congelado es OCSVM"),
    ("38 perfiles", r"\b38 perfiles",
     "son 44, verificado sobre el CSV congelado"),
    ("57 corridas", r"\b57 corridas",
     "son 58, con 55 verificadas y 0 caidas registradas"),
    ("disponibilidad 100 %", r"disponibilidad (del |de )?100 ?%|100 ?% de disponibilidad",
     "cero caidas registradas no es lo mismo que 100 % verificado"),
    ("puntaje de ficha superado", r"32/51|62[.,]7 ?%|36/51|70[.,]6 ?%|39/51|76[.,]5 ?%",
     "la ficha vigente da 42/51 = 82,4 %"),
    ("ablacion pendiente", r"ablaci[oó]n (est[aá] )?(pendiente|sin ejecutar|nunca se ejecut)",
     "la ablacion esta ejecutada"),
    ("sin significancia", r"[Nn]o se (realiz[oó]|ha realizado) ninguna prueba (de significancia|\(t, Wilcoxon)",
     "McNemar con Holm esta ejecutado"),
    ("datos no publicados", r"datos (no est[aá]n|NO) publicados|dataset no (est[aá] )?publicado",
     "dataset y 7 modelos estan publicados con checksums"),
    ("carpeta renombrada", r"07-dataset-campanas",
     "la carpeta es fase03-dataset"),
]


# Excepciones DECLARADAS, con su motivo. No se ignora nada en silencio: si una
# coincidencia es legitima, debe poder justificarse en una linea.
EXCEPCIONES = [
    ("docs/entregables/03-auditoria-comparativa/", None,
     "compara el MVP con la version final; citar el mecanismo antiguo es su objeto"),
    ("docs/entregables/05-ppi/CAMBIOS-PROPUESTOS-PPI-v2.md", None,
     "cita textos ANTIGUOS del PPI junto a su correccion; el rastro es la cita"),
    ("docs/entregables/05-ppi/README.md", "38 perfiles|57 corridas",
     "registro de los errores corregidos en el PPI"),
    ("docs/entregables/06-plan-de-mejora/", "38 perfiles|57 corridas|puntaje de ficha",
     "registro de lo ya corregido y de la evolucion del puntaje"),
    ("docs/entregables/04-ficha-auditoria/ficha-auditoria.md", "puntaje de ficha",
     "la frase de evolucion cita a proposito el puntaje anterior"),
    ("docs/fase04-modelado/04-protocolo-modelado-multilayer-v2-y-hoja-de-ruta.md", None,
     "documento historico, marcado como SUPERADO en su encabezado"),
    ("docs/requisitos-jurado/README.md", "14 variables",
     "describe el MVP del que se parte, no el contrato vigente"),
]


def exento(rel: str, etiqueta: str) -> str | None:
    for ruta, pat, motivo in EXCEPCIONES:
        if rel.startswith(ruta) and (pat is None or re.search(pat, etiqueta)):
            return motivo
    return None


def esperadas() -> dict[str, tuple[str, str]]:
    o = MANIFEST["evaluation"]["ocsvm_scaled"]
    n = list(csv.DictReader((REPO / "artifacts/dataset/multilayer-v2-normal.csv").open(encoding="utf-8")))
    perf = len({re.sub(r"-R\d+.*$", "", re.sub(r"-\d+$", "", r["campaign_id"])) for r in n})
    det = o["anomalies"]["detected_strict"] / o["anomalies"]["n_windows"] * 100
    kali = o["anomalies"]["kali_real_detection_rate"] * 100
    fpr = o["test"]["fpr"] * 100
    return {
        "umbral":        (r"1[.,]8126", f"{o['threshold_used']}"),
        "ventanas norm": (r"1[ .,]373", str(AUDIT["normal_rows"])),
        "ventanas anom": (r"\b179\b", str(AUDIT["anomaly_rows"])),
        "perfiles":      (r"\b44 perfiles", str(perf)),
        "deteccion":     (r"88[.,]3", f"{det:.1f}"),
        "kali":          (r"88[.,]8", f"{kali:.1f}"),
        "fpr offline":   (r"4[.,]71", f"{fpr:.2f}"),
    }


def archivos():
    for a in AMBITO:
        p = REPO / a
        if p.is_file():
            yield p
        else:
            for f in sorted(p.rglob("*.md")):
                if not any(x in str(f.relative_to(REPO)) for x in EXCLUIR):
                    yield f


def main() -> None:
    hallazgos, exentos = [], []
    for f in archivos():
        rel = str(f.relative_to(REPO))
        texto = f.read_text(encoding="utf-8", errors="ignore")
        for i, linea in enumerate(texto.splitlines(), 1):
            l = linea.strip()
            if l.startswith(">") or "~~" in l or "✅" in l or "❌" in l:
                continue  # citas, tachados y marcas de resuelto: son declaraciones, no afirmaciones
            for etq, pat, motivo in OBSOLETOS:
                if re.search(pat, l):
                    justificacion = exento(rel, etq)
                    if justificacion:
                        exentos.append((rel, etq, justificacion))
                    else:
                        hallazgos.append((rel, i, etq, motivo, l[:110]))

    print("=" * 78)
    print(f"RASTROS OBSOLETOS: {len(hallazgos)}")
    print("=" * 78)
    porarch = {}
    for rel, i, etq, motivo, frag in hallazgos:
        porarch.setdefault(rel, []).append((i, etq, motivo, frag))
    for rel, items in sorted(porarch.items()):
        print(f"\n  {rel}")
        for i, etq, motivo, frag in items:
            print(f"    L{i:<5} [{etq}] {motivo}")
            print(f"           » {frag}")
    if not hallazgos:
        print("\n  ninguno")

    if exentos:
        print("\n" + "-" * 78)
        print(f"EXCEPCIONES DECLARADAS: {len(exentos)} coincidencias legítimas")
        print("-" * 78)
        vistos = {}
        for rel, etq, motivo in exentos:
            vistos.setdefault((rel, motivo), 0)
            vistos[(rel, motivo)] += 1
        for (rel, motivo), n in sorted(vistos.items()):
            print(f"  {n:>2}× {rel}\n      → {motivo}")

    print("\n" + "=" * 78)
    print("CIFRAS CLAVE — contrastadas contra el artefacto, no entre documentos")
    print("=" * 78)
    esp = esperadas()
    for etq, (pat, valor) in esp.items():
        n = sum(len(re.findall(pat, f.read_text(encoding="utf-8", errors="ignore"))) for f in archivos())
        print(f"  {etq:16} valor real {valor:<22} apariciones en documentos vivos: {n}")

    sys.exit(1 if hallazgos else 0)


if __name__ == "__main__":
    main()
