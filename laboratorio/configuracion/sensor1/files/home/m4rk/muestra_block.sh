cd ~/cyberflow
for f in logs/motor_decision.log*; do zcat -f "$f"; done 2>/dev/null | grep -a '"accion": "BLOCK"' | head -2 | cut -c1-1800
echo "---- limit"
for f in logs/motor_decision.log*; do zcat -f "$f"; done 2>/dev/null | grep -a '"accion": "LIMIT"' | head -1 | cut -c1-1200
