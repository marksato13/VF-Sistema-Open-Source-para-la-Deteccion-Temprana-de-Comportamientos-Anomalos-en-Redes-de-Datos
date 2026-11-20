set -u
cd ~/cyberflow
nice -n 19 .venv/bin/python - <<'EOF'
import csv, sys, collections
from pathlib import Path
sys.path.insert(0, "scripts/modeling")
import cyberflow_aprendizaje as ap
KALI = "10.10.20.30"
pipe, umbral = ap.cargar_modelo(Path("artifacts/preliminar/if_recalibrado_desplegable.joblib"),
                                Path("artifacts/preliminar/manifest-if-recalibrado.json"), "if_recalibrado_2026_09")
n = ap.nombres_v2()
oro = list(csv.DictReader(open("artifacts/aprendizaje/oro/oro.csv")))
s = ap.puntuar(pipe, oro, n)
k = [(r, x) for r, x in zip(oro, s) if r["entity_ip"] == KALI]
resto = [x for r, x in zip(oro, s) if r["entity_ip"] != KALI]
print("oro: %d filas, FPR %.4f" % (len(oro), sum(x < umbral for x in s) / len(oro)))
print("  ventanas Kali en oro: %d, marcadas: %d" % (len(k), sum(x < umbral for _, x in k)))
print("  FPR sin la Kali: %.4f" % (sum(x < umbral for x in resto) / len(resto)))
act = [(r, x) for r, x in k if float(r["packet_count_10s"]) > 0]
print("  Kali activas en oro: %d, marcadas: %d" % (len(act), sum(x < umbral for _, x in act)))
print("  horas (UTC) de las Kali marcadas en oro:", sorted({r["window_end_utc"][:13] for r, x in k if x < umbral}))
# la Kali en la base de entrenamiento
base = [r for r in csv.DictReader(open("artifacts/aprendizaje/base/particionado-nota-L.csv"))
        if r["entity_ip"] == KALI]
print("Kali en la base: %s" % collections.Counter(r["particion"] for r in base))
# 09-30: cuando estuvo activa (por hora)
d = [r for r in csv.DictReader(open("artifacts/linea-base/multilayer-v3.csv"))
     if r["entity_ip"] == KALI and r["window_end_utc"].startswith("2026-09-30") and float(r["packet_count_10s"]) > 0]
print("09-30 activas por hora:", sorted(collections.Counter(r["window_end_utc"][11:13] for r in d).items()))
EOF
