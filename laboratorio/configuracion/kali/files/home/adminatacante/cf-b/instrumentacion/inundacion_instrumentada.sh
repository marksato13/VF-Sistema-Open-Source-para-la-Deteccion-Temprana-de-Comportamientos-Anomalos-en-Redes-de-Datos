#!/bin/bash
# VARIANTE INSTRUMENTADA del comando de la inundación HTTP (E3) — v2 (11-nov): MISMA CARGA que el original. Mismas condiciones que el original de `escenarios-4c.json`:
#   fin=$((SECONDS+90)); n=8; N bucles en paralelo; cada iteración = un `curl -s -o /dev/null --max-time 2 URL`; al final imprime `intentos=N`.
# Añade UN registro por iteración, con hora y resultado, para distinguir los INTENTOS del generador de las peticiones que el servidor ACEPTÓ:
#   t_inicio  t_fin  codigo_http  t_conexion_s  rc_curl  lazo
#   - intento aceptado por el servidor: codigo_http != 000 (el servidor respondió);
#   - intento sin respuesta: codigo_http = 000 (rc_curl 28 = tiempo agotado, 7 = conexión rechazada).
# v2: SIN procesos extra por iteración (la v1 hacía 2 `date` y una sustitución de comando: ≈ -19 % de iteraciones/s medido contra un servidor local). Las horas salen de
#     $EPOCHREALTIME (bash ≥ 5, microsegundos, sin fork) y la salida de curl va a un fichero de tmpfs que se lee con `read` (sin subshell). Un único proceso por iteración: curl, igual que el original.
# Uso: inundacion_instrumentada.sh <salida.tsv> [url] [segundos] [n_paralelo]      (CF_MAXTIME cambia --max-time, solo para pruebas)
# El registro es temporal y local: se escribe en un fichero por lazo y se fusiona al final.
set -u
export LC_ALL=C
[ "${BASH_VERSINFO[0]}" -ge 5 ] || { echo "PARAR: se necesita bash >= 5 (EPOCHREALTIME)" >&2; exit 2; }
SALIDA="${1:?uso: $0 <salida.tsv> [url] [segundos] [n]}"
URL="${2:-http://10.10.30.10/}"
DUR="${3:-90}"
N="${4:-8}"
MAXT="${CF_MAXTIME:-2}"
fin=$((SECONDS+DUR))
d=$(mktemp -d -p /dev/shm 2>/dev/null || mktemp -d)
for i in $(seq "$N"); do
  (
    c=0
    : > "$d/$i.tsv"
    while [ "$SECONDS" -lt "$fin" ]; do
      t0=$EPOCHREALTIME
      curl -s -o /dev/null -w '%{http_code} %{time_connect}' --max-time "$MAXT" "$URL" > "$d/$i.o"
      rc=$?
      t1=$EPOCHREALTIME
      read -r cod tc < "$d/$i.o"
      printf '%s\t%s\t%s\t%s\t%s\t%s\n' "$t0" "$t1" "${cod:-000}" "${tc:-0.000000}" "$rc" "$i" >> "$d/$i.tsv"
      c=$((c+1))
    done
    echo "$c" > "$d/$i.n"
  ) &
done
wait
{ printf '# t_inicio\tt_fin\tcodigo_http\tt_conexion_s\trc_curl\tlazo\n'; sort -n "$d"/*.tsv; } > "$SALIDA"
echo "intentos=$(cat "$d"/*.n | awk '{s+=$1} END{print s+0}')"
rm -rf "$d"
