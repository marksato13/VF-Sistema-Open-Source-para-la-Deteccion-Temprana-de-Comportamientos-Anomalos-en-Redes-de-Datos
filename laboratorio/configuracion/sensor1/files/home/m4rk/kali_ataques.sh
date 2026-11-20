set -u
cd ~/cyberflow
nice -n 19 .venv/bin/python - <<'EOF'
import csv, sys, collections, json, hashlib
from pathlib import Path
sys.path.insert(0, "scripts/modeling")
import cyberflow_aprendizaje as ap
KALI = "10.10.20.30"
pipe, umbral = ap.cargar_modelo(Path("artifacts/preliminar/if_recalibrado_desplegable.joblib"),
                                Path("artifacts/preliminar/manifest-if-recalibrado.json"), "if_recalibrado_2026_09")
n = ap.nombres_v2()
src = "artifacts/linea-base/multilayer-v3.csv"
lector = csv.DictReader(open(src)); cab = lector.fieldnames
kali = [r for r in lector if r["entity_ip"] == KALI]

# 1) Las Kali marcadas del 27-sep: dentro o fuera de la base?
base = {(r["entity_ip"], r["window_end_utc"]): r["particion"]
        for r in csv.DictReader(open("artifacts/aprendizaje/base/particionado-nota-L.csv")) if r["entity_ip"] == KALI}
d27 = [r for r in kali if r["window_end_utc"].startswith("2026-09-27") and float(r["packet_count_10s"]) > 0]
s27 = ap.puntuar(pipe, d27, n)
marc = [(r["window_end_utc"], base.get((r["entity_ip"], r["window_end_utc"]), "fuera de la base")) for r, x in zip(d27, s27) if x < umbral]
print("27-sep Kali marcadas:", len(marc), "| en la base:", collections.Counter(p for _, p in marc))
print("   de", marc[0][0] if marc else "-", "a", marc[-1][0] if marc else "-")
tb = [r for r in kali if base.get((r["entity_ip"], r["window_end_utc"])) == "train"]
st = ap.puntuar(pipe, tb, n)
print("Kali en train de la base: %d ventanas, marcadas por el modelo: %d" % (len(tb), sum(x < umbral for x in st)))

# 2) La rafaga de la nota M: 30-sep 00:00-01:59 UTC, ventanas activas
raf = [r for r in kali if "2026-09-30T00:00" <= r["window_end_utc"] < "2026-09-30T02:00"
       and float(r["packet_count_10s"]) > 0]
sr = ap.puntuar(pipe, raf, n)
print("rafaga nota M: %d ventanas, detectadas %d (%.1f %%), de %s a %s" % (
    len(raf), sum(x < umbral for x in sr), 100 * sum(x < umbral for x in sr) / len(raf),
    raf[0]["window_end_utc"], raf[-1]["window_end_utc"]))
dest = Path("artifacts/aprendizaje/ataques/ataques-nota-M.csv"); dest.parent.mkdir(parents=True, exist_ok=True)
with dest.open("w", newline="", encoding="utf-8") as f:
    w = csv.DictWriter(f, fieldnames=cab); w.writeheader(); w.writerows(raf)
dest.chmod(0o444)
info = {"tipo": "ataques", "origen": src, "entidad": KALI,
        "criterio": "ventanas con packet_count_10s > 0 de la Kali entre 2026-09-30T00:00 y 02:00 UTC (campana de la nota M)",
        "filas": len(raf), "detectadas_por_vigente": sum(x < umbral for x in sr),
        "sha256": hashlib.sha256(dest.read_bytes()).hexdigest()}
dest.with_suffix(".json").write_text(json.dumps(info, indent=2) + "\n")
print("escrito", dest, info["sha256"][:16])
EOF
