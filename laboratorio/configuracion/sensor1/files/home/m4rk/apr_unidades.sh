set -u
cd ~/cyberflow
echo "== por que se rechazo el lote 2026-10-10 (PSI por variable)"
python3 - <<'EOF'
import json, csv, statistics
e = [json.loads(l) for l in open("artifacts/aprendizaje/registro.jsonl") if '"lote"' in l][-1]
print("peores:", e["psi_peores"])
# medias de esas variables: oro frente al lote
nombres = [n for n, _ in e["psi_peores"]]
def medias(ruta):
    filas = list(csv.DictReader(open(ruta)))
    return len(filas), {n: round(statistics.fmean(float(f[n]) for f in filas), 3) for n in nombres}
print("oro :", medias("artifacts/aprendizaje/oro/oro.csv"))
print("lote:", medias("artifacts/aprendizaje/lotes/lote-20261010.csv"))
EOF
echo "== entidades: oro frente al lote"
python3 -c "
import csv,collections
for r in ('artifacts/aprendizaje/oro/oro.csv','artifacts/aprendizaje/lotes/lote-20261010.csv'):
    c=collections.Counter(f['entity_ip'] for f in csv.DictReader(open(r)))
    print(r.split('/')[-1], len(c), 'IPs; top:', c.most_common(6))"
echo "== decisiones del motor el 10-10"
for f in logs/motor_decision.log logs/motor_decision.log.1; do [ -f $f ] && echo "$f: $(grep -c '2026-10-10T' $f) del 10-10, ALERT: $(grep '2026-10-10T' $f | grep -c '\"decision\": \"ALERT\"')"; done
echo "== generador de unidades nuevo y unidades del temporizador"
cp -p scripts/setup/cyberflow_config.py scripts/setup/cyberflow_config.py.bak-apr
cp ~/cf-deploy/cyberflow_config.py scripts/setup/cyberflow_config.py
mkdir -p ~/cf-deploy/unidades
.venv/bin/python - <<'EOF'
import sys
sys.path.insert(0, "scripts/setup")
import cyberflow_config as cc
from pathlib import Path
u = cc.render(cc.cargar(Path("configs/cyberflow.local.toml")))
for n in ("cyberflow-aprendizaje.service", "cyberflow-aprendizaje.timer"):
    Path.home().joinpath("cf-deploy/unidades", n).write_text(u[n], encoding="utf-8")
    print("preparada", n)
EOF
grep -hE 'ExecStart|--config|OnCalendar|^User' ~/cf-deploy/unidades/*
