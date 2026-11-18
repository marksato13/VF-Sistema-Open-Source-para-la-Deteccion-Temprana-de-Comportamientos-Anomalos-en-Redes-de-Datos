#!/bin/bash
# Una linea JSON con los hitos de una IP desde t0 (sensor + host). Solo lectura.
# Uso: estado.sh <IP> <t0_epoch>     ·     estado.sh reloj   (hora del sensor)
if [ "$1" = reloj ]; then timeout 10 ssh -o BatchMode=yes sensor1 'date +%s.%N'; exit; fi
IP=$1; T0=$2
S=$(timeout 15 ssh -o BatchMode=yes sensor1 "python3 - $IP $T0" < ~/cf-demo/estado_sensor.py 2>/dev/null)
H=$(timeout 15 ssh -o BatchMode=yes srvdmz "
  a=\$(systemctl is-active ppi-enforce-agent.timer)
  n=\$(~/cf-demo/en-firewall.sh $IP)
  echo \"{\\\"agente\\\": \\\"\$a\\\", \\\"nft\\\": \\\"\$n\\\", \\\"feed_recibido\\\": \$(stat -c %Y ~/enforce/feed.json)}\"" 2>/dev/null)
# hora en que el host vio la regla por primera vez (acuse que trae el relay cada 10 s)
A=$(python3 - "$IP" "$T0" <<'EOF' 2>/dev/null
import json, os, sys
ip, t0 = sys.argv[1], float(sys.argv[2])
try:
    d = json.load(open(os.path.expanduser("~/relay/srv-dmz.json")))
except (OSError, ValueError):
    print("null"); sys.exit()
ev = [e for e in d.get("eventos", []) if e.get("ip") == ip and e.get("t", 0) >= t0]
ap = [e for e in ev if e.get("evento") in ("aplicada", "cambiada")]
print(json.dumps({"generado": d.get("generado"), "aplicada_t": ap[0]["t"] if ap else None,
                  "eventos": [[e["t"], e["evento"], e.get("accion", "")] for e in ev]}))
EOF
)
echo "{\"sensor\": ${S:-null}, \"host\": ${H:-null}, \"acuse\": ${A:-null}}"
