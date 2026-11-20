set -u
cd ~/cyberflow
nice -n 19 .venv/bin/python - <<'EOF'
import csv, sys, collections
from pathlib import Path
sys.path.insert(0, "scripts/modeling")
import cyberflow_aprendizaje as ap
pipe, umbral = ap.cargar_modelo(Path("artifacts/preliminar/if_recalibrado_desplegable.joblib"),
                                Path("artifacts/preliminar/manifest-if-recalibrado.json"), "if_recalibrado_2026_09")
filas = list(csv.DictReader(open("artifacts/aprendizaje/ataques/ataques-nota-M.csv")))
s = ap.puntuar(pipe, filas, ap.nombres_v2())
def familia(r):
    if float(r["http_request_count_60s"]) > 0: return "HTTP"
    if float(r["dns_query_count_60s"]) > 0: return "DNS"
    return "escaneo/sondeo"
tot, det = collections.Counter(), collections.Counter()
for r, x in zip(filas, s):
    f = familia(r); tot[f] += 1; det[f] += x < umbral
for f in tot: print("%-16s %3d ventanas %3d detectadas %5.1f %%" % (f, tot[f], det[f], 100*det[f]/tot[f]))
print("TOTAL %d / %d = %.1f %%" % (sum(det.values()), sum(tot.values()), 100*sum(det.values())/sum(tot.values())))
# por tramo de 10 min, para ver si las 6 de mas estan en los bordes
c = collections.Counter(r["window_end_utc"][11:15] + "0" for r in filas)
print("por decena:", sorted(c.items()))
EOF
