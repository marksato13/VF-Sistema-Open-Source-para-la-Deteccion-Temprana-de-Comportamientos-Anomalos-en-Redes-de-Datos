#!/bin/bash
# Campaña B - R6 (E4 tras la reversión): el cliente de control alcanza srv-dmz. Solo lectura (GET).
# Se ejecuta EN la VM de clientes (10.10.20.20), nunca en la Kali. rc 0 = las N peticiones respondieron 2xx/3xx; 6 = alguna falló.
# Variables: CF_DESTINO (por omisión http://10.10.30.10/), CF_N (3), CF_CURL (curl, para pruebas).
set -u
DESTINO="${CF_DESTINO:-http://10.10.30.10/}"
N="${CF_N:-3}"
CURL="${CF_CURL:-curl}"
mal=0
echo "== R6 control hacia $DESTINO, $N peticiones, $(date -u +%FT%TZ)"
for i in $(seq 1 "$N"); do
  c=$($CURL -sS -o /dev/null -w '%{http_code}' --max-time 5 "$DESTINO" 2>&1) || true
  case "$c" in 2??|3??) echo "  OK    petición $i: HTTP $c";; *) echo "  FALLO petición $i: $c"; mal=$((mal + 1));; esac
  sleep 1
done
[ "$mal" = 0 ] && { echo "== R6 OK rc=0"; exit 0; }
echo "== R6 FALLO: $mal de $N peticiones rc=6"
exit 6
