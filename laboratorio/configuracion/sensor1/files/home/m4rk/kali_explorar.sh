set -u
cd ~/cyberflow
nice -n 19 .venv/bin/python - <<'EOF'
import csv, json, collections, sys
sys.path.insert(0, "scripts/modeling")
import cyberflow_aprendizaje as ap
KALI = "10.10.20.30"
filas = [r for r in csv.DictReader(open("artifacts/linea-base/multilayer-v3.csv"))
         if r["entity_ip"] == KALI]
print("filas de la Kali:", len(filas))
por_dia = collections.Counter(r["window_end_utc"][:10] for r in filas)
print("por dia:", sorted(por_dia.items()))
pipe, umbral = ap.cargar_modelo(
    __import__("pathlib").Path("artifacts/preliminar/if_recalibrado_desplegable.joblib"),
    __import__("pathlib").Path("artifacts/preliminar/manifest-if-recalibrado.json"),
    "if_recalibrado_2026_09")
nombres = ap.nombres_v2()
def medir(sub, nombre):
    if not sub:
        print(nombre, "vacio"); return
    s = ap.puntuar(pipe, sub, nombres)
    print("%-45s %4d ventanas  %4d detectadas" % (nombre, len(sub), sum(x < umbral for x in s)))
d30 = [r for r in filas if r["window_end_utc"].startswith("2026-09-30")]
medir(d30, "09-30 todas")
medir([r for r in d30 if float(r["packet_count_10s"]) > 0], "09-30 packet_count_10s>0")
medir([r for r in d30 if r["eligible_training"] == "True"], "09-30 elegibles")
medir([r for r in d30 if r["eligible_training"] == "True" and float(r["packet_count_10s"]) > 0], "09-30 elegibles y activas")
medir([r for r in d30 if float(r["flow_attempt_count_30s"]) > 0 or float(r["http_request_count_60s"]) > 0 or float(r["dns_query_count_60s"]) > 0], "09-30 con flujos/http/dns")
for dia in sorted(por_dia):
    sub = [r for r in filas if r["window_end_utc"].startswith(dia) and float(r["packet_count_10s"]) > 0]
    medir(sub, dia + " activas")
# en la base o el oro?
claves = {(r["entity_ip"], r["window_end_utc"]) for r in csv.DictReader(open("artifacts/aprendizaje/oro/oro.csv")) if r["entity_ip"] == KALI}
print("ventanas de la Kali en el oro:", len(claves))
EOF
