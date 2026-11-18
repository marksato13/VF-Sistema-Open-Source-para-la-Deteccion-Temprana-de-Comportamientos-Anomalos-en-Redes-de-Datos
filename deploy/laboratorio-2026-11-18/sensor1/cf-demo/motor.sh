#!/bin/bash
# Deteccion en vivo del motor para una IP (una linea por ventana de 10 s).
IP=${1:?uso: motor.sh IP}
stdbuf -oL tail -n 0 -f ~/cyberflow/logs/motor_decision.log | python3 -u -c "import sys,json
ip=sys.argv[1]
for l in sys.stdin:
    try: d=json.loads(l)
    except: continue
    if d.get(\"entity_ip\")!=ip: continue
    hs=d.get(\"heuristicos\") or []
    reg=\",\".join(\"%s:%s\"%(h.get(\"heuristico\"),h.get(\"accion\")) for h in hs) or \"-\"
    print(\"%s  score=%+.3f umbral=%.3f  decision=%-7s regla=%s\"%(d.get(\"window_end_utc\",\"?\")[11:19],d.get(\"score\") or 0,d.get(\"threshold\") or 0,d.get(\"decision\"),reg),flush=True)" "$IP"
