set -u
cd ~/cyberflow
python3 - <<'EOF'
import csv, collections
k = [r for r in csv.DictReader(open("artifacts/linea-base/multilayer-v3.csv"))
     if r["entity_ip"] == "10.10.20.30" and r["window_end_utc"][:10] in ("2026-09-27", "2026-09-28", "2026-09-29")
     and float(r["packet_count_10s"]) > 0]
c = collections.Counter(r["window_end_utc"][:15] for r in k)   # por decena de minutos
for t, v in sorted(c.items()):
    if v >= 3: print(t + "0", v)
print("total activas 27-29:", len(k))
EOF
grep -h '2026-09-27T21:[3-5]' logs/motor_decision.log* 2>/dev/null | grep -c '10.10.20.30' || true
